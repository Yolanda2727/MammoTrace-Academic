"""Native acceptance tests; require Streamlit installed. Not replaced by mocks."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
CBIS_NAMES=('calc_case_description_train_set.csv','calc_case_description_test_set.csv','mass_case_description_train_set.csv','mass_case_description_test_set.csv')
pytestmark=pytest.mark.skipif(not all((ROOT/'data/cbis'/name).is_file() for name in CBIS_NAMES), reason='CBIS-DDSM metadata are not redistributed in the public source tree')

def test_cbis_navigation():
    at=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    at.sidebar.radio(key='page').set_value('6 · CBIS-DDSM y cohortes').run(timeout=30)
    assert not at.exception
    assert any(m.value=='3568' for m in at.metric)

def test_cbis_partition_acknowledgment():
    at=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    at.sidebar.radio(key='page').set_value('6 · CBIS-DDSM y cohortes').run(timeout=30)
    at.checkbox(key='cbis_split_confirm').check().run(timeout=30)
    assert not at.exception
