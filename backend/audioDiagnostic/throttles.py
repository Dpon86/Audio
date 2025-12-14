"""
Custom throttle classes for rate limiting different types of operations.
"""
from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """Throttle for file upload operations (more restrictive)"""
    scope = 'upload'


class TranscribeRateThrottle(UserRateThrottle):
    """Throttle for transcription operations (very restrictive - expensive)"""
    scope = 'transcribe'


class ProcessRateThrottle(UserRateThrottle):
    """Throttle for processing operations (restrictive)"""
    scope = 'process'
