"""Interfaz Streamlit. Sin caché compartida de informes, imágenes ni síntomas."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from datetime import date
from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st
from mammotrace.errors import ResearchError
from .config import ROOT, DISCLAIMER, VERSION, IMAGE_EXT, REPORT_EXT
from .images import load_image, image_statistics, png_bytes, KINDS
from .documents import read_report, extract_birads, confirm_category, clean_text
from .guidance import guide, SYMPTOMS, ANSWERS, explanation_blocks
from .knowledge import SOURCES, BLOCKS
from .examples import CASES, scenario, image_bytes
from .exports import guide_pdf, guide_payload, technical_pdf, appointment_ics
from .narrative import retrieve, QUESTIONS, order_with_external_ai, external_payload

CSS='''<style>
:root{--mt-ink:#17263b;--mt-blue:#1d6273;--mt-line:#d6e1e7;}
.stApp{background:#f5f7fa;color:var(--mt-ink);}
.block-container{max-width:1400px;padding-top:2.3rem;padding-bottom:3rem;}
.mt-hero{background:linear-gradient(120deg,#152943 0%,#174d60 70%,#39767a 100%);border-radius:19px;padding:30px 34px;color:white;margin:0 0 20px;position:relative;overflow:hidden;}
.mt-hero:after{content:'';position:absolute;border:1px solid #ffffff35;border-radius:50%;width:250px;height:250px;right:25px;top:-100px;pointer-events:none;}
.mt-kicker{letter-spacing:2.4px;text-transform:uppercase;font-size:11px;color:#bddde3;font-weight:700;}
.mt-hero h1{color:white!important;font-size:34px!important;line-height:1.2!important;font-weight:750!important;padding:10px 0!important;margin:0;}
.mt-hero p{color:#e0eff1;max-width:900px;line-height:1.6;font-size:15px;margin-bottom:0;}
.mt-strip{display:flex;gap:0;background:white;border:1px solid var(--mt-line);border-radius:12px;overflow:hidden;margin-bottom:20px;}
.mt-strip div{flex:1;padding:15px 18px;border-right:1px solid var(--mt-line);font-size:12px;}
.mt-strip b{display:block;color:#1d6273;font-size:16px;margin-bottom:4px;}
.mt-source{font-size:12px;color:#506176;line-height:1.5;}
[data-testid=stSidebar]{background:#edf2f6;border-right:1px solid #d6e1e7;}
[data-testid=stMetric]{background:white;border:1px solid #d6e1e7;border-radius:12px;padding:13px;}
[data-testid=stFileUploader]{background:white;border-radius:12px;}
h2,h3{color:var(--mt-ink);}
button[kind=primary]{background:#196475!important;border:1px solid #196475!important;}
@media(max-width:700px){.mt-hero{padding:23px 21px}.mt-hero h1{font-size:27px!important}.mt-strip{display:block}.mt-strip div{border-right:none;border-bottom:1px solid #d6e1e7}}
</style>'''
PAGES=('1 · Imágenes e informe','2 · Orientación de espera','3 · Laboratorio explicable','4 · Aula y evidencia','5 · Despliegue y privacidad','6 · CBIS-DDSM y cohortes')


from . import session as case_state
from .cbis_ui import cbis_page


def defaults():case_state.defaults(st.session_state)
def reset_case():case_state.reset_case(st.session_state)
def load_example(code):case_state.load_example(st.session_state,code)
def set_report(text,notes,source):case_state.set_report(st.session_state,text,notes,source)
def current_category():return case_state.current_category(st.session_state)


def sources(ids):
    for key in dict.fromkeys(ids):
        s=SOURCES[key]
        if s['url']:st.caption(s['title']+' · '+s['url'])
        else:st.caption(s['title'])


def show_blocks(ids):
    for k in ids:
        b=BLOCKS[k]
        st.markdown('**'+b['title']+'**')
        st.write(b['text'])
        sources(b['sources'])


@st.cache_resource(show_spinner=False)
def get_model():
    from .xai import ExplainableLegacy
    return ExplainableLegacy()


def sidebar():
    with st.sidebar:
        st.markdown('### MammoTrace\n**Academic · 4.1 CBIS**')
        st.caption('Dirección académica del proyecto\nDr. Anderson Díaz Pérez')
        audience=st.radio('Perspectiva',('Académica / investigación','Comprender y preparar la consulta'),key='audience')
        pages=PAGES if audience=='Académica / investigación' else tuple(p for p in PAGES if not p.startswith(('3','6')))
        if st.session_state.get('page') not in pages:st.session_state['page']=pages[0]
        st.radio('Espacio de trabajo',pages,key='page')
        st.divider()
        code=st.selectbox('Ejemplo académico',list(CASES),format_func=lambda k:k+' · '+CASES[k]['title'],key='example_choice')
        st.button('Cargar ejemplo completo',on_click=load_example,args=(code,),use_container_width=True)
        st.button('Nuevo caso / limpiar sesión',on_click=reset_case,use_container_width=True)
        st.caption('Los ejemplos son ficticios. Sus imágenes son fantomas geométricos, no casos clínicos.')
        st.divider()
        st.caption('Sin historial de pacientes en la aplicación. En la nube, los archivos viajan al servidor; no se quedan solo en el navegador.')
        st.caption('No hay vigilancia continua ni avisos externos automáticos.')


def workspace():
    st.subheader('Estación multimodal')
    st.write('Cargue imágenes y el informe por separado. El contenido del informe siempre se confirma antes de utilizar su categoría en la orientación.')
    epoch=st.session_state['case_epoch']
    flash=st.session_state.pop('flash',None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])
    allowed=st.checkbox('Trabajo solo con material sintético o previamente desidentificado y autorizado; revisé también los textos incrustados en los píxeles.',key=f'auth_{epoch}')
    if allowed:
        left,right=st.columns([1,1],gap='large')
        with left:
            st.markdown('#### Imágenes · hasta cuatro vistas')
            kind=st.selectbox('Tipo declarado de imagen',KINDS,key=f'kind_{epoch}')
            uploaded=st.file_uploader('DICOM, PNG, JPG/JPEG, TIFF, BMP o WebP',type=list(IMAGE_EXT),accept_multiple_files=True,key=f'images_upload_{epoch}')
            st.caption('64 MiB por archivo; DICOM 2D sin compresión dentro del perfil documentado. No se procesa tomosíntesis ni TIFF multipágina.')
            if st.button('Procesar imágenes y abrir caso nuevo',key=f'load_images_{epoch}',disabled=not uploaded):
                # Cambio de caso: nunca conservar informe/síntomas de una imagen anterior.
                files=[(f.name,f.getvalue()) for f in uploaded]
                reset_case();st.session_state['synthetic']=False
                if len(files)>4:st.session_state['flash']=(False,'Se admiten hasta cuatro imágenes por caso.')
                elif sum(len(b) for _,b in files)>128*1024*1024:st.session_state['flash']=(False,'El conjunto supera 128 MiB.')
                else:
                    valid=[]
                    try:
                        for name,data in files:valid.append(load_image(data,name,kind))
                        st.session_state['images']=valid
                        st.session_state['flash']=(True,'Imágenes leídas. Añada el informe del mismo caso y confirme su categoría.')
                    except ResearchError as e:
                        st.session_state['flash']=(False,e.message)
                st.rerun()
        with right:
            st.markdown('#### Informe radiológico')
            report=st.file_uploader('Archivo de lectura · TXT, PDF textual o DOCX',type=list(REPORT_EXT),key=f'report_upload_{epoch}')
            st.caption('10 MiB, 12 páginas PDF y 30.000 caracteres. El PDF escaneado requiere transcripción revisada; no hay OCR automático.')
            if st.button('Leer archivo de informe',key=f'load_report_{epoch}',disabled=report is None):
                set_report('',[],'Ninguno');st.session_state['synthetic']=False
                try:
                    doc=read_report(report.getvalue(),report.name)
                    set_report(doc.text,doc.warnings,'Archivo '+doc.format)
                    st.session_state['flash']=(True,'Texto extraído; revise que la conclusión esté completa. Se reiniciaron las señales y fechas para evitar mezclar casos.')
                except ResearchError as e:st.session_state['flash']=(False,e.message)
                st.rerun()
    else:
        st.info('Los cargadores de archivos se habilitan después de la declaración anterior. Los ocho ejemplos integrados pueden utilizarse sin archivos externos.')
    images=st.session_state['images']
    if images:
        st.divider()
        st.markdown('#### Visor de investigación')
        columns=st.columns(min(4,len(images)))
        for i,img in enumerate(images):
            with columns[i]:
                st.image(img.display,caption=f"Vista {i+1} · {img.technical['format']} · {img.technical['laterality']} {img.technical['view']}",use_container_width=True)
        st.caption('Contraste técnico del visor. No es una estación calibrada para lectura diagnóstica.')
        with st.expander('Metadatos técnicos y límites del formato'):
            for i,img in enumerate(images):
                st.write('Vista '+str(i+1));st.json(img.technical)
                for note in img.warnings:st.caption(note)
    st.divider()
    st.markdown('#### Revisar o transcribir la lectura')
    if allowed or st.session_state['synthetic'] or st.session_state['report_text']:
        revision=st.session_state['report_revision'];e=st.session_state['case_epoch']
        text=st.text_area('Texto del informe, sin identificadores personales',value=st.session_state['report_text'],height=190,max_chars=30000,key=f'report_text_{e}_{revision}')
        case_state.set_manual_text(st.session_state,text)
        for warning in st.session_state['report_warnings']:st.warning(warning)
        if text.strip():
            try:
                matches=extract_birads(text)
                if matches:
                    st.dataframe(pd.DataFrame([{'Categoría encontrada':m['category'],'Fragmento literal':m['evidence'],
                                               'Posible mención previa':m['historical_hint'],'Posible negación':m['negated_hint']} for m in matches]),hide_index=True,use_container_width=True)
                    if len(matches)>1:st.warning('Hay varias menciones. Compruebe la conclusión actual, lateralidad y fecha; el programa no elige la categoría más alta.')
                    available=list(dict.fromkeys(m['category'] for m in matches if not m['negated_hint'] and not m['historical_hint']))
                    digest=hashlib.sha256(text.encode()).hexdigest()
                    selected=st.selectbox('Categoría de la conclusión actual que usted confirma', ['Sin confirmar']+available,key=f'birads_{e}_{digest[:12]}')
                    reviewed=st.checkbox('Contrasté esta categoría con el informe original completo y corresponde al caso actual.',key=f'review_{e}_{digest[:12]}')
                    if not reviewed or (st.session_state['confirmation'] and st.session_state['confirmation']['category']!=selected):
                        st.session_state['confirmation']=None
                    if st.button('Confirmar lectura para la orientación',disabled=not reviewed or selected=='Sin confirmar',key=f'confirm_{e}_{digest[:12]}'):
                        category=confirm_category(text,selected,reviewed)
                        st.session_state['confirmation']={'category':category,'hash':digest}
                    if current_category():st.success('Categoría confirmada por usted: BI-RADS '+current_category()+'. La aplicación no la ha diagnosticado.')
                else:
                    st.info('No se identificó una categoría BI-RADS explícita. Se permite orientación por síntomas, pero no se inventa la lectura del informe.')
            except ResearchError as e:st.error(e.message)
    else:
        st.caption('Abra un ejemplo o habilite la carga autorizada para introducir texto.')


def support():
    st.subheader('Comprender el informe y preparar la consulta')
    st.caption('Este módulo no utiliza la salida del modelo de imágenes. Las fechas son datos introducidos por usted, no una programación verificada con el prestador.')
    category=current_category()
    if category:
        show_blocks(['birads_'+category[0]])
        if len(extract_birads(st.session_state['report_text']))>1:
            st.warning('El documento contiene varias menciones. La categoría confirmada no resume automáticamente todas las lesiones o ambas mamas. No omita otra categoría relevante; solicite aclaración al radiólogo.')
    else:st.warning('No hay una categoría del informe confirmada. La orientación siguiente puede funcionar con los síntomas declarados, sin interpretar la imagen.')
    st.markdown('#### Señales actuales')
    st.caption('En un caso real, no deje una respuesta negativa por comodidad. «No sé» significa que la información no está disponible.')
    epoch=str(st.session_state['case_epoch'])+'_'+str(st.session_state['clinical_epoch'])
    for k,label in SYMPTOMS.items():
        value=st.radio(label,ANSWERS,index=ANSWERS.index(st.session_state['answers'][k]),horizontal=True,key=f'sym_{epoch}_{k}')
        st.session_state['answers'][k]=value
    st.markdown('#### Organización de la consulta')
    a,b=st.columns(2)
    with a:
        has_date=st.checkbox('Tengo una fecha de consulta anotada',value=st.session_state['appointment'] is not None,key=f'has_appt_{epoch}')
        if has_date:
            appt=st.date_input('Fecha que debo confirmar con el prestador',value=st.session_state['appointment'] or date.today(),key=f'appt_{epoch}')
            st.session_state['appointment']=appt
        else:st.session_state['appointment']=None
    with b:
        has_due=st.checkbox('El profesional indicó una fecha objetivo',value=st.session_state['clinician_due'] is not None,key=f'has_due_{epoch}')
        if has_due:
            due=st.date_input('Fecha indicada por el profesional, no por la IA',value=st.session_state['clinician_due'] or date.today(),key=f'due_{epoch}')
            st.session_state['clinician_due']=due
        else:st.session_state['clinician_due']=None
    result=guide(st.session_state['answers'],category,st.session_state['appointment'],st.session_state['clinician_due'])
    st.divider()
    if result.level>=3:st.error(result.title+'\n\n'+result.action)
    elif result.level>=1:st.warning(result.title+'\n\n'+result.action)
    else:st.info(result.title+'\n\n'+result.action)
    st.caption('La presentación por niveles organiza mensajes educativos. No es una clasificación de urgencias validada para uso asistencial.')
    if result.unknown:st.warning(f'Quedan {len(result.unknown)} señales sin evaluar. No se consideran ausentes.')
    with st.expander('Explicación trazable: dato → regla → orientación',expanded=True):
        st.dataframe(pd.DataFrame([{'Regla':e['rule'],'Dato que la activa':e['trigger'],'Nivel educativo':e['level'],'Fuentes':', '.join(e['sources'])} for e in result.evidence]),hide_index=True,use_container_width=True)
        sources([s for e in result.evidence for s in e['sources']])
    for i,step in enumerate(result.next_steps,1):st.write(str(i)+'. '+step)
    st.caption('Un cambio nuevo puede requerir otra valoración. La aplicación no monitorea a la persona después de cerrar la sesión.')
    col1,col2,col3=st.columns(3)
    with col1:
        st.download_button('Descargar guía PDF',data=guide_pdf(result,st.session_state['synthetic']),file_name='MammoTrace_guia_educativa.pdf',mime='application/pdf',use_container_width=True)
    with col2:
        st.download_button('Descargar trazabilidad JSON',data=json.dumps(guide_payload(result,st.session_state['synthetic']),ensure_ascii=False,indent=2).encode(),file_name='MammoTrace_guia_trazable.json',mime='application/json',use_container_width=True)
    with col3:
        if st.session_state['appointment']:
            st.download_button('Evento de calendario .ics',data=appointment_ics(st.session_state['appointment']),file_name='recordatorio_consulta.ics',mime='text/calendar',use_container_width=True)
    st.caption('El .ics crea una anotación genérica al importarlo. No solicita ni confirma citas y no configura un sistema de alertas médicas.')
    st.divider();assistant_panel(category)


def assistant_panel(category):
    st.markdown('#### Asistente interpretativo explicable')
    st.write('La base local recupera explicaciones curadas con sus fuentes. La IA externa opcional solo puede ordenar fragmentos aprobados; no interpreta píxeles ni cambia alertas.')
    preset=st.selectbox('Pregunta orientadora',QUESTIONS,key='assistant_preset')
    question=st.text_input('O escriba una pregunta breve, sin datos personales',max_chars=2000,key='assistant_question')
    ids=retrieve(question or preset,category)
    show_blocks(ids)
    with st.expander('Conexión opcional de IA · sin enviar el informe ni la pregunta libre'):
        def setting(name,default=''):
            value=os.environ.get(name,default)
            try:value=st.secrets.get(name,value)
            except Exception:pass
            return value
        enabled=setting('ENABLE_EXTERNAL_AI',False)
        enabled=enabled is True or str(enabled).lower()=='true'
        key=setting('OPENAI_API_KEY');model=setting('OPENAI_MODEL','gpt-5')
        st.caption('Por defecto no se llama a ninguna API. La clave se configura solo en Secrets o variables del servidor. store=false no equivale a retención cero por el proveedor.')
        if not enabled or not key:
            st.info('IA externa desactivada o sin credenciales. El asistente local está operativo sin clave.')
        else:
            st.json({'fragmentos_educativos_que_se_enviarian':ids,'modelo_configurado':model,
                     'imagenes':False,'texto_del_informe':False,'sintomas':False,'pregunta_libre':False})
            consent=st.checkbox('Autorizo esta llamada para ordenar únicamente los fragmentos educativos públicos mostrados. Puede generar un cargo de API.',key='api_consent')
            if st.button('Ordenar fragmentos con IA externa',disabled=not consent):
                try:
                    selected=order_with_external_ai(ids,key,model,consent)
                    st.success('Selección externa validada: solo se muestran fragmentos de la base curada.')
                    show_blocks(selected)
                except ResearchError as e:st.warning(e.message)


def laboratory():
    st.subheader('Laboratorio de imagen y explicabilidad')
    st.warning('Modelo experimental legado: etiquetas sintéticas. Los nombres originales de las clases se conservan solo para trazabilidad. Ningún resultado se utiliza para orientar a la persona durante la espera.')
    images=st.session_state['images']
    if not images:
        st.info('Cargue un ejemplo o una imagen autorizada en la estación multimodal.');return
    index=st.selectbox('Vista del caso',range(len(images)),format_func=lambda i:'Vista '+str(i+1),key='lab_view')
    img=images[index];fingerprint=img.session_fingerprint
    if st.session_state['xai_image']!=fingerprint:
        st.session_state['xai']=None;st.session_state['xai_image']=fingerprint
    left,right=st.columns([1,1],gap='large')
    with left:
        st.image(img.display,caption='Visor técnico · no calibración diagnóstica',use_container_width=True)
    with right:
        stats=image_statistics(img)
        st.dataframe(pd.DataFrame([{'Descriptor':k,'Valor':str(v)} for k,v in stats.items() if k!='interpretacion']),hide_index=True,use_container_width=True)
        st.caption(stats['interpretacion'])
        hist=np.bincount(img.display.ravel(),minlength=256)
        st.bar_chart(pd.DataFrame({'Frecuencia':hist}),height=170)
    with st.expander('Ver la entrada que realmente recibe el modelo'):
        if img.legacy_input is not None:
            st.image(img.legacy_input,caption='Tensor 224 × 224; 0–1 antes de la resta de medias ResNet. Separado del contraste del visor.',width=300)
            st.caption('Para archivos no DICOM, se utiliza una adaptación exploratoria en luminancia. La equivalencia clínica o con el DICOM de origen no está demostrada.')
        else:st.info('Inferencia bloqueada para el tipo de imagen declarado.')
    weights_available=(ROOT/'models'/'parts.json').exists() or (ROOT/'models'/'modelo.h5').exists()
    if not weights_available:
        st.info('Edición pública sin pesos: el visor y el análisis técnico están disponibles. Para ejecutar el modelo y la oclusión utilice el paquete privado completo; no se sustituye por predicciones aleatorias.')
    accepted=st.checkbox('Comprendo que esta prueba no determina normalidad, benignidad ni malignidad reales.',key='lab_accept')
    if st.button('Ejecutar modelo y oclusión explicable',type='primary',disabled=not accepted or img.legacy_input is None or not weights_available):
        try:
            with st.spinner('Verificando los pesos y calculando 49 oclusiones de regiones…'):
                model=get_model();st.session_state['xai']=model.explain(img.legacy_input)
        except ResearchError as e:st.error(e.message)
        except Exception:st.error('No pudo completarse el cálculo. Revise las dependencias del perfil de modelo y la memoria disponible. No se generan resultados simulados como sustituto.')
    result=st.session_state['xai']
    if result:
        st.markdown('#### Resultado experimental — separado de la orientación')
        st.dataframe(pd.DataFrame([{'Nombre histórico de clase':k,'Puntuación softmax (no riesgo clínico)':v} for k,v in result['score']['scores'].items()]),hide_index=True,use_container_width=True)
        if result['score']['saturated_output']:st.warning('Salida softmax saturada. Una puntuación cercana a uno no es certeza diagnóstica ni buena calibración.')
        from .xai import heatmap_overlay
        overlay=heatmap_overlay(img.legacy_input,result)
        a,b=st.columns([1,1])
        with a:
            if overlay is not None:st.image(overlay,caption='Magnitud absoluta del cambio de logit; no mapa de una lesión.',width=380)
            else:st.info('El mapa no tiene variación numérica suficiente. No se colorea un mapa ficticio.')
        with b:
            st.write('Objetivo histórico:',result['target'])
            st.write('Cambio absoluto máximo de activación:',result['max_abs_delta'])
            st.caption(result['warning'])
            st.caption('Cada celda oculta 32 × 32 píxeles del tensor y reemplaza su contenido por la mediana. El signo positivo indica disminución de la activación al ocultarla; no prueba causalidad clínica.')
        with st.expander('Deltas firmados y manifiesto de explicación'):
            st.dataframe(pd.DataFrame(result['signed_delta']),use_container_width=True)
            st.json({k:v for k,v in result.items() if k not in {'signed_delta'}})
    a,b=st.columns(2)
    with a:
        st.download_button('Informe técnico PDF',data=technical_pdf(img.technical,stats,result),file_name='MammoTrace_informe_tecnico.pdf',mime='application/pdf',use_container_width=True)
    with b:
        if result:
            st.download_button('Mapa y trazabilidad JSON',data=json.dumps(result,ensure_ascii=False,indent=2).encode(),file_name='MammoTrace_XAI_experimental.json',mime='application/json',use_container_width=True)


def evidence_page():
    st.subheader('Aula, investigación y evidencia')
    st.write('Ocho escenarios para estudiar incertidumbre, comunicación de hallazgos, señales declaradas y límites de la explicabilidad. Los fantomas no tienen diagnósticos asociados.')
    rows=[{'Caso':k,'Escenario':c['title'],'Pregunta de aprendizaje':c['lesson']} for k,c in CASES.items()]
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    for title,fmt,ext,mime in [('PNG','PNG','png','image/png'),('DICOM','DICOM','dcm','application/dicom'),('TIFF 16 bits','TIFF','tiff','image/tiff')]:
        st.download_button('Descargar fantoma '+title,data=image_bytes('ED03',fmt),file_name='ED03_FANTOMA_NO_CLINICO.'+ext,mime=mime,key='demo_download_'+ext)
    st.download_button('Descargar informe ficticio TXT',data=CASES['ED03']['report'].encode(),file_name='ED03_INFORME_FICTICIO.txt',mime='text/plain')
    with st.expander('Ejercicio crítico para estudiantes',expanded=True):
        st.write('Compare ED03, ED04 y ED06. Identifique de dónde procede cada afirmación: informe, síntoma declarado, regla educativa o modelo experimental.')
        st.write('Explique por qué una puntuación alta y un mapa llamativo no compensan la ausencia de etiquetas verificables. Documente qué dato falta y quién debe resolverlo.')
        st.write('Buenas prácticas: preservar incertidumbre, confirmar la lectura, comunicar cambios y mantener las fuentes. Malas prácticas: convertir un mapa en diagnóstico, ocultar información faltante o usar un informe antiguo para descartar síntomas nuevos.')
    st.markdown('#### Evaluación científica de predicciones — solo datos autorizados')
    st.caption('El módulo heredado permite calcular métricas a partir de un CSV. No trae exactitudes clínicas precargadas. Consulte docs/INVESTIGACION.md antes de utilizarlo.')
    permitted=st.checkbox('El CSV contiene solo códigos seudonimizados y tengo autorización para procesarlo.',key='eval_permission')
    if permitted:
        file=st.file_uploader('CSV de evaluación',type=['csv'],key='eval_csv')
        if file and st.button('Validar y calcular métricas'):
            try:
                from mammotrace.evaluation import evaluate_csv
                result=evaluate_csv(file.getvalue())
                st.json(result)
            except ImportError:st.error('Faltan dependencias del módulo de evaluación. Instale requirements.txt; no se presentan métricas de sustitución.')
            except ResearchError as e:st.error(e.message)
            except Exception:st.error('No se pudo evaluar el CSV. Revise las columnas y el formato indicado en la plantilla.')
    with st.expander('Fuentes educativas'):
        sources(list(SOURCES))
    audit=ROOT/'reports'/'audit_summary.json'
    if audit.exists():
        st.markdown('#### Evidencia técnica de esta entrega')
        st.json(json.loads(audit.read_text(encoding='utf-8')))
    st.caption('Pasar pruebas de software no constituye validación clínica ni aprobación regulatoria.')


def deployment_page():
    st.subheader('Despliegue y privacidad')
    st.markdown('#### GitHub → Streamlit')
    st.write('Punto de entrada: streamlit_app.py · Rama sugerida: main · Python: 3.13. El paquete completo con pesos debe ir únicamente a un repositorio privado autorizado.')
    st.code('python -m pip install -r requirements.txt\npython -m streamlit run streamlit_app.py',language='bash')
    st.write('En Community Cloud seleccione el repositorio, la rama y streamlit_app.py. Revise Advanced settings para fijar Python y los Secrets. No copie una carpeta venv al repositorio.')
    st.markdown('#### Privacidad y control humano')
    st.write('Los archivos se procesan en el servidor que ejecuta Streamlit. La aplicación no crea un historial persistente de casos ni escribe las cargas en disco. El proveedor de alojamiento puede gestionar su propia infraestructura y registros.')
    st.write('No cargue datos identificables en una demostración pública. Las comprobaciones técnicas no detectan todos los identificadores, textos incrustados, riesgos de malware o circunstancias clínicas.')
    st.write('El modelo es un recurso compartido sin datos de casos; los informes, imágenes y síntomas se mantienen en la sesión del usuario. «Limpiar sesión» libera esas referencias y reinicia el caso; no certifica borrado forense ni borra descargas ya realizadas.')
    st.markdown('#### Activar la IA externa opcional')
    st.code('ENABLE_EXTERNAL_AI = false\n# Activar solo tras la revisión institucional:\n# OPENAI_API_KEY = "configurar_en_Secrets_no_en_GitHub"\n# OPENAI_MODEL = "gpt-5"',language='toml')
    st.write('La integración externa envía solo fragmentos educativos públicos y sus IDs. No envía los archivos, la pregunta libre ni los síntomas. Se valida que la respuesta solo ordene fragmentos permitidos; no se expone texto libre generado como consejo.')
    st.markdown('#### Antes de investigación con participantes')
    st.write('Defina responsables, autorización ética y protección de datos; revise las reglas con especialistas; pruebe usabilidad, riesgos de comprensión y falsas tranquilizaciones; documente errores y límites. El uso asistencial requiere una evaluación adicional, independiente de este prototipo.')
    st.caption(DISCLAIMER)


def main():
    st.set_page_config(page_title='MammoTrace Academic | IA explicable',page_icon='🔬',layout='wide',initial_sidebar_state='expanded')
    st.markdown(CSS,unsafe_allow_html=True)
    defaults();sidebar()
    st.markdown('<div class="mt-hero"><div class="mt-kicker">Imagen · Evidencia · Comprensión</div><h1>MammoTrace Academic</h1><p>Una estación académico-científica para explorar imágenes, comprender el informe y preparar una consulta informada. La explicabilidad acompaña el juicio humano; no lo reemplaza.</p></div>',unsafe_allow_html=True)
    st.markdown('<div class="mt-strip"><div><b>01 · Imagen</b>Visor y laboratorio experimental</div><div><b>02 · Informe</b>Texto, evidencia y confirmación</div><div><b>03 · Consulta</b>Señales declaradas y guía educativa</div></div>',unsafe_allow_html=True)
    st.caption(DISCLAIMER)
    if st.session_state['synthetic']:
        code=st.session_state['scenario_code']
        st.info('EJEMPLO SINTÉTICO '+str(code)+' · '+CASES[code]['lesson'])
    st.warning('Si hay dificultad importante para respirar, confusión reciente, dificultad para despertar o deterioro intenso, busque atención urgente sin esperar una lectura informática.')
    page=st.session_state['page']
    {'1':workspace,'2':support,'3':laboratory,'4':evidence_page,'5':deployment_page,'6':cbis_page}[page[0]]()
    st.divider();st.caption('MammoTrace Academic '+VERSION+' · Proyecto académico de Anderson Díaz Pérez · Sin validación clínica. Fuentes educativas consultadas el 13 de septiembre de 2026.')
