from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    Token authentication with configurable expiry.
    Tokens older than TOKEN_EXPIRY_DAYS (default: 30) are rejected and deleted.
    The client will receive a 401 and must re-login to obtain a fresh token.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        expiry_days = getattr(settings, 'TOKEN_EXPIRY_DAYS', 30)
        token_age = timezone.now() - token.created
        if token_age > timedelta(days=expiry_days):
            token.delete()
            raise AuthenticationFailed(
                'Token has expired. Please log in again.',
                code='token_expired',
            )

        return user, token


class CookieTokenAuthentication(ExpiringTokenAuthentication):
    """
    Extends ExpiringTokenAuthentication to also accept tokens from httpOnly cookies.
    Checks the 'auth_token' cookie first, then falls back to the Authorization header.
    This prevents token theft via XSS since httpOnly cookies are inaccessible to JavaScript.
    """

    def authenticate(self, request):
        # Try cookie first (not readable by JavaScript)
        token_key = request.COOKIES.get('auth_token')
        if token_key:
            return self.authenticate_credentials(token_key)
        # Fall back to Authorization header (for API clients / backward compat)
        return super().authenticate(request)


# Make all views that import ExpiringTokenAuthentication automatically use
# the cookie-aware version without needing to change any of those files.
ExpiringTokenAuthentication = CookieTokenAuthentication

