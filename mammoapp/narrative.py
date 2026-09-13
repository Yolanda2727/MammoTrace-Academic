"""Asistente explicable: recuperación local y selección opcional con IA externa.

El servicio externo SOLO recibe IDs temáticos y fragmentos educativos públicos.
Nunca recibe imágenes, texto del informe, síntomas, nombres, fechas o la pregunta
libre del usuario. Su respuesta se restringe a IDs; no se muestra texto inventado.
"""
from __future__ import annotations
import json, re, unicodedata
from .knowledge import BLOCKS
from mammotrace.errors import ResearchError

QUESTIONS=("¿Qué significa la categoría de mi informe?", "¿Una sospecha significa cáncer confirmado?",
           "¿Qué debo preguntar sobre una biopsia?", "¿Qué cambios debo comunicar antes de la cita?",
           "¿Qué significa densidad mamaria?", "¿Qué muestra y qué no muestra el mapa explicable?")

def tokens(text: str) -> set[str]:
    text=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
    return set(re.findall(r'[a-z0-9]{3,}',text[:2000]))


def retrieve(question: str, category: str | None=None) -> list[str]:
    if not isinstance(question,str) or len(question)>2000:
        raise ResearchError('QUESTION_SIZE','Use una pregunta de hasta 2.000 caracteres sin datos personales.')
    from .documents import CATS
    if category is not None and category not in CATS:
        raise ResearchError('TOPIC_CATEGORY','Categoría confirmada no válida.')
    q=tokens(question)
    ranked=sorted(((len(q.intersection(tokens(' '.join(b['tags'])+' '+b['title']))),k) for k,b in BLOCKS.items()),reverse=True)
    selected=[k for score,k in ranked if score>0][:3]
    if category and ('categoria' in q or 'informe' in q or 'birads' in q or not selected):
        selected=['birads_'+category[0]]+selected
    # No rescatar otra categoría no confirmada por una coincidencia léxica.
    allowed_category='birads_'+category[0] if category else None
    selected=[k for k in selected if not k.startswith('birads_') or k==allowed_category]
    selected=list(dict.fromkeys(selected))[:4]
    return selected or ['scope','planning']


def external_payload(selected: list[str], model: str) -> dict:
    if not selected or any(k not in BLOCKS for k in selected) or len(selected)>6:
        raise ResearchError('TOPIC_IDS','Selección temática no válida.')
    if not model or len(model)>120:
        raise ResearchError('API_MODEL','El administrador debe configurar OPENAI_MODEL.')
    # No texto libre del caso: solo fragmentos previamente escritos y auditables.
    return {'model':model,'store':False,'max_output_tokens':1000,
            'instructions':('Ordena los fragmentos educativos suministrados para facilitar la comprensión. '
                            'Devuelve únicamente un JSON {"block_ids":[...]} con 1 a 4 IDs de la lista. '
                            'No escribas recomendaciones nuevas, diagnósticos, tratamientos ni texto adicional.'),
            'input':json.dumps([{'id':k,'title':BLOCKS[k]['title'],'text':BLOCKS[k]['text']} for k in selected],ensure_ascii=False),
            'text':{'format':{'type':'json_object'}}}


def parse_external_response(payload: dict, selected: list[str]) -> list[str]:
    if payload.get('status')!='completed':
        raise ResearchError('API_INCOMPLETE','La IA externa no completó la respuesta; se conserva la explicación local.')
    try:
        raw=''.join(c['text'] for item in payload.get('output',[]) if item.get('type')=='message'
                    for c in item.get('content',[]) if c.get('type')=='output_text')
        if len(raw)>2000: raise ValueError()
        ids=json.loads(raw)['block_ids']
        if not isinstance(ids,list) or not 1<=len(ids)<=4 or any(not isinstance(k,str) or k not in selected for k in ids):
            raise ValueError()
        return list(dict.fromkeys(ids))
    except Exception:
        raise ResearchError('API_UNSAFE','La respuesta externa no respeta los fragmentos permitidos; no se muestra.') from None


def order_with_external_ai(selected: list[str], key: str, model: str, consent: bool, transport=None) -> list[str]:
    if consent is not True:
        raise ResearchError('API_CONSENT','Falta autorización explícita para esta llamada externa.')
    if not key:
        raise ResearchError('API_KEY','No hay una clave de API configurada en el servidor.')
    import requests
    transport=transport or requests.post
    try:
        response=transport('https://api.openai.com/v1/responses',
                           headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                           json=external_payload(selected,model),timeout=(5,25),allow_redirects=False)
        if response.status_code!=200:
            raise ResearchError('API_REQUEST','La API rechazó la solicitud. Revise permisos, modelo o saldo; no se muestran credenciales ni detalles del servidor.')
        if len(response.content)>200_000:
            raise ResearchError('API_SIZE','La respuesta externa excede el límite.')
        return parse_external_response(response.json(),selected)
    except ResearchError:
        raise
    except Exception:
        raise ResearchError('API_NETWORK','No se pudo conectar con la IA externa. El asistente local continúa disponible.') from None
