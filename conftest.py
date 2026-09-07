from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TMP_ROOT = Path(__file__).resolve().parent / ".test_tmp"
_TMP_ROOT.mkdir(exist_ok=True)

for key in ("TMPDIR", "TEMP", "TMP"):
    os.environ[key] = str(_TMP_ROOT)

tempfile.tempdir = str(_TMP_ROOT)
