"""Imágenes en memoria: validación del contenido, visor y entrada experimental separada."""
from __future__ import annotations
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import hashlib
import warnings
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from mammotrace.dicom import read_dicom, transform, safe_preview
from mammotrace.errors import ResearchError
from .config import IMAGE_EXT, MAX_IMAGE, MAX_PIXELS, MAX_DIM

FORMATS = {"png":"PNG", "jpg":"JPEG", "jpeg":"JPEG", "tif":"TIFF", "tiff":"TIFF", "bmp":"BMP", "webp":"WEBP"}
KINDS = ("Mamografía 2D", "Ecografía / otra imagen radiológica", "Fotografía externa de la mama", "No sé qué tipo de imagen es")

@dataclass
class ImageRecord:
    display: np.ndarray
    legacy_input: np.ndarray | None
    technical: dict
    warnings: list[str] = field(default_factory=list)
    # Solo para invalidación en la sesión. No se exporta ni se registra.
    session_fingerprint: str = ""


def _scaled_preview(a: np.ndarray, invert: bool = False) -> np.ndarray:
    lo, hi = np.percentile(a, [1, 99])
    if hi <= lo:
        lo, hi = float(a.min()), float(a.max())
    b = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
    if invert:
        b = 1-b
    scale = min(1., 1000/max(a.shape))
    return cv2.resize((b*255).astype(np.uint8), (round(a.shape[1]*scale), round(a.shape[0]*scale)), interpolation=cv2.INTER_AREA)


def load_image(data: bytes, filename: str, kind: str = KINDS[0]) -> ImageRecord:
    if kind not in KINDS:
        raise ResearchError("IMAGE_KIND", "Seleccione un tipo de imagen válido.")
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in IMAGE_EXT:
        raise ResearchError("IMAGE_EXT", "Formato no admitido. No cambie la extensión para convertir el archivo.")
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMAGE:
        raise ResearchError("IMAGE_SIZE", "Imagen vacía o superior al límite de 64 MiB.")
    notes = []
    tensor = None
    if ext in {"dcm", "dicom"}:
        image = read_dicom(data, max_pixels=MAX_PIXELS, max_dimension=MAX_DIM)
        display = safe_preview(image)
        technical = dict(image.technical)
        technical.update(format="DICOM", declared_kind=kind, input_pipeline="legacy_0_1_resnet")
        notes += image.warnings
        # Vista y tensor no son equivalentes. La escala legada se conserva para sus pesos.
        if kind == KINDS[0]:
            try:
                tensor = transform(image, "legacy")
            except ResearchError:
                notes.append("El visor puede mostrar esta imagen, pero no es compatible con la escala del modelo legado.")
        notes.append("La vista aplica contraste percentil e inversión MONOCHROME1; no aplica LUT/VOI diagnósticas. El modelo conserva el flujo legado sin esas operaciones.")
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as im:
                    if im.format != FORMATS[ext]:
                        raise ResearchError("IMAGE_SIGNATURE", "La extensión no coincide con el contenido de la imagen.")
                    width, height = im.size
                    if min(width, height) < 16 or max(width, height) > MAX_DIM or width*height > MAX_PIXELS:
                        raise ResearchError("IMAGE_DIM", "Dimensiones no admitidas: mínimo 16, máximo 8192 por lado y 32 millones de píxeles.")
                    if getattr(im, "n_frames", 1) != 1:
                        raise ResearchError("MULTIFRAME", "Use una imagen 2D por archivo. TIFF multipágina y animaciones no se procesan silenciosamente.")
                    original_mode = im.mode
                    im.load()
                    im = ImageOps.exif_transpose(im)
                    if im.mode in {"I", "I;16", "I;16L", "I;16B", "F", "L"}:
                        a = np.asarray(im, dtype=np.float32)
                    else:
                        rgba = im.convert("RGBA")
                        rgba = Image.alpha_composite(Image.new("RGBA", rgba.size, (0,0,0,255)), rgba)
                        a = np.asarray(rgba.convert("L"), dtype=np.float32)
                        notes.append("Conversión a luminancia para el laboratorio; no se interpreta el color como hallazgo clínico.")
                    if not np.isfinite(a).all() or np.min(a) < 0:
                        raise ResearchError("PIXEL_VALUES", "Intensidades no finitas o negativas: imagen no compatible.")
                    if np.ptp(a) <= 0:
                        raise ResearchError("CONSTANT_IMAGE", "La imagen no tiene variación de intensidad utilizable.")
                    display = _scaled_preview(a)
                    if kind == KINDS[0]:
                        r = cv2.resize(a/float(a.max()), (224,224), interpolation=cv2.INTER_AREA)
                        tensor = np.repeat(r[...,None], 3, axis=-1).astype(np.float32)
                    technical = {"format":FORMATS[ext], "rows":a.shape[0], "columns":a.shape[1],
                                 "source_mode":original_mode, "declared_kind":kind,
                                 "view":"no documentada", "laterality":"no documentada",
                                 "input_pipeline":"luminancia_0_1_resnet_exploratorio"}
        except ResearchError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ResearchError("IMAGE_DECODE", "No se pudo decodificar una imagen 2D válida dentro de los límites.") from None
        notes.append("Una imagen exportada o fotografiada no equivale al DICOM original; puede haber compresión, recortes y cambios de escala. No se garantiza equivalencia de inferencia.")
        notes.append("No se inspecciona todo el texto incrustado ni se certifica anonimización; revise la imagen antes de cargarla.")
    if kind != KINDS[0]:
        tensor = None
        notes.append("Clasificador mamográfico bloqueado: una fotografía externa, una ecografía o una modalidad desconocida no son entradas validadas para él.")
    return ImageRecord(display, tensor, technical, notes, hashlib.sha256(data).hexdigest())


def image_statistics(image: ImageRecord) -> dict:
    """Descriptores técnicos del visor, NO densidad mamaria, lesión o diagnóstico."""
    a = image.display
    hist = np.bincount(a.ravel(), minlength=256).astype(float)
    p = hist[hist>0]/hist.sum()
    return {"media_del_visor":round(float(a.mean()),3), "desviacion_del_visor":round(float(a.std()),3),
            "entropia_bits_del_visor":round(float(-(p*np.log2(p)).sum()),3),
            "contraste_p99_p1_del_visor":round(float(np.percentile(a,99)-np.percentile(a,1)),3),
            "varianza_laplaciano_del_visor":round(float(cv2.Laplacian(a,cv2.CV_64F).var()),3),
            "interpretacion":"Descriptores del archivo mostrado; no determinan BI-RADS, densidad mamaria, malignidad ni aptitud diagnóstica."}


def png_bytes(a: np.ndarray) -> bytes:
    output=BytesIO()
    Image.fromarray(np.asarray(a,dtype=np.uint8)).save(output, format="PNG")
    return output.getvalue()
