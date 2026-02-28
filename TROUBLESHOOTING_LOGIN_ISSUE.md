# Login Issue Troubleshooting Guide

**Date:** February 27-28, 2026  
**Issue:** Frontend getting "Network Error" when attempting login  
**URL:** https://audio.precisepouchtrack.com/api/auth/login/

---

## 🎯 **SOLUTION FOUND - February 28, 2026**

### **Root Cause: Browser Cache**

After server restart, the frontend container is serving the **correct** JavaScript files with production URLs, but the browser is still using **cached** versions with `localhost:8000`.

**Evidence:**
- Browser console shows: `Failed to load localhost:8000/api/auth/login/`
- Frontend container JavaScript files contain: `audio.precisepouchtrack.com`
- Login API endpoint is working correctly (tested with curl)

### **Fix: Hard Refresh Browser**

**IMPORTANT:** You must clear your browser cache to get the new JavaScript files.

**How to Hard Refresh:**
1. **Windows/Linux:** `Ctrl + Shift + R` or `Ctrl + F5`
2. **Mac:** `Cmd + Shift + R`
3. **Alternative:** Clear browser cache manually or open in Incognito/Private mode

**After hard refresh, login should work immediately.**

---

## 📝 Complete Timeline of Fixes Applied

### ✅ February 27, 2026 - Initial Fixes
1. **Frontend URL Patching (11:00 PM):**
   - Patched `main.c8255e29.js` to replace `http://localhost:8000` with `https://audio.precisepouchtrack.com`
   - Used `sed -i` directly in running container
   - **Problem:** These patches were lost after server restart (Docker containers are ephemeral)

2. **Backend Permission Fix (8:09 PM):**
   - Added `permission_classes = [AllowAny]` to `CustomAuthToken` view
   - Fixed subscription access to use `get_or_create()` 
   - Copied to container, restarted backend

3. **ALLOWED_HOSTS Fix (8:15 PM):**
   - **ROOT CAUSE:** settings.py had hardcoded `ALLOWED_HOSTS = ['192.168.148.110', 'localhost', '127.0.0.1']`
   - **SOLUTION:** Changed to `ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')`
   - Now reads from `.env.production` which includes `audio.precisepouchtrack.com`
   - Copied to container, restarted backend
   - **Result:** Login API endpoint now returns HTTP 200 with valid tokens

### ✅ February 28, 2026 - Post-Restart Issue
4. **Server Restart (overnight):**
   - Server was restarted
   - Frontend JavaScript patches were LOST (containers lose changes on restart)
   - Backend settings.py changes were LOST
   - **Problem:** Need to re-apply fixes after restart

5. **Browser Cache Issue (current):**
   - Frontend container currently being rebuilt/fixed
   - Browser is serving cached JavaScript with old localhost URLs
   - **Solution:** Hard refresh browser to clear cache

---

## 🔍 Current Status (February 28, 2026)

---

## 🔍 Current Status (February 28, 2026)

### What's Working ✅
1. **Backend Login API:**
   ```bash
   curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"audioadmin123"}'
   # Returns: {"token": "...", "user": {...}, "subscription": {...}}
   ```
   - HTTP 200 OK
   - Returns valid authentication token
   - Returns user data (id: 4, username: admin)
   - Returns subscription data (plan: Free Trial, status: trialing)

2. **Frontend Container:**
   - Container running (Up 13 hours)
   - JavaScript files contain production URLs (`audio.precisepouchtrack.com`)
   - Serving files correctly on port 3001

3. **Database:**
   - PostgreSQL healthy
   - Users exist: admin, Nick, unlimited_user, testuser
   - Admin credentials work: admin / audioadmin123

4. **SSL & CORS:**
   - Let's Encrypt certificate valid
   - CORS configured for `https://audio.precisepouchtrack.com`
   - CORS headers present in responses

### What's NOT Working ❌
1. **Browser Login:**
   - Browser console shows: `Failed to load localhost:8000/api/auth/login/:1`
   - Error: `net::ERR_CONNECTION_REFUSED`
   - **Cause:** Browser is using cached JavaScript files with old localhost URLs
   - **Solution:** Hard refresh browser (`Ctrl+Shift+R` or `Cmd+Shift+R`)

### Files Modified (Need to Re-apply After Restart)

---

## 🤔 Why It's Not Working - Analysis

### Theory 1: Login Endpoint Missing or Misconfigured (MOST LIKELY)
**Evidence:**
- HTTP 400 suggests endpoint exists but rejects the request format
- No authentication errors (401) or permission errors (403)
- REST_FRAMEWORK config shows `DEFAULT_PERMISSION_CLASSES = IsAuthenticated` globally

**Problem:**
The login view likely doesn't have `permission_classes = [AllowAny]` override, OR the endpoint doesn't exist in `urls.py`.

**Files to check:**
- `/opt/audioapp/backend/api/urls.py` - Does `/auth/login/` route exist?
- `/opt/audioapp/backend/api/views.py` - Does the login view allow anonymous access?

---

### Theory 2: CSRF Token Required
**Evidence:**
- Django REST Framework requires CSRF tokens for session authentication
- Browser requests include `"https://audio.precisepouchtrack.com/login/"` as referer
- Settings show `SessionAuthentication` is enabled

**Problem:**
The login form might need a CSRF token from Django, but the React app isn't sending it.

**Solution needed:**
- Check if CSRF exemption is configured for `/api/auth/login/`
- Or implement CSRF token retrieval in frontend

---

### Theory 3: Request Body Format Wrong
**Evidence:**
- Exact same error from both curl and browser
- Request body: `{"username":"admin","password":"audioadmin123"}`
- Content-Type: `application/json`

**Problem:**
The backend might expect different field names (e.g., `email` instead of `username`) or a different authentication method.

**Files to check:**
- Serializer expects which fields?
- Is it using Django's built-in auth or custom authentication?

---

### Theory 4: Database Connection Issue
**Evidence:**
- Database container shows `(healthy)` status
- Migrations ran successfully during deployment
- Users exist in database (we queried them earlier)

**Likelihood:** Low - database queries work fine

---

### Theory 5: DEBUG=False Hiding Errors
**Evidence:**
- `.env.production` has `DEBUG=False`
- Error response is generic Django 400 page with no details
- No detailed error messages in logs

**Problem:**
We can't see the actual error because Django is hiding it in production mode.

**Solution:**
Temporarily enable DEBUG logging or check Django error logs directly.

---

### Files Modified (Need to Re-apply After Restart)

**Critical Changes Made to Fix Login:**

1. **`/opt/audioapp/backend/myproject/settings.py`** (REQUIRED after every restart)
   ```python
   # OLD (causes HTTP 400 - hardcoded hosts):
   ALLOWED_HOSTS = [
       '192.168.148.110',
       'localhost',
       '127.0.0.1',
   ]
   
   # NEW (reads from environment - CORRECT):
   ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
   ```
   **After changing:**
   ```bash
   sudo docker cp /opt/audioapp/backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
   docker compose -f /opt/audioapp/docker-compose.production.yml restart backend
   ```

2. **`/opt/audioapp/backend/accounts/views.py`** (RECOMMENDED)
   ```python
   @method_decorator(csrf_exempt, name='dispatch')
   class CustomAuthToken(ObtainAuthToken):
       permission_classes = [permissions.AllowAny]  # ADD THIS LINE
       
       def post(self, request, *args, **kwargs):
           serializer = self.serializer_class(data=request.data, context={'request': request})
           serializer.is_valid(raise_exception=True)
           user = serializer.validated_data['user']
           token, created = Token.objects.get_or_create(user=user)
           
           # CHANGE FROM: user.subscription (can fail)
           # CHANGE TO: (safer)
           subscription, created = UserSubscription.objects.get_or_create(user=user)
           
           return Response({
               'token': token.key,
               'user': {...},
               'subscription': {...}
           })
   ```
   **After changing:**
   ```bash
   sudo docker cp /opt/audioapp/backend/accounts/views.py audioapp_backend:/app/accounts/views.py
   docker compose -f /opt/audioapp/docker-compose.production.yml restart backend
   ```

3. **Frontend JavaScript** (TEMPORARY - lost on restart)
   - Originally patched `main.c8255e29.js` inside running container
   - Replaced `http://localhost:8000` with `https://audio.precisepouchtrack.com`
   - **Problem:** Container changes lost on restart
   - **Solution:** Rebuild frontend with correct environment variables OR re-apply patches

### How to Make Changes Permanent

**Option A: Rebuild Frontend (PREFERRED but needs ~2GB RAM)**
```bash
cd /opt/audioapp
# Ensure .env.production has correct values:
# REACT_APP_API_URL=https://audio.precisepouchtrack.com/api
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml up -d frontend
```

**Option B: Script to Re-apply Patches After Restart (WORKAROUND)**
```bash
# Create /opt/audioapp/fix-after-restart.sh
#!/bin/bash
sudo docker cp /opt/audioapp/backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
sudo docker cp /opt/audioapp/backend/accounts/views.py audioapp_backend:/app/accounts/views.py
docker compose -f /opt/audioapp/docker-compose.production.yml restart backend
sudo docker exec audioapp_frontend sed -i 's|http://localhost:8000|https://audio.precisepouchtrack.com|g' /usr/share/nginx/html/static/js/main.*.js
echo "Fixes applied! Now hard refresh browser: Ctrl+Shift+R"
chmod +x /opt/audioapp/fix-after-restart.sh
```

---

## 🚀 QUICK FIX STEPS (After Server Restart)

If login stops working after server restart:

1. **Re-apply backend fixes:**
   ```bash
   cd /opt/audioapp
   sudo docker cp backend/myproject/settings.py audioapp_backend:/app/myproject/settings.py
   sudo docker cp backend/accounts/views.py audioapp_backend:/app/accounts/views.py
   docker compose -f docker-compose.production.yml restart backend
   sleep 10  # Wait for backend to restart
   ```

2. **Test login API:**
   ```bash
   curl -s https://audio.precisepouchtrack.com/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"audioadmin123"}'
   ```
   Should return: `{"token": "...", "user": {...}, "subscription": {...}}`

3. **Clear browser cache:**
   - Windows/Linux: `Ctrl + Shift + R`
   - Mac: `Cmd + Shift + R`
   - Alternative: Open Incognito/Private window

4. **Login should now work!**

---

## 🔍 Old Troubleshooting Steps (For Reference)

### Priority 1: Find the Login Endpoint Definition

- [ ] **Step 1.1:** Check if login endpoint exists
  ```bash
  grep -r "auth/login" /opt/audioapp/backend/api/urls.py
  grep -r "LoginView\|login" /opt/audioapp/backend/api/views.py
  ```

- [ ] **Step 1.2:** Verify the endpoint allows anonymous access
  ```bash
  grep -A10 "class.*Login" /opt/audioapp/backend/api/views.py | grep -i "AllowAny\|permission"
  ```

- [ ] **Step 1.3:** Check if authentication backend is configured
  ```bash
  grep "AUTHENTICATION_BACKENDS" /opt/audioapp/backend/myproject/settings.py
  ```

**Fix if needed:** Add `permission_classes = [AllowAny]` to login view

---

### Priority 2: Enable Detailed Error Logging

- [ ] **Step 2.1:** Check current logging configuration
  ```bash
  grep -A20 "LOGGING" /opt/audioapp/backend/myproject/settings.py
  ```

- [ ] **Step 2.2:** Add detailed logging for API errors (if not present)
  ```python
  LOGGING = {
      'version': 1,
      'disable_existing_loggers': False,
      'handlers': {
          'console': {
              'class': 'logging.StreamHandler',
          },
      },
      'loggers': {
          'django.request': {
              'handlers': ['console'],
              'level': 'DEBUG',
              'propagate': True,
          },
          'api': {
              'handlers': ['console'],
              'level': 'DEBUG',
          },
      },
  }
  ```

- [ ] **Step 2.3:** Restart backend and check logs
  ```bash
  sudo docker compose -f docker-compose.production.yml restart backend
  sudo docker logs -f audioapp_backend
  ```

**Expected:** Detailed error messages showing why request is rejected

---

### Priority 3: Verify CSRF Configuration

- [ ] **Step 3.1:** Check CSRF exemption for API
  ```bash
  grep -i "csrf_exempt\|CSRF_COOKIE" /opt/audioapp/backend/myproject/settings.py
  grep -i "csrf_exempt" /opt/audioapp/backend/api/views.py
  ```

- [ ] **Step 3.2:** Check if CSRF middleware is interfering
  ```bash
  grep "MIDDLEWARE" /opt/audioapp/backend/myproject/settings.py | grep -i csrf
  ```

**Fix if needed:** Exempt `/api/auth/login/` from CSRF or configure CSRF cookie for frontend

---

### Priority 4: Test with Django Admin Login (Known Working Path)

- [ ] **Step 4.1:** Try logging into Django admin panel
  ```
  URL: https://audio.precisepouchtrack.com/admin/
  Username: admin
  Password: audioadmin123
  ```

- [ ] **Step 4.2:** If admin login works:
  - Proves: Database connection OK, user exists, password correct
  - Means: Issue is specific to `/api/auth/login/` endpoint

- [ ] **Step 4.3:** If admin login fails:
  - Broader authentication problem
  - Check `ALLOWED_HOSTS` configuration

---

### Priority 5: Check API URLs Configuration

- [ ] **Step 5.1:** Verify API URLs are included in main urls.py
  ```bash
  cat /opt/audioapp/backend/myproject/urls.py | grep -A5 "api/"
  ```

- [ ] **Step 5.2:** Verify api/urls.py has auth routes
  ```bash
  cat /opt/audioapp/backend/api/urls.py | grep -A5 "auth"
  ```

- [ ] **Step 5.3:** List all available API endpoints
  ```bash
  sudo docker exec audioapp_backend python manage.py show_urls 2>/dev/null || \
  sudo docker exec audioapp_backend python manage.py shell -c "from django.urls import get_resolver; print('\n'.join([str(p) for p in get_resolver().url_patterns]))"
  ```

**Expected:** Should see `/api/auth/login/` or similar authentication endpoint

---

### Priority 6: Test Backend Directly (Bypass Nginx)

- [ ] **Step 6.1:** Test backend container directly on port 8001
  ```bash
  curl -v http://localhost:8001/api/auth/login/ \
    -H "Content-Type: application/json" \
    -X POST \
    -d '{"username":"admin","password":"audioadmin123"}'
  ```

- [ ] **Step 6.2:** Compare response to Nginx-proxied request
  ```bash
  curl -v https://audio.precisepouchtrack.com/api/auth/login/ \
    -H "Content-Type: application/json" \
    -X POST \
    -d '{"username":"admin","password":"audioadmin123"}'
  ```

**If direct works but proxied fails:** Nginx configuration issue  
**If both fail:** Backend authentication endpoint issue

---

### Priority 7: Alternative - Use Django REST Framework's Built-in Auth

- [ ] **Step 7.1:** Check if DRF auth token endpoint exists
  ```bash
  curl -X POST https://audio.precisepouchtrack.com/api-token-auth/ \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"audioadmin123"}'
  ```

- [ ] **Step 7.2:** Check if browsable API login works
  ```
  Open in browser: https://audio.precisepouchtrack.com/api/
  ```

**Alternative endpoints to try:**
- `/api-auth/login/` (DRF default)
- `/api/token/` (if using JWT)
- `/rest-auth/login/` (if using dj-rest-auth)

---

## 🚨 Immediate Actions (Do These First)

1. **Read the authentication views to understand the endpoint:**
   ```bash
   cat /opt/audioapp/backend/api/views.py | grep -A30 "login"
   ```

2. **Check what URL patterns are registered:**
   ```bash
   cat /opt/audioapp/backend/api/urls.py
   ```

3. **Try Django admin login to verify basic auth works:**
   - Go to: https://audio.precisepouchtrack.com/admin/
   - Login: admin / audioadmin123

4. **Enable debug logging and watch live logs:**
   ```bash
   sudo docker logs -f audioapp_backend
   ```
   (Then try login from browser to see detailed error)

---

## 📊 Success Criteria

- [ ] Login request returns HTTP 200 with authentication token
- [ ] No "Network Error" in browser console
- [ ] Backend logs show successful authentication
- [ ] User can access authenticated endpoints after login

---

## 🔧 Quick Fixes to Try

### Fix 1: Add AllowAny to Login View
If login view exists but returns 400, add this decorator:
```python
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes

@permission_classes([AllowAny])
class LoginView(APIView):
    # ... existing code
```

### Fix 2: Exempt API from CSRF
In `settings.py`:
```python
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read it
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = ['https://audio.precisepouchtrack.com']
```

### Fix 3: Use Token Authentication (if view exists)
Test with DRF's obtain_auth_token:
```bash
curl -X POST https://audio.precisepouchtrack.com/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"audioadmin123"}'
```

---

## 📝 Files to Check (In Order)

1. `/opt/audioapp/backend/api/urls.py` - URL routing
2. `/opt/audioapp/backend/api/views.py` - View definitions
3. `/opt/audioapp/backend/myproject/urls.py` - Main URL config
4. `/opt/audioapp/backend/myproject/settings.py` - Auth settings
5. `/opt/audioapp/backend/.env.production` - Environment config
6. `/opt/audioapp/backend/api/serializers.py` - Request validation

---

## 🎯 Most Likely Root Cause

Based on the symptoms, **the login endpoint probably doesn't have `AllowAny` permission**, causing it to reject unauthenticated requests with generic 400 error instead of proper 401 Unauthorized.

**Next Step:** Read `api/views.py` and `api/urls.py` to find the login view and verify it allows anonymous access.

---

## 📞 Need Help?

Once you provide the contents of:
- `backend/api/urls.py`
- `backend/api/views.py` (login-related sections)

We can pinpoint the exact issue and apply the correct fix.
