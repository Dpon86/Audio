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
