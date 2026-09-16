"""
Import-isolation test for local-only deployments.

Importing the app and the pure matcher must not pull in the heavy cloud ML
stack, otherwise a lite image would fail to boot (and would not fit in a small
free-tier instance). We run this in a subprocess so other tests that do import
InsightFace cannot mask the result.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

CHECK = (
    "import sys\n"
    "import main  # noqa: F401\n"
    "import services.matching  # noqa: F401\n"
    "heavy = [m for m in ('insightface', 'cv2', 'onnxruntime', 'PIL') "
    "if m in sys.modules]\n"
    "print(','.join(heavy))\n"
    "raise SystemExit(1 if heavy else 0)\n"
)


def test_lite_import_does_not_load_heavy_stack():
    result = subprocess.run(
        [sys.executable, "-c", CHECK],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Heavy modules were imported: {result.stdout.strip()}\n{result.stderr}"
    )
