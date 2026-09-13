"""Escenarios ficticios. Ninguna imagen corresponde a un paciente o diagnóstico."""
from io import BytesIO
from PIL import Image
from mammotrace.phantom import phantom_array,encode_dicom
from .guidance import SYMPTOMS

CASES={
 'ED01':{'title':'Evaluación incompleta · BI-RADS 0','report':'EJEMPLO ACADÉMICO FICTICIO.\nConclusión: BI-RADS 0.\nSe requiere comparación con estudios previos e imágenes adicionales. Coordinar con el equipo que solicitó el examen.','category':'0','symptoms':{},'expected_min_level':1,'lesson':'Una evaluación incompleta no es un resultado negativo.'},
 'ED02':{'title':'Vigilancia · BI-RADS 3','report':'EJEMPLO ACADÉMICO FICTICIO.\nConclusión: BI-RADS 3.\nHallazgo probablemente benigno. Se propone control por imágenes en seis meses, sujeto a confirmación por el profesional responsable.','category':'3','symptoms':{},'expected_min_level':1,'lesson':'El intervalo se lee del informe; no lo decide el clasificador.'},
 'ED03':{'title':'Sospecha que requiere estudio · BI-RADS 4A','report':'EJEMPLO ACADÉMICO FICTICIO.\nConclusión del estudio actual: BI-RADS 4A.\nHallazgo sospechoso. Se recomienda valoración para biopsia y correlación clínica. No existe un resultado histopatológico en este ejemplo.','category':'4A','symptoms':{},'expected_min_level':2,'lesson':'Sospecha radiológica no significa confirmación de cáncer.'},
 'ED04':{'title':'Informe benigno, pero bulto nuevo','report':'EJEMPLO ACADÉMICO FICTICIO.\nInforme disponible: BI-RADS 2.\nHallazgos benignos en el examen descrito. Seguimiento según indicación profesional.','category':'2','symptoms':{'new_lump':'Sí'},'expected_min_level':2,'lesson':'Un síntoma nuevo no se descarta por un informe benigno.'},
 'ED05':{'title':'Inflamación y fiebre durante la espera','report':'EJEMPLO ACADÉMICO FICTICIO.\nConclusión: BI-RADS 2.\nEl escenario del taller añade síntomas nuevos después del examen.','category':'2','symptoms':{'red_hot':'Sí','fever':'Sí'},'expected_min_level':3,'lesson':'La prioridad educativa se activa por los síntomas, no por la imagen.'},
 'ED06':{'title':'Deterioro intenso · no esperar al software','report':'EJEMPLO ACADÉMICO FICTICIO.\nNo se dispone de una categoría radiológica documentada.','category':None,'symptoms':{'emergency':'Sí'},'expected_min_level':4,'lesson':'Una señal importante de deterioro requiere ayuda sin esperar la lectura.'},
 'ED07':{'title':'Dos menciones · separar previo y actual','report':'EJEMPLO ACADÉMICO FICTICIO.\nEstudio anterior: BI-RADS 2.\nConclusión del estudio actual: BI-RADS 5.\nSe recomienda evaluación diagnóstica y coordinación con el equipo tratante.','category':'5','symptoms':{},'expected_min_level':2,'lesson':'El usuario revisa la conclusión actual; el programa no selecciona el máximo.'},
 'ED08':{'title':'Sin informe legible · incertidumbre explícita','report':'EJEMPLO ACADÉMICO FICTICIO.\nLa conclusión no está disponible en el texto. Solicitar copia legible.','category':None,'symptoms':{k:'No sé / no evaluado' for k in SYMPTOMS},'expected_min_level':0,'lesson':'Lo que no se conoce no debe presentarse como ausencia de riesgo.'}
}


def scenario(code:str) -> dict:
    c=dict(CASES[code]);c['code']=code
    c['symptoms']={**{k:'No' for k in SYMPTOMS},**c['symptoms']}
    c['synthetic']=True
    return c


def image_bytes(code:str='ED01',fmt:str='PNG') -> bytes:
    a=phantom_array(seed=17+list(CASES).index(code))
    if fmt.upper() in ('DCM','DICOM'):return encode_dicom(a)
    image=Image.fromarray(a) if fmt.upper()=='TIFF' else Image.fromarray((a/4095*255).astype('uint8'))
    if fmt.upper() in ('JPEG','WEBP'):image=image.convert('RGB')
    b=BytesIO();image.save(b,format=fmt.upper());return b.getvalue()
