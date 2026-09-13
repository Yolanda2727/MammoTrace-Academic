import csv,io,json
import numpy as np
import pytest
from mammotrace.config import CLASSES
from mammotrace.datasets import read_csv,safe_relative,validate_dataset,grouped_split
from mammotrace.evaluation import evaluate_csv
from mammotrace.errors import ResearchError

def csv_bytes(rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);return s.getvalue().encode()
def rows_dataset(n=5):return [{'dicom_path':f'{c}_{i}.dcm','label':c,'patient_id':f'{c}_{i}','label_source':'reference_documented','label_verified':'true'} for c in CLASSES for i in range(n)]
@pytest.mark.parametrize('path',['/etc/passwd','../x.dcm','a/../b.dcm','C:/a.dcm','x\\y.dcm','a//x.dcm','./x.dcm','=formula.dcm','-x.dcm','test.png',''])
def test_unsafe_paths(path):assert not safe_relative(path)
@pytest.mark.parametrize('path',['case1/image.dcm','case_2/i.DICOM','x.dcm'])
def test_valid_paths(path):assert safe_relative(path)
@pytest.mark.parametrize('content',[b'',b'a,a\n1,2\n',b'a,b\n1\n',b'a\n1,2\n',b'\xff\xfe',b'a\n\0'])
def test_malformed_csv(content):
    with pytest.raises(ResearchError):read_csv(content)
def test_csv_row_cap():
    with pytest.raises(ResearchError) as e:read_csv(b'a\n1\n2\n',1)
    assert e.value.code=='CSV_ROWS'
def test_missing_columns():
    with pytest.raises(ResearchError):validate_dataset(b'a\nb\n')
def test_valid_csv_without_files_never_training_ready():
    d=validate_dataset(csv_bytes(rows_dataset()));assert d['valid_structure'];assert d['split_feasible'];assert not d['ready_for_training'];assert not d['files_checked']
@pytest.mark.parametrize('key,value,code',[('label','cancer','LABEL_NOT_ALLOWED'),('patient_id','Full Name','PATIENT_CODE_FORMAT'),('label_verified','false','LABEL_NOT_VERIFIED'),('label_source','random','LABEL_SOURCE_REQUIRED'),('dicom_path','../x.dcm','UNSAFE_PATH')])
def test_dataset_controls(key,value,code):
    rows=rows_dataset();rows[0][key]=value;d=validate_dataset(csv_bytes(rows));assert code in [e['code'] for e in d['errors']]
def test_duplicate_paths():
    rows=rows_dataset();rows[1]['dicom_path']=rows[0]['dicom_path'];assert not validate_dataset(csv_bytes(rows))['valid_structure']
def test_conflicting_patients():
    rows=rows_dataset();rows[-1]['patient_id']=rows[0]['patient_id'];d=validate_dataset(csv_bytes(rows));assert d['conflicting_patients']==1
    with pytest.raises(ResearchError):grouped_split(rows)
def test_files_missing(tmp_path):assert validate_dataset(csv_bytes(rows_dataset()),tmp_path)['error_count']==15
def test_duplicate_binary(tmp_path):
    rows=rows_dataset()
    for row in rows:(tmp_path/row['dicom_path']).write_bytes(b'duplicate')
    d=validate_dataset(csv_bytes(rows),tmp_path);assert 'DUPLICATE_CONTENT' in [e['code'] for e in d['errors']]
def test_symlink_escape(tmp_path):
    outside=tmp_path.parent/'outside-dicom.bin';outside.write_bytes(b'x');rows=rows_dataset();(tmp_path/rows[0]['dicom_path']).symlink_to(outside)
    assert 'PATH_ESCAPE' in [e['code'] for e in validate_dataset(csv_bytes(rows),tmp_path)['errors']]
def test_group_split_reproducible_and_disjoint():
    rows=rows_dataset(10);rows+=[dict(r,dicom_path='extra/'+r['dicom_path']) for r in rows]
    a=grouped_split(rows,42);b=grouped_split(rows,42);assert a==b
    sets=[{r['patient_id'] for r in value} for value in a.values()];assert all(not sets[i]&sets[j] for i in range(3) for j in range(i));assert sum(map(len,a.values()))==len(rows)
def test_group_split_too_small():
    with pytest.raises(ResearchError):grouped_split(rows_dataset(4))
def rows_eval():
    out=[]
    for k in range(12):
        i=k%3;p=[.05,.05,.05];p[i]=.9
        out.append({'image_id':f'I{k}','patient_id':f'P{k}','label':CLASSES[i],'p_normal':p[0],'p_benigno':p[1],'p_maligno':p[2]})
    return out
def test_perfect_metrics_and_cluster_bootstrap():
    d=evaluate_csv(csv_bytes(rows_eval()),100);assert d['accuracy']==1;assert d['macro_f1']==1;assert d['confusion_matrix']==[[4,0,0],[0,4,0],[0,0,4]];assert d['per_class']['maligno']['auc_ovr']==1;assert d['intervals']['accuracy']['lower']==1;json.dumps(d,allow_nan=False)
@pytest.mark.parametrize('value',['nan','inf','-0.1','2','nonnumeric'])
def test_invalid_scores(value):
    rows=rows_eval();rows[0]['p_normal']=value
    with pytest.raises(ResearchError):evaluate_csv(csv_bytes(rows))
def test_sum_invalid():
    rows=rows_eval();rows[0]['p_normal']=.8
    with pytest.raises(ResearchError):evaluate_csv(csv_bytes(rows))
def test_duplicate_image_id():
    rows=rows_eval();rows[1]['image_id']=rows[0]['image_id']
    with pytest.raises(ResearchError):evaluate_csv(csv_bytes(rows))
def test_patient_bootstrap_is_deterministic():
    raw=csv_bytes(rows_eval());assert evaluate_csv(raw,40,2)['intervals']==evaluate_csv(raw,40,2)['intervals']
def test_missing_class_none_not_nan():
    d=evaluate_csv(csv_bytes([r for r in rows_eval() if r['label']=='normal']),100);assert d['per_class']['maligno']['sensitivity'] is None;assert d['per_class']['maligno']['auc_ovr'] is None;assert not d['intervals'];json.dumps(d,allow_nan=False)
def test_known_nonperfect_matrix():
    rows=rows_eval();rows[0].update(p_normal=.1,p_benigno=.1,p_maligno=.8);rows[2].update(p_normal=.8,p_benigno=.1,p_maligno=.1)
    d=evaluate_csv(csv_bytes(rows),0);assert d['confusion_matrix']==[[3,0,1],[0,4,0],[1,0,3]];assert d['per_class']['maligno']['sensitivity']==.75;assert d['accuracy']==10/12
