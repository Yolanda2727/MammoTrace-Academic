"""Control de contexto probado sin depender del motor visual.

El adaptador de UI entrega st.session_state, pero estas funciones solo necesitan
un mapping. No almacenan datos en variables globales ni en caché entre personas.
"""
from __future__ import annotations
from collections.abc import MutableMapping
from typing import Any
import hashlib
from .guidance import ANSWERS,SYMPTOMS
from .documents import confirm_category
from .examples import scenario,image_bytes
from .images import load_image

Session=MutableMapping[str,Any]

def defaults(state:Session) -> None:
    values={'case_epoch':0,'report_revision':0,'clinical_epoch':0,'images':[],
            'report_text':'','report_warnings':[],'confirmation':None,
            'synthetic':False,'scenario_code':None,'xai':None,'xai_image':None,
            'answers':{k:ANSWERS[0] for k in SYMPTOMS},'appointment':None,
            'clinician_due':None,'report_source':'Ninguno'}
    for key,value in values.items():
        if key not in state:state[key]=value


def reset_case(state:Session) -> None:
    epoch=state.get('case_epoch',0)+1
    # Los tres elementos preservados son navegación; nunca datos del caso.
    for key in list(state.keys()):
        if key not in {'page','audience','example_choice'}:del state[key]
    state['case_epoch']=epoch
    defaults(state)


def clear_clinical_inputs(state:Session) -> None:
    state['answers']={k:ANSWERS[0] for k in SYMPTOMS}
    state['appointment']=None;state['clinician_due']=None
    state['clinical_epoch']+=1;state['confirmation']=None


def load_example(state:Session,code:str) -> None:
    # Validar el código antes de tocar un contexto existente.
    case=scenario(code)
    image=load_image(image_bytes(code,'DICOM'),'phantom.dcm')
    reset_case(state)
    state['images']=[image];state['report_text']=case['report'];state['synthetic']=True
    state['scenario_code']=code;state['answers']=case['symptoms']
    state['report_source']='Informe ficticio integrado'


def set_report(state:Session,text:str,notes:list|tuple,source:str) -> None:
    clear_clinical_inputs(state)
    state['report_text']=text;state['report_warnings']=list(notes)
    state['report_source']=source;state['report_revision']+=1
    state['synthetic']=False;state['scenario_code']=None


def set_manual_text(state:Session,text:str) -> None:
    if text!=state['report_text']:
        state['report_text']=text;state['synthetic']=False;state['scenario_code']=None
        state['report_source']='Texto revisado manualmente'
        clear_clinical_inputs(state)


def current_category(state:Session) -> str|None:
    confirmation=state['confirmation'];text=state['report_text']
    if confirmation and confirmation['hash']==hashlib.sha256(text.encode()).hexdigest():
        return confirm_category(text,confirmation['category'],True)
    return None
