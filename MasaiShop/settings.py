from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Load the simple KEY=value values used by the documented local .env file.

    Deployment environments still take precedence and no third-party package is
    required just to run the project locally.  Quotes around a value are
    accepted; complex shell expansion deliberately is not.
    """
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace('_', '').isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# Security defaults: development remains easy to run, while a production
# process refuses to start without an explicit, non-placeholder secret.
# Fails closed: without an explicit DEBUG=1/true the project runs as it would in
# production.  A forgotten environment variable must never leave a public
# deployment serving tracebacks with ALLOWED_HOSTS='*'.  ``run.sh``/``run.bat``
# and ``cp .env.example .env`` all set DEBUG=True explicitly for local work.
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('1', 'true', 'yes')
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'SECRET_KEY is not set. Copy .env.example to .env (or export SECRET_KEY); '
        'run.sh / run.bat generate a random one for local development.'
    )
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured('SECRET_KEY must be a strong, random value of at least 50 characters in production.')

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
if DEBUG and os.environ.get('ALLOW_ALL_HOSTS', '1').lower() in ('1', 'true', 'yes'):
    # در حالت توسعه همه هاست‌ها پذیرفته می‌شود تا پیش‌نمایش آنلاین و دامنه‌های تست کار کنند.
    ALLOWED_HOSTS += ['*']
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]

# Only trust a forwarded protocol when the deployment really sits behind a
# TLS-terminating proxy that you control.  Leaving it off while
# SECURE_SSL_REDIRECT is on makes Django see plain HTTP forever and answer every
# request with a redirect — an infinite loop on shared hosting.  Enabling it
# without a proxy would let a client spoof the header and bypass HTTPS.
if os.environ.get('BEHIND_HTTPS_PROXY', '0').lower() in ('1', 'true', 'yes'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

# درگاه‌ها فقط با کلید محیطی فعال می‌شوند.
ZARINPAL_MERCHANT_ID = os.environ.get('ZARINPAL_MERCHANT_ID', '')
SNAPPAY_CLIENT_ID = os.environ.get('SNAPPAY_CLIENT_ID', '')
SNAPPAY_CLIENT_SECRET = os.environ.get('SNAPPAY_CLIENT_SECRET', '')
TOROBPAY_MERCHANT_ID = os.environ.get('TOROBPAY_MERCHANT_ID', '')
ZARINPAL_REQUEST_URL = os.environ.get('ZARINPAL_REQUEST_URL', 'https://api.zarinpal.com/pg/v4/payment/request.json')
ZARINPAL_VERIFY_URL = os.environ.get('ZARINPAL_VERIFY_URL', 'https://api.zarinpal.com/pg/v4/payment/verify.json')
ZARINPAL_START_URL = os.environ.get('ZARINPAL_START_URL', 'https://www.zarinpal.com/pg/StartPay/')
# Prevent a compromised database/configuration from making payment requests to
# arbitrary hosts. Add a verified provider host here only when needed.
ZARINPAL_ALLOWED_HOSTS = tuple(
    host.strip().lower()
    for host in os.environ.get('ZARINPAL_ALLOWED_HOSTS', 'api.zarinpal.com,sandbox.zarinpal.com').split(',')
    if host.strip()
)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_ckeditor_5',
    # installed apps
    'jalali_date',
    'django_cleanup.apps.CleanupConfig',
    # my apps
    'core',
    'product',
    'accounts',
    'blog',
    'cart',
    'dashboard',
    'payments',
    'downloads',
    'services',
    'pages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.BrowserPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.RedirectMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'MasaiShop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'context_processors.context_processors.shop_func',
                'context_processors.context_processors.seo_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'MasaiShop.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
#
# توسعهٔ محلی بدون هیچ تنظیمی با SQLite کار می‌کند. در تولید کافی است
# DATABASE_URL ست شود (postgresql://user:pass@host:5432/dbname یا
# sqlite:///path)؛ هیچ وابستگیِ اضافه‌ای برای پارس‌کردن آن لازم نیست و
# درایور PostgreSQL (psycopg) در requirements هست.

def _database_from_url(url):
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in ('postgres', 'postgresql'):
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed.path.lstrip('/'),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '',
            'PORT': str(parsed.port or ''),
        }
    if scheme == 'sqlite':
        name = parsed.path
        if name.startswith('/'):
            name = name[1:]
        if not name or name == ':memory:':
            resolved = ':memory:'
        elif name.startswith('/'):
            resolved = name  # sqlite:////absolute/path
        else:
            resolved = str(BASE_DIR / name)
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': resolved}
    raise ImproperlyConfigured(f'Unsupported DATABASE_URL scheme: {scheme!r}')


_database_url = os.environ.get('DATABASE_URL', '')
DATABASES = {
    'default': (
        _database_from_url(_database_url)
        if _database_url
        else {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    )
}

# Cache: پیش‌فرض حافظهٔ محلیِ هر پردازه است (توسعه و هاست تک‌پردازه کافی است).
# در استقرار چندپردازه‌ای CACHE_URL=redis://127.0.0.1:6379/1 بگذارید تا
# محدودسازی نرخ و شمارنده‌ها بین همهٔ پردازه‌ها مشترک شوند؛ بک‌اند Redis
# داخل خودِ جنگو است و وابستگی تازه‌ای لازم نیست.
_cache_url = os.environ.get('CACHE_URL', '')
if _cache_url.startswith(('redis://', 'rediss://')):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _cache_url,
        }
    }
elif _cache_url in ('', 'locmem://'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'rahsadev-local',
        }
    }
else:
    raise ImproperlyConfigured(f'Unsupported CACHE_URL: {_cache_url!r}')


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# مقصد دستور collectstatic برای اجرا روی سرور (بدون این مقدار دستور خطا می‌دهد
# و سایت روی هاست بدون CSS/JS و کاملاً بهم‌ریخته بالا می‌آید).
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
# Paid digital assets are deliberately separate from public media. Do not map
# this directory to a web-server URL; downloads are served after token checks.
PRIVATE_MEDIA_ROOT = os.path.join(BASE_DIR, 'private_media')

# Uploads are automatically converted to compact WebP files where safe. Values
# can be tuned per deployment without a migration.
IMAGE_OPTIMIZATION_ENABLED = os.environ.get('IMAGE_OPTIMIZATION_ENABLED', 'true').lower() in ('1', 'true', 'yes')
try:
    IMAGE_OPTIMIZATION_MAX_DIMENSION = max(1, int(os.environ.get('IMAGE_OPTIMIZATION_MAX_DIMENSION', '2000')))
    IMAGE_OPTIMIZATION_WEBP_QUALITY = min(100, max(1, int(os.environ.get('IMAGE_OPTIMIZATION_WEBP_QUALITY', '82'))))
except ValueError:
    IMAGE_OPTIMIZATION_MAX_DIMENSION = 2000
    IMAGE_OPTIMIZATION_WEBP_QUALITY = 82

# CKEditor 5: uploads are staff-only and use the same safe WebP optimisation
# pipeline as model ImageFields. The compact toolbar avoids source editing and
# remote-media embedding in the CMS.
CKEDITOR_5_FILE_UPLOAD_PERMISSION = 'staff'
CKEDITOR_5_FILE_STORAGE = 'core.storage.CkeditorImageStorage'
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': {
            'items': [
                'heading', '|', 'bold', 'italic', 'link',
                'bulletedList', 'numberedList', 'blockQuote', 'imageUpload',
                'insertTable', 'undo', 'redo',
            ],
        },
        'language': 'fa',
        'image': {'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:alignCenter', 'imageStyle:alignRight']},
        'table': {'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells']},
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'account:login'

# ------------------------------------------------------------------ ایمیل
# در توسعه، ایمیل‌ها در کنسول چاپ می‌شوند تا جریان بازیابی رمز بدون هیچ
# سرویس خارجی قابل آزمایش باشد. در تولید، EMAIL_BACKEND=smtp و مقادیر
# EMAIL_HOST/USER/PASSWORD (از محیط، هرگز در کد) تنظیم می‌شوند.
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'FileMarket <no-reply@localhost>')

# لینک بازیابی رمز ۲۴ ساعت معتبر است و درخواست‌های آن محدودسازی می‌شوند
# تا نه حساب‌ها شمرده شوند و نه صندوق ایمیل کسی بمباران شود.
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60
PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS = 60 * 60
PASSWORD_RESET_RATE_LIMIT_IDENTITY_ATTEMPTS = 3
PASSWORD_RESET_RATE_LIMIT_IP_ATTEMPTS = 10

# ------------------------------------------------------------------ لاگ‌گیری
# Django's stock configuration routes ``django.request`` errors only to
# ``mail_admins``, and ``AdminEmailHandler`` returns silently when ADMINS is
# empty.  On a WSGI server that means a 500 is recorded nowhere at all, so a
# failed payment callback leaves no trace.  These handlers always emit to
# stderr (captured by gunicorn/systemd/cPanel) and optionally to a file.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.environ.get('LOG_FILE', '')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'},
    },
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        # Request logging for ``runserver``, kept so local output is unchanged.
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        # Still honour e-mail alerting when an operator configures ADMINS.
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        # HTTP 4xx/5xx summaries (``django.request``) are logged separately so
        # they are never swallowed by an empty ADMINS setting.
        'django.request': {
            'handlers': ['console', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        # SQL logging stays off unless explicitly requested: ``django`` at DEBUG
        # would otherwise echo every query.
        'django.db.backends': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_SQL_LEVEL', 'WARNING').upper(),
            'propagate': False,
        },
        # Application loggers used by the payments and cart flows.
        'payments': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'cart': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        'downloads': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
    },
}

if LOG_FILE:
    LOGGING['handlers']['file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': LOG_FILE,
        'maxBytes': int(os.environ.get('LOG_FILE_MAX_BYTES', 5 * 1024 * 1024)),
        'backupCount': int(os.environ.get('LOG_FILE_BACKUP_COUNT', 3)),
        'formatter': 'verbose',
    }
    for _logger in ('django', 'django.request', 'payments', 'cart', 'downloads'):
        LOGGING['loggers'][_logger]['handlers'].append('file')

# Cache-backed throttling. Use a shared cache such as Redis in production so the
# limits apply across all application workers.
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
LOGIN_RATE_LIMIT_IDENTITY_ATTEMPTS = 5
LOGIN_RATE_LIMIT_IP_ATTEMPTS = 20

# Public write endpoints (comments, contact, service requests, newsletter) are
# anonymously reachable and would otherwise accept unlimited automated posts.
PUBLIC_WRITE_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
PUBLIC_WRITE_RATE_LIMITS = {
    # namespace: (attempts per address+identity, attempts per address)
    'comment': (10, 40),
    'contact': (5, 20),
    'register': (5, 20),
    'service_request': (5, 20),
    'newsletter': (10, 40),
}


# JALALI DATE Settings (optional)
JALALI_DATE_DEFAULTS = {
   # if change it to true then all dates of the list_display will convert to the Jalali.
   'LIST_DISPLAY_AUTO_CONVERT': False,
   'Strftime': {
        'date': '%y/%m/%d',
        'datetime': '%H:%M:%S _ %y/%m/%d',
    },
    'Static': {
        'js': [
            # loading datepicker
            'admin/js/django_jalali.min.js',
            # OR
            # 'admin/jquery.ui.datepicker.jalali/scripts/jquery.ui.core.js',
            # 'admin/jquery.ui.datepicker.jalali/scripts/calendar.js',
            # 'admin/jquery.ui.datepicker.jalali/scripts/jquery.ui.datepicker-cc.js',
            # 'admin/jquery.ui.datepicker.jalali/scripts/jquery.ui.datepicker-cc-fa.js',
            # 'admin/js/main.js',
        ],
        'css': {
            'all': [
                'admin/jquery.ui.datepicker.jalali/themes/base/jquery-ui.min.css',
            ]
        }
    },
}


# CKEditor Settings
CKEDITOR_UPLOAD_PATH = 'uploads/'
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_JQUERY_URL = '/static/js/core/jquery.min.js'
CKEDITOR_CONFIGS = {
    'default':
        {
            'toolbar': 'advanced'
        }
}

