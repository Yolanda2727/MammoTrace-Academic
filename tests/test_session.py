from datetime import date
import hashlib
import pytest
from mammoapp import session
from mammoapp.guidance import ANSWERS,SYMPTOMS

def confirmed(state,category):
    state['confirmation']={'category':category,'hash':hashlib.sha256(state['report_text'].encode()).hexdigest()}

def test_default_cases_are_independent():
    a={};b={};session.defaults(a);session.defaults(b)
    a['answers']['new_lump']='Sí';a['images'].append('private')
    assert b['answers']['new_lump']==ANSWERS[0] and b['images']==[]

def test_clear_removes_uploads_symptoms_model_results():
    s={'page':'2','audience':'a','example_choice':'ED01'};session.defaults(s)
    s.update(report_text='PRIVATE',xai={'score':.9},images=['PRIVATE'],report_text_widget='PRIVATE',upload_widget='PRIVATE')
    old=s['case_epoch'];session.reset_case(s)
    assert s['case_epoch']==old+1 and s['page']=='2'
    assert s['images']==[] and s['report_text']=='' and s['xai'] is None
    assert 'upload_widget' not in s and 'PRIVATE' not in str(s)

@pytest.mark.parametrize('code',['ED01','ED02','ED03','ED04','ED05','ED06','ED07','ED08'])
def test_examples_load_without_auto_confirmation(code):
    s={};session.defaults(s);session.load_example(s,code)
    assert s['synthetic'] and len(s['images'])==1 and session.current_category(s) is None

def test_replacing_example_with_report_discards_fictitious_negatives():
    s={};session.defaults(s);session.load_example(s,'ED03');confirmed(s,'4A')
    s['appointment']=date(2026,10,3);old=s['clinical_epoch']
    session.set_report(s,'Conclusión: BI-RADS 2.',[],'TXT')
    assert session.current_category(s) is None
    assert set(s['answers'].values())=={ANSWERS[0]} and s['appointment'] is None
    assert not s['synthetic'] and s['clinical_epoch']==old+1

def test_editing_changes_context_not_just_text():
    s={};session.defaults(s);session.load_example(s,'ED04');confirmed(s,'2')
    assert session.current_category(s)=='2'
    session.set_manual_text(s,'Nuevo informe: BI-RADS 0.')
    assert session.current_category(s) is None and not s['synthetic']
    assert s['answers']['new_lump']==ANSWERS[0]

def test_same_text_does_not_reset_valid_context():
    s={};session.defaults(s);session.load_example(s,'ED04');confirmed(s,'2')
    old=s['clinical_epoch'];session.set_manual_text(s,s['report_text'])
    assert session.current_category(s)=='2' and s['clinical_epoch']==old
    assert s['answers']['new_lump']=='Sí'

def test_hash_binds_confirmation_to_text():
    s={};session.defaults(s);session.load_example(s,'ED03');confirmed(s,'4A')
    s['report_text']='Other text BI-RADS 4A.'
    assert session.current_category(s) is None

def test_unknown_example_does_not_destroy_existing_state():
    s={};session.defaults(s);s['report_text']='keep'
    with pytest.raises(KeyError):session.load_example(s,'DOES_NOT_EXIST')
    assert s['report_text']=='keep'
