"""Métricas sobre CSV aportado, sin confundir evaluación con validación clínica."""
from __future__ import annotations
import numpy as np
from sklearn.metrics import confusion_matrix,roc_auc_score,f1_score,log_loss
from .config import CLASSES
from .datasets import read_csv,ID_RE
from .errors import ResearchError

def metric_set(y,p):
    pred=p.argmax(1);cm=confusion_matrix(y,pred,labels=[0,1,2]);per={}
    for i,c in enumerate(CLASSES):
        tp=int(cm[i,i]);fn=int(cm[i,:].sum()-tp);fp=int(cm[:,i].sum()-tp);tn=int(cm.sum()-tp-fp-fn)
        ratio=lambda a,b:float(a/b) if b else None
        auc=float(roc_auc_score(y==i,p[:,i])) if len(np.unique(y==i))==2 else None
        per[c]={'sensitivity':ratio(tp,tp+fn),'specificity':ratio(tn,tn+fp),'precision':ratio(tp,tp+fp),
          'f1':ratio(2*tp,2*tp+fp+fn),'auc_ovr':auc,'tp':tp,'fn':fn,'fp':fp,'tn':tn,'support':int((y==i).sum())}
    recalls=[v['sensitivity'] for v in per.values() if v['sensitivity'] is not None]
    onehot=np.eye(3)[y]
    return {'confusion_matrix':cm.tolist(),'per_class':per,'accuracy':float((pred==y).mean()),
      'balanced_accuracy_present_classes':float(np.mean(recalls)),
      'macro_f1':float(f1_score(y,pred,labels=[0,1,2],average='macro',zero_division=0)),
      'brier_multiclass':float(np.mean(np.sum((p-onehot)**2,axis=1))),
      'log_loss':float(log_loss(y,p,labels=[0,1,2]))}

def evaluate_csv(raw:bytes,bootstrap=300,seed=42,max_rows=10000):
    fields,rows=read_csv(raw,max_rows)
    required={'patient_id','label','p_normal','p_benigno','p_maligno'}
    if not required.issubset(fields):raise ResearchError('EVAL_COLUMNS','Columnas requeridas: patient_id,label,p_normal,p_benigno,p_maligno.')
    ids=[];y=[];p=[];seen=set()
    for k,row in enumerate(rows,2):
        if row['label'] not in CLASSES or not ID_RE.fullmatch(row['patient_id']):raise ResearchError('EVAL_LABEL',f'Código o etiqueta inválidos en fila {k}.')
        try:s=np.array([float(row['p_'+c]) for c in CLASSES])
        except ValueError:raise ResearchError('EVAL_SCORE',f'Puntuación no numérica en fila {k}.') from None
        if not np.isfinite(s).all() or (s<0).any() or (s>1).any() or not np.isclose(s.sum(),1,atol=1e-5):
            raise ResearchError('EVAL_SCORE',f'Puntuaciones fuera de rango o suma distinta de 1 en fila {k}.')
        if 'image_id' in fields:
            im=row['image_id']
            if not ID_RE.fullmatch(im) or im in seen:raise ResearchError('EVAL_DUPLICATE','image_id no es único o no tiene formato seudonimizado.')
            seen.add(im)
        ids.append(row['patient_id']);y.append(CLASSES.index(row['label']));p.append(s)
    y=np.array(y);p=np.array(p);ids=np.array(ids);unique=np.unique(ids)
    out=metric_set(y,p);out.update({'n_images':len(y),'n_patients':len(unique),'classes':list(CLASSES),
       'unit_of_estimation':'imagen; intervalos remuestreando conglomerados de pacientes',
       'source':'CSV aportado por el operador; no se certifica su procedencia ni independencia del entrenamiento.',
       'intervals':{},'bootstrap_replicates':0,'bootstrap_seed':seed,
       'warnings':['Estas métricas describen exclusivamente el CSV cargado, no el desempeño del modelo incluido ni su utilidad clínica.',
       'El remuestreo conserva juntas las imágenes del mismo paciente. No corrige sesgo de selección, etiquetas erróneas ni fuga previa.',
       'No hay umbrales clínicos optimizados ni evaluación externa automática.']})
    if not isinstance(bootstrap,int) or not 0<=bootstrap<=1000:raise ResearchError('BOOTSTRAP','Réplicas permitidas: 0 a 1000.')
    if len(unique)<5:
        out['warnings'].append('Menos de 5 pacientes: no se calculan intervalos bootstrap.');return out
    if bootstrap:
        groups=[np.where(ids==pid)[0] for pid in unique];rng=np.random.default_rng(seed)
        values={'accuracy':[],'macro_f1':[],'sensitivity_maligno':[]}
        for _ in range(bootstrap):
            ix=np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]);yy=y[ix];pp=p[ix];pr=pp.argmax(1)
            values['accuracy'].append(float((yy==pr).mean()))
            values['macro_f1'].append(float(f1_score(yy,pr,labels=[0,1,2],average='macro',zero_division=0)))
            malignant=yy==2
            if malignant.any():values['sensitivity_maligno'].append(float((pr[malignant]==2).mean()))
        out['intervals']={k:{'lower':float(np.percentile(v,2.5)),'upper':float(np.percentile(v,97.5)),
           'valid_replicates':len(v),'method':'percentil 95% / bootstrap por paciente'} for k,v in values.items() if v}
        out['bootstrap_replicates']=bootstrap
    if 'image_id' not in fields:out['warnings'].append('Sin image_id: no se puede comprobar duplicación de registros de imagen.')
    if len(np.unique(y))<3:out['warnings'].append('Faltan clases: AUC y sensibilidad sin denominador se expresan como no estimables.')
    return out
