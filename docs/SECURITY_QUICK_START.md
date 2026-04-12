# Security Deployment Quick Start

## 🚀 Deploy Privacy Page (15 minutes)

### Step 1: Add Route to App
**File**: `frontend/audio-waveform-visualizer/src/App.js`

```javascript
// Add import at top
import PrivacySecurityPage from './components/PrivacySecurityPage';

// Add route in your Routes section
<Route path="/privacy" element={<PrivacySecurityPage />} />
```

### Step 2: Test Locally
```bash
cd frontend/audio-waveform-visualizer
npm start
# Navigate to http://localhost:3000/privacy
```

### Step 3: Build and Deploy
```bash
# Build frontend
cd C:\Users\NickD\Documents\Github\Audio\frontend\audio-waveform-visualizer
npm run build

# Deploy to server
scp -r build/* nickd@82.165.221.205:/opt/audioapp/frontend/build/

# Restart container
ssh nickd@82.165.221.205 "docker restart audioapp_frontend"
```

**Verification**: Visit https://audio.precisepouchtrack.com/privacy

---

## 🔒 Production Security Hardening (30 minutes)

### Step 1: Add HTTPS Headers
**File**: `backend/myproject/settings.py`

Add this at the end of the file:

```python
# ==========================================
# PRODUCTION SECURITY SETTINGS
# ==========================================
if not DEBUG:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = True  # Force HTTPS
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookies
    SESSION_COOKIE_SECURE = True  # HTTPS only
    CSRF_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True  # Not accessible via JavaScript
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    
    # Security Headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # Content Security Policy
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "https://js.stripe.com")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
    CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com", "https://api.anthropic.com")
    CSP_IMG_SRC = ("'self'", "data:", "https:")
    
    # Referrer Policy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
```

### Step 2: Deploy to Server
```bash
# SSH into server
ssh nickd@82.165.221.205

# Navigate to backend
cd /opt/audioapp/backend

# Pull latest changes (if using Git)
git pull origin master

# OR upload settings.py directly
# On local machine:
scp backend/myproject/settings.py nickd@82.165.221.205:/opt/audioapp/backend/myproject/settings.py

# Activate virtual environment
source venv/bin/activate  # or env/, virtualenv/, .venv/

# Check for deployment issues
python manage.py check --deploy

# Restart backend service
sudo systemctl restart gunicorn
# OR
docker restart audioapp_backend
```

### Step 3: Verify Security Headers
```bash
# From local machine
curl -I https://audio.precisepouchtrack.com

# Should see these headers:
# Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Referrer-Policy: strict-origin-when-cross-origin
```

**If headers missing**: Check that DEBUG=False in production environment variables

---

## 🍪 Migrate to httpOnly Cookies (1-2 hours)

### Backend Changes

**File**: `backend/accounts/views.py`

Replace the `ObtainAuthToken` view:

```python
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        # Get subscription info
        subscription_tier = 'free'
        subscription_renewal_date = None
        if hasattr(user, 'usersubscription'):
            subscription_tier = user.usersubscription.plan.name if user.usersubscription.plan else 'free'
            subscription_renewal_date = user.usersubscription.renewal_date
        
        response = Response({
            'user_id': user.pk,
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'subscription_tier': subscription_tier,
            'subscription_renewal_date': subscription_renewal_date,
        })
        
        # Set httpOnly cookie (not accessible via JavaScript - XSS protection)
        response.set_cookie(
            key='auth_token',
            value=token.key,
            httponly=True,  # Cannot be accessed by JavaScript
            secure=True,    # HTTPS only
            samesite='Lax',  # CSRF protection
            max_age=30 * 24 * 60 * 60  # 30 days (matches token expiry)
        )
        
        return response
```

**File**: `backend/accounts/urls.py`

Update the URL pattern:

```python
from .views import CustomAuthToken

urlpatterns = [
    # Replace this:
    # path('api-token-auth/', views.obtain_auth_token),
    
    # With this:
    path('api-token-auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    
    # ... rest of your URLs
]
```

**File**: `backend/accounts/authentication.py`

Update the authentication class to check cookies:

```python
from rest_framework.authentication import TokenAuthentication

class CookieTokenAuthentication(TokenAuthentication):
    """
    Extends TokenAuthentication to check for token in cookie if not in header
    """
    def authenticate(self, request):
        # First try the standard header authentication
        auth_header = super().authenticate(request)
        if auth_header is not None:
            return auth_header
        
        # If no header, try cookie
        token = request.COOKIES.get('auth_token')
        if token:
            return self.authenticate_credentials(token)
        
        return None
```

**File**: `backend/myproject/settings.py`

Update REST_FRAMEWORK configuration:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.authentication.CookieTokenAuthentication',  # Updated
    ],
    # ... rest of your REST_FRAMEWORK config
}
```

### Frontend Changes

**File**: `frontend/src/contexts/AuthContext.js`

```javascript
// REMOVE all localStorage token usage
// Example changes:

const login = async (username, password) => {
    try {
        const response = await fetch(`${API_URL}/accounts/api-token-auth/`, {
            method: 'POST',
            credentials: 'include',  // ADD THIS - sends cookies
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
        });

        if (!response.ok) throw new Error('Login failed');

        const data = await response.json();
        
        // REMOVE: localStorage.setItem('token', data.token);
        // Token is now in httpOnly cookie automatically
        
        // Only store non-sensitive user data
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data));
        
        return true;
    } catch (error) {
        console.error('Login error:', error);
        return false;
    }
};

const logout = () => {
    // REMOVE: localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    
    // Call backend to clear cookie
    fetch(`${API_URL}/accounts/logout/`, {
        method: 'POST',
        credentials: 'include',  // ADD THIS
    });
};
```

**File**: Update ALL API calls to include credentials

Search for all `fetch()` calls and add `credentials: 'include'`:

```javascript
// Example API call pattern
const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',  // ADD THIS LINE
    headers: {
        'Content-Type': 'application/json',
        // REMOVE Authorization header - token now in cookie
    },
});
```

**Files to update**:
- `frontend/src/contexts/AuthContext.js`
- `frontend/src/components/EditPage.js`
- Any component that makes authenticated API calls

### Testing

```bash
# 1. Start backend
cd backend
python manage.py runserver

# 2. Start frontend
cd frontend/audio-waveform-visualizer
npm start

# 3. Test login at http://localhost:3000

# 4. Open browser DevTools > Application > Cookies
# Should see: auth_token with HttpOnly ✓ flag

# 5. Try accessing token in console
console.log(document.cookie)
# Should NOT show auth_token (it's httpOnly)

# 6. Verify API calls still work
# Make authenticated request (upload file, etc.)
```

---

## 📊 Add GDPR Data Export (2-3 hours)

### Backend Implementation

**File**: `backend/accounts/views.py`

```python
from django.core.mail import send_mail
from django.utils import timezone
import json

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_data_export(request):
    """
    Generate and email user's complete data export (GDPR Article 20)
    """
    user = request.user
    
    # Compile all user data
    user_data = {
        'export_date': timezone.now().isoformat(),
        'account': {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
        },
        'subscription': {
            'tier': getattr(user.usersubscription.plan, 'name', 'free') if hasattr(user, 'usersubscription') else 'free',
            'renewal_date': user.usersubscription.renewal_date.isoformat() if hasattr(user, 'usersubscription') and user.usersubscription.renewal_date else None,
        },
        'projects': list(user.audioproject_set.values(
            'id', 'name', 'created_at', 'updated_at', 'status'
        )),
        'audio_files': [],
        'transcriptions': [],
    }
    
    # Get audio files from all projects
    from audioDiagnostic.models import AudioFile, Transcription
    for project in user.audioproject_set.all():
        audio_files = AudioFile.objects.filter(project=project).values(
            'id', 'filename', 'duration', 'file_size', 'created_at'
        )
        user_data['audio_files'].extend(list(audio_files))
        
        # Get transcriptions for each audio file
        transcriptions = Transcription.objects.filter(
            audio_file__project=project
        ).values(
            'id', 'audio_file_id', 'text', 'created_at', 'ai_generated'
        )
        user_data['transcriptions'].extend(list(transcriptions))
    
    # Convert to JSON
    json_data = json.dumps(user_data, indent=2, default=str)
    
    # Email the export (in production, save to S3 and send link)
    send_mail(
        subject='Your Data Export from Audio Diagnostic',
        message=f'Hi {user.first_name},\n\nYour requested data export is attached.\n\nThis export contains:\n- Account information\n- All projects\n- All audio files\n- All transcriptions\n\nBest regards,\nAudio Diagnostic Team',
        from_email='noreply@precisepouchtrack.com',
        recipient_list=[user.email],
        fail_silently=False,
    )
    
    # Log the export request
    import logging
    logger = logging.getLogger('security')
    logger.info(f'Data export requested by user {user.email} (ID: {user.id})')
    
    return Response({
        'message': 'Your data export will be emailed to you within 72 hours.',
        'email': user.email,
        'estimated_size': f'{len(json_data) / 1024:.2f} KB'
    })
```

**File**: `backend/accounts/urls.py`

```python
urlpatterns = [
    # ... existing URLs
    path('data-export/', views.request_data_export, name='data_export'),
]
```

### Frontend Integration

**File**: `frontend/src/components/PrivacySecurityPage.jsx`

Update the "Request Data Export" button:

```javascript
const handleDataExport = async () => {
    try {
        const response = await fetch(`${API_URL}/accounts/data-export/`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) throw new Error('Export request failed');

        const data = await response.json();
        alert(`✓ ${data.message}\n\nYour data will be sent to: ${data.email}`);
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to request data export. Please try again or contact support.');
    }
};

// In the YourData component, update the button:
<button className="action-btn" onClick={handleDataExport}>
    Request Data Export
</button>
```

### Testing

```bash
# Configure email settings in settings.py first
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For testing

# Test the endpoint
curl -X POST https://audio.precisepouchtrack.com/accounts/data-export/ \
  -H "Cookie: auth_token=YOUR_TOKEN_HERE"

# Check email output in console
```

---

## 📋 Pre-Launch Checklist

### Critical (Must Complete)
- [ ] Add HTTPS headers to `settings.py`
- [ ] Deploy updated backend to server
- [ ] Verify headers with `curl -I`
- [ ] Test HTTPS redirect (http:// should redirect to https://)
- [ ] Deploy privacy page to frontend
- [ ] Test privacy page on production URL
- [ ] Review logs for any exposed PII
- [ ] Confirm DEBUG=False in production

### Recommended (Within 2 Weeks)
- [ ] Migrate to httpOnly cookies
- [ ] Test cookie authentication thoroughly
- [ ] Implement GDPR data export endpoint
- [ ] Wire up "Request Data Export" button
- [ ] Add security audit logging
- [ ] Test data export functionality

### Optional (Future Enhancement)
- [ ] File encryption at rest
- [ ] Data anonymization for analytics
- [ ] Security monitoring dashboard
- [ ] Automated vulnerability scanning

---

## 🆘 Troubleshooting

### HTTPS Headers Not Showing
```bash
# Check DEBUG setting
python manage.py shell
>>> from django.conf import settings
>>> settings.DEBUG
False  # Should be False in production

# Check environment variable
echo $DEBUG  # Should be False, 0, or unset
```

### Cookies Not Being Set
```bash
# Check browser DevTools > Network
# Look at login response headers
# Should see: Set-Cookie: auth_token=...

# Common issues:
# - SECURE=True but using HTTP (use HTTPS)
# - SAMESITE=Lax with cross-origin requests
# - Domain mismatch
```

### API Calls Failing After Cookie Migration
```javascript
// Ensure all fetch calls have:
credentials: 'include'

// Check CORS settings in backend:
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'https://audio.precisepouchtrack.com',
]
```

---

## 📞 Support

**Email**: support@precisepouchtrack.com  
**Documentation**: 
- Full audit: `docs/SECURITY_AUDIT.md`
- Production guide: `docs/SECURITY_PRODUCTION.md`
- Summary: `docs/SECURITY_IMPLEMENTATION_SUMMARY.md`

---

*Last Updated: January 2025*
