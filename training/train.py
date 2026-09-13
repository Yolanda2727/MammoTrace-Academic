"""Entrenador ejecutable con etiquetas documentadas; nunca genera etiquetas clínicas.

Uso: python -m training.train --labels data/labels.csv --data-root data --output training_runs/run_001
Se debe usar una carpeta de salida nueva. La API no lanza este proceso.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from mammotrace.config import CLASSES
from mammotrace.datasets import validate_dataset,read_csv,grouped_split
from mammotrace.dicom import read_dicom,transform
from mammotrace.errors import ResearchError


def build_model(weights=None):
    import keras
    from mammotrace.keras_layers import ResNetPreprocess
    inputs=keras.Input(shape=(224,224,3),name='mammogram')
    x=keras.layers.RandomFlip('horizontal',name='training_flip')(inputs)
    x=keras.layers.RandomRotation(.03,fill_mode='constant',fill_value=0,name='training_rotation')(x)
    x=ResNetPreprocess(name='resnet_preprocessing')(x)
    base=keras.applications.ResNet50(include_top=False,weights=weights,input_shape=(224,224,3),name='resnet50_backbone')
    base.trainable=False
    x=base(x,training=False)  # BatchNorm stays in inference mode, also during fine-tuning.
    x=keras.layers.GlobalAveragePooling2D()(x)
    x=keras.layers.Dense(128,activation='relu')(x)
    x=keras.layers.Dropout(.3)(x)
    out=keras.layers.Dense(3,activation='softmax',name='class_scores')(x)
    return keras.Model(inputs,out,name='mamografia_research_v3')


def unfreeze_backbone(model,last_n=30):
    import keras
    if not isinstance(last_n,int) or last_n<0:raise ValueError('last_n debe ser un entero >= 0')
    base=model.get_layer('resnet50_backbone');base.trainable=True
    for layer in base.layers:layer.trainable=False
    # [-0:] significaría TODAS las capas; aquí cero se trata explícitamente.
    if last_n:
        for layer in base.layers[-last_n:]:
            if not isinstance(layer,keras.layers.BatchNormalization):layer.trainable=True
    count=sum(bool(layer.trainable_weights) for layer in base.layers)
    return count


def class_weights(rows):
    counts=np.array([sum(row['label']==label for row in rows) for label in CLASSES])
    if (counts==0).any():raise ResearchError('TRAINING_CLASS','Falta alguna clase en entrenamiento.')
    return {i:float(counts.sum()/(3*n)) for i,n in enumerate(counts)}


def make_dataset(rows,root,batch_size,shuffle,seed):
    import keras
    class DicomDataset(keras.utils.PyDataset):
        def __init__(self):
            super().__init__(workers=1,use_multiprocessing=False,max_queue_size=1)
            self.indices=np.arange(len(rows));self.rng=np.random.default_rng(seed)
            if shuffle:self.rng.shuffle(self.indices)
        def __len__(self):return int(np.ceil(len(rows)/batch_size))
        def __getitem__(self,index):
            ix=self.indices[index*batch_size:(index+1)*batch_size]
            x=[];y=[]
            for k in ix:
                r=rows[k];path=(root/r['dicom_path']).resolve()
                if not path.is_relative_to(root.resolve()):raise ResearchError('PATH_ESCAPE','Ruta fuera de la raíz.')
                if path.stat().st_size>64*1024**2:raise ResearchError('FILE_SIZE','DICOM de entrenamiento demasiado grande.')
                x.append(transform(read_dicom(path.read_bytes()),'standardized_v3'));y.append(CLASSES.index(r['label']))
            return np.stack(x),np.array(y,dtype=np.int32)
        def on_epoch_end(self):
            if shuffle:self.rng.shuffle(self.indices)
    return DicomDataset()


def write_rows(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--labels',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--batch-size',type=int,default=4)
    p.add_argument('--epochs-head',type=int,default=8);p.add_argument('--epochs-finetune',type=int,default=12)
    p.add_argument('--unfreeze-layers',type=int,default=30);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--weights',choices=['none','imagenet'],default='none',help='imagenet descarga pesos externos de Keras explícitamente.')
    p.add_argument('--backend',choices=['torch','tensorflow'],default='torch')
    p.add_argument('--authorized-data',action='store_true',help='Declara autorización y revisión de desidentificación del conjunto.')
    a=p.parse_args(argv)
    if not a.authorized_data:p.error('Se requiere --authorized-data después de revisar autorización y privacidad.')
    if min(a.batch_size,a.epochs_head,a.epochs_finetune)<1 or a.batch_size>32 or a.unfreeze_layers<1:
        p.error('Épocas y capas >= 1; batch-size entre 1 y 32.')
    if a.output.exists():p.error('La carpeta de salida ya existe. Use una nueva; nunca se sobrescribe una corrida.')
    if not a.labels.is_file() or a.labels.stat().st_size>4*1024**2:p.error('CSV inexistente o mayor de 4 MB.')
    raw=a.labels.read_bytes();check=validate_dataset(raw,a.data_root)
    if not check['ready_for_training']:
        print(json.dumps(check,indent=2,ensure_ascii=False));return 2
    _,rows=read_csv(raw);splits=grouped_split(rows,a.seed)
    os.environ['KERAS_BACKEND']=a.backend
    if a.backend=='torch':
        import torch
        torch.set_num_threads(2)
    import keras
    from mammotrace.keras_layers import ResNetPreprocess
    keras.utils.set_random_seed(a.seed)
    a.output.mkdir(parents=True)
    metadata={'started_at':datetime.now(timezone.utc).isoformat(),'seed':a.seed,'backend':a.backend,'keras':keras.__version__,
       'weights_initialization':a.weights,'pipeline':'standardized_v3','classes':list(CLASSES),'clinical_validation':False,
       'labels_csv_sha256':hashlib.sha256(raw).hexdigest(),'validation':check,'args':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()}}
    (a.output/'run_config.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),'utf-8')
    for name,subset in splits.items():write_rows(a.output/f'{name}_split.csv',subset)
    train=make_dataset(splits['train'],a.data_root,a.batch_size,True,a.seed)
    valid=make_dataset(splits['validation'],a.data_root,a.batch_size,False,a.seed)
    test=make_dataset(splits['test'],a.data_root,a.batch_size,False,a.seed)
    model=build_model(None if a.weights=='none' else 'imagenet')
    def callbacks(phase):
        return [keras.callbacks.EarlyStopping(monitor='val_loss',patience=4,restore_best_weights=True),
          keras.callbacks.ReduceLROnPlateau(monitor='val_loss',factor=.5,patience=2,min_lr=1e-7),
          keras.callbacks.CSVLogger(str(a.output/f'{phase}_training_log.csv'))]
    model.compile(optimizer=keras.optimizers.Adam(1e-3),loss='sparse_categorical_crossentropy',metrics=['accuracy'])
    head=model.fit(train,validation_data=valid,epochs=a.epochs_head,class_weight=class_weights(splits['train']),callbacks=callbacks('head'))
    head_path=a.output/'head_best.keras';model.save(head_path)
    trainable_count=unfreeze_backbone(model,a.unfreeze_layers)
    if trainable_count<=0:raise ResearchError('FINETUNE','No hay capas con pesos entrenables en el backbone.')
    model.compile(optimizer=keras.optimizers.Adam(1e-5),loss='sparse_categorical_crossentropy',metrics=['accuracy'])
    fine=model.fit(train,validation_data=valid,epochs=a.epochs_finetune,class_weight=class_weights(splits['train']),callbacks=callbacks('finetune'))
    selected='finetune'
    if min(head.history['val_loss'])<min(fine.history['val_loss']):
        model=keras.models.load_model(head_path,safe_mode=True);selected='head'
    model_path=a.output/'modelo_mamografia_v3.keras';model.save(model_path)
    # Test se utiliza solo después de seleccionar el modelo por validación.
    scores=[]
    for k in range(len(test)):
        x,y=test[k];scores.extend(np.asarray(keras.ops.convert_to_numpy(model(x,training=False))).tolist())
    predictions=[{'image_id':f'TEST_{k:06d}','patient_id':row['patient_id'],'label':row['label'],
       **{'p_'+c:float(v) for c,v in zip(CLASSES,score)}} for k,(row,score) in enumerate(zip(splits['test'],scores))]
    write_rows(a.output/'test_predictions.csv',predictions)
    from mammotrace.evaluation import evaluate_csv
    metrics=evaluate_csv((a.output/'test_predictions.csv').read_bytes())
    metrics.update({'selected_phase':selected,'trainable_backbone_layers_finetune':trainable_count,'research_evaluation_only':True})
    (a.output/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False,allow_nan=False),'utf-8')
    np.savetxt(a.output/'confusion_matrix.csv',metrics['confusion_matrix'],fmt='%d',delimiter=',',header=','.join(CLASSES),comments='')
    manifest={'schema_version':1,'model_id':'mamografia-research-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
      'model_file':model_path.name,'sha256':hashlib.file_digest(model_path.open('rb'),'sha256').hexdigest(),
      'classes':list(CLASSES),'input_shape':[224,224,3],'pipeline':'standardized_v3','input_mode':'embedded_0_255',
      'status':'research_retrained','clinical_use':False,'label_provenance':'reference_declared_by_operator',
      'limitations':['Datos y referencia requieren revisión independiente.','No constituye validación clínica ni autorización de despliegue.']}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),'utf-8')
    print('Corrida terminada. Revise splits, errores, métricas y procedencia antes de reemplazar cualquier modelo.');return 0
if __name__=='__main__':
    try:sys.exit(main())
    except ResearchError as e:print(f'{e.code}: {e.message}');sys.exit(2)
