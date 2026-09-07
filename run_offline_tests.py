"""Run regression tests without access to employer/network or live runtimes."""
import sys
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def forbid_live_io(event, args):
    if event == 'socket.connect':
        sock, address = args
        if sock.family != socket.AF_UNIX or not isinstance(address, str) or not address.startswith(('/private/var/folders/', '/var/folders/', '/tmp/')):
            raise RuntimeError('offline test guard: real network/browser connection forbidden')
    if event == 'subprocess.Popen':
        command = args[1]
        text = ' '.join(map(str, command)) if isinstance(command, (list, tuple)) else str(command)
        if any(part in text for part in ['google_api.py', '/Documents/job-agent/', 'security find-', '/.hermes/cache/landedhq-job/', 'osascript', 'Google Chrome']):
            raise RuntimeError('offline test guard: external application or private runtime forbidden')

class OfflineOnly:
    """Do not let additional CLI flags accidentally re-enable browser fixtures."""
    def pytest_collection_modifyitems(self, config, items):
        browser_files = {
            ROOT/'tests/test_local_cdp_operator.py',
            ROOT/'tests/test_production_operator_live_chrome.py',
        }
        excluded=[]
        kept=[]
        for item in items:
            path=Path(item.path).resolve()
            browser_demo=(path==ROOT/'tests/test_production_operator.py'
                and getattr(item,'originalname',None)=='test_cli_runs_and_audits_full_sanitized_learned_ats_operator_under_targets')
            (excluded if path in browser_files or browser_demo else kept).append(item)
        items[:]=kept
        if excluded:
            config.hook.pytest_deselected(items=excluded)


sys.addaudithook(forbid_live_io)
import pytest
if __name__ == '__main__':
    args=sys.argv[1:] or [str(ROOT/'tests'),'-q']
    args += ['--ignore='+str(ROOT/'tests/test_local_cdp_operator.py'),
             '--ignore='+str(ROOT/'tests/test_production_operator_live_chrome.py')]
    raise SystemExit(pytest.main(args, plugins=[OfflineOnly()]))
