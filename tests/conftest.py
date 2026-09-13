from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mammotrace.phantom import encode_dicom
@pytest.fixture(scope='session')
def raw():return encode_dicom()
