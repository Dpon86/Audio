# Audio Processing App - System Architecture

**Last Updated:** March 21, 2026  
**Domain:** https://audio.precisepouchtrack.com

## Overview

The Audio Processing App is a full-stack web application for processing and analyzing audio files. It consists of:
- **Frontend:** React SPA with audio waveform visualization
- **Backend:** Django REST Framework API in Docker
- **Reverse Proxy:** Nginx for routing and static file serving
- **Database:** PostgreSQL (presumed, in Docker)
- **Storage:** Local filesystem for media files

## Architecture Diagram

```
[Browser Client]
      |
      | HTTPS (443)
      v
[Nginx Web Server] ---> [Static Frontend Files]
      |                  /opt/audioapp/frontend/audio-waveform-visualizer/build/
      |
      |---> /api/        [Proxy to Django Backend]
      |---> /admin/      [Proxy to Django Backend]
      |---> /ws/         [WebSocket Proxy]
      |---> /media/      [Direct File Serving] --> /opt/audioapp/backend/media/
      |
      v
[Docker: audioapp_backend]
      |
      |---> Django App (Port 8001)
      |---> Gunicorn/Uvicorn
      |---> Volume: ./backend/media:/app/media
      |---> Volume: static_files:/app/staticfiles
```

## Request Flow Details

### 1. Static Frontend Assets (HTML, CSS, JS)
```
Browser → Nginx (443) → File System
Path: /opt/audioapp/frontend/audio-waveform-visualizer/build/
```
- Nginx serves React build files directly
- Main JS bundle: `main.[hash].js`
- Cache: 1 year for immutable assets
- React Router handles client-side routing via `index.html` fallback

### 2. API Requests
```
Browser → Nginx (443) → Proxy → Django Backend (localhost:8001)
```
- All `/api/*` requests proxied to backend
- Headers forwarded: Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto
- Long timeouts (300s) for audio processing operations
- Django handles authentication, business logic, database operations

### 3. Media Files (Audio, PDFs)
```
Browser → Nginx (443) → Direct File Serving
Host Path: /opt/audioapp/backend/media/
Container Path: /app/media (volume mount)
```
- **Critical:** Nginx serves media files DIRECTLY from disk
- Does NOT proxy to Django (would fail in production with DEBUG=False)
- Cache: 30 days
- File structure:
  - `/media/audio/` - Uploaded original files
  - `/media/processed/` - Processed audio files
  - `/media/assembled/` - Assembled output files
  - `/media/audio/processed/` - Nested processed files (legacy?)

### 4. Django Admin Interface
```
Browser → Nginx (443) → Proxy → Django Admin (localhost:8001/admin/)
```
- Full proxy with Django headers
- Admin static files served via `/backend-static/` location

### 5. WebSocket Connections
```
Browser → Nginx (443) → WebSocket Upgrade → Django Channels (localhost:8001/ws/)
```
- Real-time updates for audio processing status
- Connection upgrade handled by Nginx

## Component Details

### Nginx Configuration
**Config File:** `/etc/nginx/sites-available/audioapp`  
**Symlink:** `/etc/nginx/sites-enabled/audioapp` → `sites-available/audioapp`

**Key Locations:**
```nginx
# Frontend root
root /opt/audioapp/frontend/audio-waveform-visualizer/build;

# Static assets (CSS, JS)
location /static/ {
    alias /opt/audioapp/frontend/audio-waveform-visualizer/build/static/;
    expires 1y;
}

# API proxy
location /api/ {
    proxy_pass http://localhost:8001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Media files - DIRECT SERVING (not proxied!)
location /media/ {
    alias /opt/audioapp/backend/media/;
    expires 30d;
}
```

**SSL Configuration:**
- Certificate: `/etc/letsencrypt/live/audio.precisepouchtrack.com/fullchain.pem`
- Auto-renewal: Certbot
- HTTP → HTTPS redirect on port 80

### Docker Backend Container
**Container Name:** `audioapp_backend`  
**Base Port:** 8001 (internal, not exposed to internet)

**Volume Mounts:**
```yaml
volumes:
  - ./backend/media:/app/media          # Media files
  - static_files:/app/staticfiles       # Django static files
```

**Django Configuration:**
```python
DEBUG = False  # Production mode
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
```

**Important:** Django does NOT serve media files when `DEBUG=False`. Nginx must handle this.

### Frontend Application
**Build Path:** `/opt/audioapp/frontend/audio-waveform-visualizer/build/`  
**Framework:** React with audio waveform visualization  
**Build Hash:** `main.03fe5211.js` (as of March 21, 2026)

**Media URL Normalization:**
Frontend normalizes API responses to handle:
- Absolute URLs: `https://audio.precisepouchtrack.com/media/...`
- Relative URLs: `/media/...`
- Ensures consistent URL handling across all components

**Key Components:**
- `Tab3Duplicates.js` - Waveform comparison
- `Tab4Results.js` - Processing results
- `WaveformDuplicateEditor.js` - Waveform editing
- `api.js` - API client with URL normalization

## File Paths Reference

### Host System
```
/opt/audioapp/
├── frontend/
│   └── audio-waveform-visualizer/
│       └── build/              # Served by nginx
├── backend/
│   └── media/                  # Media storage (mounted to container)
├── docker-compose.production.yml
└── Documentation/
    └── ARCHITECTURE.md         # This file
```

### Docker Container
```
/app/
├── media/                      # Mounted from host
│   ├── audio/
│   ├── processed/
│   └── assembled/
├── staticfiles/                # Django static files
├── myproject/                  # Django settings
└── manage.py
```

### Nginx
```
/etc/nginx/
├── sites-available/
│   └── audioapp               # Main config
├── sites-enabled/
│   └── audioapp -> ../sites-available/audioapp
└── nginx.conf                 # Global config
```

## Common Issues & Solutions

### Issue: Media Files Return 404
**Symptoms:**
- Browser shows 404 for `/media/` URLs
- Django headers present (X-Frame-Options: DENY)
- Files exist in `/opt/audioapp/backend/media/`

**Root Cause:** Nginx is proxying to Django instead of serving files directly. Django doesn't serve media in production (`DEBUG=False`).

**Solution:** Configure nginx to use `alias` instead of `proxy_pass`:
```nginx
location /media/ {
    alias /opt/audioapp/backend/media/;  # Direct serving
    expires 30d;
}
```

### Issue: 301 Redirect to localhost:8001
**Symptoms:**
- Browser Network tab shows: `301 → https://localhost:8001/media/...`
- Results in ERR_TIMED_OUT

**Root Cause:** Missing proxy headers; Django generates URLs with `localhost:8001`

**Solution:** Add proxy headers to nginx:
```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_redirect off;
```

### Issue: Permission Denied on Static Files
**Symptoms:**
- Nginx error log: `stat() failed (13: Permission denied)`
- Browser shows 403 or 404 for CSS/JS files

**Root Cause:** Files not readable by nginx user (www-data)

**Solution:**
```bash
sudo chmod -R u=rwX,go=rX /opt/audioapp/frontend/audio-waveform-visualizer/build/
sudo chown -R nickd:www-data /opt/audioapp/frontend/audio-waveform-visualizer/build/
```

### Issue: Changes Not Reflected
**Symptoms:**
- Updated nginx config but old config still active
- Browser still shows old frontend version

**Troubleshooting:**
```bash
# Check if nginx reloaded config
sudo nginx -T | grep "location /media/"

# Verify file being served
curl -I https://audio.precisepouchtrack.com/static/js/main.[hash].js

# Force nginx reload
sudo systemctl reload nginx

# Browser: Hard refresh (Ctrl+Shift+R)
```

## Deployment Process

### Frontend Deployment
1. Build React app locally: `npm run build`
2. SCP build to server: `scp -r build/* user@server:/opt/audioapp/frontend/audio-waveform-visualizer/build/`
3. Fix permissions: `sudo chmod -R u=rwX,go=rX` + `sudo chown -R nickd:www-data`
4. Verify hash in HTML: `curl https://audio.precisepouchtrack.com/ | grep main`
5. Hard refresh browser to clear cache

### Backend Deployment
1. Update code in Docker container
2. Rebuild container: `docker-compose -f docker-compose.production.yml build`
3. Restart container: `docker-compose -f docker-compose.production.yml up -d`
4. Check logs: `docker logs audioapp_backend`

### Nginx Configuration Changes
1. Backup config: `sudo cp /etc/nginx/sites-available/audioapp /etc/nginx/audioapp.backup.$(date +%Y%m%d_%H%M%S)`
2. Edit: `sudo nano /etc/nginx/sites-available/audioapp`
3. Test syntax: `sudo nginx -t`
4. Reload: `sudo systemctl reload nginx`
5. Verify in compiled config: `sudo nginx -T | grep -A 10 "location /media/"`

## Monitoring & Logs

### Nginx Logs
```bash
# Access log (requests)
sudo tail -f /var/log/nginx/access.log | grep media

# Error log (failures)
sudo tail -f /var/log/nginx/error.log
```

### Docker Logs
```bash
# Backend application logs
docker logs -f audioapp_backend

# All containers
docker-compose -f docker-compose.production.yml logs -f
```

### System Status
```bash
# Nginx status
sudo systemctl status nginx

# Docker containers
docker ps

# Disk space (media files can be large)
df -h /opt/audioapp/
```

## Security Considerations

1. **SSL/TLS:** Let's Encrypt certificate with auto-renewal
2. **Nginx:** Only internal port 8001 exposed to localhost, not internet
3. **Django:** SECURE_PROXY_SSL_HEADER configured for HTTPS detection
4. **CORS:** Configured in Django for frontend domain
5. **File Upload:** Max size 500MB (`client_max_body_size 500M`)
6. **Timeouts:** 300s for long audio processing operations

## Performance Notes

- **Static Assets:** 1-year cache for immutable files (CSS, JS with hash)
- **Media Files:** 30-day cache for processed audio
- **Compression:** Nginx gzip enabled (check `/etc/nginx/nginx.conf`)
- **CDN:** Not currently used; consider CloudFlare for media files
- **Database:** Connection pooling in Django settings

## Troubleshooting Checklist

When debugging production issues:

1. **Check Nginx is running:** `sudo systemctl status nginx`
2. **Check Docker is running:** `docker ps | grep audioapp`
3. **Test media URL directly:** `curl -I https://audio.precisepouchtrack.com/media/processed/[filename]`
4. **Check file exists:** `ls -la /opt/audioapp/backend/media/processed/`
5. **Check nginx error log:** `sudo tail -50 /var/log/nginx/error.log`
6. **Check Django logs:** `docker logs --tail 100 audioapp_backend`
7. **Verify nginx config loaded:** `sudo nginx -T | grep "server_name audio.precisepouchtrack.com" -A 50`
8. **Test from container:** `docker exec audioapp_backend ls -la /app/media/processed/`
9. **Check permissions:** `ls -la /opt/audioapp/backend/media/ | head`
10. **Browser console:** Check for CORS, 404, or timeout errors

## Key Takeaways

1. **Media files MUST be served directly by Nginx**, not proxied to Django in production
2. **File permissions matter:** www-data must be able to read files
3. **Nginx config changes require reload** to take effect
4. **Symlink structure:** Changes to `sites-available/audioapp` automatically apply to `sites-enabled/`
5. **Docker volumes persist data** across container restarts
6. **Frontend hash changes** with each build; update references accordingly
7. **Browser caching is aggressive**; hard refresh required to see changes

## References

- Deployment Guide: `/opt/audioapp/DEPLOYMENT_GUIDE.md`
- Nginx Config: `/etc/nginx/sites-available/audioapp`
- Docker Compose: `/opt/audioapp/docker-compose.production.yml`
- Frontend Build: `/opt/audioapp/frontend/audio-waveform-visualizer/build/`

---

**Maintenance Notes:**
- Update this document when architecture changes
- Record major configuration changes with dates
- Include lessons learned from production issues
