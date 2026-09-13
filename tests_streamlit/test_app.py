"""Pruebas NATIVAS AppTest para ejecutar tras instalar Streamlit.
No se sustituyen por mocks. Se reportan separadas de las pruebas del núcleo.
"""
from pathlib import Path
import pytest
pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]

def app():return AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=40).run()

def click(at,label):
    next(b for b in at.button if b.label==label).click().run();assert not at.exception

def test_start_real_streamlit():
    at=app();assert not at.exception
    assert at.session_state['report_text']==''

@pytest.mark.parametrize('code',['ED01','ED02','ED03','ED04','ED05','ED06','ED07','ED08'])
def test_integrated_scenarios_streamlit(code):
    at=app();at.selectbox(key='example_choice').set_value(code).run();click(at,'Cargar ejemplo completo')
    assert at.session_state['scenario_code']==code and at.session_state['confirmation'] is None
    at.radio(key='page').set_value('2 · Orientación de espera').run();assert not at.exception
    assert len(at.get('download_button'))>=2

def test_human_confirmation_and_reset():
    at=app();at.selectbox(key='example_choice').set_value('ED03').run();click(at,'Cargar ejemplo completo')
    select=next(x for x in at.selectbox if x.label.startswith('Categoría de la conclusión'))
    select.set_value('4A').run()
    next(x for x in at.checkbox if x.label.startswith('Contrasté')).check().run()
    click(at,'Confirmar lectura para la orientación')
    assert at.session_state['confirmation']['category']=='4A'
    at.radio(key='page').set_value('2 · Orientación de espera').run();assert not at.exception
    click(at,'Nuevo caso / limpiar sesión')
    assert at.session_state['confirmation'] is None and at.session_state['images']==[]

def test_patient_perspective_hides_classifier():
    at=app();at.radio(key='audience').set_value('Comprender y preparar la consulta').run()
    assert not at.exception
    assert '3 · Laboratorio explicable' not in at.radio(key='page').options
