from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='/accounts/login/')
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('landing')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
