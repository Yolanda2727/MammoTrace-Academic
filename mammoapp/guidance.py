"""Motor educativo explícito, independiente del clasificador de imágenes.

No recibe puntuaciones, mapas, imágenes ni decisiones de un LLM. La severidad nunca
baja cuando se añade una señal de alarma. No calcula un plazo seguro de espera.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from .documents import CATS
from .knowledge import BLOCKS

ANSWERS=("No sé / no evaluado", "No", "Sí")
SYMPTOMS={
 "emergency":"¿Hay dificultad importante para respirar, confusión nueva, dificultad para despertar o deterioro intenso?",
 "red_hot":"¿La mama está roja, caliente o hinchada de forma nueva?",
 "fever":"¿Hay fiebre o escalofríos junto con dolor o molestias en la mama?",
 "new_lump":"¿Hay un bulto nuevo en la mama o en la axila?",
 "bloody_discharge":"¿Hay secreción por el pezón con sangre?",
 "skin_nipple":"¿Hay hundimiento nuevo de la piel, cambio llamativo de forma o retracción reciente del pezón?",
 "worsening":"¿Los síntomas están empeorando rápidamente?"
}
@dataclass(frozen=True)
class GuidanceResult:
    level: int
    title: str
    action: str
    confirmed_birads: str | None
    evidence: tuple[dict,...]
    unknown: tuple[str,...]
    next_steps: tuple[str,...]
    limits: tuple[str,...]
    engine: str="reglas_educativas_4.0.0"
    def to_dict(self): return asdict(self)


def guide(symptoms: dict[str,str], confirmed_birads: str | None = None,
          appointment: date | None = None, clinician_due: date | None = None,
          today: date | None = None) -> GuidanceResult:
    today=today or date.today()
    if confirmed_birads is not None and confirmed_birads not in CATS:
        raise ValueError("BI-RADS no permitido")
    if any(k not in SYMPTOMS or v not in ANSWERS for k,v in symptoms.items()):
        raise ValueError("Síntomas no válidos")
    if any(d is not None and (not isinstance(d,date) or type(d)!=date) for d in [appointment,clinician_due,today]):
        raise ValueError("Fecha inválida")
    s={k:symptoms.get(k,ANSWERS[0]) for k in SYMPTOMS}
    candidates=[];evidence=[]
    def add(level,rule,trigger,title,action,sources):
        candidates.append((level,title,action))
        evidence.append({"rule":rule,"trigger":trigger,"level":level,"sources":sources,
                         "meaning":"Regla educativa propuesta; no validación clínica del software."})
    if s['emergency']=='Sí':
        add(4,'G01','Señales generales de deterioro intenso declaradas','Busque atención de urgencias ahora',
            'No espere la consulta programada ni el resultado de una IA. Busque ayuda urgente por el canal de emergencias de su localidad.', ['NHS_EMERGENCY'])
    if any(s[k]=='Sí' for k in ('red_hot','fever','worsening')):
        which=[SYMPTOMS[k] for k in ('red_hot','fever','worsening') if s[k]=='Sí']
        add(3,'G02',' | '.join(which),'Solicite valoración pronta, hoy',
            'Contacte hoy a un servicio de salud para que valore la prioridad. Si hay deterioro intenso, utilice urgencias; no se automedique basándose en esta aplicación.', ['NHS_PAIN','DESIGN'])
    if any(s[k]=='Sí' for k in ('new_lump','bloody_discharge','skin_nipple')):
        add(2,'G03','Cambios mamarios nuevos declarados','Contacte al equipo para una valoración prioritaria',
            'Comunique el cambio y solicite valoración. No posponga la consulta por un informe anterior o una puntuación del modelo.', ['NHS_LUMP'])
    if confirmed_birads:
        root=confirmed_birads[0]
        if root in ('4','5'):
            add(2,'G04','BI-RADS '+confirmed_birads+' confirmado por quien usa el informe','Coordine los siguientes pasos diagnósticos',
                'Contacte al profesional que solicitó el estudio para coordinar la evaluación y la posible biopsia indicada en el informe. Una sospecha no confirma cáncer.', ['RAD_REPORT','ACS_REPORT'])
        elif root=='6':
            add(2,'G05','BI-RADS 6 confirmado por quien usa el informe','Mantenga el contacto con su equipo tratante',
                'Confirme el plan y los contactos del equipo que conoce la biopsia. La aplicación no confirma ni modifica el diagnóstico ya documentado.', ['NCI_MAMMO'])
        elif root=='0':
            add(1,'G06','BI-RADS 0 confirmado por quien usa el informe','Complete la evaluación pendiente',
                'Pregunte qué imágenes o comparaciones faltan y gestione su programación. No interprete un examen incompleto como un resultado normal.', ['NCI_MAMMO','ACS_REPORT'])
        elif root=='3':
            add(1,'G07','BI-RADS 3 confirmado por quien usa el informe','Confirme el control indicado',
                'Siga el intervalo de vigilancia que figure en su informe y confirme la fecha con su profesional. Este software no establece un plazo seguro.', ['RAD_REPORT'])
        else:
            add(0,'G08','BI-RADS '+root+' confirmado por quien usa el informe','Continúe el seguimiento indicado por su profesional',
                'Revise el resultado con su equipo. Las señales nuevas deben comunicarse, aunque el informe describa hallazgos negativos o benignos.', ['ACS_REPORT','NHS_LUMP'])
    if not candidates:
        add(0,'G00','No hay un informe confirmado ni señales afirmativas registradas','Falta información para orientar el siguiente paso',
            'Obtenga o revise el informe y solicite explicación al profesional. No hay una conclusión sobre la imagen ni una certificación de que pueda esperar.', ['DESIGN'])
    highest=max(candidates,key=lambda c:c[0])
    unknown=tuple(k for k,v in s.items() if v==ANSWERS[0])
    title=highest[1]; action=highest[2]
    if unknown and highest[0]==0:
        title='Información incompleta: no se puede valorar la prioridad'
        action='No se han evaluado todas las señales. Revise las preguntas y consulte con su profesional; la ausencia de datos no significa ausencia de riesgo.'
    if unknown:
        evidence.append({'rule':'G09','trigger':'Señales sin evaluar: '+str(len(unknown)), 'level':0,
                         'sources':['DESIGN'],'meaning':'Lo desconocido no se interpreta como respuesta negativa.'})
    steps=['Conserve el informe y los estudios anteriores para su consulta.',
           'Anote cuándo comenzaron los cambios y cómo han evolucionado.',
           'Confirme con el equipo qué examen, consulta o procedimiento está pendiente.']
    if appointment:
        steps.append('Fecha registrada por usted: '+appointment.isoformat()+'. No ha sido verificada con el prestador.')
        if appointment<today:
            steps.append('La fecha registrada ya pasó: confirme si necesita reprogramación.')
    else:
        steps.append('No registró una fecha de consulta: contacte al prestador para verificar la programación.')
    if clinician_due and clinician_due<today:
        evidence.append({'rule':'G10','trigger':'La fecha objetivo indicada por el profesional ya pasó','level':1,
                         'sources':['DESIGN'],'meaning':'Aviso administrativo; no estima riesgo biológico.'})
        steps.append('Informe al prestador que ya pasó la fecha objetivo indicada por su profesional.')
        if highest[0]<1:
            highest=(1,'Gestione el seguimiento pendiente','Contacte al prestador para revisar el plazo indicado por su profesional, sin asumir que el retraso es seguro.')
            title=highest[1];action=highest[2]
    if clinician_due and appointment and appointment>clinician_due:
        evidence.append({'rule':'G11','trigger':'La cita está después de la fecha objetivo profesional','level':1,
                         'sources':['DESIGN'],'meaning':'Conflicto de agenda; requiere revisión del prestador, no cálculo de riesgo.'})
        steps.append('La cita registrada es posterior al plazo profesional: solicite revisión de la programación.')
        if highest[0]<1:
            highest=(1,'Revise la fecha de consulta','Comunique que la cita asignada supera el plazo que indicó su profesional.')
            title=highest[1];action=highest[2]
    limits=('No es un diagnóstico ni un sistema de triaje clínicamente validado.',
            'No asigna medicamentos ni determina cuánto tiempo es seguro esperar.',
            'Las imágenes, el clasificador y la IA generativa no modifican estas reglas.',
            'No vigila síntomas en segundo plano ni envía alertas automáticas fuera de esta sesión.')
    return GuidanceResult(highest[0],title,action,confirmed_birads,tuple(evidence),unknown,tuple(steps),limits)


def explanation_blocks(category: str | None) -> list[str]:
    return ['scope']+(['birads_'+category[0]] if category else [])+['new_symptoms','planning']
