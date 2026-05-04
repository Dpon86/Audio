# Troubleshooting: Static Assets 404 / 403 (May 2026)

## Summary

After deploying a new frontend build, the React app failed to load entirely. All requests to `/static/js/main.*.js` returned 404, then 403 during diagnosis. Root causes were a misconfigured nginx `try_files` directive and incorrect directory permissions.

---

## Symptoms

- Browser showed blank page with no React app loaded
- DevTools Network tab: `main.HASH.js` returning 404
- `curl https://audio.precisepouchtrack.com/static/js/main.284fcfe1.js` → `404`
- Both old and new JS filenames returned 404 (ruled out hash mismatch)
- File confirmed present on disk at correct path with correct permissions (`-rw-rw-r--`)

---

## Root Cause 1: `try_files` incompatible with `alias`

**Location:** `/etc/nginx/sites-enabled/audioapp`

**The broken config:**
```nginx
location /static/ {
    alias /opt/audioapp/frontend/audio-waveform-visualizer/build/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;   # <-- THIS BREAKS EVERYTHING
}
```

**Why it fails:** nginx's `try_files` resolves paths using the `root` directive, not `alias`. So `try_files $uri` always resolves to `/opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/main.HASH.js` *relative to root*, not relative to the alias path. The file is never found, so nginx always falls through to `=404`.

**The fix:**
```nginx
location /static/ {
    alias /opt/audioapp/frontend/audio-waveform-visualizer/build/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    # No try_files — incompatible with alias
}
```

**Rule:** Never use `try_files` inside a `location` block that uses `alias`.

---

## Root Cause 2: Directory permissions blocked nginx (403)

After fixing the nginx config, requests changed from `404` to `403`.

**The problem:** Build subdirectories had `drwx------` (700) permissions — owner-only access. nginx runs as `www-data`, which is not the owner, so it could not traverse the directories to read the files inside.

```
drwx------ 2 nickd nickd 4096 build/static/       ← www-data blocked
drwx------ 2 nickd nickd 4096 build/static/js/    ← www-data blocked
drwx------ 2 nickd nickd 4096 build/static/css/   ← www-data blocked
```

**Why this happened:** Files were deployed via manual SCP. The local `build/` directories happened to have 700 permissions (set by Create React App or a previous deploy), and they were preserved through SCP. The normal deploy script (`deploy-frontend.sh`) includes a `chmod` step, but it was bypassed.

**The fix:**
```bash
sudo chmod -R a+rX /opt/audioapp/frontend/audio-waveform-visualizer/build/
```

This sets read + execute for all users on all directories and files, allowing `www-data` to traverse and serve them.

**Verification:**
```bash
# Should return 200
curl -sk -o /dev/null -w '%{http_code}\n' https://audio.precisepouchtrack.com/static/js/main.HASH.js
```

---

## Additional Fix: CSP blocking HuggingFace + WASM

When testing client-side Whisper transcription, the browser console showed CSP violations.

**Missing from CSP:**
- `connect-src` did not include HuggingFace CDN URLs (needed to download model weights)
- `script-src` did not include `wasm-unsafe-eval` (needed for ONNX WASM runtime)

**Fix applied to `/etc/nginx/sites-enabled/audioapp`:**
```nginx
add_header Content-Security-Policy "
  ...
  script-src 'self' 'wasm-unsafe-eval';
  connect-src 'self'
    https://huggingface.co
    https://*.huggingface.co
    https://cdn-lfs.huggingface.co
    https://cdn-lfs-us-1.huggingface.co;
  ...
" always;
```

---

## Diagnosis Commands

```bash
# Check what HTTP status static files return
curl -sk -o /dev/null -w '%{http_code}\n' https://audio.precisepouchtrack.com/static/js/main.HASH.js

# Confirm file exists on disk
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/static/js/

# Check directory permissions (look for drwx------ which blocks www-data)
ls -la /opt/audioapp/frontend/audio-waveform-visualizer/build/static/

# Check nginx error log for permission denied
sudo tail -20 /var/log/nginx/error.log | grep -E "Permission denied|static"

# Check active nginx config for try_files in static location
grep -A5 'location /static/' /etc/nginx/sites-enabled/audioapp
```

---

## Prevention

1. **Always deploy frontend using `deploy-frontend.sh`** — it includes `chmod -R 755` on the nginx root.
2. **If deploying manually via SCP + rsync**, always run permissions fix afterwards (see Deployment Guide section 3.3).
3. **Never add `try_files` to `alias` location blocks** in nginx.
4. The nginx config in `/etc/nginx/sites-enabled/audioapp` should never have `try_files $uri =404` in the `/static/` block.
