"""Session-based authentication and role authorization.

The project uses a hand-rolled ``User``/``Role`` model (not
``django.contrib.auth``), so authorization is built directly on top of
Django's session framework: ``login_view`` stores ``user_id``, ``role`` and
(for supplier accounts) ``supplier_id`` in ``request.session``, and
``require_auth`` reads them back on every protected request. Session data is
kept server-side and only a signed session key travels in the cookie, so none
of it can be forged by the client the way the old ``X-User-Role`` /
``X-User-Username`` headers could be.
"""
from functools import wraps

from django.http import JsonResponse

from .models import User


def _auth_error(message: str, status: int):
    return JsonResponse({'success': False, 'message': message}, status=status)


def require_auth(role=None, owner_param=None):
    """Require a logged-in session, optionally restricted to a role.

    ``role`` may be a single role name (e.g. ``'admin'``) or an iterable of
    role names.

    ``owner_param`` names a URL kwarg (typically ``supplier_id``) that must
    equal the session's own ``supplier_id``. Use it on supplier-portal
    endpoints so one supplier can never reach another supplier's data by
    editing the id in the URL.

    On success the view gains:
      - ``request.auth_user``: the ``User`` instance for the session.
      - ``request.auth_role``: that user's role name.
      - ``request.auth_supplier_id``: the supplier id bound at login, or
        ``None`` for non-supplier accounts.
    """
    allowed_roles = None
    if role is not None:
        allowed_roles = {role} if isinstance(role, str) else set(role)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user_id = request.session.get('user_id')
            if not user_id:
                return _auth_error('Authentication required.', 401)

            user = User.objects.filter(id=user_id, is_active=True).select_related('role').first()
            if user is None:
                # The account was deleted/deactivated after the session was
                # issued - the session is no longer valid.
                request.session.flush()
                return _auth_error('Authentication required.', 401)

            if allowed_roles is not None and user.role.name not in allowed_roles:
                return _auth_error('You do not have permission to perform this action.', 403)

            if owner_param is not None:
                session_supplier_id = request.session.get('supplier_id')
                try:
                    url_supplier_id = int(kwargs.get(owner_param))
                except (TypeError, ValueError):
                    url_supplier_id = None
                if session_supplier_id is None or url_supplier_id != session_supplier_id:
                    return _auth_error('You do not have permission to access this supplier.', 403)

            request.auth_user = user
            request.auth_role = user.role.name
            request.auth_supplier_id = request.session.get('supplier_id')
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
