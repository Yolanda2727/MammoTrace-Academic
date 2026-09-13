"""Verifica archivos entregados. No cubre datos creados después de la entrega."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    try:entries=json.loads((ROOT/'SHA256SUMS.json').read_text())
    except Exception:print('No existe el manifiesto de la entrega.');return 1
    failed=[]
    for name,digest in entries.items():
        path=ROOT/name
        if not path.resolve().is_relative_to(ROOT.resolve()):failed.append(name);continue
        try:
            with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        except OSError:failed.append(name);continue
        if actual!=digest:failed.append(name)
    print(json.dumps({'checked':len(entries),'failed':failed},ensure_ascii=False,indent=2))
    return int(bool(failed))
if __name__=='__main__':raise SystemExit(main())
