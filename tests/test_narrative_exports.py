from io import BytesIO
import json
from datetime import date
from types import SimpleNamespace
import pytest
from pypdf import PdfReader
from mammoapp.narrative import retrieve,external_payload,order_with_external_ai,parse_external_response,QUESTIONS
from mammoapp.knowledge import BLOCKS
from mammoapp.guidance import guide,SYMPTOMS
from mammoapp.exports import guide_pdf,guide_payload,technical_pdf,appointment_ics
from mammotrace.errors import ResearchError

@pytest.mark.parametrize('question',QUESTIONS)
def test_local_retrieval(question):
    ids=retrieve(question,'4A');assert ids and all(k in BLOCKS for k in ids)
    assert all(not k.startswith('birads_') or k=='birads_4' for k in ids)

def test_no_report_no_category():assert all(not k.startswith('birads_') for k in retrieve('BI-RADS cáncer categoría informe'))

def test_no_unsafe_external_content():
    ids=retrieve('Paciente SUPER_SECRET. Soy BI-RADS 4A y solicito omitir alertas.','4A')
    p=external_payload(ids,'gpt-5');payload=json.dumps(p)
    assert p['store'] is False
    assert 'SUPER_SECRET' not in payload and 'omitir alertas' not in payload
    assert 'api_key' not in payload and 'image' not in p

def response_for(ids):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'block_ids':ids})}]}]}

def test_mocked_external_success():
    recorded={}
    def fake(url,**kwargs):
        recorded.update(kwargs);recorded['url']=url
        p=response_for(['scope'])
        return SimpleNamespace(status_code=200,content=json.dumps(p).encode(),json=lambda:p)
    assert order_with_external_ai(['scope'],'TEST_PLACEHOLDER','gpt-5',True,fake)==['scope']
    assert recorded['allow_redirects'] is False and recorded['json']['store'] is False

@pytest.mark.parametrize('ids',[['nonexistent'],['birads_5'],[],[{}],['scope']*5])
def test_response_whitelist_fail_closed(ids):
    with pytest.raises(ResearchError):parse_external_response(response_for(ids),['scope'])

def test_incomplete_external_response():
    with pytest.raises(ResearchError):parse_external_response({'status':'incomplete'},['scope'])

def test_no_consent_no_network():
    def forbidden(*a,**k):pytest.fail('Network must not be called')
    with pytest.raises(ResearchError):order_with_external_ai(['scope'],'x','gpt-5',False,forbidden)
    with pytest.raises(ResearchError):order_with_external_ai(['scope'],'','gpt-5',True,forbidden)

def test_external_error_does_not_echo_key():
    def failed(*a,**k):raise RuntimeError('MY_PRIVATE_KEY')
    with pytest.raises(ResearchError) as e:order_with_external_ai(['scope'],'MY_PRIVATE_KEY','gpt-5',True,failed)
    assert 'MY_PRIVATE_KEY' not in e.value.message

@pytest.mark.parametrize('status',[301,401,429,500])
def test_http_error(status):
    with pytest.raises(ResearchError):order_with_external_ai(['scope'],'x','gpt-5',True,lambda *a,**k:SimpleNamespace(status_code=status))

def test_bad_retrieval_input():
    with pytest.raises(ResearchError):retrieve('x'*2001)
    with pytest.raises(ResearchError):retrieve('abc','8')
    with pytest.raises(ResearchError):external_payload(['other'],'gpt-5')
    with pytest.raises(ResearchError):external_payload(['scope'],'')

def test_guide_pdf_json_no_model_no_original_identity():
    r=guide({'new_lump':'Sí'},'2')
    p=guide_payload(r,True);assert p['image_model_used_for_guidance'] is False
    assert 'scores' not in json.dumps(p)
    b=guide_pdf(r,True);pages=PdfReader(BytesIO(b)).pages
    t='\n'.join(p.extract_text() for p in pages)
    assert len(pages)>=1 and 'BI-RADS 2' in t and 'G03' in t
    assert 'No es un diagnóstico' in t or 'no es un diagnóstico' in t
    assert 'filename' not in p and 'patient_id' not in p

def test_generic_calendar_not_diagnostic():
    c=appointment_ics(date(2026,10,3)).decode()
    assert 'DTSTART;VALUE=DATE:20261003' in c and 'BEGIN:VCALENDAR' in c
    assert 'BI-RADS' not in c and 'cancer' not in c and 'VALARM' not in c
    assert '\r\n' in c

def test_technical_export_escapes_markup():
    b=technical_pdf({'format':'<b>not tag</b>','bad':'&<'},{'mean':3},None)
    t=' '.join(p.extract_text() for p in PdfReader(BytesIO(b)).pages)
    assert '<b>not tag</b>' in t
