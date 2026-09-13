"""Inferencia experimental y oclusión sobre logits, separadas de toda orientación."""
from __future__ import annotations
import hashlib, hmac, json, os, threading
from pathlib import Path
import numpy as np
import cv2
from mammotrace.model import ModelService
from mammotrace.errors import ResearchError
from .config import ROOT

ORIGINAL_SHA256='0fae4daed4eaa93f05ea3e0c996181b463c21e464cab2a4e8fabef73f951977a'
_ASSEMBLY_LOCK=threading.Lock()


def ensure_legacy_weights(folder: Path | None=None) -> Path:
    """Reconstruye únicamente el modelo legado conocido, desde partes verificadas.
    No descarga pesos ni permite cargar modelos arbitrarios desde la interfaz.
    """
    folder=Path(folder or ROOT/'models')
    output=folder/'modelo.h5'
    with _ASSEMBLY_LOCK:
        if output.exists():
            with output.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            if not hmac.compare_digest(digest,ORIGINAL_SHA256):
                raise ResearchError('MODEL_HASH','Los pesos locales no coinciden con el modelo legado esperado.')
            return output
        index=folder/'parts.json'
        if not index.exists():
            raise ResearchError('MODEL_ABSENT','Este paquete no contiene los pesos privados. El visor, los informes y la orientación local siguen disponibles; no se inventan predicciones.')
        try:
            manifest=json.loads(index.read_text(encoding='utf-8'))
            if manifest.get('sha256')!=ORIGINAL_SHA256 or not 1<=len(manifest['parts'])<=8:
                raise ValueError()
            if sum(p['size'] for p in manifest['parts'])>110_000_000:raise ValueError()
            temp=folder/'modelo.assembling'
            try:
                with temp.open('wb') as w:
                    for part in manifest['parts']:
                        name=part['name']
                        if not isinstance(name,str) or not __import__('re').fullmatch(r'legacy_part_\d{2}\.bin',name):raise ValueError()
                        p=folder/name
                        if p.is_symlink() or p.stat().st_size!=part['size']:raise ValueError()
                        data=p.read_bytes()
                        if hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError()
                        w.write(data)
                with temp.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
                if actual!=ORIGINAL_SHA256:raise ValueError()
                os.replace(temp,output)
            finally:
                temp.unlink(missing_ok=True)
        except Exception:
            raise ResearchError('MODEL_PARTS','Partes del modelo ausentes, dañadas o incompatibles. No se ejecuta inferencia.') from None
    return output


class ExplainableLegacy:
    def __init__(self,folder:Path | None=None):
        folder=folder or ROOT/'models'
        ensure_legacy_weights(folder)
        self.service=ModelService(folder,'torch')
        self.service.load()
        if not self.service.ready:
            raise ResearchError('MODEL_LOAD',self.service.error['message'])
        import keras
        final=self.service.model.layers[-1]
        if final.__class__.__name__!='Dense' or len(final.get_weights())!=2:
            raise ResearchError('LOGIT_LAYER','La salida no permite recuperar logits de forma explícita.')
        self.features=keras.Model(self.service.model.inputs, final.input)
        self.kernel,self.bias=final.get_weights()
        self.lock=self.service.lock

    def logits_batch(self,rgb: np.ndarray) -> np.ndarray:
        import keras
        with self.lock:
            a=self.service.prepare(rgb)
            f=np.asarray(keras.ops.convert_to_numpy(self.features([a],training=False)),dtype=np.float32)
            logits=f@self.kernel+self.bias
        if logits.shape!=(len(a),3) or not np.isfinite(logits).all():
            raise ResearchError('LOGIT_OUTPUT','No se obtuvo una activación válida.')
        return logits.astype(np.float64)

    def explain(self,rgb:np.ndarray,grid:int=7) -> dict:
        if grid!=7:raise ResearchError('XAI_GRID','La cuadrícula de auditoría es 7 por 7.')
        with self.lock:
            score=self.service.score(rgb)
            baseline=self.logits_batch(rgb)[0]
            target=score['class_index']
            if int(np.argmax(baseline))!=target:
                raise ResearchError('LOGIT_CLASS','No coincide el objetivo del mapa con la salida del modelo.')
            fill=float(np.median(rgb)); delta=[]
            for start in range(0,49,4):
                batch=[]
                for k in range(start,min(start+4,49)):
                    r,c=divmod(k,7);a=rgb.copy();a[r*32:(r+1)*32,c*32:(c+1)*32,:]=fill;batch.append(a)
                values=self.logits_batch(np.stack(batch))[:,target]
                delta.extend((baseline[target]-values).tolist())
        matrix=np.array(delta).reshape(7,7)
        return {'method':'occlusion_logit','target':score['experimental_class'],
                'units':'cambio firmado de activación pre-softmax; no probabilidad',
                'baseline_logit':float(baseline[target]),'fill':fill,'grid':7,'signed_delta':matrix.tolist(),
                'max_abs_delta':float(np.abs(matrix).max()),
                'informative_numerically':bool(np.max(np.abs(matrix))>1e-6),
                'coordinates':'tensor 224 × 224, no coordenadas anatómicas',
                'warning':'Sensibilidad del modelo legado entrenado con etiquetas sintéticas. No localiza lesiones ni explica causas clínicas.',
                'score':score,'model_sha256':ORIGINAL_SHA256,'runtime':self.service.runtime}


def heatmap_overlay(rgb:np.ndarray,result:dict) -> np.ndarray | None:
    a=np.asarray(result['signed_delta'],dtype=float)
    maximum=float(np.max(np.abs(a)))
    if not np.isfinite(a).all() or a.shape!=(7,7):
        raise ResearchError('XAI_MAP','Mapa incompatible.')
    if maximum<=1e-6:return None
    # Intensidad = magnitud absoluta. El signo se consulta en la tabla de deltas.
    values=cv2.resize((np.abs(a)/maximum*255).astype(np.uint8),(224,224),interpolation=cv2.INTER_NEAREST)
    colors=cv2.cvtColor(cv2.applyColorMap(values,cv2.COLORMAP_VIRIDIS),cv2.COLOR_BGR2RGB)
    base=np.clip(rgb*255,0,255).astype(np.uint8)
    return cv2.addWeighted(base,.55,colors,.45,0)
