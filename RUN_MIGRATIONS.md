# Enable Server Persistence - Run Migrations

## Problem
- Client-side transcriptions disappear after logout
- Data stored only in localStorage (not persistent)
- Backend code exists but database tables not created

## Solution
Run database migrations to create the ClientTranscription table.

## Steps

### SSH to Server
```bash
ssh nickd@82.165.221.205
```

### Navigate to Backend
```bash
cd /opt/audioapp/backend
```

### Activate Virtual Environment
Try one of these (depending on which exists):
```bash
source venv/bin/activate
# OR
source env/bin/activate
# OR
source virtualenv/bin/activate
```

### Create Migration Files
```bash
python manage.py makemigrations audioDiagnostic
```

**Expected output:**
```
Migrations for 'audioDiagnostic':
  audioDiagnostic/migrations/0XXX_auto_YYYYMMDD_HHMM.py
    - Create model ClientTranscription
    - Create model DuplicateAnalysis
    - Alter field...
```

### Apply Migrations
```bash
python manage.py migrate audioDiagnostic
```

**Expected output:**
```
Running migrations:
  Applying audioDiagnostic.0XXX_auto_YYYYMMDD_HHMM... OK
```

### Restart Backend Services
```bash
# If using systemd
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# OR if using Docker
sudo docker restart audioapp_backend
sudo docker restart audioapp_celery
```

### Verify Tables Created
```bash
python manage.py dbshell
```

Then in SQLite shell:
```sql
.tables
SELECT COUNT(*) FROM audioDiagnostic_clienttranscription;
.exit
```

## After Migration

### What Changes:
1. ✅ Transcriptions save to server database after client-side processing
2. ✅ Data persists across logins/browsers/devices
3. ✅ Console shows: "Transcription synced to server"
4. ✅ On page load, transcriptions reload from server automatically

### Test It:
1. Upload an audio file
2. Transcribe it (client-side)
3. Check console for: `[Tab1Files] Transcription saved to server:`
4. Log out and back in
5. **Transcription should still be there!**

### Current Workflow (After Migrations):
```
Upload File → Client Transcription (heavy lifting on your device)
           ↓
    Save to Server (lightweight metadata + segments)
           ↓
    Data persists forever
           ↓
    Reload from server on any login/device
```

## Backend Code Already Exists

### Models (backend/audioDiagnostic/models.py):
- `ClientTranscription` - Stores transcription data

### API Endpoints (already working):
- `POST /api/projects/{id}/client-transcriptions/` - Save transcription
- `GET /api/projects/{id}/client-transcriptions/` - Load all transcriptions

### Frontend Integration (already working):
- Saves after transcription completes
- Loads on page load
- Merges server data with localStorage
- Falls back gracefully if server unavailable

## No Code Changes Needed!
Just run the migrations and it'll work automatically.
