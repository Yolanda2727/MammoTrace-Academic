from datetime import date,datetime
import inspect,itertools
import pytest
from mammoapp.guidance import guide,ANSWERS,SYMPTOMS
from mammoapp.documents import CATS
from mammoapp.examples import CASES,scenario
from mammoapp.knowledge import SOURCES

@pytest.mark.parametrize('code',list(CASES))
def test_eight_scenarios(code):
    c=scenario(code);r=guide(c['symptoms'],c['category'])
    assert r.level==c['expected_min_level']
    assert 'no' in ' '.join(r.limits).lower()
    assert all(s in SOURCES for e in r.evidence for s in e['sources'])

@pytest.mark.parametrize('category',CATS+(None,))
def test_emergency_overrides_every_report(category):
    r=guide({'emergency':'Sí'},category)
    assert r.level==4 and 'ahora' in r.title

@pytest.mark.parametrize('category',CATS+(None,))
def test_yes_monotonicity(category):
    # Todos los subconjuntos de señales; agregar una afirmativa nunca reduce el nivel.
    keys=list(SYMPTOMS)
    for flags in itertools.product((False,True),repeat=len(keys)):
        s={k:('Sí' if flag else 'No') for k,flag in zip(keys,flags)}
        baseline=guide(s,category).level
        for key,flag in zip(keys,flags):
            if not flag:assert guide({**s,key:'Sí'},category).level>=baseline

def test_unknown_not_no():
    r=guide({},'2');assert len(r.unknown)==7 and 'incompleta' in r.title
    assert not guide({k:'No' for k in SYMPTOMS},'2').unknown

def test_bad_input():
    with pytest.raises(ValueError):guide({'new_lump':True})
    with pytest.raises(ValueError):guide({'unknown':'Sí'})
    with pytest.raises(ValueError):guide({},'7')
    with pytest.raises(ValueError):guide({},None,datetime.now())

def test_no_model_argument_or_import():
    assert set(inspect.signature(guide).parameters)=={'symptoms','confirmed_birads','appointment','clinician_due','today'}
    import mammoapp.guidance as g
    assert 'mammotrace.model' not in inspect.getsource(g)

def test_admin_due_never_delays_urgent():
    r=guide({'emergency':'Sí'},'2',date(2026,11,1),date(2026,9,1),date(2026,9,13))
    assert r.level==4 and {'G01','G10','G11'}.issubset({e['rule'] for e in r.evidence})

def test_due_date_and_appointment():
    r=guide({k:'No' for k in SYMPTOMS},'2',date(2026,10,1),date(2026,9,1),date(2026,9,13))
    assert r.level==1 and 'no estima riesgo' in next(e for e in r.evidence if e['rule']=='G10')['meaning']

def test_past_appointment_not_assumed_booked():
    r=guide({},None,date(2026,1,1),today=date(2026,9,13))
    assert any('reprogramación' in s for s in r.next_steps)
    assert any('No ha sido verificada' in s for s in r.next_steps)
