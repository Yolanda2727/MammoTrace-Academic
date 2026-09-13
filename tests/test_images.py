from io import BytesIO
import numpy as np
import pytest
from PIL import Image
from mammoapp.images import load_image, KINDS,image_statistics,png_bytes
from mammoapp.examples import image_bytes
from mammotrace.errors import ResearchError

@pytest.mark.parametrize('fmt,ext',[('PNG','png'),('JPEG','jpg'),('JPEG','jpeg'),('TIFF','tif'),('TIFF','tiff'),('BMP','bmp'),('WEBP','webp'),('DICOM','dcm'),('DICOM','dicom')])
def test_all_formats_read_content(fmt,ext):
    record=load_image(image_bytes('ED03',fmt),'image.'+ext)
    assert record.display.ndim==2 and record.display.dtype==np.uint8
    assert record.legacy_input.shape==(224,224,3) and record.legacy_input.dtype==np.float32
    assert 0<=record.legacy_input.min()<record.legacy_input.max()<=1
    assert 'filename' not in record.technical

@pytest.mark.parametrize('fmt',['PNG','JPEG','TIFF','BMP','WEBP','DICOM'])
@pytest.mark.parametrize('kind',KINDS[1:])
def test_other_modalities_have_no_inference(fmt,kind):
    ext={'DICOM':'dcm','JPEG':'jpg'}.get(fmt,fmt.lower())
    r=load_image(image_bytes('ED02',fmt),'i.'+ext,kind)
    assert r.legacy_input is None
    assert any('bloqueado' in w for w in r.warnings)

@pytest.mark.parametrize('name',['image.jpg','image.tiff','image.bmp','image.webp','image.dcm','image.pdf','image.svg','image'])
def test_renaming_does_not_convert(name):
    with pytest.raises(ResearchError):load_image(image_bytes('ED01','PNG'),name)

@pytest.mark.parametrize('bad',[b'',b'garbage',b'%PDF-1.7',b'PK\x03\x04xxxx'])
def test_bad_content(bad):
    with pytest.raises(ResearchError):load_image(bad,'test.png')

def test_16_bit_tiff_is_not_truncated():
    r=load_image(image_bytes('ED01','TIFF'),'test.tiff')
    assert r.technical['source_mode']=='I;16'
    assert np.unique(r.legacy_input).size>256

def test_multipage_tiff_rejected():
    im=Image.fromarray(np.arange(1024,dtype=np.uint16).reshape(32,32));b=BytesIO()
    im.save(b,format='TIFF',save_all=True,append_images=[im])
    with pytest.raises(ResearchError) as e:load_image(b.getvalue(),'test.tiff')
    assert e.value.code=='MULTIFRAME'

@pytest.mark.parametrize('shape',[(1,1),(15,100),(8193,16)])
def test_dimensions(shape):
    b=BytesIO();Image.fromarray(np.zeros(shape,dtype=np.uint8)).save(b,format='PNG')
    with pytest.raises(ResearchError):load_image(b.getvalue(),'i.png')

def test_constant_png_rejected():
    b=BytesIO();Image.new('L',(32,32),3).save(b,format='PNG')
    with pytest.raises(ResearchError) as e:load_image(b.getvalue(),'i.png')
    assert e.value.code=='CONSTANT_IMAGE'

def test_image_budget(monkeypatch):
    monkeypatch.setattr('mammoapp.images.MAX_IMAGE',10)
    with pytest.raises(ResearchError):load_image(b'a'*11,'i.png')

def test_preview_descriptors_not_risk():
    r=load_image(image_bytes('ED01','PNG'),'i.png');d=image_statistics(r)
    assert 0<=d['entropia_bits_del_visor']<=8
    assert 'no determinan' in d['interpretacion']
    assert png_bytes(r.display).startswith(b'\x89PNG')

def test_colored_photo_not_mammogram():
    a=np.zeros((32,32,4),dtype=np.uint8);a[:,:,0]=np.arange(32)*7;a[:,:,3]=255
    b=BytesIO();Image.fromarray(a).save(b,format='PNG')
    r=load_image(b.getvalue(),'foto.png',KINDS[2]);assert r.legacy_input is None
    assert any('luminancia' in w for w in r.warnings)
