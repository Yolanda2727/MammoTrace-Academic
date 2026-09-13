"""Local-only index of authorized CBIS files; no external download or training."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mammoapp.cbis import read_bundle,csv_bytes
from mammoapp.cbis_dicom import read_cbis
from mammotrace.errors import ResearchError

def index(root:Path,data:Path):
    root=root.resolve(strict=True);rows=read_bundle(data)
    lookup={r[k+'_series_uid']:r['patient_id'] for r in rows for k in ('full','crop','mask')}
    full={r['full_series_uid'] for r in rows};out=[];errors=[]
    paths=sorted(p for p in root.rglob('*') if p.suffix.lower() in ('.dcm','.dicom'))
    if len(paths)>20000:raise ValueError('Máximo 20.000 archivos por ejecución.')
    for path in paths:
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size>64*1024*1024:raise ValueError('path_or_size')
            im=read_cbis(path.read_bytes(),lookup,True)
            t=im.technical
            out.append({'path':path.relative_to(root).as_posix(),**t,'role_candidate':'full' if t['series_uid'] in full and not t['binary_pixels'] else 'mask_candidate' if t['binary_pixels'] else 'crop_candidate'})
        except ResearchError as e:errors.append({'path':path.relative_to(root).as_posix(),'error':e.code})
        except (OSError,ValueError):errors.append({'path':path.relative_to(root).as_posix(),'error':'path_or_io'})
    return out,errors
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[1]/'data/cbis');p.add_argument('--out',type=Path,default=Path('reports/local_index.csv'));a=p.parse_args()
    rows,errs=index(a.root,a.data);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(csv_bytes(rows));a.out.with_suffix('.errors.json').write_text(json.dumps(errs,indent=2))
    print(json.dumps({'files_verified':len(rows),'rejected':len(errs),'coverage_is_only_local_scanned_root':True}))
