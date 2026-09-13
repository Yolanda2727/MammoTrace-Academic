"""Carga local de pesos verificados; nunca usa un modelo simulado como sustituto."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import threading
from pathlib import Path
import numpy as np
from .config import CLASSES
from .errors import ResearchError

ALLOWED_H5_CLASSES={"Functional","Model","Sequential","Activation","Add","BatchNormalization","Conv2D","Dense",
 "Dropout","GlobalAveragePooling2D","InputLayer","MaxPooling2D","ZeroPadding2D","DTypePolicy","__keras_tensor__","GlorotUniform","Zeros","Ones","L2"}


def load_manifest(folder: Path) -> dict:
    try:
        m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        file=folder/m['model_file']
        if file.resolve().parent!=folder.resolve() or file.suffix not in {'.h5','.keras'}:
            raise ValueError('model path')
        if m.get('classes')!=list(CLASSES) or m.get('input_shape')!=[224,224,3] or m.get('clinical_use') is not False:
            raise ValueError('schema')
        valid={('legacy','legacy_0_1_resnet'),('standardized_v3','embedded_0_255')}
        if (m.get('pipeline'),m.get('input_mode')) not in valid:raise ValueError('pipeline')
        if m.get('status') not in {'legacy_integration_only','research_retrained'}:raise ValueError('status')
        if not isinstance(m.get('sha256'),str) or len(m['sha256'])!=64:raise ValueError('hash')
    except (OSError,ValueError,KeyError,TypeError):
        raise ResearchError('MODEL_MANIFEST','Manifiesto de modelo ausente o incompatible.',503) from None
    if not file.is_file():raise ResearchError('MODEL_MISSING','No se encontró el archivo de pesos.',503)
    with file.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if not __import__('hmac').compare_digest(actual,m['sha256']):
        raise ResearchError('MODEL_HASH','Los pesos no coinciden con su huella SHA-256. Inferencia bloqueada.',503)
    return m


def audit_h5(path):
    import h5py
    try:
        with h5py.File(path,'r') as f:
            config=json.loads(f.attrs['model_config'])
            def walk(obj):
                if isinstance(obj,dict):
                    c=obj.get('class_name')
                    if c and c not in ALLOWED_H5_CLASSES:raise ValueError('class')
                    for value in obj.values():walk(value)
                elif isinstance(obj,list):
                    for value in obj:walk(value)
            walk(config)
            if len(config['config']['layers'])>500:raise ValueError('layers')
    except (OSError,ValueError,KeyError,TypeError):
        raise ResearchError('MODEL_STRUCTURE','Estructura H5 fuera de la lista de capas admitidas.',503) from None

class ModelService:
    def __init__(self,folder:Path,backend='torch'):
        self.folder=folder;self.backend=backend;self.manifest=None;self.model=None;self.error=None
        self.lock=threading.RLock();self.runtime={}

    @property
    def ready(self):return self.model is not None

    def load(self):
        try:
            self.manifest=load_manifest(self.folder)
            name=self.manifest['model_file'];path=self.folder/name
            if path.suffix=='.h5':audit_h5(path)
            os.environ['KERAS_BACKEND']=self.backend
            os.environ.setdefault('OMP_NUM_THREADS','2')
            if importlib.util.find_spec(self.backend) is None:
                raise ResearchError('BACKEND_MISSING','No está instalado el motor de inferencia configurado.',503)
            if self.backend=='torch':
                import torch
                torch.set_num_threads(2)
            import keras
            if keras.backend.backend()!=self.backend:
                raise ResearchError('BACKEND_MISMATCH','Reinicie el proceso para cambiar el motor Keras.',503)
            if path.suffix=='.keras':
                from .keras_layers import ResNetPreprocess  # registers the only custom layer
            model=keras.models.load_model(path,compile=False,safe_mode=True)
            if tuple(model.input_shape)!=(None,224,224,3) or tuple(model.output_shape)!=(None,3):
                raise ResearchError('MODEL_SHAPE','Forma de entrada/salida incompatible.',503)
            self.model=model
            from importlib.metadata import version
            self.runtime={'keras':keras.__version__,'backend':self.backend,'backend_version':version(self.backend),
                          'parameter_count':int(model.count_params()),'layer_count':len(model.layers)}
            self.error=None
        except ResearchError as e:self.error={'code':e.code,'message':e.message};self.model=None
        except Exception:
            self.error={'code':'MODEL_LOAD','message':'No se pudo cargar el modelo. Ejecute scripts/check_environment.py.'};self.model=None

    def prepare(self,rgb):
        a=np.asarray(rgb,dtype=np.float32)
        if a.ndim==3:a=a[None,...]
        if a.ndim!=4 or a.shape[1:]!=(224,224,3) or not np.isfinite(a).all():
            raise ResearchError('MODEL_INPUT','Tensor de entrada inválido.')
        limit=1.0 if self.manifest['input_mode']=='legacy_0_1_resnet' else 255.0
        if a.min()<0 or a.max()>limit+1e-5:
            raise ResearchError('MODEL_SCALE','La escala del tensor no corresponde al manifiesto del modelo.')
        if self.manifest['input_mode']=='legacy_0_1_resnet':
            return a[...,::-1].copy()-np.array([103.939,116.779,123.68],np.float32)
        return a

    def predict_batch(self,rgb):
        if not self.ready:raise ResearchError('MODEL_NOT_READY','Modelo no disponible; no se genera una predicción de sustitución.',503)
        import keras
        with self.lock:
            a=self.prepare(rgb)
            # Legacy h5 serializes input_layers as a list. Preserve that structure.
            inp=[a] if self.manifest['pipeline']=='legacy' else a
            p=np.asarray(keras.ops.convert_to_numpy(self.model(inp,training=False)),dtype=np.float64)
        if p.shape!=(len(a),3) or not np.isfinite(p).all() or (p<0).any() or (p>1).any() or not np.allclose(p.sum(1),1,atol=1e-5):
            raise ResearchError('MODEL_OUTPUT','Salida inválida: no se convierte ni se aplica softmax de forma silenciosa.',503)
        return p

    def score(self,rgb):
        p=self.predict_batch(rgb)[0];idx=int(np.argmax(p))
        entropy=float(-(p[p>0]*np.log(p[p>0])).sum()/np.log(3))
        return {'class_index':idx,'experimental_class':CLASSES[idx],
          'scores':{c:float(v) for c,v in zip(CLASSES,p)},'normalized_entropy':entropy,
          'score_interpretation':'Puntuaciones softmax no calibradas; no son probabilidades clínicas.',
          'clinical_recommendation':None,'saturated_output':bool(p.max()>=0.999)}

    def occlusion(self,rgb,grid=7):
        if grid!=7:raise ResearchError('GRID','La cuadrícula de esta versión es 7 x 7.')
        with self.lock:
            baseline=self.predict_batch(rgb)[0];target=int(np.argmax(baseline));fill=float(np.median(rgb));values=[]
            for start in range(0,grid*grid,4):
                batch=[]
                for k in range(start,min(start+4,grid*grid)):
                    r,c=divmod(k,grid);a=rgb.copy();a[r*32:(r+1)*32,c*32:(c+1)*32,:]=fill;batch.append(a)
                preds=self.predict_batch(np.stack(batch))[:,target]
                values.extend((float(baseline[target])-preds).tolist())
        return {'method':'occlusion_sensitivity','grid':grid,'target_class':CLASSES[target],
          'baseline_score':float(baseline[target]),'fill_value':fill,'informative_at_output_precision':bool(np.max(np.abs(values))>0),'signed_delta':np.array(values).reshape(grid,grid).tolist(),
          'space':'tensor 224x224, no coordenadas anatómicas',
          'warning':'Sensibilidad experimental a perturbaciones. No es segmentación, localización de lesión ni explicación causal; un mapa pequeño no demuestra robustez.'}
