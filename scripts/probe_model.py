"""Prueba real de integración y oclusión; exclusivamente fantoma sintético."""
from pathlib import Path
import sys,time,json,platform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mammoapp.examples import image_bytes
from mammoapp.images import load_image,png_bytes
from mammoapp.xai import ExplainableLegacy,heatmap_overlay
start=time.monotonic();image=load_image(image_bytes('ED03','DICOM'),'phantom.dcm')
print('Fantoma leído',flush=True)
model=ExplainableLegacy();print('Modelo cargado',round(time.monotonic()-start,3),flush=True)
result=model.explain(image.legacy_input)
print('Oclusión completada',round(time.monotonic()-start,3),flush=True)
record={'python':platform.python_version(),'platform':platform.platform(),'synthetic_only':True,
        'elapsed_seconds':round(time.monotonic()-start,3),'result':result}
(ROOT/'reports/model_probe.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
overlay=heatmap_overlay(image.legacy_input,result)
if overlay is not None:(ROOT/'reports/occlusion_phantom.png').write_bytes(png_bytes(overlay))
print('Salida guardada; sin inferencias clínicas.',flush=True)
