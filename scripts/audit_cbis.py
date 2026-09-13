"""Reproduce CBIS audit and explicit holdout-priority partition; never train."""
from pathlib import Path
import argparse,csv,json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mammoapp.cbis import *

def run(data:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True);rows=read_bundle(data)
    manifest=read_manifest((data/'download_manifest.tcia').read_bytes())
    dr=list(csv.DictReader((data/'digest_export.csv').open(encoding='utf-8-sig',newline='')))
    dl,rep=read_download_metadata((data/'metadata_drive_original.csv').read_bytes())
    a=audit(rows,manifest,dr,dl);parts=partition(rows,'holdout_priority');images=image_inventory(parts)
    a['metadata_decimal_repairs']=len(rep)
    a['partitions']={p:{'rows':sum(r['partition']==p for r in parts),'subjects':len({r['patient_id'] for r in parts if r['partition']==p})} for p in ('train','validation','test','excluded_overlap')}
    a['image_inventory']={p:{'series':sum(r['partition']==p for r in images),'eligible_series':sum(r['partition']==p and r['eligible_metadata'] for r in images)} for p in ('train','validation','test','excluded_overlap','ambiguous')}
    a['inputs_sha256']={p.name:digest(p.read_bytes()) for p in sorted(data.glob('*')) if p.is_file()}
    (out/'cbis_audit.json').write_text(json.dumps(a,indent=2,ensure_ascii=False))
    for name,rr in [('cohort_annotations.csv',rows),('partition_annotations.csv',parts),('image_inventory.csv',images),('metadata_normalized.csv',dl),('metadata_repairs.csv',rep),('overlap_subjects.csv',[{'patient_id':p} for p in a['overlap_subjects']])]:
        (out/name).write_bytes(csv_bytes(rr))
    return a
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=Path(__file__).resolve().parents[1]/'data/cbis');p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'reports/cbis');args=p.parse_args()
    print(json.dumps(run(args.data,args.out),indent=2,ensure_ascii=False))
