# Production Deployment Guide
# Audio Duplicate Detection System

## 🚀 **Production Readiness Checklist**

This document identifies **all locations** that need updating when deploying the Audio Duplicate Detection system to production.

---

## 🔒 **Security & Authentication**

### **Django Settings** (`backend/myproject/settings.py`)

#### **❌ Current Development Settings (MUST CHANGE)**
```python
# Line ~25: SECURITY WARNING - CHANGE FOR PRODUCTION
DEBUG = True  # ❌ MUST be False in production

# Line ~30: SECURITY WARNING - CHANGE FOR PRODUCTION  
SECRET_KEY = 'django-insecure-your-secret-key-here'  # ❌ Use environment variable

# Line ~35: Currently allows all hosts - SECURITY RISK
ALLOWED_HOSTS = []  # ❌ MUST specify production domains
```

#### **✅ Required Production Changes**
```python
# Use environment variables
import os
from decouple import config

# SECURITY: Production settings
DEBUG = config('DEBUG', default=False, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# Add your production domains
ALLOWED_HOSTS = [
    'your-production-domain.com',
    'www.your-production-domain.com', 
    'api.your-production-domain.com'
]
```

### **CORS Configuration** (`backend/myproject/settings.py`)

#### **❌ Current Development Settings**
```python
# Line ~150: Allows all origins - SECURITY RISK
CORS_ALLOW_ALL_ORIGINS = True  # ❌ DANGEROUS in production

# Line ~155: Development frontend URL
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # ❌ Only for development
]
```

#### **✅ Required Production Changes**
```python
# SECURITY: Restrict CORS to production domains
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com",
]

# Additional security headers
CORS_ALLOW_CREDENTIALS = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

### **Authentication System** (`backend/audioDiagnostic/views.py`)

#### **❌ Current Development Settings**
```python
# Line ~40: Authentication temporarily disabled
# authentication_classes = [SessionAuthentication, BasicAuthentication]
# permission_classes = [IsAuthenticated]
```

#### **✅ Required Production Changes**
```python
# SECURITY: Enable authentication for all views
authentication_classes = [SessionAuthentication, BasicAuthentication]
permission_classes = [IsAuthenticated]

# Add JWT authentication for API
from rest_framework_simplejwt.authentication import JWTAuthentication
authentication_classes = [JWTAuthentication, SessionAuthentication]
```

---

## 🗄️ **Database Configuration**

### **Database Settings** (`backend/myproject/settings.py`)

#### **❌ Current Development Database**
```python
# Line ~80: SQLite for development only
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

#### **✅ Required Production Database**
```python
# Production PostgreSQL configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Connection pooling for production
DATABASES['default']['CONN_MAX_AGE'] = 600
```

### **Database Migrations**
```bash
# ❌ Current: Manual migration management
python manage.py makemigrations
python manage.py migrate

# ✅ Production: Automated in deployment pipeline
# Add to CI/CD scripts or Docker entrypoint
```

---

## 📁 **File Storage & Media Handling**

### **Static Files** (`backend/myproject/settings.py`)

#### **❌ Current Development Settings**
```python
# Line ~130: Local file serving
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

#### **✅ Required Production Settings**
```python
# AWS S3 or similar cloud storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE = 'storages.backends.s3boto3.StaticS3Boto3Storage'

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')  
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')

# CDN configuration
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
```

### **File Upload Security** (`backend/audioDiagnostic/views.py`)

#### **❌ Current Basic Validation**
```python
# Line ~200: Basic file type checking
if not file.name.endswith(('.pdf')):
    return Response({'error': 'Invalid file type'})
```

#### **✅ Enhanced Production Validation**
```python
import magic
from django.core.files.uploadedfile import UploadedFile

def validate_file_security(file: UploadedFile):
    # File type validation with python-magic
    file_type = magic.from_buffer(file.read(1024), mime=True)
    
    # Size limits
    if file.size > 100 * 1024 * 1024:  # 100MB limit
        raise ValidationError("File too large")
    
    # Virus scanning (integrate with ClamAV or similar)
    scan_result = virus_scan(file)
    if not scan_result.is_clean:
        raise ValidationError("File failed security scan")
```

---

## 🐳 **Docker & Container Configuration**

### **Docker Compose** (`backend/docker-compose.yml`)

#### **❌ Current Development Setup**
```yaml
version: '3.8'  # ❌ Version field is deprecated

services:
  redis:
    image: redis:7-alpine  # ❌ No resource limits
    ports:
      - "6379:6379"  # ❌ Exposes port to host
```

#### **✅ Production Configuration**
```yaml
services:
  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    networks:
      - internal  # ❌ Don't expose to host
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery_worker:
    build: .
    deploy:
      replicas: 2  # ✅ Multiple workers for production
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - DJANGO_SETTINGS_MODULE=myproject.production_settings
    depends_on:
      redis:
        condition: service_healthy

networks:
  internal:
    driver: bridge
    internal: true  # ✅ No external access
```

### **Dockerfile** (`backend/Dockerfile`)

#### **❌ Current Development Setup**
```dockerfile
FROM python:3.12-slim  # ❌ No specific version tag

# ❌ No security hardening
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

#### **✅ Production Dockerfile**
```dockerfile
FROM python:3.12.2-slim  # ✅ Specific version

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Security: Update packages and remove package manager
RUN apt-get update && apt-get install -y \
    ffmpeg libsndfile1 build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

# Security: Run as non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python manage.py check || exit 1

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "myproject.wsgi:application"]
```

---

## 🌐 **Frontend Production Build**

### **React Environment** (`frontend/audio-waveform-visualizer/.env`)

#### **❌ Current Development Settings**
```bash
# ❌ Development API endpoint
REACT_APP_API_URL=http://localhost:8000/api

# ❌ No production optimizations
```

#### **✅ Production Environment Variables**
```bash
# Production API endpoint
REACT_APP_API_URL=https://api.your-production-domain.com/api

# Production optimizations
GENERATE_SOURCEMAP=false
REACT_APP_ENV=production

# Analytics and monitoring
REACT_APP_ANALYTICS_ID=your-analytics-id
REACT_APP_SENTRY_DSN=your-sentry-dsn
```

### **Build Configuration** (`frontend/audio-waveform-visualizer/package.json`)

#### **❌ Current Development Scripts**
```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build"
  }
}
```

#### **✅ Production Build Scripts**
```json
{
  "scripts": {
    "build:prod": "NODE_ENV=production react-scripts build",
    "build:analyze": "npm run build && npx webpack-bundle-analyzer build/static/js/*.js",
    "serve:prod": "serve -s build -p 3000"
  }
}
```

### **API Configuration** (`frontend/audio-waveform-visualizer/src/screens/ProjectDetailPage.js`)

#### **❌ Current Hardcoded URLs**
```javascript
// Line ~50: Hardcoded localhost URLs
const response = await fetch('http://localhost:8000/api/projects/');
const statusResponse = await fetch('http://localhost:8000/api/infrastructure/status/');
```

#### **✅ Environment-Based Configuration**
```javascript
// Use environment variable for API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const response = await fetch(`${API_BASE_URL}/projects/`);
const statusResponse = await fetch(`${API_BASE_URL}/infrastructure/status/`);

// Add error handling for production
try {
  const response = await fetch(`${API_BASE_URL}/projects/`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
} catch (error) {
  // Send to monitoring service in production
  console.error('API Error:', error);
  sendToSentry(error);
}
```

---

## 🔧 **Infrastructure & Deployment**

### **Environment Variables** (Create `.env` files)

#### **Backend Environment** (`backend/.env`)
```bash
# Database
DB_NAME=audio_detection_prod
DB_USER=audio_user
DB_PASSWORD=secure_password_here
DB_HOST=db.your-domain.com
DB_PORT=5432

# Django
SECRET_KEY=your-very-long-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.your-domain.com,your-domain.com

# AWS Storage
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=audio-detection-media
AWS_S3_REGION_NAME=us-east-1

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Monitoring
SENTRY_DSN=your-sentry-dsn-here
```

### **Web Server Configuration**

#### **Nginx Configuration** (`/etc/nginx/sites-available/audio-detection`)
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/private.key;

    # Frontend (React build)
    location / {
        root /var/www/audio-detection/frontend/build;
        try_files $uri $uri/ /index.html;
        
        # Caching for static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Media files (if not using S3)
    location /media/ {
        alias /var/www/audio-detection/backend/media/;
        expires 30d;
    }
}
```

### **SSL/TLS Configuration**
```bash
# ❌ Current: No HTTPS
# ✅ Required: Let's Encrypt or commercial SSL

# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## 📊 **Monitoring & Logging**

### **Django Logging** (`backend/myproject/settings.py`)

#### **❌ Current: No Production Logging**
```python
# No logging configuration
```

#### **✅ Production Logging Configuration**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/audio-detection/django.log',
            'maxBytes': 15728640,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'sentry': {
            'level': 'ERROR',
            'class': 'sentry_sdk.integrations.logging.EventHandler',
        },
    },
    'root': {
        'handlers': ['file', 'sentry'],
        'level': 'INFO',
    },
}
```

### **Error Tracking** 

#### **Backend Sentry Integration** (`backend/myproject/settings.py`)
```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=config('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
    traces_sample_rate=0.1,
    send_default_pii=True
)
```

#### **Frontend Error Tracking** (`frontend/src/index.js`)
```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: process.env.REACT_APP_SENTRY_DSN,
  integrations: [new Sentry.BrowserTracing()],
  tracesSampleRate: 0.1,
});
```

---

## 🔄 **CI/CD Pipeline**

### **GitHub Actions** (`.github/workflows/deploy.yml`)
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Django Tests
        run: |
          python manage.py test
          
  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        run: |
          # Build Docker images
          docker build -t audio-detection:latest .
          
          # Deploy with zero-downtime
          docker-compose -f docker-compose.prod.yml up -d
          
          # Run migrations
          docker-compose exec web python manage.py migrate
          
          # Collect static files
          docker-compose exec web python manage.py collectstatic --noinput
```

---

## 📋 **Production Deployment Checklist**

### **✅ Security Checklist**
- [ ] Change `DEBUG = False` in Django settings
- [ ] Set strong `SECRET_KEY` from environment variable
- [ ] Configure `ALLOWED_HOSTS` with production domains
- [ ] Enable Django authentication on all API views
- [ ] Configure CORS for production frontend URLs only
- [ ] Set up SSL/TLS certificates (HTTPS)
- [ ] Implement file upload security scanning
- [ ] Configure secure headers (HSTS, CSP, etc.)

### **✅ Database & Storage**
- [ ] Migrate from SQLite to PostgreSQL
- [ ] Set up database connection pooling
- [ ] Configure automated database backups
- [ ] Move file storage to AWS S3 or similar
- [ ] Set up CDN for static asset delivery
- [ ] Configure Redis for production (persistence, clustering)

### **✅ Infrastructure & Performance**
- [ ] Set up production web server (Nginx/Apache)
- [ ] Configure Gunicorn for Django WSGI
- [ ] Set up Docker Compose for production
- [ ] Configure container resource limits
- [ ] Set up load balancing (if needed)
- [ ] Configure auto-scaling policies

### **✅ Monitoring & Maintenance**
- [ ] Set up application monitoring (Sentry)
- [ ] Configure log aggregation and rotation
- [ ] Set up uptime monitoring
- [ ] Configure performance monitoring (APM)
- [ ] Set up automated backups
- [ ] Create disaster recovery procedures

### **✅ Frontend Production**
- [ ] Update API URLs to production endpoints
- [ ] Configure environment variables for production
- [ ] Set up CDN for frontend assets
- [ ] Enable production optimizations (minification, etc.)
- [ ] Configure analytics and error tracking

---

## 🚨 **Critical Security Notes**

1. **Never commit secrets to git** - Use environment variables
2. **Always use HTTPS** in production - No exceptions
3. **Validate all file uploads** - Implement virus scanning
4. **Enable authentication** - Remove development bypasses
5. **Configure CORS properly** - Don't allow all origins
6. **Set up monitoring** - Know when things break
7. **Regular security updates** - Keep dependencies current

This guide covers **every location** that needs attention for a secure, scalable production deployment of your Audio Duplicate Detection system.