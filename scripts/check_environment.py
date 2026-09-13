"""Comprueba dependencias instaladas; no declara una validación clínica."""
from __future__ import annotations
import importlib.util,importlib.metadata,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
NAMES={'streamlit':'streamlit','numpy':'numpy','pandas':'pandas','Pillow':'PIL','opencv-python-headless':'cv2',
       'reportlab':'reportlab','pypdf':'pypdf','defusedxml':'defusedxml','requests':'requests','scikit-learn':'sklearn'}

def main():
    full=(ROOT/'models/parts.json').exists() or (ROOT/'models/modelo.h5').exists()
    names={**NAMES,**({'torch':'torch','keras':'keras','h5py':'h5py'} if full else {})}
    missing=[]
    print('Python',sys.version.split()[0],'| Perfil:', 'completo privado' if full else 'sin pesos')
    if sys.version_info[:2]!=(3,13):print('[AVISO] Esta entrega fue preparada para Python 3.13; otra versión requiere comprobación.')
    for distribution,module in names.items():
        try:
            if importlib.util.find_spec(module) is None:raise ModuleNotFoundError()
            print('[OK]',distribution,importlib.metadata.version(distribution))
        except (ModuleNotFoundError,importlib.metadata.PackageNotFoundError):
            missing.append(distribution);print('[FALTA]',distribution)
    if full:
        from mammoapp.xai import ensure_legacy_weights
        try:ensure_legacy_weights();print('[OK] Integridad del modelo legado conocida.')
        except Exception:missing.append('pesos');print('[FALTA] Pesos o integridad; no hay inferencia sustitutiva.')
    print('Esto no prueba todavía la interfaz ni el despliegue. Ejecute pytest tests_streamlit y abra la aplicación.')
    return 1 if missing else 0
if __name__=='__main__':raise SystemExit(main())
