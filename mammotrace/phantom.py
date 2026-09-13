"""Objeto de prueba sintético. No proviene de pacientes ni representa una patología."""
from __future__ import annotations
import struct
import uuid
import numpy as np
from .dicom import EXPLICIT_LE, IMPLICIT_LE, IMPLICIT, LONG_VR


def phantom_array(seed=17,rows=512,cols=384):
    rng=np.random.default_rng(seed)
    y,x=np.mgrid[-1:1:complex(rows),0:1.35:complex(cols)]
    mask=(x/1.15)**2+(y/1.02)**2<1
    base=(0.4+0.18*np.cos(y*6)+0.14*np.sin(x*9+y*3)+0.12*np.cos(x*26)*np.sin(y*19))
    a=(base+rng.normal(0,0.025,(rows,cols)))*mask
    # Figuras deliberadamente geométricas, no lesiones.
    a[(x-0.55)**2+(y+0.3)**2<0.045]+=0.17
    a=np.clip(a,0,1)
    return (a*4095).astype(np.uint16)


def encode_dicom(pixels=None, *, implicit=False, tags=None, seed=17):
    a=phantom_array(seed) if pixels is None else np.asarray(pixels,dtype=np.uint16)
    sop='1.2.840.10008.5.1.4.1.1.1.2';uid='2.25.'+str(uuid.uuid4().int)
    def elem(tag,vr,v,explicit=True):
        if isinstance(v,bytes):b=v
        elif vr=='US':b=struct.pack('<H',int(v))
        elif vr=='SS':b=struct.pack('<h',int(v))
        elif vr=='UL':b=struct.pack('<I',int(v))
        else:b=str(v).encode('ascii')
        if len(b)%2:b+=b'\0' if vr in {'UI','OB','OW'} else b' '
        h=struct.pack('<HH',*tag)
        if not explicit:return h+struct.pack('<I',len(b))+b
        return h+vr.encode()+(b'\0\0'+struct.pack('<I',len(b)) if vr in LONG_VR else struct.pack('<H',len(b)))+b
    meta=b''.join([elem((2,1),'OB',b'\0\1'),elem((2,2),'UI',sop),elem((2,3),'UI',uid),
                  elem((2,0x10),'UI',IMPLICIT_LE if implicit else EXPLICIT_LE),elem((2,0x12),'UI','2.25.117220432379489930409')])
    fields={(8,8):('CS','ORIGINAL\\PRIMARY'),(8,0x16):('UI',sop),(8,0x18):('UI',uid),(8,0x60):('CS','MG'),
       (0x12,0x62):('CS','YES'),(0x18,0x5101):('CS','CC'),(0x20,0x62):('CS','L'),
       (0x28,2):('US',1),(0x28,4):('CS','MONOCHROME2'),(0x28,0x10):('US',a.shape[0]),(0x28,0x11):('US',a.shape[1]),
       (0x28,0x100):('US',16),(0x28,0x101):('US',12),(0x28,0x102):('US',11),(0x28,0x103):('US',0),
       (0x28,0x301):('CS','NO'),(0x7fe0,0x10):('OW',a.astype('<u2').tobytes())}
    if tags:fields.update(tags)
    ds=b''.join(elem(t,vr,v,not implicit) for t,(vr,v) in sorted(fields.items()))
    return b'\0'*128+b'DICM'+elem((2,0),'UL',len(meta))+meta+ds
