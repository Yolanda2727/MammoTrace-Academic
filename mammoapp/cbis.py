"""CBIS-DDSM metadata audit. No image prediction or educational guidance dependency.

All units are explicit: rows=lesion-view annotations, images=full-image series,
lesions=(patient,side,type,abnormality), subjects=normalized patient_id.
"""
from __future__ import annotations
import csv, hashlib, io, json, re
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from mammotrace.errors import ResearchError

FILENAMES=tuple(f'{kind}_case_description_{split}_set.csv' for kind in ('calc','mass') for split in ('train','test'))
PATHS={'full':'image file path','crop':'cropped image file path','mask':'ROI mask file path'}
LABELS={'BENIGN':0,'BENIGN_WITHOUT_CALLBACK':0,'MALIGNANT':1}
UID=re.compile(r'[0-9]+(?:\.[0-9]+)+\Z')
PATIENT=re.compile(r'P_\d{5}\Z')
MAX_CSV=12*1024*1024

def fail(message):raise ResearchError('CBIS_INPUT',message)

def digest(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def series_from_path(value:str)->str:
    value=value.strip().replace('\\','/')
    if not value or value.startswith('/') or ':' in value:fail('Ruta CBIS vacía, absoluta o no admitida.')
    parts=PurePosixPath(value).parts
    if len(parts)!=4 or '..' in parts or not UID.fullmatch(parts[-2]) or not UID.fullmatch(parts[-3]) or not parts[-1].lower().endswith('.dcm'):
        fail('La ruta CBIS debe contener sujeto/StudyUID/SeriesUID/archivo.dcm.')
    return parts[-2]

def read_cases(raw:bytes,filename:str)->list[dict]:
    if filename not in FILENAMES or not isinstance(raw,bytes) or not raw or len(raw)>MAX_CSV:fail('Se requieren los CSV oficiales y un tamaño de hasta 12 MiB por archivo.')
    try:
        rd=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        required={'patient_id','pathology','left or right breast','image view','abnormality id','abnormality type','assessment',*PATHS.values()}
        if not rd.fieldnames or not required<=set(rd.fieldnames):fail('Faltan columnas obligatorias de CBIS-DDSM.')
        rows=[]
        for n,source in enumerate(rd,2):
            if n>20001 or None in source or any(v is None for v in source.values()):fail('Fila incompleta o límite de registros excedido.')
            src={k:v.strip() for k,v in source.items()}; pid=src['patient_id'];pathology=src['pathology']
            if not PATIENT.fullmatch(pid) or pathology not in LABELS:fail('Identificador o patología no admitidos. No se infieren etiquetas.')
            kind=filename.split('_')[0];split='train' if '_train_' in filename else 'test'
            if src['left or right breast'] not in {'LEFT','RIGHT'} or src['image view'] not in {'CC','MLO'}:fail('Lateralidad o vista no admitida.')
            if src['abnormality type']!={'calc':'calcification','mass':'mass'}[kind]:fail('Tipo de lesión incompatible con el archivo.')
            if not src['abnormality id'].isdigit():fail('abnormality id debe ser entero positivo.')
            row={'record_id':f'{kind}_{split}_{n-1:04d}','source_file':filename,'source_record':n-1,
                 'patient_id':pid,'side':src['left or right breast'],'view':src['image view'],'kind':kind,
                 'abnormality_id':src['abnormality id'],'official_split':split,'pathology':pathology,
                 'binary_target':LABELS[pathology],'assessment':src['assessment'],
                 'density':src.get('breast_density',src.get('breast density',''))}
            for role,key in PATHS.items():
                row[role+'_path']=src[key];row[role+'_series_uid']=series_from_path(src[key])
            row['lesion_key']='|'.join(row[k] for k in ['patient_id','side','kind','abnormality_id'])
            row['image_key']=row['full_series_uid'];rows.append(row)
        if not rows:fail('El CSV no contiene registros.')
        return rows
    except (UnicodeError,csv.Error) as e:fail('CSV no legible: '+type(e).__name__)

def read_bundle(folder:Path)->list[dict]:
    return [r for name in FILENAMES for r in read_cases((folder/name).read_bytes(),name)]

def read_manifest(raw:bytes)->set[str]:
    if not raw or len(raw)>MAX_CSV:fail('Manifiesto vacío o demasiado grande.')
    try:text=raw.decode('utf-8-sig')
    except UnicodeError:fail('Manifiesto no textual.')
    if 'ListOfSeriesToDownload=' not in text:fail('No es un manifiesto NBIA de series.')
    entries=[x.strip() for x in text.split('ListOfSeriesToDownload=',1)[1].splitlines() if x.strip()]
    if not entries or any(not UID.fullmatch(x) for x in entries):fail('El manifiesto contiene UID inválidos.')
    if len(set(entries))!=len(entries):fail('UID duplicados en el manifiesto.')
    return set(entries)

def read_download_metadata(raw:bytes)->tuple[list[dict],list[dict]]:
    """Repair only the exact 17-column NBIA schema / unquoted decimal-comma case."""
    if not raw or len(raw)>MAX_CSV:fail('metadata.csv vacío o excesivo.')
    try: rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline='')))
    except (UnicodeError,csv.Error):fail('metadata.csv no legible.')
    if not rows or len(rows[0])!=17 or rows[0][0]!='Series UID' or rows[0][14:]!=['File Size','File Location','Download Timestamp']:fail('Esquema de metadata.csv no reconocido.')
    header=rows[0];out=[];repairs=[]
    for n,r in enumerate(rows[1:],2):
        if len(r)==18 and re.fullmatch(r'\d+',r[14]) and re.fullmatch(r'\d+\s+(?:B|KB|MB|GB)',r[15]) and re.match(r'\d{4}-\d\d-\d\dT',r[17]):
            r=r[:14]+[r[14]+','+r[15]]+r[16:];repairs.append({'line':n,'repair':'rejoin_decimal_comma_File_Size'})
        if len(r)!=17 or not UID.fullmatch(r[0]):fail(f'metadata.csv: fila {n} ambigua; no se corrige automáticamente.')
        if not r[13].isdigit():fail('Número de imágenes no entero.')
        out.append(dict(zip(header,r)))
    if len({r['Series UID'] for r in out})!=len(out):fail('Series duplicadas en metadata.csv.')
    return out,repairs

def audit(rows:list[dict],manifest:set[str]|None=None,digest_rows:list[dict]|None=None,downloads:list[dict]|None=None)->dict:
    ids=[r['record_id'] for r in rows]
    if len(ids)!=len(set(ids)):fail('Duplicación de archivos/registros de origen.')
    subjects={r['patient_id'] for r in rows};tr={r['patient_id'] for r in rows if r['official_split']=='train'};te={r['patient_id'] for r in rows if r['official_split']=='test'}
    overlap=tr&te
    groups=defaultdict(list)
    for r in rows:groups[r['image_key']].append(r)
    lesion_groups=defaultdict(list)
    for r in rows:lesion_groups[r['lesion_key']].append(r)
    summary={'version':'4.1.0','annotation_rows':len(rows),'subjects':len(subjects),'full_image_series':len(groups),'lesion_keys':len(lesion_groups),
        'pathology_counts':dict(Counter(r['pathology'] for r in rows)),
        'source_counts':[{'source':f,'rows':sum(r['source_file']==f for r in rows),'subjects':len({r['patient_id'] for r in rows if r['source_file']==f}),**dict(Counter(r['pathology'] for r in rows if r['source_file']==f))} for f in FILENAMES],
        'official_train_subjects':len(tr),'official_test_subjects':len(te),'overlap_subjects':sorted(overlap),
        'train_rows_removed_holdout_priority':sum(r['official_split']=='train' and r['patient_id'] in overlap for r in rows),
        'mixed_binary_image_groups':sum(len({r['binary_target'] for r in g})>1 for g in groups.values()),
        'mixed_binary_lesion_groups':sum(len({r['binary_target'] for r in g})>1 for g in lesion_groups.values()),
        'normal_cohort_present':False,'diagnostic_metrics_calculated':False,
        'cross_source_subject_overlap':{a+' / '+b:len({r['patient_id'] for r in rows if r['source_file']==a}&{r['patient_id'] for r in rows if r['source_file']==b}) for i,a in enumerate(FILENAMES) for b in FILENAMES[i+1:]}}
    requested={r[role+'_series_uid'] for r in rows for role in PATHS}
    if manifest is not None:summary['manifest']={'series':len(manifest),'referenced_series':len(requested),'referenced_missing':len(requested-manifest),'manifest_not_referenced':len(manifest-requested)}
    if digest_rows is not None:
        uids={r['Series Instance UID'] for r in digest_rows}
        summary['digest']={'rows':len(digest_rows),'unique_series':len(uids),'sum_image_count':sum(int(r['Image Count']) for r in digest_rows),'bytes':sum(int(r['File Size']) for r in digest_rows),'referenced_missing':len(requested-uids),'series_descriptions':dict(Counter(r['Series Description'] for r in digest_rows))}
        if manifest is not None:summary['digest']['manifest_missing']=len(manifest-uids);summary['digest']['digest_not_in_manifest']=len(uids-manifest)
    if downloads is not None:
        uids={r['Series UID'] for r in downloads}
        summary['download_log']={'series':len(uids),'declared_instances':sum(int(r['Number of Images']) for r in downloads),'full_image_series':sum(r['Series Description']=='full mammogram images' for r in downloads),'referenced_series_present':len(requested&uids), 'annotation_rows_full_image_logged':sum(r['full_series_uid'] in uids for r in rows),'log_is_pixel_verification':False}
    return summary

def partition(rows:list[dict],policy='reject',validation_fraction=.2,seed=20260913)->list[dict]:
    if policy not in {'reject','holdout_priority'} or not 0<validation_fraction<1:fail('Política o fracción de validación no admitida.')
    te={r['patient_id'] for r in rows if r['official_split']=='test'}
    overlap=te&{r['patient_id'] for r in rows if r['official_split']=='train'}
    if overlap and policy=='reject':fail(f'Solapamiento de {len(overlap)} sujetos. Seleccione explícitamente holdout_priority para excluir sus filas de entrenamiento.')
    eligible=sorted({r['patient_id'] for r in rows if r['official_split']=='train' and r['patient_id'] not in te},key=lambda p:hashlib.sha256(f'{seed}:{p}'.encode()).hexdigest())
    if len(eligible)<2:fail('Se requieren al menos dos sujetos de entrenamiento independientes.')
    nval=max(1,min(len(eligible)-1,round(len(eligible)*validation_fraction)))
    va=set(eligible[:nval]);out=[]
    for r in rows:
        split='test' if r['official_split']=='test' else 'excluded_overlap' if r['patient_id'] in te else 'validation' if r['patient_id'] in va else 'train'
        out.append({**r,'partition':split,'partition_policy':policy,'partition_seed':seed,'engineering_exposed_subject':r['patient_id']=='P_00038'})
    for a,b in [('train','validation'),('train','test'),('validation','test')]:
        if {r['patient_id'] for r in out if r['partition']==a}&{r['patient_id'] for r in out if r['partition']==b}:fail('Error interno: particiones no disjuntas.')
    return out

def csv_bytes(rows:list[dict])->bytes:
    if not rows:return b''
    out=io.StringIO(newline='');w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return out.getvalue().encode('utf-8-sig')

def image_inventory(rows:list[dict])->list[dict]:
    """One row per full-image series. Mixed targets excluded, never assigned by max."""
    groups=defaultdict(list)
    for r in rows:groups[r['image_key']].append(r)
    lesions=defaultdict(set)
    for r in rows:lesions[r['lesion_key']].add(r['binary_target'])
    discordant={k for k,v in lesions.items() if len(v)>1}
    out=[]
    for uid,g in sorted(groups.items()):
        y={r['binary_target'] for r in g};sp={r.get('partition',r['official_split']) for r in g}
        flag=any(r['lesion_key'] in discordant for r in g)
        eligible=len(y)==1 and len(sp)==1 and 'excluded_overlap' not in sp and not flag
        out.append({'series_uid':uid,'patient_id':g[0]['patient_id'],'partition':next(iter(sp)) if len(sp)==1 else 'ambiguous',
            'binary_target':next(iter(y)) if len(y)==1 else '', 'eligible_metadata':eligible,'annotation_rows':len(g),
            'pathology_values':'|'.join(sorted({r['pathology'] for r in g})),'source_path':g[0]['full_path'],
            'engineering_exposed_subject':g[0]['patient_id']=='P_00038','discordant_lesion_key':flag,'exclusion_reason':'' if eligible else 'target_or_lesion_or_partition_conflict_or_overlap'})
    return out
