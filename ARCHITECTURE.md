# Software Architecture Documentation
# Audio Duplicate Detection System

## 🏗️ **System Overview**

The Audio Duplicate Detection system is built with a **microservices architecture** using Django REST API backend, React frontend, and Docker containerization for audio processing tasks.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  React Frontend │────│   Django API     │────│ Docker Services │
│   (Port 3000)   │    │   (Port 8000)    │    │ Celery + Redis  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        │                        │                        │
    User Interface         Business Logic           Audio Processing
```

---

## 🎨 **Frontend Architecture** 
**Location:** `frontend/audio-waveform-visualizer/`

### **Core Application Files**

#### **`src/App.js`**
- **Purpose:** Main application component and routing configuration
- **Responsibilities:** 
  - React Router setup for navigation
  - Global app-wide state management
  - Authentication context provider
  - Error boundary implementation
- **Routes:**
  - `/` → Project list page
  - `/project/:id` → Project detail page
  - `/create` → New project creation

#### **`src/index.js`**
- **Purpose:** Application entry point and React DOM mounting
- **Responsibilities:**
  - React app initialization
  - Global CSS imports
  - Service worker registration (if applicable)

### **Screen Components** 
**Location:** `src/screens/`

#### **`ProjectListPage.js`**
- **Purpose:** Main dashboard showing all user projects
- **Features:**
  - Project grid/list view with status indicators
  - Create new project button
  - Project filtering and search
  - Real-time status updates
- **API Calls:** `GET /api/projects/`
- **State Management:** Project list state, loading states

#### **`ProjectDetailPage.js`** ⭐ **Core Component**
- **Purpose:** Complete project workflow interface with interactive duplicate detection
- **Features:**
  - PDF file upload with drag-and-drop
  - Audio file upload with validation
  - Enhanced 3-step processing workflow:
    - Step 1: Transcribe all audio files
    - Step 2a: Match audio to PDF section with side-by-side comparison
    - Step 2b: Detect duplicates with detailed analysis
    - Step 2c: Interactive duplicate review with audio playback
  - Infrastructure status monitoring
  - Real-time progress tracking
  - Results download interface
- **API Calls:** 
  - `GET /api/projects/{id}/`
  - `POST /api/projects/{id}/upload-pdf/`
  - `POST /api/projects/{id}/upload-audio/`
  - `POST /api/projects/{id}/transcribe/`
  - `POST /api/projects/{id}/match-pdf/` ⭐ **New**
  - `POST /api/projects/{id}/detect-duplicates/` ⭐ **New**
  - `GET /api/projects/{id}/duplicates/` ⭐ **New**
  - `POST /api/projects/{id}/confirm-deletions/` ⭐ **New**
  - `PATCH /api/projects/{id}/` ⭐ **New** (Reset match status)
  - `GET /api/infrastructure/status/`
- **State Management:** 
  - Project data, file upload progress
  - Infrastructure status polling
  - Processing status updates
  - PDF match results with side-by-side comparison ⭐ **New**
  - Duplicate detection results and review interface ⭐ **New**
- **Interactive Components:**
  - `PDFMatchComparison`: Side-by-side text comparison with highlighting ⭐ **New**
  - `DuplicateReviewComponent`: Interactive duplicate confirmation ⭐ **New**
  - Audio segment playback for duplicate review ⭐ **New**

### **Component Library**
**Location:** `src/components/`

#### **`FileUpload.js`**
- **Purpose:** Reusable file upload component
- **Features:**
  - Drag and drop interface
  - File type validation
  - Upload progress indicators
  - Error handling and user feedback

#### **`ProgressTracker.js`**
- **Purpose:** Real-time progress monitoring
- **Features:**
  - Progress bars with percentages
  - Status message display
  - Error state handling
  - Background task monitoring

#### **`AudioPlayer.js`**
- **Purpose:** Custom audio playback interface
- **Features:**
  - Waveform visualization
  - Playback controls
  - Timestamp navigation
  - Volume control

### **Styling and Assets**
**Location:** `src/styles/` and `public/`

#### **`App.css`**
- **Purpose:** Global application styles
- **Contains:** Layout, typography, color scheme, responsive breakpoints

#### **`components/`** (CSS files)
- **Purpose:** Component-specific styling
- **Structure:** Modular CSS for each component

---

## 🚀 **Backend Architecture** 
**Location:** `backend/`

### **Django Project Structure**

#### **`myproject/` (Django Settings)**

##### **`settings.py`** ⭐ **Configuration Hub**
- **Purpose:** Central configuration for entire Django application
- **Key Sections:**
  - Database configuration (SQLite/PostgreSQL)
  - Celery settings for background tasks
  - File storage and media handling
  - CORS configuration for React frontend
  - Security settings (CSRF, ALLOWED_HOSTS)
  - API authentication settings
- **Environment Variables:** Database URLs, secret keys, debug flags

##### **`urls.py`**
- **Purpose:** Root URL routing configuration
- **Routes:**
  - `/api/` → API endpoints
  - `/media/` → File serving
  - `/admin/` → Django admin interface

##### **`celery.py`**
- **Purpose:** Celery configuration for background task processing
- **Responsibilities:**
  - Redis broker configuration
  - Task routing and serialization
  - Worker settings and monitoring

##### **`wsgi.py` / `asgi.py`**
- **Purpose:** WSGI/ASGI application entry points for production deployment

### **Main Application: `audioDiagnostic/`**

#### **Data Models** (`models.py`) ⭐ **Data Architecture**
```python
class AudioProject(models.Model):
    """Main project container with step-by-step processing tracking"""
    # Core Fields: title, status, pdf_file, created_at, updated_at
    # PDF Matching (Step 2a): pdf_matched_section, pdf_match_confidence, 
    #                        pdf_chapter_title, pdf_match_completed ⭐ New
    # Duplicate Detection (Step 2b): duplicates_detected, 
    #                                duplicates_detection_completed ⭐ New
    # User Confirmations (Step 2c): duplicates_confirmed_for_deletion ⭐ New
    
class AudioFile(models.Model):
    """Individual audio files within project"""
    # Fields: project (FK), file, status, task_id, transcript
    # Order management: order_index, chapter_number, section_number
    
class TranscriptionSegment(models.Model):
    """Timestamped text segments from audio with duplicate tracking"""
    # Core: audio_file (FK), text, start_time, end_time, segment_index
    # Duplicate Detection: is_duplicate, duplicate_type, is_kept ⭐ Enhanced
    # PDF Matching: pdf_match_found, pdf_match_confidence ⭐ New
    # Grouping: duplicate_group_id ⭐ New
    
class TranscriptionWord(models.Model):
    """Word-level timestamps and confidence scores"""
    # Fields: segment (FK), word, start_time, end_time, confidence, word_index

class ProcessingResult(models.Model): ⭐ New
    """Tracks comprehensive results of step-by-step processing"""
    # Statistics: total_segments_processed, duplicates_removed, time_saved
    # Content Analysis: pdf_coverage_percentage, missing_content_count
    # Processing Log: detailed_processing_steps (JSON)
```

#### **API Layer** (`views.py`) ⭐ **Business Logic**

##### **Project Management Views**
- **`ProjectListCreateView`:** Create/list projects
- **`ProjectDetailView`:** Get/update/patch project details ⭐ **Enhanced**
- **`ProjectPDFUploadView`:** Handle PDF file uploads
- **`ProjectAudioUploadView`:** Handle audio file uploads

##### **Step-by-Step Processing Views** ⭐ **New Architecture**
- **`ProjectMatchPDFView`:** Step 2a - Match audio transcript to PDF section
- **`ProjectDetectDuplicatesView`:** Step 2b - Detect duplicates with detailed analysis
- **`ProjectDuplicatesReviewView`:** Step 2c - Get duplicates for interactive review
- **`ProjectConfirmDeletionsView`:** Step 3 - Process user-confirmed deletions

##### **Legacy Processing Views** (Backward Compatible)
- **`TranscribeAudioFileView`:** Start audio transcription (Step 1)
- **`ProcessAudioFileView`:** Legacy automatic duplicate detection
- **`InfrastructureStatusView`:** Monitor Docker/Celery status

##### **Utility Views**
- **`ProjectProgressView`:** Real-time progress tracking
- **`ProjectDownloadView`:** Serve processed files

#### **Background Tasks** (`tasks.py`) ⭐ **Core Processing**

##### **`transcribe_audio_file_task()`**
- **Purpose:** Audio-to-text conversion using OpenAI Whisper
- **Process:**
  1. Auto-start Docker/Celery infrastructure
  2. Load Whisper model for speech recognition
  3. Generate timestamped transcription segments
  4. Save segments and words to database
  5. Update audio file status to 'transcribed'
- **Infrastructure:** Manages Docker containers automatically

##### **`process_confirmed_deletions_task()`** ⭐ **New Core Task**
- **Purpose:** Process user-confirmed duplicate deletions and audio reconstruction
- **Process:**
  1. Receive user-confirmed deletion list
  2. Mark confirmed segments for removal in database
  3. Generate clean audio excluding confirmed duplicates
  4. Apply smooth transitions (fade in/out)
  5. Create downloadable result file
  6. Update project status to 'completed'

##### **`process_audio_file_task()`** (Legacy - Maintained for Compatibility)
- **Purpose:** Legacy automatic duplicate detection and audio reconstruction
- **Process:**
  1. Load transcribed segments and PDF text
  2. Apply duplicate detection algorithms
  3. Generate cleaned audio without duplicates
  4. Create downloadable result file
  5. Update project status to 'completed'

#### **Service Layer** (`services/`)

##### **`docker_manager.py`** ⭐ **Infrastructure Management**
- **Purpose:** Automatic Docker and Celery lifecycle management
- **Key Methods:**
  - `setup_infrastructure()`: Start Docker containers
  - `register_task()`: Track active processing tasks
  - `unregister_task()`: Monitor task completion
  - `shutdown_infrastructure()`: Auto-shutdown after 60s idle
- **Features:**
  - Resource-efficient auto-scaling
  - Graceful shutdown management
  - Redis connectivity monitoring

### **Docker Infrastructure**

#### **`docker-compose.yml`**
- **Purpose:** Multi-container orchestration configuration
- **Services:**
  - **redis:** Message broker for Celery tasks
  - **celery_worker:** Background task processing
  - **celery_beat:** Scheduled task management
- **Networking:** Internal Docker network for service communication
- **Volumes:** Shared media storage between containers

#### **`Dockerfile`**
- **Purpose:** Container image definition for audio processing
- **Base Image:** Python 3.12-slim with audio processing libraries
- **Dependencies:** FFmpeg, libsndfile, OpenAI Whisper, PyTorch
- **Environment:** Production-ready Python environment

#### **`requirements.txt`**
- **Purpose:** Python dependency specification
- **Key Libraries:**
  - Django 5.2.7 + DRF for API
  - Celery 5.5.2 for background tasks
  - OpenAI Whisper for transcription
  - PyPDF2 for PDF processing
  - pydub for audio manipulation

---

## 🔄 **Data Flow Architecture**

### **File Upload Flow**
```
1. React FileUpload → POST /api/projects/{id}/upload-audio/
2. Django validates file → Save to media/audio/
3. AudioFile model created → Status: 'pending'
4. Frontend updates → Show "Ready to transcribe"
```

### **Enhanced Step-by-Step Processing Flow** ⭐ New
```
Step 1: Transcription
1. User clicks "Start Transcription" → POST /api/projects/{id}/transcribe/
2. Docker Manager starts containers → Redis + Celery worker
3. Celery task starts → transcribe_audio_file_task.delay()
4. Whisper processes audio → Generate timestamped segments
5. Save to database → TranscriptionSegment + TranscriptionWord
6. Update status → 'transcribed', ready for Step 2a

Step 2a: PDF Section Matching
1. User clicks "Match Audio to PDF Section" → POST /api/projects/{id}/match-pdf/
2. System analyzes PDF structure → Identify chapters/sections
3. Compare transcript against PDF → Find best matching section
4. Display side-by-side comparison → User reviews match quality
5. User confirms/rejects match → Update pdf_match_completed status

Step 2b: Duplicate Detection
1. User clicks "Detect Duplicates" → POST /api/projects/{id}/detect-duplicates/
2. Compare transcript against matched PDF section
3. Identify repeated words/sentences/paragraphs
4. Group duplicates and mark last occurrences
5. Save results → duplicates_detected field

Step 2c: Interactive Review
1. User clicks "Review Duplicates" → GET /api/projects/{id}/duplicates/
2. Display interactive interface with audio playback
3. User selects/deselects duplicates for deletion
4. User clicks "Confirm Deletions" → POST /api/projects/{id}/confirm-deletions/
5. Background task processes confirmed deletions → Generate clean audio

Step 3: Automatic Clean Audio Transcription ⭐ New
1. After generating clean audio, system automatically transcribes it
2. Saves verification segments with is_verification=True flag
3. Sets clean_audio_transcribed = True
4. Ready for verification comparison

Step 4: Post-Processing Verification ⭐ New
1. User clicks "Compare Clean Audio to PDF" → POST /api/projects/{id}/verify-cleanup/
2. System compares clean audio transcript against original PDF matched section
3. Calculates similarity score and identifies any remaining duplicates
4. Displays side-by-side comparison with statistics
5. Alerts user if repeated sentences still exist
6. Sets verification_completed = True

Step 5: Word-by-Word PDF Validation ⭐ New
1. User clicks "Test Against PDF Section" → POST /api/projects/{id}/validate-against-pdf/
2. System starts Celery background task → Returns task_id for tracking
3. Task gets clean transcript (excludes confirmed deletions)
4. Tokenizes PDF section and clean transcript into individual words
5. Sequential matching algorithm:
   - For each word in PDF, search in transcript from last matched position
   - If found: Mark GREEN in both PDF and transcript
   - If not found: Mark RED in PDF, continue searching in transcript
   - Move to next PDF word, resume from last matched transcript position
6. Generate color-coded HTML with <span> tags for highlighting
7. Calculate statistics: matched words, unmatched PDF words, unmatched transcript words
8. Save results to database → pdf_validation_results, pdf_validation_html
9. Frontend polls progress endpoint every second → Update progress bar
10. Display results with side-by-side panels, match percentage, quality warnings
11. Sets pdf_validation_completed = True
```
6. Sets verification_completed = True
```

### **Infrastructure Management**
```
Task Registration:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Action   │───▶│   Docker Manager │───▶│ Container Start │
└─────────────────┘    └──────────────────┘    └─────────────────┘

Task Completion:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Task Finished  │───▶│   60s Timer      │───▶│Container Shutdown│
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## 🔌 **API Architecture**

### **RESTful Endpoints**
```
Projects:
  GET    /api/projects/                    # List projects
  POST   /api/projects/                    # Create project
  GET    /api/projects/{id}/               # Get project details
  PATCH  /api/projects/{id}/               # Update project fields ⭐ New
  DELETE /api/projects/{id}/               # Delete project

File Management:
  POST   /api/projects/{id}/upload-pdf/    # Upload PDF
  POST   /api/projects/{id}/upload-audio/  # Upload audio

Step-by-Step Processing (New Interactive Workflow): ⭐ New
  POST   /api/projects/{id}/match-pdf/                      # Step 2a: Match PDF section
  POST   /api/projects/{id}/detect-duplicates/             # Step 2b: Detect duplicates
  GET    /api/projects/{id}/duplicates/                    # Step 2c: Get review data
  POST   /api/projects/{id}/confirm-deletions/             # Step 3: Process confirmations
  POST   /api/projects/{id}/verify-cleanup/                # Step 4: Verify clean audio ⭐ New
  POST   /api/projects/{id}/validate-against-pdf/          # Step 5: Start PDF validation ⭐ New
  GET    /api/projects/{id}/validation-progress/{task_id}/ # Step 5: Check validation progress ⭐ New

Legacy Processing (Backward Compatible):
  POST   /api/projects/{id}/transcribe/    # Step 1: Start transcription
  POST   /api/projects/{id}/process/       # Legacy: Auto duplicate detection
  GET    /api/projects/{id}/progress/      # Get progress status

Audio File Management: ⭐ Enhanced
  GET    /api/projects/{id}/audio-files/                    # List audio files
  GET    /api/projects/{id}/audio-files/{file_id}/         # Get file details
  DELETE /api/projects/{id}/audio-files/{file_id}/         # Delete audio file
  POST   /api/projects/{id}/audio-files/{file_id}/process/ # Process individual file

Infrastructure:
  GET    /api/infrastructure/status/       # Docker/Celery status
  POST   /api/infrastructure/shutdown/     # Force shutdown

Downloads:
  GET    /api/projects/{id}/download/      # Download processed audio
```

### **WebSocket Architecture** (Future Enhancement)
```
Real-time Updates:
  ws://localhost:8000/ws/project/{id}/     # Live progress updates
  ws://localhost:8000/ws/infrastructure/   # Infrastructure monitoring
```

---

## 📊 **Database Schema**

### **Relationships**
```
User (Django Auth)
  │
  └── AudioProject
        │
        ├── pdf_file (FileField)
        │
        └── AudioFile
              │
              ├── file (FileField) 
              │
              └── TranscriptionSegment
                    │
                    └── TranscriptionWord
```

### **Status State Machine**
```
AudioFile Status Flow:
pending → transcribing → transcribed → processing → completed
   │                                                     │
   └── failed ←──────────────────────────────────────────┘

Project Status Flow:  
setup → ready → processing → completed
  │                             │
  └── error ←───────────────────┘
```

---

## 🔧 **Development Workflow**

### **Local Development Setup**
1. **Backend:** `python manage.py runserver` (Port 8000)
2. **Frontend:** `npm start` (Port 3000) 
3. **Docker:** Auto-started on first transcription task
4. **Database:** SQLite for development, automatic migrations

### **File Structure Summary**
```
Audio repetative detection/
├── frontend/audio-waveform-visualizer/    # React App
│   ├── src/screens/ProjectDetailPage.js   # Main UI
│   ├── src/components/                    # Reusable components
│   └── public/                           # Static assets
├── backend/                              # Django API
│   ├── audioDiagnostic/                  # Main app
│   │   ├── models.py                     # Database schema
│   │   ├── views.py                      # API endpoints  
│   │   ├── tasks.py                      # Background jobs
│   │   └── services/docker_manager.py    # Infrastructure
│   ├── myproject/settings.py             # Configuration
│   ├── docker-compose.yml               # Container setup
│   └── requirements.txt                  # Dependencies
├── start-dev.bat                         # Development launcher
└── docker-diagnostic.bat                # Setup troubleshooting
```

This architecture provides **scalable, maintainable, and production-ready** audio duplicate detection with automatic infrastructure management and a modern user interface.