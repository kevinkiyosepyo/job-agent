import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_extra_pytest_flags_cannot_remove_browser_exclusions(monkeypatch):
    observed={}
    excluded=[]
    def main(args, **kwargs):
        plugins=kwargs.get('plugins',[])
        observed['plugin_count']=len(plugins)
        if plugins:
            items=[
                SimpleNamespace(path=ROOT/'tests/test_local_cdp_operator.py',originalname='test_anything'),
                SimpleNamespace(path=ROOT/'tests/test_production_operator_live_chrome.py',originalname='test_anything'),
                SimpleNamespace(path=ROOT/'tests/test_production_operator.py',originalname='test_cli_runs_and_audits_full_sanitized_learned_ats_operator_under_targets'),
                SimpleNamespace(path=ROOT/'tests/test_production_operator.py',originalname='ordinary'),
            ]
            config=SimpleNamespace(hook=SimpleNamespace(pytest_deselected=lambda items:excluded.extend(items)))
            plugins[0].pytest_collection_modifyitems(config,items)
            observed['kept']=[item.originalname for item in items]
        return 0
    with monkeypatch.context() as m:
        m.setitem(sys.modules,'pytest',SimpleNamespace(main=main))
        m.setattr(sys,'argv',[str(ROOT/'run_offline_tests.py'),'--junitxml=not-created.xml'])
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(ROOT/'run_offline_tests.py'),run_name='__main__')
    assert exit_info.value.code==0
    assert observed['plugin_count']==1
    assert observed['kept']==['ordinary']
    assert len(excluded)==3
