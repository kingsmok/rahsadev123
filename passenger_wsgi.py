"""cPanel/Passenger entry point with a no-SSH installation fallback."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# A fresh upload has no .env, so Django cannot safely start. Serve the
# dependency-free browser installer until setup succeeds. The marker keeps the
# installer available after an interrupted/failed installation.
if not (PROJECT_ROOT / ".env").exists() or (PROJECT_ROOT / ".installing").exists():
    from web_installer import application
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MasaiShop.settings")
    from MasaiShop.wsgi import application
