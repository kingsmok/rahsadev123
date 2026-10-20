"""Small, dependency-free web installer for hosting accounts without SSH.

This module is loaded by passenger_wsgi.py only while no .env exists or an
installation is in progress. It deliberately uses only Python's standard
library so it can install requirements before Django is importable.
"""

from __future__ import annotations

import hmac
import html
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
IN_PROGRESS = ROOT / ".installing"


def page(body: str, status: str = "200 OK"):
    document = f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>نصب فایل‌مارکت</title>
<style>body{{font-family:Tahoma,sans-serif;background:#f3f6f8;margin:0;color:#17242c}}main{{max-width:720px;margin:35px auto;background:#fff;padding:28px;border-radius:14px;box-shadow:0 8px 35px #1232}}label{{display:block;margin:14px 0 5px}}input,select{{box-sizing:border-box;width:100%;padding:11px;border:1px solid #b9c5ca;border-radius:7px}}button{{margin-top:20px;padding:12px 24px;border:0;border-radius:8px;background:#087f8c;color:white;font-weight:bold;cursor:pointer}}.error{{background:#fee;padding:12px;border-right:4px solid #c22}}.ok{{background:#e9fff1;padding:14px;border-right:4px solid #198754}}pre{{direction:ltr;text-align:left;white-space:pre-wrap;background:#17242c;color:#eaf7f8;padding:14px;border-radius:8px;max-height:420px;overflow:auto}}small{{color:#586970}}</style></head><body><main><h1>نصب فایل‌مارکت</h1>{body}</main></body></html>"""
    return status, [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(document.encode())))], [document.encode()]


def field(name, label, value="", kind="text", required=True):
    req = " required" if required else ""
    return f'<label for="{name}">{label}</label><input id="{name}" name="{name}" type="{kind}" value="{html.escape(value, quote=True)}"{req}>'


def form(error=""):
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return error_html + """<p>این صفحه اتصال دیتابیس، جدول‌ها و حساب مدیر را بدون SSH می‌سازد.</p>
<form method="post" autocomplete="off">
<label for="engine">نوع دیتابیس</label><select id="engine" name="engine"><option value="mysql">MySQL / MariaDB</option><option value="postgresql">PostgreSQL</option></select>""" + field("db_host", "هاست دیتابیس", "localhost") + field("db_port", "پورت دیتابیس", "3306") + field("db_name", "نام کامل دیتابیس (با پیشوند هاست)") + field("db_user", "نام کامل کاربر دیتابیس") + field("db_password", "رمز کاربر دیتابیس", kind="password") + field("domain", "دامنه سایت، بدون https://") + field("admin_user", "نام کاربری مدیر", "admin") + field("admin_email", "ایمیل مدیر", kind="email") + field("admin_password", "رمز مدیر (حداقل ۸ کاراکتر)", kind="password") + field("admin_confirm", "تکرار رمز مدیر", kind="password") + field("token", "کلید نصب تعریف‌شده در cPanel", kind="password") + """<button type="submit">بررسی اتصال و نصب کامل</button></form>
<p><small>این عملیات ممکن است یک تا چند دقیقه طول بکشد؛ صفحه را نبندید. کلید نصب در فایل یا دیتابیس ذخیره نمی‌شود.</small></p>"""


def command(args, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        raise RuntimeError(f"دستور ناموفق بود: {' '.join(args)}\n{result.stdout}")
    return result.stdout


def application(environ, start_response):
    configured_token = os.environ.get("INSTALLER_TOKEN", "")
    if not configured_token:
        response = page('<p class="error">ابتدا در بخش Environment Variables برنامه Python در cPanel یک مقدار قوی و تصادفی با نام <b>INSTALLER_TOKEN</b> تعریف و برنامه را Restart کنید.</p>', "503 Service Unavailable")
    elif environ.get("REQUEST_METHOD") != "POST":
        response = page(form())
    else:
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > 64 * 1024:
                raise ValueError("درخواست بیش از حد بزرگ است.")
            data = {k: v[-1].strip() for k, v in parse_qs(environ["wsgi.input"].read(length).decode("utf-8"), keep_blank_values=True).items()}
            if not hmac.compare_digest(data.get("token", ""), configured_token):
                raise ValueError("کلید نصب اشتباه است.")
            required = ("db_host", "db_port", "db_name", "db_user", "db_password", "domain", "admin_user", "admin_email", "admin_password")
            if any(not data.get(key) for key in required):
                raise ValueError("همه فیلدها الزامی هستند.")
            engine = data.get("engine")
            if engine not in {"mysql", "postgresql"}:
                raise ValueError("نوع دیتابیس نامعتبر است.")
            if not data["db_port"].isdigit() or not 1 <= int(data["db_port"]) <= 65535:
                raise ValueError("پورت دیتابیس نامعتبر است.")
            domain = data["domain"].lower().removeprefix("https://").removeprefix("http://").strip("/")
            if not re.fullmatch(r"[a-z0-9.-]+", domain):
                raise ValueError("دامنه نامعتبر است.")
            password = data["admin_password"]
            if password != data.get("admin_confirm"):
                raise ValueError("تکرار رمز مدیر یکسان نیست.")
            if len(password) < 8 or password == "admin1234":
                raise ValueError("رمز مدیر باید حداقل ۸ کاراکتر و غیر از admin1234 باشد.")

            scheme = "mysql" if engine == "mysql" else "postgresql"
            db_url = f'{scheme}://{quote(data["db_user"], safe="")}:{quote(data["db_password"], safe="")}@{data["db_host"]}:{data["db_port"]}/{quote(data["db_name"], safe="")}'
            config = "\n".join((
                "# Generated by the secure web installer", f"SECRET_KEY={secrets.token_urlsafe(64)}", "DEBUG=False",
                f"ALLOWED_HOSTS={domain},www.{domain}", f"CSRF_TRUSTED_ORIGINS=https://{domain},https://www.{domain}",
                "BEHIND_HTTPS_PROXY=0", f"SITE_URL=https://{domain}", f"DATABASE_URL={db_url}", "DB_CONN_MAX_AGE=0",
                "CACHE_URL=locmem://", "NOTIFICATIONS_ASYNC=1", "DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE=5242880",
                "DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE=1048576", "IMAGE_OPTIMIZATION_MAX_DIMENSION=1600",
                "IMAGE_OPTIMIZATION_WEBP_QUALITY=80", "LOG_LEVEL=INFO", ""
            ))
            IN_PROGRESS.write_text("Installation is not complete.\n", encoding="utf-8")
            if ENV_FILE.exists():
                shutil.copy2(ENV_FILE, ROOT / ".env.before-install")
            temporary = ROOT / ".env.installing.tmp"
            temporary.write_text(config, encoding="utf-8")
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
            temporary.replace(ENV_FILE)

            logs = []
            logs.append(command([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"]))
            logs.append(command([sys.executable, "manage.py", "check", "--database", "default"]))
            logs.append(command([sys.executable, "manage.py", "migrate", "--noinput"]))
            logs.append(command([sys.executable, "manage.py", "collectstatic", "--noinput"]))
            child = os.environ.copy()
            child.update(ADMIN_DEFAULT_USERNAME=data["admin_user"], ADMIN_DEFAULT_EMAIL=data["admin_email"], ADMIN_DEFAULT_PASSWORD=password)
            admin_log = command([sys.executable, "manage.py", "create_default_admin", "--reset-password"], child)
            logs.append(admin_log.replace(password, "********"))
            IN_PROGRESS.unlink(missing_ok=True)
            safe_logs = html.escape("\n".join(logs))
            response = page(f'<div class="ok"><b>نصب با موفقیت انجام شد.</b><br>نام کاربری مدیر: {html.escape(data["admin_user"])}<br><a href="/admin/">ورود به مدیریت</a></div><p>اکنون متغیر <b>INSTALLER_TOKEN</b> را از cPanel حذف و Python App را Restart کنید.</p><pre>{safe_logs}</pre>')
        except (ValueError, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            # Keep .installing after an operational failure so Passenger serves
            # this installer again rather than booting a half-installed site.
            response = page(form(str(exc)), "400 Bad Request")
    status, headers, body = response
    start_response(status, headers)
    return body
