from functools import wraps
from urllib.parse import quote

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.urls import reverse


def wants_json(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('accept', '')
    content_type = request.headers.get('content-type', '')
    return 'application/json' in accept or content_type.startswith('application/json')


def login_required_json(view):
    """``login_required`` that answers AJAX calls with JSON 401 instead of a 302.

    A fetch() follows the login redirect and receives an HTML page; the
    storefront then failed to parse it and showed a generic «عملیات انجام نشد»
    whenever a session had expired in an open tab.
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        if wants_json(request):
            referer_path = request.headers.get('x-current-path') or '/'
            if not referer_path.startswith('/') or referer_path.startswith('//'):
                referer_path = '/'
            return JsonResponse({
                'success': False,
                'status': 'fail',
                'login_required': True,
                'login_url': f"{reverse('account:login')}?next={quote(referer_path)}",
                'message': 'نشست شما منقضی شده است؛ لطفاً دوباره وارد حساب کاربری شوید.',
            }, status=401)
        return redirect_to_login(request.get_full_path())
    return wrapper
