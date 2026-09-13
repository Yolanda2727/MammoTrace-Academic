"""Candidate binary training, never a relabeling of legacy weights.
Run audit_cbis.py, index_cbis.py and the default preflight before --execute.
This program is NOT a clinical validation; exported scores cannot feed guidance.
"""
from pathlib import Path
from collections import defaultdict
import argparse,csv,json,sys,hashlib,os
os.environ.setdefault('KERAS_BACKEND','torch')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mammoapp.cbis import read_bundle,partition,image_inventory
from mammoapp.cbis_dicom import read_cbis,preview

def prepare(data:Path,index_file:Path,root:Path):
    rows=read_bundle(data);parts=partition(rows,'holdout_priority');inv=image_inventory(parts)
    lookup={r[k+'_series_uid']:r['patient_id'] for r in rows for k in ('full','crop','mask')}
    ix=defaultdict(list)
    with index_file.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['role_candidate']=='full':ix[r['series_uid']].append(r)
    sets=defaultdict(list);missing=[]
    for r in inv:
        if not r['eligible_metadata']:continue
        got=ix.get(r['series_uid'],[])
        if len(got)!=1:missing.append(r['series_uid']);continue
        item=got[0];path=(root/item['path']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():raise ValueError('Ruta fuera del corpus o inexistente.')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Un archivo cambió después del indexado.')
        if item['subject']!=r['patient_id']:raise ValueError('El sujeto del índice no corresponde.')
        sets[r['partition']].append({**r,'path':str(path)})
    summary={'eligible_series':sum(r['eligible_metadata'] for r in inv),'missing_or_ambiguous_series':len(missing),'available':{k:len(v) for k,v in sets.items()},'legacy_model_used':False,'normal_class':False,'full_training_executed':False}
    return sets,lookup,summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[1]/'data/cbis');p.add_argument('--index',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('runs/cbis_binary'));p.add_argument('--epochs',type=int,default=10);p.add_argument('--seed',type=int,default=20260913);p.add_argument('--batch',type=int,default=4);p.add_argument('--execute',action='store_true');a=p.parse_args()
    sets,lookup,summary=prepare(a.data,a.index,a.root);a.out.mkdir(parents=True,exist_ok=True);(a.out/'preflight.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
    if not a.execute:return
    if not 1<=a.epochs<=500 or not 1<=a.batch<=32:raise ValueError('Límites de entrenamiento inválidos.')
    if summary['missing_or_ambiguous_series']:raise ValueError('Se bloquea entrenamiento con corpus incompleto; complete el inventario, sin seleccionar un subconjunto oportunista.')
    if any({r['binary_target'] for r in sets[k]}!={0,1} for k in ('train','validation','test')):raise ValueError('Se requieren ambas clases en cada partición.')
    import numpy as np,cv2,keras
    keras.utils.set_random_seed(a.seed)
    class Dataset(keras.utils.PyDataset):
        def __init__(self,items,**kwargs):super().__init__(**kwargs);self.items=items
        def __len__(self):return (len(self.items)+a.batch-1)//a.batch
        def __getitem__(self,idx):
            chunk=self.items[idx*a.batch:(idx+1)*a.batch];x=[];y=[]
            for r in chunk:
                im=read_cbis(Path(r['path']).read_bytes(),lookup,True);v=preview(im,224)
                h,w=v.shape;canvas=np.zeros((224,224),dtype='float32');canvas[:h,:w]=v/255.;x.append(np.repeat(canvas[...,None],3,axis=-1));y.append(r['binary_target'])
            return np.asarray(x,dtype='float32'),np.asarray(y,dtype='float32')
    # Intentionally no ImageNet download or legacy weights; architecture is a baseline, not validated.
    inputs=keras.Input((224,224,3));x=inputs
    for filters in (16,32,64):x=keras.layers.Conv2D(filters,3,padding='same',activation='relu')(x);x=keras.layers.MaxPooling2D()(x)
    x=keras.layers.GlobalAveragePooling2D()(x);x=keras.layers.Dropout(.3)(x);outputs=keras.layers.Dense(1,activation='sigmoid')(x)
    model=keras.Model(inputs,outputs);model.compile(optimizer=keras.optimizers.Adam(1e-4),loss='binary_crossentropy',metrics=[keras.metrics.AUC(name='auc')])
    model.fit(Dataset(sets['train']),validation_data=Dataset(sets['validation']),epochs=a.epochs,callbacks=[keras.callbacks.EarlyStopping(monitor='val_loss',patience=3,restore_best_weights=True)])
    model.save(a.out/'candidate_binary.keras')
    (a.out/'MODEL_STATUS.json').write_text(json.dumps({'status':'research_candidate_not_clinically_validated','training_completed':True,'test_evaluation_executed':False,'preprocess':'percentile1_99_preview224_top_left_pad_zero_RGB01','seed':a.seed,'epochs_max':a.epochs,'architecture':'three_block_CNN_random_initialization','guidance_connection':False},indent=2))
    print('Candidato de investigación guardado. Test NO usado por fit ni evaluado automáticamente.')
if __name__=='__main__':main()
