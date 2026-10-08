#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  فایل‌مارکت — اسکریپت اجرای سریع (لینوکس / مک)
#  ────────────────────────────────────────────────────────────────────
#  معادل run.bat: ساخت venv، نصب وابستگی‌ها، ساخت .env محلی، migrate،
#  ساخت کاربر مدیر پیش‌فرض و اجرای سرور توسعه.
#
#  نمونه:  ./run.sh
#  نمونه:  ./run.sh reza My-Long-Pass-123
#  نمونه:  ./run.sh admin admin1234 9000 --seed
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

cd "$(dirname "$0")"

ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin1234"
ADMIN_EMAIL="admin@example.test"
PORT="8000"
SEED_DATA=0
OPEN_BROWSER=1

POSITIONAL=0
for arg in "$@"; do
    case "$arg" in
        --seed) SEED_DATA=1 ;;
        --no-browser) OPEN_BROWSER=0 ;;
        *)
            POSITIONAL=$((POSITIONAL + 1))
            case "$POSITIONAL" in
                1) ADMIN_USERNAME="$arg" ;;
                2) ADMIN_PASSWORD="$arg" ;;
                3) PORT="$arg" ;;
            esac
            ;;
    esac
done

echo ""
echo "══════════════════════════════════════════════════"
echo "  فایل‌مارکت — راه‌اندازی و اجرای فروشگاه"
echo "══════════════════════════════════════════════════"

# ۱) پیدا کردن پایتون
echo "[1/6] جست‌وجوی پایتون ..."
if command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "[خطا] پایتون پیدا نشد. نسخهٔ ۳.۱۰ یا بالاتر را نصب کنید."
    exit 1
fi
"$PY_CMD" --version

# ۲) محیط مجازی
echo "[2/6] آماده‌سازی محیط مجازی (.venv) ..."
if [ ! -x ".venv/bin/python" ]; then
    "$PY_CMD" -m venv .venv
fi
VENV_PY=".venv/bin/python"

# ۳) نصب وابستگی‌ها
echo "[3/6] نصب بسته‌ها از requirements.txt ..."
"$VENV_PY" -m pip install --upgrade pip --disable-pip-version-check >/dev/null
"$VENV_PY" -m pip install --disable-pip-version-check -r requirements.txt

# ۴) فایل .env محلی
echo "[4/6] بررسی فایل .env ..."
if [ ! -f ".env" ]; then
    "$VENV_PY" -c "import secrets, pathlib; pathlib.Path('.env').write_text('# ساخته‌شده توسط run.sh — فقط برای توسعه\nDEBUG=True\nSECRET_KEY=' + secrets.token_urlsafe(64) + '\nALLOWED_HOSTS=localhost,127.0.0.1\n', encoding='utf-8')"
    echo "      فایل .env ساخته شد (DEBUG=True + کلید مخفی تصادفی)."
else
    echo "      فایل .env از قبل وجود دارد؛ تغییر نکرد."
fi

# ۵) پایگاه داده + کاربر مدیر
echo "[5/6] ساخت جدول‌های پایگاه داده ..."
"$VENV_PY" manage.py migrate --noinput

if [ "$SEED_DATA" = "1" ]; then
    echo "      ساخت داده‌های نمونه ..."
    "$VENV_PY" manage.py seed_demo
fi

echo "      ساخت کاربر مدیر پیش‌فرض ..."
"$VENV_PY" manage.py create_default_admin \
    --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --email "$ADMIN_EMAIL"

# ۶) اجرای سرور
port_in_use() {
    "$VENV_PY" -c "import socket, sys; s = socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) == 0 else 1)" "$1"
}
ATTEMPTS=0
while port_in_use "$PORT" && [ "$ATTEMPTS" -lt 20 ]; do
    echo "      پورت $PORT اشغال است؛ پورت $((PORT + 1)) امتحان می‌شود ..."
    PORT=$((PORT + 1))
    ATTEMPTS=$((ATTEMPTS + 1))
done
echo "[6/6] اجرای سرور توسعه روی پورت $PORT ..."
echo ""
echo "══════════════════════════════════════════════════"
echo "  فروشگاه        http://127.0.0.1:$PORT/"
echo "  پنل مدیریت     http://127.0.0.1:$PORT/admin-panel/"
echo "  ادمین جنگو     http://127.0.0.1:$PORT/admin/"
echo "  کاربر / رمز    $ADMIN_USERNAME / $ADMIN_PASSWORD"
echo "  توقف سرور      Ctrl+C"
echo "══════════════════════════════════════════════════"
echo ""

if [ "$OPEN_BROWSER" = "1" ] && command -v xdg-open >/dev/null 2>&1; then
    ( sleep 4 && xdg-open "http://127.0.0.1:$PORT/admin-panel/" >/dev/null 2>&1 ) &
fi

exec "$VENV_PY" manage.py runserver "0.0.0.0:$PORT"
