import sys
from pathlib import Path

# Ensure the backend root is on sys.path so `import app.*` works in all tests.
_backend_root = str(Path(__file__).parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)
