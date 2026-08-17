import sys
import tempfile
from pathlib import Path


def pytest_configure(config):
    """Keep Windows test paths short and outside Dropbox's sync locks."""
    if sys.platform == "win32" and config.option.basetemp is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / "crm_invoice_pytest"
