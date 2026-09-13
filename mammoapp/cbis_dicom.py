"""Restricted CBIS research reader, isolated from the personal-image pathway.

Requires a series -> published subject mapping; checks are NOT authentication,
complete de-identification or universal DICOM validation. No weights are used.
"""
from __future__ import annotations
import re,struct,hashlib
import numpy as np
import cv2
from mammotrace.dicom import Parser, DicomImage, IMPLICIT, EXPLICIT_LE, IMPLICIT_LE, PRIVACY_TAGS, Element
from mammotrace.errors import ResearchError
SC='1.2.840.10008.5.1.4.1.1.7'
EXTRA={(8,0x64):'CS',(0x18,0x1016):'LO',(0x18,0x1018):'LO',(0x20,0x20):'CS',(0x28,0x106):'US',(0x28,0x107):'US', (8,0x23):'DA',(8,0x33):'TM',(0x13,0x10):'LO',(0x13,0x1010):'LO',(0x13,0x1013):'LO'}
class CBISParser(Parser):
    def header(self,pos,explicit):
        if explicit or pos+8>self.n:return super().header(pos,explicit)
        tag=struct.unpack_from('<HH',self.raw,pos)
        if tag[0]==0xfffe:return super().header(pos,explicit)
        vr=IMPLICIT.get(tag,EXTRA.get(tag))
        if vr is None:raise ResearchError('CBIS_TAG','El perfil CBIS restringido no admite este atributo implícito.')
        return tag,vr,struct.unpack_from('<I',self.raw,pos+4)[0],pos+8

    def dataset(self, pos, end, explicit, depth=0, stop_item=False):
        if depth>12:raise ResearchError("DICOM_DEPTH", "Estructura DICOM excesivamente anidada.")
        fields={}
        while pos < end:
            self.count+=1
            if self.count>12000:raise ResearchError("DICOM_ELEMENTS", "Demasiados atributos DICOM.")
            tag,vr,length,start=self.header(pos,explicit)
            if tag==(0xfffe,0xe00d) and stop_item and length==0:return fields,start
            if tag[0]==0xfffe:raise ResearchError("DICOM_SEQUENCE", "Delimitación de secuencia inválida.")
            if tag in fields:raise ResearchError("DICOM_DUPLICATE_TAG", "DICOM con atributos duplicados.")
            if tag[0]%2 and tag not in {(0x13,0x10),(0x13,0x1010),(0x13,0x1013)}:raise ResearchError("PRIVATE_TAG", "Se detectaron atributos privados; revise la desidentificación.")
            if 0x6000<=tag[0]<=0x60ff:raise ResearchError("OVERLAY", "Los overlays requieren revisión externa.")
            if vr=="SQ":
                fields[tag]=Element(tag,vr,b"")
                pos=self.sequence(start,length,explicit,depth+1,end)
                continue
            if length==0xffffffff:raise ResearchError("DICOM_COMPRESSED", "Longitud indefinida fuera de secuencia o imagen encapsulada no admitida.")
            if length%2 or start+length>end:raise ResearchError("DICOM_LENGTH", "Longitud de atributo DICOM inválida.")
            if tag[0]%2 and tag not in {(0x13,0x10),(0x13,0x1010),(0x13,0x1013)}:raise ResearchError("PRIVATE_TAG", "Se detectaron atributos privados. Revise la desidentificación antes de cargar la imagen.")
            if vr=="UN" and length:raise ResearchError("UNKNOWN_CONTENT", "Contenido de representación desconocida: no se puede revisar su privacidad.")
            e=Element(tag,vr,self.raw[start:start+length]);fields[tag]=e;self.all_elements.append(e)
            pos=start+length
        if stop_item:raise ResearchError("DICOM_SEQUENCE", "Falta el delimitador de un elemento de secuencia.")
        return fields,pos

def read_cbis(raw:bytes,series_subjects:dict[str,str],authorized:bool=False)->DicomImage:
    def no(code,msg):raise ResearchError(code,msg)
    if not authorized:no('CBIS_AUTH','Confirme procedencia pública/autorizada y revisión de privacidad.')
    if not isinstance(raw,bytes) or len(raw)>64*1024*1024 or len(raw)<140 or raw[128:132]!=b'DICM':no('CBIS_FILE','DICOM Part 10 requerido; máximo 64 MiB.')
    p=CBISParser(raw);pos=132;meta={}
    while pos+8<=len(raw) and struct.unpack_from('<H',raw,pos)[0]==2:
        tag,vr,n,s=p.header(pos,True)
        if n==0xffffffff or n%2 or s+n>len(raw) or tag in meta:no('CBIS_META','Metadatos inválidos.')
        meta[tag]=raw[s:s+n];pos=s+n
    ts=meta.get((2,0x10),b'').rstrip(b'\0 ').decode('ascii',errors='replace')
    if ts not in {EXPLICIT_LE,IMPLICIT_LE}:no('CBIS_TRANSFER','Solo Little Endian sin compresión en este perfil.')
    fields,_=p.dataset(pos,len(raw),ts==EXPLICIT_LE);im=DicomImage(np.empty((0,0)),fields,{},[])
    uid=im.text((0x20,0xe));expected=series_subjects.get(uid)
    if expected is None or not re.fullmatch(r'P_\d{5}',expected):no('CBIS_LINK','La serie no figura en los CSV de referencia cargados.')
    if im.text((8,0x16))!=SC or meta.get((2,2),b'').rstrip(b'\0 ').decode()!=SC or im.text((8,0x60))!='MG':no('CBIS_SOP','Solo Secondary Capture MG del perfil de investigación CBIS.')
    if meta.get((2,3),b'').rstrip(b'\0 ').decode()!=im.text((8,0x18)):no('CBIS_SOP_UID','SOP Instance UID inconsistente.')
    if (0x13,0x10) in fields and (im.text((0x13,0x10))!='CTP' or im.text((0x13,0x1010))!='CBIS-DDSM' or not im.text((0x13,0x1013)).isdigit()):no('CBIS_CTP','El bloque privado CTP no corresponde al perfil publicado.')
    for e in p.all_elements:
        text=e.value.rstrip(b'\0 ').decode('ascii',errors='replace')
        if not text:continue
        if e.tag in {(0x10,0x10),(0x10,0x20)}:
            if not re.fullmatch(r'(?:Calc|Mass)-(?:Training|Test)_P_\d{5}_(?:LEFT|RIGHT)_(?:CC|MLO)(?:_\d+)?|P_\d{5}(?:\^P_\d{5}|_(?:LEFT|RIGHT)_(?:CC|MLO)(?:_\d+)?(?:\.dcm)?)?',text) or set(re.findall(r'P_\d{5}',text))!={expected}:no('CBIS_SUBJECT','El pseudocódigo no corresponde a la serie de referencia.')
        elif e.tag==(0x20,0x10) and text=='DDSM':continue
        elif e.vr=='PN' or e.tag in PRIVACY_TAGS:no('CBIS_PRIVACY','Atributo potencialmente identificador fuera del perfil público admitido.')
    rows=im.number((0x28,0x10));cols=im.number((0x28,0x11));bits=im.number((0x28,0x100));stored=im.number((0x28,0x101));high=im.number((0x28,0x102));signed=im.number((0x28,0x103))
    photo=im.text((0x28,4))
    if not isinstance(rows,int) or not isinstance(cols,int) or not 1<=rows<=8192 or not 1<=cols<=8192 or rows*cols>32_000_000:no('CBIS_DIM','Dimensiones no admitidas.')
    if bits not in (8,16) or not isinstance(stored,int) or not 1<=stored<=bits or high!=stored-1 or signed not in (0,1):no('CBIS_BITS','Representación de píxel no admitida.')
    if im.number((0x28,2))!=1 or photo not in ('MONOCHROME1','MONOCHROME2') or im.number((0x28,8),1)!=1:no('CBIS_FRAME','Solo imagen monocroma de un fotograma.')
    pixel=fields.get((0x7fe0,0x10));n=rows*cols*bits//8
    if pixel is None or len(pixel.value)!=n+n%2:no('CBIS_PIXELS','PixelData y dimensiones no coinciden.')
    a=np.frombuffer(pixel.value[:n],dtype='<u2' if bits==16 else 'u1').reshape(rows,cols)
    a=(a.astype(np.int32)&((1<<stored)-1))
    if signed:a=(a^(1<<(stored-1)))-(1<<(stored-1))
    im.pixels=a.astype(np.float32)
    im.technical={'reader':'cbis_research_4.1','series_uid':uid,'sop_instance_uid':im.text((8,0x18)),'subject':expected,'rows':rows,'columns':cols,'bits_allocated':bits,'photometric':photo,'transfer_syntax':ts,'binary_pixels':bool(np.unique(a).size<=2),'sha256':hashlib.sha256(raw).hexdigest(),'clinical_inference_enabled':False}
    im.warnings=['Archivo público enlazado por UID/pseudocódigo; esta coincidencia no autentica el archivo ni certifica anonimización.','No se usa el modelo legado, ni se genera un informe radiológico, BI-RADS o guía para una persona.']
    return im

def preview(im:DicomImage,max_side:int=1200)->np.ndarray:
    if not 64<=max_side<=4096:raise ResearchError('PREVIEW_SIZE','Tamaño de vista no admitido.')
    a=im.pixels.copy();lo,hi=np.percentile(a,[1,99]);lo,hi=(float(a.min()),float(a.max())) if hi<=lo else (lo,hi)
    if hi<=lo:raise ResearchError('CBIS_CONSTANT','No hay contraste para la vista previa.')
    a=np.clip((a-lo)/(hi-lo),0,1)
    if im.technical['photometric']=='MONOCHROME1':a=1-a
    h,w=a.shape;scale=min(1,max_side/max(h,w));a=cv2.resize(a,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
    return (a*255).round().astype('uint8')
