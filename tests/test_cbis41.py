from pathlib import Path
import csv,io,json,struct,importlib.util
import pytest,numpy as np
from mammoapp.config import ROOT
from mammoapp.cbis import *
from mammoapp.cbis_dicom import read_cbis,preview,SC
from mammoapp.documents import confirm_category,extract_birads
from mammotrace.phantom import encode_dicom
from mammotrace.errors import ResearchError

PUBLIC_SOURCE_DATA_AVAILABLE = all((ROOT/'data/cbis'/name).is_file() for name in FILENAMES)
pytestmark = pytest.mark.skipif(not PUBLIC_SOURCE_DATA_AVAILABLE, reason='CBIS-DDSM metadata are not redistributed in the public source tree; see data/cbis/README.md')

@pytest.fixture(scope='module')
def rows():return read_bundle(ROOT/'data/cbis')

@pytest.mark.parametrize('name,count',[(FILENAMES[0],1546),(FILENAMES[1],326),(FILENAMES[2],1318),(FILENAMES[3],378)])
def test_source_counts(name,count):assert len(read_cases((ROOT/'data/cbis'/name).read_bytes(),name))==count

def test_reference_targets(rows):
    assert all(r['binary_target']==0 for r in rows if r['pathology']=='BENIGN_WITHOUT_CALLBACK')
    assert {r['pathology'] for r in rows}==set(LABELS)

def test_total_subjects_and_units(rows):
    a=audit(rows);assert (a['annotation_rows'],a['subjects'],a['full_image_series'],a['lesion_keys'])==(3568,1566,3103,2050)

def test_overlap_exact(rows):
    a=audit(rows);assert len(a['overlap_subjects'])==31 and a['train_rows_removed_holdout_priority']==83

def test_default_rejects_overlap(rows):
    with pytest.raises(ResearchError):partition(rows)

def test_holdout_unchanged(rows):
    p=partition(rows,'holdout_priority');assert {r['record_id'] for r in p if r['partition']=='test'}=={r['record_id'] for r in rows if r['official_split']=='test'}

@pytest.mark.parametrize('a,b',[('train','validation'),('train','test'),('validation','test')])
def test_disjointness(rows,a,b):
    p=partition(rows,'holdout_priority');assert not {r['patient_id'] for r in p if r['partition']==a}&{r['patient_id'] for r in p if r['partition']==b}

def test_partition_order_invariant(rows):
    a=partition(rows,'holdout_priority');b=partition(rows[::-1],'holdout_priority')
    assert {r['record_id']:r['partition'] for r in a}=={r['record_id']:r['partition'] for r in b}

@pytest.mark.parametrize('value',[-.1,0,1,2])
def test_fraction_rejected(rows,value):
    with pytest.raises(ResearchError):partition(rows,'holdout_priority',value)

@pytest.mark.parametrize('path',['/abs/1/2/a.dcm','a/../1.2/a.dcm','https://bad/path','a/1.2/3.4/x.exe','a/1/2/a.dcm',''])
def test_unsafe_paths(path):
    with pytest.raises(ResearchError):series_from_path(path)

def test_path_whitespace():assert series_from_path('a/1.2/3.4/000001.dcm\n')=='3.4'

@pytest.mark.parametrize('bad',[b'',b'patient_id\nP_00001',b'\xff'])
def test_broken_csv(bad):
    with pytest.raises(ResearchError):read_cases(bad,FILENAMES[0])

def test_unknown_label():
    raw=(ROOT/'data/cbis'/FILENAMES[0]).read_bytes().replace(b'MALIGNANT',b'NORMAL',1)
    with pytest.raises(ResearchError):read_cases(raw,FILENAMES[0])

def test_duplicate_source(rows):
    with pytest.raises(ResearchError):audit(rows+rows[:1])

def test_mixed_labels_not_forced(rows):
    a=audit(rows);assert a['mixed_binary_image_groups']==17 and a['mixed_binary_lesion_groups']==3
    inv=image_inventory(partition(rows,'holdout_priority'))
    assert all(not r['eligible_metadata'] for r in inv if r['binary_target']=='' or r['discordant_lesion_key'])

def test_manifest_equals_references(rows):
    m=read_manifest((ROOT/'data/cbis/download_manifest.tcia').read_bytes());assert len(m)==6775
    assert m=={r[k+'_series_uid'] for r in rows for k in PATHS}

@pytest.mark.parametrize('bad',[b'',b'nothing',b'ListOfSeriesToDownload=\nnotuid',b'ListOfSeriesToDownload=\n1.2\n1.2'])
def test_bad_manifest(bad):
    with pytest.raises(ResearchError):read_manifest(bad)

def test_metadata_repair():
    dl,rep=read_download_metadata((ROOT/'data/cbis/metadata_drive_original.csv').read_bytes());assert len(dl)==544 and len(rep)==544
    assert dl[0]['File Size']=='14,06 MB' and 'CBIS-DDSM' in dl[0]['File Location']
    assert sum(int(r['Number of Images']) for r in dl)==837

def test_normalized_metadata_no_second_repair():
    dl,_=read_download_metadata((ROOT/'data/cbis/metadata_drive_original.csv').read_bytes())
    d2,r2=read_download_metadata(csv_bytes(dl));assert d2==dl and not r2

def test_metadata_ambiguous_rejected():
    raw=(ROOT/'data/cbis/metadata_drive_original.csv').read_bytes().replace(b'14,06 MB',b'14,broken,06 MB',1)
    with pytest.raises(ResearchError):read_download_metadata(raw)

@pytest.mark.parametrize('text,cat',[('Sin criterios para BI-RADS 4.','4'),('No hay hallazgos BI-RADS 5.','5'),('Se descarta la categoría BI-RADS 4A.','4A'),('Estudio anterior: BI-RADS 2. Actual: BI-RADS 5.','2')])
def test_parser_regression_blocked(text,cat):
    with pytest.raises(ResearchError):confirm_category(text,cat,True)

def test_current_after_prior_sentence():assert confirm_category('Estudio anterior: BI-RADS 2. Actual: BI-RADS 5.','5',True)=='5'

@pytest.fixture
def cbisraw():
    raw=encode_dicom(np.arange(64*64,dtype=np.uint16).reshape(64,64),tags={(0x20,0xe):('UI','1.2.3.4'),(0x10,0x20):('LO','P_00038_LEFT_CC.dcm')})
    # Rebuild explicit elements after replacing the SOP string with a different length.
    from mammotrace.dicom import Parser,LONG_VR
    p=Parser(raw);out=raw[:132];pos=132
    while pos<len(raw):
        tag,vr,n,s=p.header(pos,True);b=raw[s:s+n]
        if tag in ((2,2),(8,0x16)):
            b=SC.encode();b+=b'\0' if len(b)%2 else b''
        h=struct.pack('<HH',*tag)+vr.encode()+(b'\0\0'+struct.pack('<I',len(b)) if vr in LONG_VR else struct.pack('<H',len(b)))
        out+=h+b;pos=s+n
    return out

def test_research_decoder(cbisraw):
    i=read_cbis(cbisraw,{'1.2.3.4':'P_00038'},True);assert i.pixels.shape==(64,64) and not i.technical['clinical_inference_enabled'];assert preview(i).dtype==np.uint8

@pytest.mark.parametrize('auth,lookup',[(False,{'1.2.3.4':'P_00038'}),(True,{}),(True,{'1.2.3.4':'P_99999'})])
def test_research_gates(cbisraw,auth,lookup):
    with pytest.raises(ResearchError):read_cbis(cbisraw,lookup,auth)

@pytest.mark.parametrize('cut',[0,128,180,300,-1])
def test_research_truncation(cbisraw,cut):
    with pytest.raises(ResearchError):read_cbis(cbisraw[:cut],{'1.2.3.4':'P_00038'},True)

def test_candidate_preflight_partial():
    spec=importlib.util.spec_from_file_location('train_cbis',ROOT/'training/train_cbis_binary.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    # Missing index/root are explicitly rejected; no fallback model or target is constructed.
    with pytest.raises((OSError,ValueError)):mod.prepare(ROOT/'data/cbis',ROOT/'does_not_exist.csv',ROOT)
