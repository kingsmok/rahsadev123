@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title فایل‌مارکت — سرور توسعه

rem ══════════════════════════════════════════════════════════════════════
rem  فایل‌مارکت — اسکریپت اجرای سریع (ویندوز)
rem  ────────────────────────────────────────────────────────────────────
rem  کارها: ساخت venv، نصب وابستگی‌ها، ساخت .env محلی، migrate،
rem          ساخت کاربر مدیر پیش‌فرض و اجرای سرور توسعه
rem
rem  نمونه:  run.bat
rem  نمونه:  run.bat reza My-Long-Pass-123
rem  نمونه:  run.bat admin admin1234 9000 --seed
rem
rem  آپشن‌ها (هر جای آرگومان‌ها):
rem    --seed        پس از migrate داده‌های نمونه و کاربران demo را هم بساز
rem    --no-browser  مرورگر را خودکار باز نکن
rem ══════════════════════════════════════════════════════════════════════

rem ── مقدارهای پیش‌فرض ──
set "ADMIN_USERNAME=admin"
set "ADMIN_PASSWORD=admin1234"
set "ADMIN_EMAIL=admin@example.test"
set "PORT=8000"
set "SEED_DATA=0"
set "OPEN_BROWSER=1"
set "POS=0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--seed" (
    set "SEED_DATA=1"
    shift
    goto parse_args
)
if /i "%~1"=="--no-browser" (
    set "OPEN_BROWSER=0"
    shift
    goto parse_args
)
set /a POS+=1
if %POS%==1 set "ADMIN_USERNAME=%~1"
if %POS%==2 set "ADMIN_PASSWORD=%~1"
if %POS%==3 set "PORT=%~1"
shift
goto parse_args
:args_done

echo.
echo ══════════════════════════════════════════════════
echo   فایل‌مارکت — راه‌اندازی و اجرای فروشگاه
echo ══════════════════════════════════════════════════
echo.

rem ── ۱) پیدا کردن پایتون ──
echo [1/6] جست‌وجوی پایتون ...
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if defined PY_CMD goto python_found
where python >nul 2>nul && set "PY_CMD=python"
if defined PY_CMD goto python_found
echo [خطا] پایتون پیدا نشد. نسخهٔ ۳.۱۰ یا بالاتر را نصب کنید و تیک
echo        "Add python.exe to PATH" را هنگام نصب بزنید.
echo        دانلود: https://www.python.org/downloads/
pause
exit /b 1
:python_found
echo       پایتون پیدا شد:
%PY_CMD% --version

rem ── ۲) محیط مجازی ──
echo [2/6] آماده‌سازی محیط مجازی (.venv) ...
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" goto venv_ready
%PY_CMD% -m venv "%~dp0.venv"
if errorlevel 1 (
    echo [خطا] ساخت محیط مجازی ناموفق بود.
    pause
    exit /b 1
)
:venv_ready
echo       محیط مجازی آماده است.

rem ── ۳) نصب وابستگی‌ها ──
echo [3/6] نصب بسته‌ها از requirements.txt ...
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check >nul 2>nul
"%VENV_PY%" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [خطا] نصب بسته‌ها ناموفق بود. اگر پیام خطا مربوط به نسخهٔ پایتون است،
    echo        پایتون ۳.۱۱ تا ۳.۱۳ را امتحان کنید یا پیام خطا را کامل بفرستید.
    pause
    exit /b 1
)
echo       بسته‌ها نصب شدند.

rem ── ۴) فایل .env محلی ──
echo [4/6] بررسی فایل .env ...
if exist "%~dp0.env" goto env_ready
"%VENV_PY%" -c "import secrets, pathlib; pathlib.Path(r'%~dp0.env').write_text('# ساخته‌شده توسط run.bat — فقط برای توسعه\nDEBUG=True\nSECRET_KEY=' + secrets.token_urlsafe(64) + '\nALLOWED_HOSTS=localhost,127.0.0.1\n', encoding='utf-8')"
if errorlevel 1 (
    echo [خطا] ساخت فایل .env ناموفق بود.
    pause
    exit /b 1
)
echo       فایل .env ساخته شد (DEBUG=True + کلید مخفی تصادفی).
goto env_done
:env_ready
echo       فایل .env از قبل وجود دارد؛ تغییر نکرد.
:env_done

rem ── ۵) پایگاه داده + کاربر مدیر ──
echo [5/6] ساخت جدول‌های پایگاه داده ...
"%VENV_PY%" "%~dp0manage.py" migrate --noinput
if errorlevel 1 (
    echo [خطا] migrate ناموفق بود.
    pause
    exit /b 1
)

if "%SEED_DATA%"=="1" (
    echo       ساخت داده‌های نمونه ...
    "%VENV_PY%" "%~dp0manage.py" seed_demo
)

echo       ساخت کاربر مدیر پیش‌فرض ...
"%VENV_PY%" "%~dp0manage.py" create_default_admin --username "%ADMIN_USERNAME%" --password "%ADMIN_PASSWORD%" --email "%ADMIN_EMAIL%"
if errorlevel 1 (
    echo [خطا] ساخت کاربر مدیر ناموفق بود.
    pause
    exit /b 1
)

rem ── ۶) اجرای سرور ──
set "PORT_TRIES=0"
:find_port
netstat -ano | findstr /c:":%PORT% " >nul 2>nul
if errorlevel 1 goto port_ready
set /a PORT_TRIES+=1
if %PORT_TRIES% gtr 20 goto port_ready
echo       پورت %PORT% اشغال است؛ پورت بعدی امتحان می‌شود ...
set /a PORT+=1
goto find_port
:port_ready
echo [6/6] اجرای سرور توسعه روی پورت %PORT% ...
echo.
echo ══════════════════════════════════════════════════
echo   فروشگاه        http://127.0.0.1:%PORT%/
echo   پنل مدیریت     http://127.0.0.1:%PORT%/admin-panel/
echo   ادمین جنگو     http://127.0.0.1:%PORT%/admin/
echo   کاربر / رمز    %ADMIN_USERNAME% / %ADMIN_PASSWORD%
echo   توقف سرور      Ctrl+C
echo ══════════════════════════════════════════════════
echo.

if not "%OPEN_BROWSER%"=="1" goto serve
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:%PORT%/admin-panel/"
:serve
"%VENV_PY%" "%~dp0manage.py" runserver 0.0.0.0:%PORT%

endlocal
