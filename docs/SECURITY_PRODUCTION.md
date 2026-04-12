# Production Security Settings

**File:** `backend/myproject/settings_production.py`  
**Purpose:** Additional security settings for production deployment

Add these settings to your production environment or create a separate `settings_production.py` file.

---

## 🔒 HTTPS & SSL Settings

```python
# Force HTTPS in production
SECURE_SSL_REDIRECT = True

# HTTP Strict Transport Security (HSTS)
# Tells browsers to ALWAYS use HTTPS for this site
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Secure cookies (HTTPS only)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent JavaScript access to session cookies
SESSION_COOKIE_HTTPONLY = True

# Set cookie domain for production
SESSION_COOKIE_DOMAIN = '.precisepouchtrack.com'
CSRF_COOKIE_DOMAIN = '.precisepouchtrack.com'

# Cookie SameSite policy
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

---

## 🛡️ Security Headers

```python
# XSS Protection
SECURE_BROWSER_XSS_FILTER = True

# Prevent MIME-sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# Prevent clickjacking
X_FRAME_OPTIONS = 'DENY'  # Or 'SAMEORIGIN' if you need iframes

# Referrer Policy
SECURE_REFERRER_POLICY = 'same-origin'

# Permissions Policy (formerly Feature-Policy)
PERMISSIONS_POLICY = {
    "geolocation": [],
    "microphone": [],
    "camera": [],
    "payment": ["self"],  # Only allow Stripe
}
```

---

## 📝 Content Security Policy (CSP)

```python
# Recommended: Use django-csp package
# pip install django-csp

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # Only if needed for inline scripts
    "https://js.stripe.com",  # Stripe JS
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Bootstrap, Tailwind, etc.
)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = (
    "'self'",
    "https://api.stripe.com",
    "https://api.anthropic.com",
)
CSP_FRAME_SRC = ("https://js.stripe.com",)

# Report CSP violations
CSP_REPORT_URI = '/api/csp-report/'
```

---

## 🔐 Token Security Improvements

### Backend: Add httpOnly Cookie Support

**File:** `backend/accounts/views.py`

```python
from django.http import JsonResponse

class CustomAuthToken(ObtainAuthToken):
    """Login with httpOnly cookie instead of localStorage"""
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = _get_or_create_fresh_token(user)
        
        response = JsonResponse({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'subscription': UserSubscriptionSerializer(user.subscription).data,
            'message': 'Login successful'
        })
        
        # Set token as httpOnly cookie (JavaScript can't access)
        response.set_cookie(
            key='auth_token',
            value=token.key,
            max_age=30 * 24 * 60 * 60,  # 30 days
            secure=True,  # HTTPS only
            httponly=True,  # Not accessible via JavaScript
            samesite='Lax',  # CSRF protection
            domain='.precisepouchtrack.com'
        )
        
        return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Logout and clear cookie"""
    response = JsonResponse({'message': 'Logged out successfully'})
    response.delete_cookie('auth_token')
    return response
```

---

### Frontend: Update to Use Cookies

**File:** `frontend/src/config/api.js`

```javascript
// Remove localStorage token usage
// Cookies are automatically sent with requests

export const apiCall = async (endpoint, options = {}) => {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    credentials: 'include',  // Send cookies with requests
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
      // No Authorization header needed - cookie sent automatically
    },
  });
  
  if (response.status === 401) {
    // Token expired, redirect to login
    window.location.href = '/login';
  }
  
  return response.json();
};
```

**File:** `frontend/src/contexts/AuthContext.js`

```javascript
// Update to NOT use localStorage for tokens

const login = async (username, password) => {
  try {
    const response = await fetch('/api/auth/login/', {
      method: 'POST',
      credentials: 'include',  // Important!
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    
    // Store only non-sensitive data
    setUser({
      id: data.user.id,
      username: data.user.username,
    });
    
    // NO token in localStorage!
    // Cookie is automatically stored by browser
    
  } catch (error) {
    console.error('Login failed:', error);
  }
};
```

---

## 🗄️ Database Security

```python
# PostgreSQL SSL mode
if not DEBUG:
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'sslrootcert': '/path/to/ca-certificate.crt',
    }

# Connection pooling
DATABASES['default']['CONN_MAX_AGE'] = 600  # 10 minutes

# Atomic requests (rollback on error)
DATABASES['default']['ATOMIC_REQUESTS'] = True
```

---

## 📁 File Upload Security

```python
# Validated file upload
ALLOWED_FILE_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
MAX_UPLOAD_SIZE = 524288000  # 500 MB

def validate_audio_file(file):
    """Validate uploaded audio file"""
    import os
    import magic
    
    # Check extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise ValidationError(f"File type {ext} not allowed")
    
    # Check file size
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError("File too large")
    
    # Check MIME type (prevent disguised executables)
    mime = magic.from_buffer(file.read(1024), mime=True)
    if not mime.startswith('audio/'):
        raise ValidationError("File is not a valid audio file")
    
    file.seek(0)  # Reset file pointer
    return True
```

---

## 🚦 Rate Limiting Enhancements

```python
# More aggressive rate limiting for production
REST_FRAMEWORK = {
    # ... existing settings ...
    'DEFAULT_THROTTLE_RATES': {
        'anon': '50/hour',       # Stricter for anonymous
        'user': '500/hour',      # Stricter for authenticated
        'login': '5/hour',       # Very strict for login attempts
        'upload': '20/hour',     # Limit file uploads
        'transcribe': '5/hour',  # Expensive AI operations
        'ai_detection': '10/hour',  # AI duplicate detection
    }
}

# Add custom throttle classes
from rest_framework.throttling import UserRateThrottle

class AIOperationThrottle(UserRateThrottle):
    scope = 'ai_detection'
    
class TranscriptionThrottle(UserRateThrottle):
    scope = 'transcribe'
```

---

## 📊 Security Monitoring

```python
# Log security events
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[SECURITY] [{asctime}] {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'security.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'security',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
```

---

## 🔍 Audit Logging

```python
# Add to accounts/signals.py

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
import logging

security_logger = logging.getLogger('django.security')

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    security_logger.info(f"User {user.username} logged in from {ip}")

@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    username = credentials.get('username', 'unknown')
    security_logger.warning(f"Failed login attempt for {username} from {ip}")
```

---

## 🛡️ Additional Middleware

```python
# Add custom security middleware

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    
    # ADD THESE:
    'csp.middleware.CSPMiddleware',  # Content Security Policy
    'accounts.middleware.SecurityHeadersMiddleware',  # Custom headers
    
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware
]
```

**Create:** `backend/accounts/middleware.py`

```python
class SecurityHeadersMiddleware:
    """Add additional security headers"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Remove server header
        response['Server'] = 'AudioPlatform'
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'same-origin'
        
        # Permissions Policy
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), payment=(self)'
        )
        
        return response
```

---

## 📋 Deployment Checklist

Before going to production:

```bash
# 1. Update settings
sudo nano /opt/audioapp/backend/myproject/settings.py
# Add all production security settings above

# 2. Verify environment variables
sudo nano /opt/audioapp/backend/.env

# Should have:
DEBUG=False
SECRET_KEY=<long-random-string>
ALLOWED_HOSTS=audio.precisepouchtrack.com
CORS_ALLOWED_ORIGINS=https://audio.precisepouchtrack.com

# 3. Run security check
cd /opt/audioapp/backend
python manage.py check --deploy

# 4. Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart nginx

# 5. Verify HTTPS
curl -I https://audio.precisepouchtrack.com
# Should see: Strict-Transport-Security header

# 6. Test login
# Verify httpOnly cookie is set in browser dev tools
```

---

## 🔧 Testing Security

```bash
# Run Django's security checks
python manage.py check --deploy

# Check for common vulnerabilities
pip install bandit
bandit -r backend/

# Check dependencies for vulnerabilities
pip install safety
safety check

# SSL/TLS test
# Visit: https://www.ssllabs.com/ssltest/
# Enter: audio.precisepouchtrack.com
# Should get A or A+ rating
```

---

**Implementation Priority:**
1. ✅ HTTPS headers (HIGH)
2. ✅ httpOnly cookies (HIGH)
3. ✅ CSP headers (MEDIUM)
4. ✅ Audit logging (MEDIUM)
5. ✅ File upload validation (LOW)

**Questions?** security@precisepouchtrack.com
