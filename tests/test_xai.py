import importlib.util,json
from pathlib import Path
import numpy as np
import pytest
from mammoapp.config import ROOT
from mammoapp.xai import ExplainableLegacy,heatmap_overlay,ensure_legacy_weights,ORIGINAL_SHA256
from mammoapp.images import load_image
from mammoapp.examples import image_bytes
from mammotrace.errors import ResearchError

@pytest.fixture(scope='module')
def model():
    if importlib.util.find_spec('torch') is None or importlib.util.find_spec('keras') is None:
        pytest.skip('Perfil sin motor de modelo; no se simula inferencia.')
    if not (ROOT/'models/parts.json').exists() and not (ROOT/'models/modelo.h5').exists():
        pytest.skip('Paquete público sin pesos.')
    return ExplainableLegacy()

@pytest.fixture(scope='module')
def image():return load_image(image_bytes('ED03','DICOM'),'phantom.dcm')

def test_original_weights_hash(model):assert model.service.manifest['sha256']==ORIGINAL_SHA256

def test_logits_match_softmax(model,image):
    scores=model.service.predict_batch(image.legacy_input)[0]
    logits=model.logits_batch(image.legacy_input)[0];expected=np.exp(logits-logits.max());expected/=expected.sum()
    np.testing.assert_allclose(scores,expected,rtol=5e-5,atol=1e-6)

def test_real_49_occlusion(model,image):
    result=model.explain(image.legacy_input)
    a=np.array(result['signed_delta'])
    assert a.shape==(7,7) and np.isfinite(a).all()
    assert result['score']['clinical_recommendation'] is None
    assert result['method']=='occlusion_logit'
    assert result['model_sha256']==ORIGINAL_SHA256
    overlay=heatmap_overlay(image.legacy_input,result)
    if result['informative_numerically']:assert overlay.shape==(224,224,3)
    assert result['coordinates'].startswith('tensor')

def test_no_flat_heatmap_fabricated(image):
    assert heatmap_overlay(image.legacy_input,{'signed_delta':np.zeros((7,7)).tolist()}) is None

def test_missing_model_does_not_invent(tmp_path):
    with pytest.raises(ResearchError) as e:ensure_legacy_weights(tmp_path)
    assert e.value.code=='MODEL_ABSENT'

def test_corrupt_weight_rejected(tmp_path):
    (tmp_path/'modelo.h5').write_bytes(b'corrupt')
    with pytest.raises(ResearchError) as e:ensure_legacy_weights(tmp_path)
    assert e.value.code=='MODEL_HASH'

def test_manifest_traversal_rejected(tmp_path):
    m={'sha256':ORIGINAL_SHA256,'parts':[{'name':'../bad','size':1,'sha256':'0'*64}]}
    (tmp_path/'parts.json').write_text(json.dumps(m))
    with pytest.raises(ResearchError):ensure_legacy_weights(tmp_path)
    assert not (tmp_path/'modelo.assembling').exists()

def test_bad_tensor_rejected(model):
    with pytest.raises(ResearchError):model.logits_batch(np.ones((12,12,3)))
    with pytest.raises(ResearchError):model.logits_batch(np.ones((224,224,3))*255)

def test_bad_grid_rejected(model,image):
    with pytest.raises(ResearchError):model.explain(image.legacy_input,8)

def test_assemble_real_original_parts(tmp_path):
    import os,hashlib
    index=ROOT/'models/parts.json'
    if not index.exists():pytest.skip('Edición sin partes privadas.')
    manifest=json.loads(index.read_text())
    (tmp_path/'parts.json').write_text(index.read_text())
    for part in manifest['parts']:
        os.link(ROOT/'models'/part['name'],tmp_path/part['name'])
    assembled=ensure_legacy_weights(tmp_path)
    with assembled.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==ORIGINAL_SHA256
    assert assembled.stat().st_size==98094968
