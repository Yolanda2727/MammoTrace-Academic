import struct
import numpy as np
import cv2
import pytest
from mammotrace.dicom import read_dicom,transform,safe_preview,Parser
from mammotrace.phantom import encode_dicom,phantom_array
from mammotrace.errors import ResearchError

@pytest.mark.parametrize('implicit',[False,True])
def test_supported_transfer_syntax(implicit):
    x=read_dicom(encode_dicom(implicit=implicit));assert x.pixels.shape==(512,384);assert x.technical['modality']=='MG'
@pytest.mark.parametrize('payload',[b'',b'not a dicom',b'\0'*128+b'NOTD',b'%PDF-1.7',b'PK\3\4'+b'\0'*1000])
def test_reject_non_dicom(payload):
    with pytest.raises(ResearchError,match='DICOM'):read_dicom(payload)
@pytest.mark.parametrize('tag,value,code',[
 ((8,0x60),('CS','CT'),'MODALITY'),((8,0x16),('UI','1.2.3'),'SOP_CLASS'),
 ((0x28,8),('IS','2'),'MULTIFRAME'),((0x28,4),('CS','RGB'),'GRAYSCALE'),
 ((0x28,2),('US',3),'GRAYSCALE'),((0x28,0x301),('CS','YES'),'BURNED_IN'),
 ((0x28,0x301),('CS',''),'BURNED_IN'),((0x28,0x100),('US',32),'BITS'),
 ((0x28,0x102),('US',10),'BITS'),((0x28,0x103),('US',3),'BITS'),
 ((0x28,0x10),('US',15),'PIXEL_LIMIT'),((0x28,0x10),('US',9000),'PIXEL_LIMIT'),
 ((0x28,0x11),('US',383),'PIXEL_LENGTH'),((0x7fe0,0x10),('OW',b'\0\0'),'PIXEL_LENGTH'),
 ((0x10,0x10),('PN','PRIVATE^PERSON'),'IDENTIFIERS'),((0x10,0x30),('DA','19700101'),'IDENTIFIERS'),
 ((8,0x80),('LO','PRIVATE INSTITUTION'),'IDENTIFIERS'),((0x11,0x10),('LO','PRIVATE'),'PRIVATE_TAG'),
 ((0x11,0x1010),('SQ',b''),'PRIVATE_TAG'),((0x6000,0x3000),('OW',b'\0\0'),'OVERLAY'),
 ((0x0008,0x1200),('UN',b'ab'),'UNKNOWN_CONTENT')])
def test_rejection_controls(tag,value,code):
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(tags={tag:value}))
    assert e.value.code==code

def test_identifiers_not_echoed():
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(tags={(0x10,0x10):('PN','SECRET^NAME')}))
    assert 'SECRET' not in e.value.message

def test_empty_patient_name_is_allowed():assert read_dicom(encode_dicom(tags={(0x10,0x10):('PN','')}))
def test_pseudonym_requires_declaration():
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(tags={(0x10,0x20):('LO','P001'),(0x12,0x62):('CS','NO')}))
    assert e.value.code=='PATIENT_ID'
def test_constant_image_rejected():
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(np.ones((32,32),np.uint16)))
    assert e.value.code=='CONSTANT_IMAGE'
@pytest.mark.parametrize('cut',[1,2,30,100,1024])
def test_truncated_pixel_data_rejected(raw,cut):
    with pytest.raises(ResearchError):read_dicom(raw[:-cut])

def test_implicit_unknown_tag_rejected():
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(implicit=True,tags={(8,0x9998):('LO','test')}))
    assert e.value.code=='IMPLICIT_TAG'
def test_compressed_transfer_syntax_rejected(raw):
    altered=raw.replace(b'1.2.840.10008.1.2.1\0',b'1.2.840.10008.1.2.5\0',1)
    with pytest.raises(ResearchError) as e:read_dicom(altered)
    assert e.value.code=='TRANSFER_SYNTAX'
def test_pixel_cap(raw):
    with pytest.raises(ResearchError) as e:read_dicom(raw,max_pixels=100)
    assert e.value.code=='PIXEL_LIMIT'
def test_legacy_equivalence_exact(raw):
    d=read_dicom(raw);x=transform(d,'legacy');a=d.pixels/d.pixels.max();a=cv2.resize(a,(224,224),interpolation=cv2.INTER_AREA);a=np.repeat(a[...,None],3,-1)
    np.testing.assert_array_equal(x,a)
@pytest.mark.parametrize('pipeline,maximum',[('legacy',1),('standardized_v3',255)])
def test_tensor_shape_dtype_range(raw,pipeline,maximum):
    x=transform(read_dicom(raw),pipeline);assert x.shape==(224,224,3);assert x.dtype==np.float32;assert 0<=x.min()<=x.max()<=maximum;assert np.isfinite(x).all()
def test_mono1_standardized_inverts():
    a=read_dicom(encode_dicom());b=read_dicom(encode_dicom(tags={(0x28,4):('CS','MONOCHROME1')}))
    np.testing.assert_allclose(transform(a,'standardized_v3')+transform(b,'standardized_v3'),255,atol=1e-3)
def test_legacy_mono1_preserved_not_silently_corrected():
    a=read_dicom(encode_dicom());b=read_dicom(encode_dicom(tags={(0x28,4):('CS','MONOCHROME1')}));np.testing.assert_array_equal(transform(a,'legacy'),transform(b,'legacy'))
@pytest.mark.parametrize('tag,value,code',[
 ((0x28,0x1053),('DS','nan'),'RESCALE'),((0x28,0x1053),('DS','0'),'RESCALE'),
 ((0x28,0x1050),('DS','100'),'WINDOW'),((0x2050,0x20),('CS','INVERSE'),'PRESENTATION_LUT'),
 ((0x28,0x3010),('SQ',b''),'LUT_UNSUPPORTED')])
def test_standard_pipeline_fail_closed(tag,value,code):
    d=read_dicom(encode_dicom(tags={tag:value}))
    with pytest.raises(ResearchError) as e:transform(d,'standardized_v3')
    assert e.value.code==code

def test_window_rescale_supported():
    d=read_dicom(encode_dicom(tags={(0x28,0x1053):('DS','2'),(0x28,0x1052):('DS','-100'),(0x28,0x1050):('DS','2000'),(0x28,0x1051):('DS','4000')}))
    assert np.isfinite(transform(d,'standardized_v3')).all()
def test_preview_preserves_aspect(raw):
    a=safe_preview(read_dicom(raw));assert a.shape==(512,384);assert a.dtype==np.uint8

def test_nested_identifier_rejected():
    name=b'SECRET^NESTED ';name+=b' '*(len(name)%2)
    pn=struct.pack('<HH',0x10,0x10)+b'PN'+struct.pack('<H',len(name))+name
    item=struct.pack('<HHI',0xfffe,0xe000,len(pn))+pn
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(tags={(8,0x1115):('SQ',item)}))
    assert e.value.code=='IDENTIFIERS'
def test_indefinite_sequence_parser():
    raw=struct.pack('<HH',8,0x1115)+b'SQ\0\0'+struct.pack('<I',0xffffffff)+struct.pack('<HHI',0xfffe,0xe000,0xffffffff)+struct.pack('<HHI',0xfffe,0xe00d,0)+struct.pack('<HHI',0xfffe,0xe0dd,0)
    fields,pos=Parser(raw).dataset(0,len(raw),True);assert (8,0x1115) in fields;assert pos==len(raw)
def test_invalid_sequence_delimiter_rejected():
    with pytest.raises(ResearchError):read_dicom(encode_dicom(tags={(8,0x1115):('SQ',b'abcdabcd')}))
def test_duplicate_attribute_rejected(raw):
    extra=struct.pack('<HH',0x28,0x10)+b'US'+struct.pack('<HH',2,512)
    with pytest.raises(ResearchError) as e:read_dicom(raw+extra)
    assert e.value.code=='DICOM_DUPLICATE_TAG'
def test_numeric_multiplicity_rejected():
    with pytest.raises(ResearchError) as e:read_dicom(encode_dicom(tags={(0x28,0x10):('US',struct.pack('<HH',512,512))}))
    assert e.value.code=='DICOM_NUMBER'
