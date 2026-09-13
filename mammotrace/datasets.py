"""Validación estructural, procedencia declarada y partición por paciente."""
from __future__ import annotations
import csv, io, hashlib, re
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
import numpy as np
from .config import CLASSES
from .errors import ResearchError

REQUIRED=('dicom_path','label','patient_id','label_source','label_verified')
ID_RE=re.compile(r'^[A-Za-z0-9_-]{1,64}$')

def read_csv(raw:bytes,max_rows=10000):
    try:
        text=raw.decode('utf-8-sig')
        if '\x00' in text:raise ValueError('null')
        reader=csv.DictReader(io.StringIO(text),strict=True)
        fields=reader.fieldnames
        if not fields or len(fields)!=len(set(fields)) or len(fields)>40:raise ValueError('columns')
        rows=[]
        for row in reader:
            if len(rows)>=max_rows:raise ResearchError('CSV_ROWS','El CSV supera el límite de filas.',413)
            if None in row or any(v is None or len(v)>1024 for v in row.values()):raise ValueError('row')
            rows.append({k:v.strip() for k,v in row.items()})
        if not rows:raise ValueError('empty')
        return fields,rows
    except ResearchError:raise
    except (UnicodeError,ValueError,csv.Error):
        raise ResearchError('CSV_FORMAT','Se requiere CSV UTF-8, separado por comas, con encabezado único y filas completas.') from None

def safe_relative(value):
    # Rechaza también rutas Windows, segmentos ambiguos y fórmulas de hoja de cálculo.
    p=PurePosixPath(value)
    if not value or '\\' in value or ':' in value or p.is_absolute() or any(x in {'..','.'} for x in value.split('/')) or value[0] in '=+@-' or '' in value.split('/'):
        return False
    return p.suffix.lower() in {'.dcm','.dicom'}

def validate_dataset(raw:bytes,data_root:Path|None=None,check_hashes=True,max_rows=10000):
    fields,rows=read_csv(raw,max_rows)
    missing=sorted(set(REQUIRED)-set(fields))
    if missing:raise ResearchError('CSV_COLUMNS','Faltan columnas: '+', '.join(missing)+'.')
    errors=[];seen=set();hashes={};patients=defaultdict(set)
    counts=Counter();path_checks=bool(data_root);resolved=[]
    for i,row in enumerate(rows,2):
        def err(code):errors.append({'row':i,'code':code})
        label=row['label'];pid=row['patient_id'];path=row['dicom_path']
        if label not in CLASSES:err('LABEL_NOT_ALLOWED')
        else:counts[label]+=1
        if not ID_RE.fullmatch(pid):err('PATIENT_CODE_FORMAT')
        if row['label_verified'].lower() not in {'true','yes','1','si','sí'}:err('LABEL_NOT_VERIFIED')
        if not row['label_source'] or row['label_source'].lower() in {'random','aleatorio','synthetic','sintetico','sintético','filename','nombre_archivo'}:err('LABEL_SOURCE_REQUIRED')
        if path.casefold() in seen:err('DUPLICATE_PATH')
        seen.add(path.casefold());patients[pid].add(label)
        if not safe_relative(path):err('UNSAFE_PATH');continue
        if data_root:
            root=data_root.resolve();p=(root/path).resolve()
            if not p.is_relative_to(root):err('PATH_ESCAPE');continue
            if not p.is_file():err('FILE_MISSING');continue
            resolved.append(p)
            if check_hashes:
                with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
                if h in hashes:err('DUPLICATE_CONTENT')
                hashes[h]=i
    # Una etiqueta única por paciente es un criterio conservador explícito de este entrenador.
    conflicts=sum(len(labels)>1 for labels in patients.values())
    if conflicts:errors.append({'row':None,'code':'CONFLICTING_PATIENT_LABELS'})
    by_patient=Counter(next(iter(v)) for v in patients.values() if len(v)==1)
    adequate=all(by_patient.get(c,0)>=5 for c in CLASSES)
    warnings=['La validación comprueba declaraciones y estructura; no verifica el diagnóstico de referencia ni la identidad del código.',
      'No coloque nombres, documentos, historias clínicas ni texto clínico libre en este CSV.']
    if not path_checks:warnings.append('Las imágenes no se adjuntaron: existencia, contenido y duplicación binaria no comprobados en la interfaz.')
    if not adequate:warnings.append('Se requieren al menos 5 pacientes de cada clase para la partición implementada. Esto no garantiza tamaño muestral suficiente científicamente.')
    return {'rows':len(rows),'patients':len(patients),'images_per_class':{c:counts[c] for c in CLASSES},
       'patients_per_class':{c:by_patient[c] for c in CLASSES},'conflicting_patients':conflicts,
       'errors':errors[:100],'error_count':len(errors),'valid_structure':not errors,
       'split_feasible':adequate and not errors,'files_checked':path_checks,
       'ready_for_training':path_checks and adequate and not errors,'warnings':warnings}

def grouped_split(rows,seed=42):
    """Determinista por paciente; ~60/20/20. Nunca replica imágenes para balancear."""
    grouped=defaultdict(set)
    for row in rows:grouped[row['patient_id']].add(row['label'])
    if any(len(x)!=1 for x in grouped.values()):raise ResearchError('PATIENT_CONFLICT','Un paciente tiene etiquetas incompatibles; revise la unidad de análisis.')
    rng=np.random.default_rng(seed);allocation={}
    for label in CLASSES:
        ids=sorted(p for p,labels in grouped.items() if labels=={label})
        if len(ids)<5:raise ResearchError('SPLIT_SIZE','Se requieren al menos 5 pacientes por clase.')
        rng.shuffle(ids);nt=max(1,round(len(ids)*.2));nv=max(1,round(len(ids)*.2))
        for k,p in enumerate(ids):allocation[p]='test' if k<nt else 'validation' if k<nt+nv else 'train'
    result={name:[dict(row,split=name) for row in rows if allocation[row['patient_id']]==name] for name in ('train','validation','test')}
    sets=[{r['patient_id'] for r in v} for v in result.values()]
    if any(sets[i]&sets[j] for i in range(3) for j in range(i)):raise ResearchError('LEAKAGE','Fuga de pacientes detectada.')
    return result
