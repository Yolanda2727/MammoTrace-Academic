from pathlib import Path
import pytest
from mammoapp.config import ROOT
from mammoapp.documents import read_report,confirm_category
from mammoapp.images import load_image
from mammoapp.examples import CASES

@pytest.mark.parametrize('code',list(CASES))
def test_packaged_example_files_match_scenarios(code):
    p=ROOT/'examples'
    assert load_image((p/f'{code}_FANTOMA.png').read_bytes(),'phantom.png').display.size>0
    d=read_report((p/f'{code}_INFORME_FICTICIO.txt').read_bytes(),'r.txt')
    if CASES[code]['category']:
        assert confirm_category(d.text,CASES[code]['category'],True)==CASES[code]['category']

@pytest.mark.parametrize('ext',['txt','pdf','docx'])
def test_packaged_ed03_report_formats(ext):
    p=ROOT/'examples'/('ED03_INFORME_FICTICIO.'+ext)
    d=read_report(p.read_bytes(),p.name)
    assert confirm_category(d.text,'4A',True)=='4A'
