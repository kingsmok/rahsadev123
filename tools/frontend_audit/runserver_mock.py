"""Dev server for the audit with ONLY the outbound Zarinpal API call mocked.

The sandbox has no route to api.zarinpal.com, so `GATEWAYS['zarinpal'].start`
is replaced by a stub returning the URL format the real adapter returns.
Every other part of the request path (views, CSP middleware, templates) is the
real code.  Run with use_reloader=False so the patch lives in the server process.
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MasaiShop.settings")
import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.conf import settings  # noqa: E402

if not settings.DEBUG:
    # It rewrites the Zarinpal row in GatewaySettings: never against production.
    sys.exit('runserver_mock.py is a local testing tool; it refuses to run with DEBUG=False.')

from payments import services  # noqa: E402
from payments.gateways import ZARINPAL_SANDBOX  # noqa: E402
from payments.models import GatewaySettings  # noqa: E402


def fake_start(transaction, callback_url):
    authority = f"A{transaction.pk:035d}"
    return authority, f"{ZARINPAL_SANDBOX['start']}{authority}"


services.GATEWAYS["zarinpal"].start = fake_start
GatewaySettings.objects.filter(key="zarinpal").update(
    is_enabled=True, is_sandbox=True, merchant_id="00000000-0000-0000-0000-000000000000"
)
addr = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8000"
call_command("runserver", addr, use_reloader=False, use_threading=True)
