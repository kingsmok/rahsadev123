#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import re
import sys
from importlib import metadata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Set to 1/true/yes to skip the dependency pre-flight (e.g. when the
# environment is provisioned by a tool that does not use requirements.txt).
SKIP_PREFLIGHT_ENV = 'MASAISHOP_SKIP_PREFLIGHT'

_REQUIREMENT_LINE = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def _canonical(name):
    """PEP 503 name normalisation so ``Pillow`` matches the installed ``pillow``."""
    return re.sub(r'[-_.]+', '-', name).strip().lower()


def _parse_requirements(path):
    """Return ``[(distribution, specifier), ...]`` for a requirements file.

    Comments, blank lines, pip options and editable/URL requirements are
    ignored.  Environment markers are not evaluated: the project ships no
    marker-conditional requirements, and a false "missing" report is far less
    harmful than a silent crash later on.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError:
        return []

    requirements = []
    for raw_line in text.splitlines():
        line = raw_line.split('#', 1)[0].strip()
        if not line or line.startswith('-'):
            continue
        match = _REQUIREMENT_LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        specifier = line[len(name):].strip()
        requirements.append((name, specifier))
    return requirements


def _installed_distributions():
    """Map of canonical distribution name -> installed version."""
    installed = {}
    for distribution in metadata.distributions():
        name = distribution.metadata['Name']
        if name:
            installed.setdefault(_canonical(name), distribution.version)
    return installed


def missing_requirements(path=None):
    """Return the pinned requirements that this interpreter cannot import.

    Presence is checked through distribution metadata rather than by importing
    the module: several packages here do not use their distribution name as the
    import name (``django-ckeditor`` installs ``ckeditor``/``ckeditor_uploader``
    while ``django-ckeditor-5`` installs ``django_ckeditor_5``).
    """
    path = BASE_DIR / 'requirements.txt' if path is None else Path(path)
    installed = _installed_distributions()
    return [
        (name, specifier)
        for name, specifier in _parse_requirements(path)
        if _canonical(name) not in installed
    ]


def _preflight_requirements(stream=None):
    """Report missing dependencies instead of failing deep inside Django."""
    if os.environ.get(SKIP_PREFLIGHT_ENV, '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return []

    missing = missing_requirements()
    if not missing:
        return []

    stream = sys.stderr if stream is None else stream
    packages = ', '.join(f'{name}{specifier}'.strip() for name, specifier in missing)
    print('بستگی‌های زیر در همین مفسر پایتون نصب نیستند / Not installed in this interpreter:', file=stream)
    print(f'  {packages}', file=stream)
    print(f'Python: {sys.executable}', file=stream)
    print('', file=stream)
    print('راه‌حل / Fix:', file=stream)
    print(f'  "{sys.executable}" -m pip install -r {BASE_DIR / "requirements.txt"}', file=stream)
    print('', file=stream)
    print(
        'اگر محیط مجازی (venv) دارید، نخست آن را فعال کنید تا پایتون درست انتخاب شود؛ '
        f'در غیر این صورت با {SKIP_PREFLIGHT_ENV}=1 این بررسی را رد کنید.',
        file=stream,
    )
    print(
        'If you use a virtual environment, activate it first so the right interpreter is used; '
        f'otherwise set {SKIP_PREFLIGHT_ENV}=1 to bypass this check.',
        file=stream,
    )
    return missing


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MasaiShop.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    if _preflight_requirements():
        raise SystemExit(1)

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
