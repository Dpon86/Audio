# Linux Server Deployment Guide

Complete step-by-step guide for deploying the Audio Processing Application to a production Linux server.

**Target Setup:**
- OS: Ubuntu/Debian Linux
- Web Server: Nginx
- Database: PostgreSQL
- Deployment: Docker Compose
- Domain: Subdomain (e.g., audio.yourdomain.com)
- SSL: Let's Encrypt (free)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Server Preparation](#server-preparation)
3. [Domain & DNS Setup](#domain--dns-setup)
4. [Install Dependencies](#install-dependencies)
5. [Application Setup](#application-setup)
6. [Environment Configuration](#environment-configuration)
7. [Database Setup](#database-setup)
8. [Docker Configuration](#docker-configuration)
9. [Build & Deploy](#build--deploy)
10. [Nginx Configuration](#nginx-configuration)
11. [SSL Certificate Setup](#ssl-certificate-setup)
12. [Start Services](#start-services)
13. [Verification & Testing](#verification--testing)
14. [Maintenance & Updates](#maintenance--updates)
15. [Troubleshooting](#troubleshooting)

---

## Prerequisites

**What you need before starting:**

- ✅ SSH access to your Linux server
- ✅ Sudo/root privileges
- ✅ Domain name with access to DNS settings
- ✅ Basic command-line knowledge
- ✅ At least 4GB RAM, 20GB free disk space
- ✅ Server firewall allows HTTP (80) and HTTPS (443)

**Estimated Time:** 60-90 minutes

---

## Server Preparation

### 1. Connect to Your Server

```bash
ssh your_username@your_server_ip
```

### 2. Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 3. Create Application User (Optional but Recommended)

```bash
sudo adduser audioapp --disabled-password --gecos ""
sudo usermod -aG sudo audioapp
sudo usermod -aG docker audioapp  # Will add docker group later
```

---

## Domain & DNS Setup

### Configure DNS Records

Log into your domain registrar (GoDaddy, Namecheap, etc.) and add an A record:

| Type | Name  | Value           | TTL  |
|------|-------|-----------------|------|
| A    | audio | YOUR_SERVER_IP  | 3600 |

**Example:** If your domain is `example.com` and server IP is `203.0.113.10`:
- Creates: `audio.example.com` → `203.0.113.10`

**Verification:** Wait 5-15 minutes, then test:
```bash
ping audio.yourdomain.com
```

---

## Install Dependencies

### 1. Install Docker

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 2. Install Nginx

```bash
sudo apt install -y nginx

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Verify
sudo systemctl status nginx
```

### 3. Install Certbot (for SSL)

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 4. Add Your User to Docker Group

```bash
sudo usermod -aG docker $USER

# Log out and back in for this to take effect, or run:
newgrp docker

# Verify
docker ps  # Should work without sudo
```

---

## Application Setup

### 1. Create Application Directory

```bash
sudo mkdir -p /opt/audioapp
sudo chown $USER:$USER /opt/audioapp
cd /opt/audioapp
```

### 2. Clone/Upload Your Application

**Option A: If using Git:**
```bash
git clone https://github.com/yourusername/Audio.git .
```

**Option B: Upload via SCP from your local machine:**
```bash
# Run this on YOUR LOCAL MACHINE (Windows PowerShell):
scp -r C:\Users\NickD\Documents\Github\Audio\* your_username@your_server_ip:/opt/audioapp/
```

**Option C: Use SFTP client (WinSCP, FileZilla):**
- Connect to your server
- Upload entire Audio folder to `/opt/audioapp`

### 3. Verify Files

```bash
cd /opt/audioapp
ls -la

# Should see:
# backend/
# frontend/
# docs/
# package.json
# README.md
# etc.
```

---

## Environment Configuration

### 1. Create Backend Environment File

```bash
cd /opt/audioapp/backend
nano .env.production
```

**Add this content (customize the values):**

```bash
# Django Settings
DJANGO_SETTINGS_MODULE=myproject.settings
SECRET_KEY=your-super-secret-key-change-this-to-random-string
DEBUG=False
ALLOWED_HOSTS=audio.yourdomain.com,localhost,127.0.0.1

# Database (PostgreSQL)
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=audioapp_db
DATABASE_USER=audioapp_user
DATABASE_PASSWORD=your-strong-database-password
DATABASE_HOST=db
DATABASE_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Media & Static Files
MEDIA_ROOT=/app/media
STATIC_ROOT=/app/staticfiles

# CORS (adjust if frontend on different domain)
CORS_ALLOWED_ORIGINS=https://audio.yourdomain.com

# Security
CSRF_TRUSTED_ORIGINS=https://audio.yourdomain.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

**Save:** Ctrl+O, Enter, Ctrl+X

**Generate a strong SECRET_KEY:**
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```
Copy the output and replace `your-super-secret-key-change-this-to-random-string` above.

### 2. Create Frontend Environment File

```bash
cd /opt/audioapp/frontend/audio-waveform-visualizer
nano .env.production
```

**Add this content:**

```bash
REACT_APP_API_URL=https://audio.yourdomain.com/api
REACT_APP_WS_URL=wss://audio.yourdomain.com/ws
NODE_ENV=production
```

**Save:** Ctrl+O, Enter, Ctrl+X

---

## Database Setup

### Create PostgreSQL User & Database (will be done in Docker)

We'll create a separate `docker-compose.yml` for production. The database will be created automatically on first startup.

---

## Docker Configuration

### 1. Update Backend Dockerfile for Production

```bash
cd /opt/audioapp/backend
nano Dockerfile.production
```

**Add this content:**

```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn psycopg2-binary

# Copy application
COPY . .

# Collect static files (will run in entrypoint)
RUN mkdir -p /app/staticfiles /app/media

# Create entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
```

### 2. Create Entrypoint Script

```bash
nano docker-entrypoint.sh
```

**Add this content:**

```bash
#!/bin/bash
set -e

# Wait for database
echo "Waiting for PostgreSQL..."
while ! pg_isready -h $DATABASE_HOST -p $DATABASE_PORT -U $DATABASE_USER; do
  sleep 1
done
echo "PostgreSQL is ready!"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
echo "Creating superuser if needed..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'changeme123')
    print('Superuser created: admin / changeme123')
else:
    print('Superuser already exists')
END

# Execute the main command
exec "$@"
```

**Make executable:**
```bash
chmod +x docker-entrypoint.sh
```

### 3. Create Production Docker Compose File

```bash
cd /opt/audioapp
nano docker-compose.production.yml
```

**Add this content:**

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    container_name: audioapp_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: audioapp_db
      POSTGRES_USER: audioapp_user
      POSTGRES_PASSWORD: your-strong-database-password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - audioapp_network

  # Redis Cache & Message Broker
  redis:
    image: redis:7-alpine
    container_name: audioapp_redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - audioapp_network

  # Django Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    container_name: audioapp_backend
    restart: unless-stopped
    env_file:
      - ./backend/.env.production
    volumes:
      - ./backend/media:/app/media
      - static_files:/app/staticfiles
    depends_on:
      - db
      - redis
    networks:
      - audioapp_network
    ports:
      - "8000:8000"

  # Celery Worker
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    container_name: audioapp_celery_worker
    restart: unless-stopped
    command: celery -A myproject worker -l info --pool=solo
    env_file:
      - ./backend/.env.production
    volumes:
      - ./backend/media:/app/media
      - static_files:/app/staticfiles
    depends_on:
      - db
      - redis
    networks:
      - audioapp_network

  # Celery Beat (Scheduler)
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    container_name: audioapp_celery_beat
    restart: unless-stopped
    command: celery -A myproject beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file:
      - ./backend/.env.production
    volumes:
      - ./backend/media:/app/media
    depends_on:
      - db
      - redis
    networks:
      - audioapp_network

networks:
  audioapp_network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  static_files:
```

**Replace `your-strong-database-password` with the same password from `.env.production`**

### 4. Build Frontend

We'll build the React app locally in the container and serve static files through Nginx.

```bash
cd /opt/audioapp/frontend/audio-waveform-visualizer
nano Dockerfile.production
```

**Add this content:**

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source
COPY . .

# Copy production environment
COPY .env.production .env

# Build application
RUN npm run build

# Production stage - serve with Nginx
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/build /usr/share/nginx/html/

# Copy custom Nginx config (we'll create this)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 5. Create Nginx Config for Frontend Container

```bash
nano nginx.conf
```

**Add this content:**

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # React Router - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 6. Add Frontend to Docker Compose

```bash
cd /opt/audioapp
nano docker-compose.production.yml
```

**Add the frontend service (add after the celery_beat service, before networks section):**

```yaml
  # React Frontend
  frontend:
    build:
      context: ./frontend/audio-waveform-visualizer
      dockerfile: Dockerfile.production
    container_name: audioapp_frontend
    restart: unless-stopped
    networks:
      - audioapp_network
    ports:
      - "3000:80"
```

---

## Build & Deploy

### 1. Build Docker Images

```bash
cd /opt/audioapp

# Build all services
docker compose -f docker-compose.production.yml build

# This will take 10-15 minutes on first build
```

### 2. Start Services (Test Mode First)

```bash
# Start in foreground to check for errors
docker compose -f docker-compose.production.yml up

# Watch the logs for any errors
# You should see:
# - PostgreSQL ready
# - Migrations running
# - Superuser created
# - Gunicorn starting
# - Celery worker ready
# - Frontend built

# If everything looks good, press Ctrl+C to stop
```

### 3. Start Services in Background

```bash
docker compose -f docker-compose.production.yml up -d

# Check status
docker compose -f docker-compose.production.yml ps

# All containers should show "Up"
```

### 4. View Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f celery_worker
```

---

## Nginx Configuration

### 1. Create Nginx Site Configuration

```bash
sudo nano /etc/nginx/sites-available/audioapp
```

**Add this content:**

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name audio.yourdomain.com;

    # Allow Certbot validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect everything else to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name audio.yourdomain.com;

    # SSL certificates (will be added by Certbot)
    # ssl_certificate /etc/letsencrypt/live/audio.yourdomain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/audio.yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Max upload size (for audio files)
    client_max_body_size 500M;

    # Timeouts for long-running uploads
    client_body_timeout 300s;
    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    # Frontend - React App
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Long timeouts for processing tasks
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://localhost:8000/admin/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django Static Files
    location /static/ {
        proxy_pass http://localhost:8000/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Media Files (uploaded audio, PDFs)
    location /media/ {
        proxy_pass http://localhost:8000/media/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # WebSocket support (if needed for real-time updates)
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**IMPORTANT:** Replace `audio.yourdomain.com` with your actual subdomain throughout the file!

### 2. Enable Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/audioapp /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# If test passes:
sudo systemctl reload nginx
```

---

## SSL Certificate Setup

### 1. Obtain Let's Encrypt Certificate

```bash
# Run Certbot
sudo certbot --nginx -d audio.yourdomain.com

# Follow the prompts:
# - Enter your email address
# - Agree to terms of service
# - Choose whether to redirect HTTP to HTTPS (recommend: Yes)

# Certbot will automatically:
# 1. Obtain the certificate
# 2. Update your Nginx config
# 3. Reload Nginx
```

### 2. Test Auto-Renewal

```bash
# Dry run
sudo certbot renew --dry-run

# If successful, certificates will auto-renew every 60 days
```

### 3. Verify SSL

Visit: `https://audio.yourdomain.com` in your browser
- Should show green padlock
- Certificate should be valid

Test with: https://www.ssllabs.com/ssltest/analyze.html?d=audio.yourdomain.com

---

## Start Services

### 1. Enable Docker Services to Start on Boot

```bash
cd /opt/audioapp

# Start services
docker compose -f docker-compose.production.yml up -d

# Enable Docker to start on boot
sudo systemctl enable docker

# Create systemd service for auto-start (optional but recommended)
sudo nano /etc/systemd/system/audioapp.service
```

**Add this content:**

```ini
[Unit]
Description=Audio Processing Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/audioapp
ExecStart=/usr/bin/docker compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.production.yml down
User=root

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable audioapp
sudo systemctl start audioapp
```

### 2. Verify All Services Running

```bash
# Check Docker containers
docker ps

# Should see 6 containers running:
# - audioapp_db
# - audioapp_redis
# - audioapp_backend
# - audioapp_celery_worker
# - audioapp_celery_beat
# - audioapp_frontend

# Check Nginx
sudo systemctl status nginx

# Check system resource usage
docker stats
```

---

## Verification & Testing

### 1. Test Backend API

```bash
# Health check (if you have one)
curl https://audio.yourdomain.com/api/health/

# Or test a simple endpoint
curl https://audio.yourdomain.com/api/projects/
```

### 2. Test Frontend

Open browser: `https://audio.yourdomain.com`

You should see your React application load.

### 3. Test Admin Panel

Visit: `https://audio.yourdomain.com/admin/`

Login with:
- Username: `admin`
- Password: `changeme123`

**IMMEDIATELY CHANGE THIS PASSWORD:**
```bash
docker exec -it audioapp_backend python manage.py changepassword admin
```

### 4. Test Full Workflow

1. Upload an audio file
2. Generate transcription
3. Run duplicate detection
4. Review results
5. Compare with PDF

### 5. Check Celery Tasks

```bash
# View Celery worker logs
docker logs -f audioapp_celery_worker

# Test by triggering a transcription task
# Watch logs for task processing
```

---

## Maintenance & Updates

### Update Application Code

```bash
cd /opt/audioapp

# Pull latest changes (if using Git)
git pull

# Or re-upload files via SCP/SFTP

# Rebuild and restart
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
```

### Database Backup

```bash
# Backup PostgreSQL database
docker exec audioapp_db pg_dump -U audioapp_user audioapp_db > backup_$(date +%Y%m%d).sql

# Restore from backup
cat backup_20240101.sql | docker exec -i audioapp_db psql -U audioapp_user audioapp_db
```

### View Logs

```bash
# All containers
docker compose -f docker-compose.production.yml logs -f

# Specific container
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f celery_worker

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Monitor Resources

```bash
# Real-time container stats
docker stats

# Disk usage
df -h
docker system df

# Clean up old images/containers
docker system prune -a
```

### Restart Services

```bash
# Restart all containers
docker compose -f docker-compose.production.yml restart

# Restart specific service
docker compose -f docker-compose.production.yml restart backend
docker compose -f docker-compose.production.yml restart celery_worker

# Restart Nginx
sudo systemctl restart nginx
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs backend

# Common issues:
# - Database connection: Check DATABASE_HOST in .env.production
# - Port conflicts: Check if port 8000/3000 already in use
# - Permission issues: Check file ownership

# Check port usage
sudo netstat -tulpn | grep LISTEN
```

### 502 Bad Gateway

```bash
# Check if backend is running
docker ps | grep backend

# Check backend logs
docker logs audioapp_backend

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log

# Test backend directly
curl http://localhost:8000/api/

# If that works, issue is in Nginx config
sudo nginx -t
```

### Static Files Not Loading

```bash
# Collect static files manually
docker exec audioapp_backend python manage.py collectstatic --noinput

# Check volume mount
docker inspect audioapp_backend | grep -A 10 Mounts

# Check Nginx proxy_pass for /static/
```

### Celery Tasks Not Running

```bash
# Check Celery worker logs
docker logs -f audioapp_celery_worker

# Check Redis connection
docker exec audioapp_redis redis-cli ping
# Should return: PONG

# Check Celery is connected to Redis
docker exec audioapp_celery_worker celery -A myproject inspect active
```

### Database Connection Issues

```bash
# Check database container
docker exec audioapp_db psql -U audioapp_user -d audioapp_db -c "SELECT 1;"

# Check credentials match in:
# - docker-compose.production.yml (POSTGRES_* variables)
# - backend/.env.production (DATABASE_* variables)

# Test connection from backend container
docker exec audioapp_backend python manage.py dbshell
```

### Out of Memory

```bash
# Check container memory usage
docker stats

# Add memory limits to docker-compose.production.yml:
services:
  backend:
    ...
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

# Check system memory
free -h

# Restart services with limits
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

### SSL Certificate Issues

```bash
# Check certificate validity
sudo certbot certificates

# Renew manually
sudo certbot renew

# If renewal fails, check:
# 1. Port 80 is accessible from internet
# 2. DNS resolves correctly
# 3. Nginx allows /.well-known/acme-challenge/

# Test renewal
sudo certbot renew --dry-run
```

### File Upload Fails

```bash
# Check Nginx client_max_body_size
sudo nano /etc/nginx/sites-available/audioapp
# Should have: client_max_body_size 500M;

# Check Django settings
docker exec audioapp_backend python manage.py shell
>>> from django.conf import settings
>>> settings.FILE_UPLOAD_MAX_MEMORY_SIZE
>>> settings.DATA_UPLOAD_MAX_MEMORY_SIZE

# Check disk space
df -h

# Check media directory permissions
docker exec audioapp_backend ls -la /app/media/
```

### Performance Issues

```bash
# Increase Gunicorn workers (in docker-compose.production.yml)
# Rule of thumb: (2 x CPU cores) + 1
command: gunicorn myproject.wsgi:application --bind 0.0.0.0:8000 --workers 8 --timeout 120

# Add Redis maxmemory (in docker-compose.production.yml)
redis:
  command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru

# Scale Celery workers
docker compose -f docker-compose.production.yml up -d --scale celery_worker=4

# Enable query logging to find slow database queries
# In backend/.env.production, temporarily add:
# DEBUG=True  (DO NOT leave this on in production!)
```

---

## Security Checklist

Before going live, verify:

- [ ] `DEBUG=False` in backend/.env.production
- [ ] Strong `SECRET_KEY` generated
- [ ] Strong database password set
- [ ] Admin password changed from default
- [ ] SSL certificate installed and working
- [ ] Firewall configured (only allow 80, 443, 22)
- [ ] `ALLOWED_HOSTS` set correctly
- [ ] `CORS_ALLOWED_ORIGINS` restricted to your domain
- [ ] Regular backups scheduled
- [ ] Server OS and packages updated
- [ ] Docker images regularly updated
- [ ] Nginx security headers enabled
- [ ] Rate limiting configured (optional, see below)

### Optional: Add Rate Limiting

In `/etc/nginx/sites-available/audioapp`, add before `server` block:

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=2r/m;
```

Then in the API location block:

```nginx
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    ...
}

location /api/upload/ {
    limit_req zone=upload_limit burst=3 nodelay;
    ...
}
```

Reload Nginx: `sudo systemctl reload nginx`

---

## Next Steps

**After successful deployment:**

1. **Set up monitoring:**
   - Install Uptime Robot or similar for downtime alerts
   - Set up log aggregation (ELK stack, Graylog, etc.)
   - Configure server monitoring (Netdata, Prometheus, etc.)

2. **Set up automated backups:**
   - Daily database backups
   - Weekly full system backups
   - Store backups off-server (S3, Backblaze B2, etc.)

3. **Performance optimization:**
   - Enable Redis caching for frequent queries
   - Set up CDN for static files (CloudFlare, etc.)
   - Optimize database queries (add indexes)

4. **Create deployment scripts:**
   - Automate updates with shell scripts
   - Set up CI/CD pipeline (GitHub Actions, etc.)

---

## Support Resources

**Official Documentation:**
- Django: https://docs.djangoproject.com/
- Docker: https://docs.docker.com/
- Nginx: https://nginx.org/en/docs/
- Certbot: https://certbot.eff.org/

**Community Support:**
- Django Forum: https://forum.djangoproject.com/
- Docker Forums: https://forums.docker.com/
- Stack Overflow: https://stackoverflow.com/

**Your Application:**
- Check other docs in `/docs` folder
- Review ARCHITECTURE.md for system design
- See QUICK_START_WORKING.md for development setup

---

## Quick Reference Commands

```bash
# Start all services
docker compose -f docker-compose.production.yml up -d

# Stop all services
docker compose -f docker-compose.production.yml down

# Restart all services
docker compose -f docker-compose.production.yml restart

# View logs
docker compose -f docker-compose.production.yml logs -f

# Update and rebuild
git pull && docker compose -f docker-compose.production.yml up -d --build

# Backup database
docker exec audioapp_db pg_dump -U audioapp_user audioapp_db > backup.sql

# Django shell
docker exec -it audioapp_backend python manage.py shell

# Django admin
docker exec -it audioapp_backend python manage.py createsuperuser

# Check status
docker ps && sudo systemctl status nginx

# Clean up Docker
docker system prune -a
```

---

**Deployment guide created on:** 2024
**Target environment:** Ubuntu/Debian Linux with Nginx, PostgreSQL, Docker Compose
**Application:** Audio Processing & Duplicate Detection System

**Questions or issues?** Review the Troubleshooting section or check application logs for detailed error messages.
