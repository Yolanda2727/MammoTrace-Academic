"""Evalúa un CSV local aportado; nunca afirma desempeño del modelo a partir de otro CSV."""
from pathlib import Path
import sys,argparse,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mammotrace.evaluation import evaluate_csv
from mammotrace.errors import ResearchError

def main():
    p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--bootstrap',type=int,default=300)
    args=p.parse_args()
    try:
        if args.csv.stat().st_size>10*1024*1024:raise ValueError('CSV mayor de 10 MiB.')
        result=evaluate_csv(args.csv.read_bytes(),bootstrap=args.bootstrap)
        print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,ResearchError) as e:
        print('No se completó la evaluación:',e,file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
