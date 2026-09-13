"""Exportaciones en memoria. La guía para la consulta no contiene etiquetas del modelo."""
from __future__ import annotations
from io import BytesIO
from datetime import datetime, date, timezone
from uuid import uuid4
from xml.sax.saxutils import escape
import json
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from .config import DISCLAIMER, VERSION
from .knowledge import SOURCES, BLOCKS
from .guidance import GuidanceResult


def _paragraph(text,style):
    # Todos los textos variables se escapan; jamás se interpretan como marcado del usuario.
    text=str(text).replace('→','a').replace('×','x').replace('−','-').replace('≤','<=').replace('≥','>=')
    return Paragraph(escape(text).replace('\n','<br/>'),style)


def _make_pdf(title:str,subtitle:str,sections:list[tuple[str,list[str]]]) -> bytes:
    b=BytesIO();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyMT',fontName='Helvetica',fontSize=10,leading=15,spaceAfter=7,textColor=colors.HexColor('#26364A')))
    styles['Title'].fontName='Helvetica-Bold';styles['Title'].fontSize=23;styles['Title'].leading=27
    styles['Heading2'].fontSize=12;styles['Heading2'].spaceBefore=13;styles['Heading2'].spaceAfter=7
    doc=SimpleDocTemplate(b,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=48,bottomMargin=50,
                          title=title,author='MammoTrace Academic — Anderson Díaz Pérez')
    story=[_paragraph('MAMMOTRACE ACADEMIC '+VERSION,styles['Heading2']),_paragraph(title,styles['Title']),
           _paragraph(subtitle,styles['BodyMT']),Spacer(1,6)]
    for heading,paras in sections:
        story.append(_paragraph(heading,styles['Heading2']))
        story.extend(_paragraph(p,styles['BodyMT']) for p in paras)
    def footer(canvas,document):
        canvas.setStrokeColor(colors.HexColor('#CDD8E2'));canvas.line(45,38,A4[0]-45,38)
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#526477'))
        canvas.drawString(45,25,'Uso académico y educativo. No diagnóstico. Versión '+VERSION)
        canvas.drawRightString(A4[0]-45,25,str(document.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return b.getvalue()


def guide_payload(result: GuidanceResult, synthetic:bool=False) -> dict:
    return {'schema':'mammotrace.guide.4.0','case_id':str(uuid4()),'generated_utc':datetime.now(timezone.utc).isoformat(),
            'synthetic_example':bool(synthetic),'disclaimer':DISCLAIMER,'guidance':result.to_dict(),
            'image_model_used_for_guidance':False,'background_monitoring':False,
            'sources':{k:SOURCES[k] for k in sorted({s for e in result.evidence for s in e['sources']})}}


def guide_pdf(result: GuidanceResult, synthetic:bool=False) -> bytes:
    category=result.confirmed_birads
    sections=[('Alcance',['EJEMPLO SINTÉTICO — informe y escenario ficticios.' if synthetic else 'Documento educativo, no historia clínica ni orden médica.',DISCLAIMER]),
              ('Orientación actual',[result.title,result.action])]
    if category:
        block=BLOCKS['birads_'+category[0]]
        sections.append(('Informe confirmado por la persona usuaria',['BI-RADS '+category,block['text']]))
    else:
        sections.append(('Informe',['No se confirmó una categoría del informe. No se deriva una categoría de la imagen.']))
    sections.append(('Por qué aparece esta orientación',[e['rule']+' | '+e['trigger']+' | Fuentes: '+', '.join(e['sources']) for e in result.evidence]))
    sections.append(('Preparar la consulta',list(result.next_steps)))
    sections.append(('Preguntas para el profesional',['¿Qué hallazgo requiere seguimiento y qué paso sigue?',
                        '¿Cuál es el plazo indicado para mi situación y a quién contacto si no consigo la cita?',
                        '¿Qué cambios deberían hacerme consultar antes?']))
    sections.append(('Límites',list(result.limits)))
    ids=sorted({s for e in result.evidence for s in e['sources']})
    sections.append(('Fuentes y trazabilidad',[SOURCES[k]['title']+(' — '+SOURCES[k]['url'] if SOURCES[k]['url'] else '') for k in ids]))
    return _make_pdf('Guía para preparar la consulta','Orientación basada en datos declarados e informe confirmado; no en la salida del clasificador.',sections)


def technical_pdf(image_meta:dict,stats:dict,xai:dict | None=None) -> bytes:
    sections=[('Alcance',[DISCLAIMER,'El modelo legado utiliza etiquetas sintéticas; sus salidas no estiman probabilidad individual de cáncer.']),
              ('Entrada técnica',[str(k)+': '+str(v) for k,v in image_meta.items()]),
              ('Descriptores del visor',[str(k)+': '+str(v) for k,v in stats.items()])]
    if xai:
        sections.append(('Modelo experimental',['SHA-256: '+xai['model_sha256'],
                       'Puntuaciones softmax sin calibración clínica: '+json.dumps(xai['score']['scores'],ensure_ascii=False),
                       xai['warning'],'Método: '+xai['method'],xai['units'],
                       'Cambio absoluto máximo observado: '+str(xai['max_abs_delta'])]))
        sections.append(('Lectura del mapa',['Cada celda oculta una región del tensor. La magnitud indica sensibilidad de la activación; el signo está en los datos JSON.',
                      'No es una segmentación, ni una explicación causal, ni una validación clínica. Un mapa plano tampoco demuestra seguridad.']))
    else:
        sections.append(('Inferencia',['No se ejecutó el modelo en este registro. No hay una predicción de sustitución.']))
    return _make_pdf('Informe técnico de investigación','Este informe está separado de la guía de acompañamiento.',sections)


def appointment_ics(day:date) -> bytes:
    """Evento de día completo genérico; no contacta servicios ni solicita citas."""
    if type(day)!=date:raise ValueError('Fecha inválida')
    uid=str(uuid4())+'@mammotrace.local'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    # Sin PHI, diagnóstico, categoría, nombre, geolocalización ni URLs externas.
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//MammoTrace//Academic '+VERSION+'//ES',
           'BEGIN:VEVENT','UID:'+uid,'DTSTAMP:'+stamp,'DTSTART;VALUE=DATE:'+day.strftime('%Y%m%d'),
           'SUMMARY:Revisar cita y preparar documentos',
           'DESCRIPTION:Fecha anotada por la persona usuaria. Confirmar con el prestador. No certifica un tiempo seguro de espera.',
           'END:VEVENT','END:VCALENDAR']
    # Plegado de líneas según RFC 5545, cortando por caracteres ASCII en este contenido.
    folded=[]
    for line in lines:
        while len(line.encode('utf-8'))>73:
            head=line[:70];folded.append(head);line=' '+line[70:]
        folded.append(line)
    return ('\r\n'.join(folded)+'\r\n').encode('utf-8')
