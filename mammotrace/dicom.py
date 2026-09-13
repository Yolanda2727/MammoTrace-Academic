"""Lector DICOM Part 10 restringido y sin dependencias DICOM externas.

Admite Explicit VR Little Endian y un subconjunto declarado de Implicit VR LE;
solo MG 2D de 8/16 bits sin compresión. NO es un de-identificador ni un validador
completo del estándar. Falla de manera cerrada ante características no cubiertas.
No abre rutas referenciadas, DICOMDIR ni archivos del sistema.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct
import warnings
import numpy as np
import cv2
from .errors import ResearchError

EXPLICIT_LE = "1.2.840.10008.1.2.1"
IMPLICIT_LE = "1.2.840.10008.1.2"
MG_SOPS = {"1.2.840.10008.5.1.4.1.1.1.2", "1.2.840.10008.5.1.4.1.1.1.2.1"}
LONG_VR = {"OB","OD","OF","OL","OV","OW","SQ","UC","UR","UT","UN","SV","UV"}
VALID_VR = LONG_VR | {"AE","AS","AT","CS","DA","DS","DT","FD","FL","IS","LO","LT","PN","SH","SL","SS","ST","TM","UI","UL","US"}
# Diccionario deliberadamente acotado del modo implícito. No se infiere VR desconocido.
IMPLICIT = {
 (0x0008,0x0005):"CS", (0x0008,0x0008):"CS", (0x0008,0x0016):"UI", (0x0008,0x0018):"UI",
 (0x0008,0x0020):"DA", (0x0008,0x0021):"DA", (0x0008,0x0022):"DA", (0x0008,0x0023):"DA",
 (0x0008,0x0030):"TM", (0x0008,0x0031):"TM", (0x0008,0x0032):"TM", (0x0008,0x0033):"TM",
 (0x0008,0x0050):"SH", (0x0008,0x0060):"CS", (0x0008,0x0070):"LO", (0x0008,0x0080):"LO",
 (0x0008,0x0081):"ST", (0x0008,0x0090):"PN", (0x0008,0x1010):"SH", (0x0008,0x1030):"LO",
 (0x0008,0x103E):"LO", (0x0008,0x1090):"LO", (0x0008,0x1115):"SQ",
 (0x0010,0x0010):"PN", (0x0010,0x0020):"LO", (0x0010,0x0030):"DA", (0x0010,0x0040):"CS",
 (0x0010,0x1010):"AS", (0x0012,0x0062):"CS", (0x0012,0x0063):"LO",
 (0x0018,0x0015):"CS", (0x0018,0x0060):"DS", (0x0018,0x1110):"DS", (0x0018,0x1111):"DS",
 (0x0018,0x1164):"DS", (0x0018,0x5101):"CS", (0x0020,0x000D):"UI", (0x0020,0x000E):"UI",
 (0x0020,0x0010):"SH", (0x0020,0x0011):"IS", (0x0020,0x0013):"IS", (0x0020,0x0060):"CS",
 (0x0020,0x0062):"CS", (0x0028,0x0002):"US", (0x0028,0x0004):"CS", (0x0028,0x0008):"IS",
 (0x0028,0x0010):"US", (0x0028,0x0011):"US", (0x0028,0x0030):"DS", (0x0028,0x0100):"US",
 (0x0028,0x0101):"US", (0x0028,0x0102):"US", (0x0028,0x0103):"US", (0x0028,0x0120):"US",
 (0x0028,0x0121):"US", (0x0028,0x0301):"CS", (0x0028,0x1050):"DS", (0x0028,0x1051):"DS",
 (0x0028,0x1052):"DS", (0x0028,0x1053):"DS", (0x0028,0x1054):"LO", (0x0028,0x1056):"CS",
 (0x0028,0x3000):"SQ", (0x0028,0x3010):"SQ", (0x0054,0x0220):"SQ",
 (0x0008,0x0100):"SH", (0x0008,0x0102):"SH", (0x0008,0x0104):"LO",
 (0x2050,0x0020):"CS", (0x7fe0,0x0010):"OW",
}
PRIVACY_TAGS = {
 (0x0010,0x0010), (0x0010,0x0030), (0x0010,0x1000), (0x0010,0x1001),
 (0x0010,0x1040), (0x0010,0x2154), (0x0008,0x0050), (0x0008,0x0080),
 (0x0008,0x0081), (0x0008,0x0090), (0x0008,0x1048), (0x0008,0x1050),
 (0x0008,0x1060), (0x0008,0x1070), (0x0008,0x1010), (0x0020,0x0010),
 (0x0032,0x1032), (0x0040,0x0006), (0x0040,0x0241), (0x0040,0x0242),
 (0x0018,0x1000), (0x0018,0x1002),
}

@dataclass
class Element:
    tag: tuple[int,int]
    vr: str
    value: bytes

@dataclass
class DicomImage:
    pixels: np.ndarray
    fields: dict[tuple[int,int], Element]
    technical: dict
    warnings: list[str]

    def text(self, tag, default=""):
        e = self.fields.get(tag)
        return e.value.rstrip(b"\0 ").decode("ascii", errors="replace") if e else default

    def number(self, tag, default=None):
        e=self.fields.get(tag)
        if not e: return default
        try:
            if e.vr in {"US","SS"} and len(e.value)!=2:raise ValueError("multiplicity")
            if e.vr in {"UL","SL"} and len(e.value)!=4:raise ValueError("multiplicity")
            if e.vr in {"US","SS"}: return struct.unpack("<H" if e.vr=="US" else "<h", e.value[:2])[0]
            if e.vr in {"UL","SL"}: return struct.unpack("<I" if e.vr=="UL" else "<i", e.value[:4])[0]
            return float(e.value.decode("ascii").strip(" \0").split("\\")[0])
        except (ValueError,struct.error,UnicodeError):
            raise ResearchError("DICOM_NUMBER", "Un atributo numérico DICOM no es válido.") from None

class Parser:
    def __init__(self, raw: bytes):
        self.raw=raw;self.n=len(raw);self.count=0;self.all_elements=[]

    def header(self, pos: int, explicit: bool):
        if pos+8 > self.n: raise ResearchError("DICOM_TRUNCATED", "DICOM incompleto o truncado.")
        tag=struct.unpack_from("<HH",self.raw,pos)
        if tag[0]==0xfffe:
            return tag, "ITEM", struct.unpack_from("<I",self.raw,pos+4)[0], pos+8
        if explicit:
            try: vr=self.raw[pos+4:pos+6].decode("ascii")
            except UnicodeError: vr="?"
            if vr not in VALID_VR: raise ResearchError("DICOM_VR", "Representación DICOM no admitida.")
            if vr in LONG_VR:
                if pos+12>self.n or self.raw[pos+6:pos+8]!=b"\0\0":
                    raise ResearchError("DICOM_HEADER", "Encabezado DICOM inválido.")
                length=struct.unpack_from("<I",self.raw,pos+8)[0];start=pos+12
            else:length=struct.unpack_from("<H",self.raw,pos+6)[0];start=pos+8
        else:
            vr=IMPLICIT.get(tag)
            if vr is None: raise ResearchError("IMPLICIT_TAG", "El modo implícito contiene atributos no cubiertos por este lector. Use una copia desidentificada Explicit VR Little Endian.")
            length=struct.unpack_from("<I",self.raw,pos+4)[0];start=pos+8
        return tag,vr,length,start

    def dataset(self, pos, end, explicit, depth=0, stop_item=False):
        if depth>12:raise ResearchError("DICOM_DEPTH", "Estructura DICOM excesivamente anidada.")
        fields={}
        while pos < end:
            self.count+=1
            if self.count>12000:raise ResearchError("DICOM_ELEMENTS", "Demasiados atributos DICOM.")
            tag,vr,length,start=self.header(pos,explicit)
            if tag==(0xfffe,0xe00d) and stop_item and length==0:return fields,start
            if tag[0]==0xfffe:raise ResearchError("DICOM_SEQUENCE", "Delimitación de secuencia inválida.")
            if tag in fields:raise ResearchError("DICOM_DUPLICATE_TAG", "DICOM con atributos duplicados.")
            if tag[0]%2:raise ResearchError("PRIVATE_TAG", "Se detectaron atributos privados; revise la desidentificación.")
            if 0x6000<=tag[0]<=0x60ff:raise ResearchError("OVERLAY", "Los overlays requieren revisión externa.")
            if vr=="SQ":
                fields[tag]=Element(tag,vr,b"")
                pos=self.sequence(start,length,explicit,depth+1,end)
                continue
            if length==0xffffffff:raise ResearchError("DICOM_COMPRESSED", "Longitud indefinida fuera de secuencia o imagen encapsulada no admitida.")
            if length%2 or start+length>end:raise ResearchError("DICOM_LENGTH", "Longitud de atributo DICOM inválida.")
            if tag[0]%2:raise ResearchError("PRIVATE_TAG", "Se detectaron atributos privados. Revise la desidentificación antes de cargar la imagen.")
            if vr=="UN" and length:raise ResearchError("UNKNOWN_CONTENT", "Contenido de representación desconocida: no se puede revisar su privacidad.")
            e=Element(tag,vr,self.raw[start:start+length]);fields[tag]=e;self.all_elements.append(e)
            pos=start+length
        if stop_item:raise ResearchError("DICOM_SEQUENCE", "Falta el delimitador de un elemento de secuencia.")
        return fields,pos

    def sequence(self, pos,length,explicit,depth,parent_end):
        end=parent_end if length==0xffffffff else pos+length
        if end>parent_end:raise ResearchError("DICOM_SEQUENCE", "Secuencia fuera de límites.")
        while pos<end:
            tag,vr,n,start=self.header(pos,explicit)
            if tag==(0xfffe,0xe0dd) and n==0 and length==0xffffffff:return start
            if tag!=(0xfffe,0xe000):raise ResearchError("DICOM_SEQUENCE", "Elemento de secuencia no válido.")
            item_end=end if n==0xffffffff else start+n
            if item_end>end:raise ResearchError("DICOM_SEQUENCE", "Elemento de secuencia fuera de límites.")
            _,pos=self.dataset(start,item_end,explicit,depth,stop_item=n==0xffffffff)
        if length==0xffffffff:raise ResearchError("DICOM_SEQUENCE", "Falta el cierre de una secuencia.")
        return pos


def read_dicom(raw: bytes, max_pixels=32_000_000, max_dimension=8192) -> DicomImage:
    if len(raw)<140 or raw[128:132]!=b"DICM":
        raise ResearchError("NOT_DICOM", "No es un archivo DICOM Part 10 válido. Cambiar la extensión no convierte una imagen a DICOM.")
    parser=Parser(raw);pos=132;meta={}
    while pos+8<=len(raw) and struct.unpack_from("<H",raw,pos)[0]==2:
        tag,vr,n,start=parser.header(pos,True)
        if n==0xffffffff or n%2 or start+n>len(raw):raise ResearchError("DICOM_META", "Metadatos de archivo inválidos.")
        if tag in meta:raise ResearchError("DICOM_DUPLICATE_TAG", "Metadatos duplicados.")
        meta[tag]=raw[start:start+n];pos=start+n
    ts=meta.get((2,0x10),b"").rstrip(b"\0 ").decode("ascii",errors="replace")
    if ts not in {EXPLICIT_LE,IMPLICIT_LE}:
        raise ResearchError("TRANSFER_SYNTAX", "Solo se admiten DICOM sin compresión, Little Endian (explícito o subconjunto implícito). No se decodifican JPEG, JPEG-LS, JPEG2000, RLE ni tomosíntesis.")
    fields,_=parser.dataset(pos,len(raw),ts==EXPLICIT_LE)
    obj=DicomImage(np.empty((0,0)),fields,{},[])
    if obj.text((8,0x60)).upper()!="MG":raise ResearchError("MODALITY", "La modalidad debe ser MG (mamografía).")
    if obj.text((8,0x16)) not in MG_SOPS:raise ResearchError("SOP_CLASS", "La clase SOP no corresponde a mamografía digital 2D admitida.")
    if meta.get((2,2),b"").rstrip(b"\0 ") != obj.text((8,0x16)).encode():
        raise ResearchError("SOP_MISMATCH", "La clase SOP del archivo y del conjunto de datos no coinciden.")
    if obj.number((0x28,8),1)!=1:raise ResearchError("MULTIFRAME", "Solo se admite una imagen 2D por archivo; no tomosíntesis ni multiframe.")
    rows=obj.number((0x28,0x10));cols=obj.number((0x28,0x11));bits=obj.number((0x28,0x100))
    stored=obj.number((0x28,0x101));high=obj.number((0x28,0x102));signed=obj.number((0x28,0x103))
    if not all(isinstance(v,int) for v in (rows,cols,bits,stored,high,signed)):
        raise ResearchError("PIXEL_HEADER", "Faltan atributos enteros obligatorios de píxel.")
    if min(rows,cols)<16 or max(rows,cols)>max_dimension or rows*cols>max_pixels:
        raise ResearchError("PIXEL_LIMIT", "Dimensiones fuera del intervalo permitido (mínimo 16; máximo 8192 por lado y 32 millones de píxeles).")
    if bits not in {8,16} or not 1<=stored<=bits or high!=stored-1 or signed not in {0,1}:
        raise ResearchError("BITS", "Solo se admiten píxeles enteros de 8/16 bits con HighBit = BitsStored - 1.")
    photo=obj.text((0x28,4))
    if photo not in {"MONOCHROME1","MONOCHROME2"} or obj.number((0x28,2))!=1:
        raise ResearchError("GRAYSCALE", "Se requiere una imagen monocromática de un solo canal.")
    if obj.text((0x28,0x301)).upper()!="NO":
        raise ResearchError("BURNED_IN", "BurnedInAnnotation debe declarar NO. La revisión visual de los píxeles sigue siendo obligatoria; este atributo no garantiza desidentificación.")
    removed=obj.text((0x12,0x62)).upper()=="YES"
    for e in parser.all_elements:
        val=e.value.rstrip(b"\0 ")
        if not val:continue
        if e.vr=="PN" or e.tag in PRIVACY_TAGS:
            raise ResearchError("IDENTIFIERS", "Se detectaron atributos potencialmente identificadores. Cargue una copia desidentificada y autorizada; no se muestran los valores.")
        if e.tag==(0x10,0x20) and not removed:
            raise ResearchError("PATIENT_ID", "El DICOM contiene PatientID sin declaración de identidad retirada. Revise su desidentificación.")
        if 0x6000<=e.tag[0]<=0x60ff:
            raise ResearchError("OVERLAY", "La imagen incluye atributos de overlay; requieren revisión externa.")
    pixel=fields.get((0x7fe0,0x10))
    if pixel is None:raise ResearchError("NO_PIXELS", "El DICOM no contiene PixelData.")
    expected=rows*cols*(bits//8)
    if len(pixel.value)!=expected+(expected%2):raise ResearchError("PIXEL_LENGTH", "El tamaño de PixelData no coincide con el encabezado.")
    a=np.frombuffer(pixel.value[:expected],dtype="<u2" if bits==16 else "u1").reshape(rows,cols)
    a=np.bitwise_and(a,(1<<stored)-1).astype(np.int32)
    if signed:a=(a ^ (1<<(stored-1))) - (1<<(stored-1))
    obj.pixels=a.astype(np.float32)
    if not np.isfinite(obj.pixels).all() or float(np.ptp(obj.pixels))<=0:
        raise ResearchError("CONSTANT_IMAGE", "La imagen no tiene variación de intensidad utilizable. No se ejecuta el modelo.")
    if (0x28,0x3000) in fields or (0x28,0x3010) in fields:
        obj.warnings.append("Contiene LUT en secuencia: no se admite en el pipeline estandarizado de esta versión.")
    view=obj.text((0x18,0x5101));view=view if view in {"CC","MLO","ML","LM","XCCL","XCCM"} else "no documentada"
    side=obj.text((0x20,0x62)) or obj.text((0x20,0x60));side=side if side in {"L","R","B"} else "no documentada"
    obj.technical={"rows":rows,"columns":cols,"bits_allocated":bits,"bits_stored":stored,
       "signed":bool(signed),"photometric":photo,"modality":"MG","frames":1,"view":view,
       "laterality":side,"transfer_syntax":"Explicit VR Little Endian" if ts==EXPLICIT_LE else "Implicit VR Little Endian (subconjunto)",
       "reader":"dicom_restringido_v3", "identity_removed_declared":removed}
    obj.warnings += ["Control de atributos limitado: no certifica anonimización ni detecta texto incrustado en los píxeles.",
                     "Visor de investigación: no tiene calidad ni calibración certificada para lectura diagnóstica."]
    return obj


def transform(image: DicomImage, pipeline: str) -> np.ndarray:
    """Única transformación utilizada en entrenamiento e inferencia."""
    a=image.pixels.copy()
    if pipeline=="legacy":
        maximum=float(a.max())
        if maximum<=0 or float(a.min())<0:
            raise ResearchError("LEGACY_SCALE", "El modo legado requiere intensidades no negativas y máximo positivo.")
        a/=maximum
    elif pipeline=="standardized_v3":
        if (0x28,0x3000) in image.fields or (0x28,0x3010) in image.fields:
            raise ResearchError("LUT_UNSUPPORTED", "Esta versión no implementa LUT en secuencia. No se omite la transformación silenciosamente.")
        slope=image.number((0x28,0x1053),1);intercept=image.number((0x28,0x1052),0)
        if not np.isfinite([slope,intercept]).all() or slope==0:
            raise ResearchError("RESCALE", "RescaleSlope/Intercept no válidos.")
        a=a*slope+intercept
        wc=image.number((0x28,0x1050));ww=image.number((0x28,0x1051))
        if (wc is None)!=(ww is None):raise ResearchError("WINDOW", "WindowCenter y WindowWidth deben estar ambos presentes o ausentes.")
        if wc is not None:
            if not np.isfinite([wc,ww]).all() or ww<1 or image.text((0x28,0x1056),"LINEAR")!="LINEAR":
                raise ResearchError("WINDOW", "Solo se admite VOI LINEAR con ventana finita y ancho >= 1.")
            a=(a>wc-0.5).astype(np.float32) if ww==1 else np.clip((a-(wc-0.5))/(ww-1)+0.5,0,1)
        if image.technical['photometric']=="MONOCHROME1":a=a.max()+a.min()-a
        shape=image.text((0x2050,0x20))
        if shape and shape not in {"IDENTITY"}:
            raise ResearchError("PRESENTATION_LUT", "PresentationLUTShape no admitida; no se omite automáticamente.")
        valid=np.ones(a.shape,dtype=bool)
        pad=image.number((0x28,0x120));pad_end=image.number((0x28,0x121),pad)
        if pad is not None and image.technical["signed"] and image.fields[(0x28,0x120)].vr!="SS":
            raise ResearchError("PADDING_VR", "El relleno de una imagen con signo debe tener VR SS explícita.")
        if pad is not None:valid=~((image.pixels>=min(pad,pad_end))&(image.pixels<=max(pad,pad_end)))
        values=a[valid]
        if not values.size:raise ResearchError("PADDING_ONLY", "La imagen solo contiene píxeles de relleno.")
        lo,hi=np.percentile(values,[1,99])
        if hi<=lo:lo,hi=float(values.min()),float(values.max())
        if hi<=lo:raise ResearchError("NO_DYNAMIC_RANGE", "No queda variación después del preprocesamiento.")
        a=np.clip((a-lo)/(hi-lo),0,1)*255;a[~valid]=0
    else:raise ResearchError("PIPELINE", "Pipeline de preprocesamiento no reconocido.")
    with warnings.catch_warnings():
        warnings.simplefilter("error",RuntimeWarning)
        try:a=cv2.resize(a,(224,224),interpolation=cv2.INTER_AREA)
        except Exception:raise ResearchError("RESIZE", "No se pudo redimensionar el tensor.") from None
    if not np.isfinite(a).all():raise ResearchError("NONFINITE", "El preprocesamiento produjo valores no finitos.")
    return np.repeat(a[...,None],3,axis=-1).astype(np.float32)


def safe_preview(image: DicomImage) -> np.ndarray:
    """Presentación técnica independiente de la entrada del modelo; no altera inferencia."""
    a=image.pixels
    lo,hi=np.percentile(a,[1,99])
    if hi<=lo:lo,hi=float(a.min()),float(a.max())
    a=np.clip((a-lo)/max(hi-lo,1e-9),0,1)
    if image.technical['photometric']=="MONOCHROME1":a=1-a
    scale=min(1,768/max(a.shape))
    return cv2.resize((a*255).astype(np.uint8),(max(1,round(a.shape[1]*scale)),max(1,round(a.shape[0]*scale))),interpolation=cv2.INTER_AREA)
