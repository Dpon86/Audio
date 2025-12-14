# Audio Duplicate Detection System
## 🎯 **Advanced AI-Powered Audio Processing** (Updated October 2025)

A production-ready Django + React application that **automatically detects and removes repetitive content** from audiobook recordings by comparing audio transcription against original PDF text.

### **🚀 Key Features (2025)**
- **2-Step Processing Workflow**: Transcribe → Process → Download
- **Automatic Docker Infrastructure**: Containers start/stop automatically
- **OpenAI Whisper Integration**: High-accuracy speech-to-text with timestamps
- **PDF-First Duplicate Detection**: Compares audio against source document
- **Project-Based Organization**: Multi-file management with progress tracking
- **Resource Efficient**: Infrastructure only runs when processing

---

## 🏗️ **System Requirements**

### **Essential Software**
- **Python 3.12+**: Backend Django application
- **Node.js 16+**: Frontend React application  
- **Docker Desktop**: Auto-managed Celery/Redis infrastructure
- **Git**: Version control and repository management

### **Hardware Recommendations**
- **RAM**: 8GB+ (16GB recommended for large audio files)
- **Storage**: 10GB free space for processing temp files
- **CPU**: Multi-core processor (for Whisper transcription)

---

## 🎯 **Quick Start (One Command)**

### **⭐ Easiest Setup - Use Startup Script**
```bash
# 1. Clone repository
git clone https://github.com/Dpon86/Audio.git
cd Audio

# 2. Install dependencies (one-time setup)
cd backend
.\scripts\setup\setup-venv.ps1  # Creates venv & installs all dependencies

# 3. Start everything with one command
cd ..
.\scripts\startup\start-dev.bat  # Or use backend\scripts\startup\start-dev-venv.ps1
```

This will:
- ✅ Check Docker Desktop is running
- ✅ Start Django API server (http://localhost:8000)
- ✅ Start React frontend (http://localhost:3000)
- ✅ Auto-configure Docker/Celery when needed

---

## 📋 **Detailed Setup Instructions**

### **1. Repository Setup**
```bash
git clone https://github.com/Dpon86/Audio.git
cd "Audio repetative detection"
```

### **2. Backend Setup (Automated)**
```bash
cd backend
.\scripts\setup\setup-venv.ps1  # Windows PowerShell
# OR
.\scripts\setup\setup-venv.bat  # Windows Command Prompt

# This automatically:
# - Creates Python virtual environment
# - Installs all dependencies from requirements-basic.txt
# - Sets up the database
```

### **3. Frontend Dependencies**
```bash
cd ../frontend/audio-waveform-visualizer
npm install
```

### **4. Create Admin User (Optional)**
```bash
cd ../../backend
.\venv\Scripts\Activate.ps1
python manage.py createsuperuser
```

### **5. Start Development Environment**

**Option A: Backend + Frontend (Recommended)**
```bash
# Terminal 1: Start Backend (Django + Celery + Redis)
cd backend
.\scripts\startup\start-dev-venv.ps1

# Terminal 2: Start Frontend
cd ..
.\scripts\startup\start-frontend.ps1
```

**Option B: Quick Frontend Only**
```bash
.\scripts\startup\start-frontend-simple.ps1
```

**Option C: Legacy Scripts (Still Available)**
```bash
.\scripts\startup\start-dev.bat  # Windows
# OR
.\scripts\startup\start-dev.sh  # Mac/Linux
```

**Option D: Manual (Advanced Users)**
```bash
# Terminal 1: Activate venv and start Django
cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver

# Terminal 2: Start Celery worker
cd backend
.\scripts\startup\start-celery.bat

# Terminal 3: Frontend  
cd frontend/audio-waveform-visualizer
npm start
```

---

## 🎨 **How to Use the System**

### **1. Access the Application**
- **Frontend Interface**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/  
- **Admin Panel**: http://localhost:8000/admin/

### **2. Complete Workflow**
1. **Create Project**: Enter title and description
2. **Upload Files**: 
   - PDF document (the book/text being read)
   - Audio recording (your reading of the book)
3. **Step 1 - Transcribe**: Click "Transcribe" → Docker auto-starts → Audio converted to text
4. **Step 2 - Process**: Click "Detect Duplicates" → AI finds repetitive content  
5. **Download Results**: Get cleaned audio file with duplicates removed

### **3. Infrastructure Monitoring**
- View Docker/Celery status in UI header
- Green badge: Containers running
- Red badge: Containers stopped
- Containers auto-shutdown 60 seconds after processing complete

---

## 🏗️ **System Architecture**

### **Project Structure (Organized 2025)**
```
Audio/
├── COMMANDS.txt                # ⚡ Quick command reference
├── README.md                  # This file
├── package.json               # Root dependencies
├── docs/                      # 📚 All documentation
│   ├── INDEX.md              # Documentation navigation guide
│   ├── architecture/         # System architecture & planning
│   │   ├── ARCHITECTURE.md
│   │   ├── IMPLEMENTATION_SUMMARY.md
│   │   └── PRODUCTION_DEPLOYMENT.md
│   ├── setup-guides/         # Setup & startup instructions
│   │   ├── START_HERE.md    # ⭐ Main setup guide
│   │   └── QUICK_START_WORKING.md
│   └── troubleshooting/      # Common issues & fixes
│       ├── FFMPEG_FIXED_CODE_LEVEL.md
│       └── INSTALL_FFMPEG.md
├── scripts/                   # 🔧 Root-level scripts
│   ├── startup/              # Frontend & legacy startup scripts
│   │   ├── start-frontend.ps1
│   │   └── start-dev.bat
│   └── utilities/            # Helper & diagnostic scripts
│       ├── install-ffmpeg.ps1
│       └── docker-diagnostic.bat
├── backend/                   # 🐍 Django REST API
│   ├── README.md             # Backend-specific guide
│   ├── scripts/
│   │   ├── startup/          # Backend startup scripts
│   │   │   ├── start-dev-venv.ps1  # ⭐ Main backend startup
│   │   │   ├── start-celery.bat
│   │   │   └── restart-celery.ps1
│   │   └── setup/            # Environment setup
│   │       └── setup-venv.ps1     # ⭐ Virtual environment setup
│   ├── docs/                 # Backend documentation
│   ├── audioDiagnostic/      # Main application
│   │   ├── models.py         # Database schema
│   │   ├── views.py          # API endpoints
│   │   ├── tasks.py          # Background processing (Celery)
│   │   └── services/         # Infrastructure management
│   ├── myproject/settings.py # Configuration hub
│   ├── docker-compose.yml    # Container orchestration
│   ├── requirements.txt      # Python dependencies
│   └── venv/                 # Virtual environment (created by setup)
└── frontend/audio-waveform-visualizer/ # ⚛️ React Interface
    ├── src/screens/          # Main UI components
    ├── src/components/       # Reusable components  
    └── package.json          # Node.js dependencies
```

### **🔄 Processing Architecture**
```
React UI → Django API → Docker Manager → Celery Worker → OpenAI Whisper → Results
    ↑                                         ↓
    └── Real-time Status Updates ← Redis ←───┘
```

---

## ⭐ **Advanced Features (2025 Update)**

### **🤖 Automatic Infrastructure Management**
- **Smart Scaling**: Docker containers start only when processing audio
- **Resource Optimization**: Auto-shutdown after 60 seconds of inactivity  
- **Health Monitoring**: Real-time status of Redis, Celery, and Docker
- **Error Recovery**: Automatic retry and graceful failure handling

### **🎯 AI-Powered Duplicate Detection**
- **PDF-First Approach**: Compares transcription against source document
- **Intelligent Matching**: Fuzzy text matching for natural speech variations
- **Contextual Analysis**: Keeps LAST occurrence of repeated content
- **Precision Timestamping**: Word-level accuracy for seamless audio editing

### **📊 Project Management** 
- **Multi-File Support**: Upload multiple audio files per project
- **Progress Tracking**: Real-time updates with detailed status messages
- **File Organization**: Automatic organization of uploads and results
- **Download Management**: Easy access to processed audio files

---

## 🔧 **Key Technologies**

### **Backend Stack (Python)**
- **Django 5.2.7**: Production-ready web framework
- **Django REST Framework**: API development with serialization
- **Celery 5.5.2**: Distributed task processing
- **Redis**: Message broker and result backend
- **OpenAI Whisper**: State-of-the-art speech recognition
- **PyPDF2**: PDF text extraction and processing
- **pydub**: Audio manipulation and editing
- **Docker**: Containerization and orchestration

### **Frontend Stack (JavaScript)**
- **React 18+**: Modern UI framework with hooks
- **React Router**: Client-side routing and navigation
- **Fetch API**: RESTful API communication
- **CSS3**: Responsive design and animations
- **npm**: Package management and build tools

### **Infrastructure**
- **Docker Compose**: Multi-container orchestration
- **Redis**: High-performance in-memory data store
- **SQLite**: Development database (PostgreSQL for production)
- **Nginx**: Production web server (see PRODUCTION_DEPLOYMENT.md)

---

## 🔍 **Troubleshooting**

### **Common Issues & Quick Fixes**

#### **🐳 Docker Issues**
```bash
# Problem: "Docker Desktop is not running"
# Solution: Start Docker Desktop and wait for full initialization

# Problem: Containers won't start
# Solution: Run diagnostic script
.\scripts\utilities\docker-diagnostic.bat
```

#### **🔌 Port Conflicts**  
```bash
# Problem: "Address already in use"
# Solutions:
netstat -ano | findstr :8000  # Find Django conflicts
netstat -ano | findstr :3000  # Find React conflicts
taskkill /F /PID <process_id>  # Kill conflicting process
```

#### **📦 Dependency Issues**
```bash
# Problem: Import errors or missing packages
# Solutions:
cd backend
.\scripts\setup\setup-venv.ps1     # Recreate venv & reinstall deps
# OR manually:
.\venv\Scripts\Activate.ps1
pip install -r requirements-basic.txt
python manage.py migrate

# Frontend:
cd frontend/audio-waveform-visualizer
npm install
```

### **🔧 Advanced Debugging**
```bash
# Check infrastructure status
curl http://localhost:8000/api/infrastructure/status/

# View Docker logs
cd backend
docker compose logs celery_worker

# Restart just Celery
.\scripts\startup\restart-celery.ps1

# Reset everything
cd backend
docker compose down
.\scripts\startup\start-dev-venv.ps1
```

---

## 📚 **Documentation**

### **📋 Complete Guides**
- **[docs/INDEX.md](docs/INDEX.md)**: ⭐ Main documentation navigation
- **[COMMANDS.txt](COMMANDS.txt)**: Quick command reference
- **[docs/setup-guides/START_HERE.md](docs/setup-guides/START_HERE.md)**: Complete setup guide
- **[backend/README.md](backend/README.md)**: Backend scripts & setup reference
- **[docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**: System architecture
- **[docs/architecture/PRODUCTION_DEPLOYMENT.md](docs/architecture/PRODUCTION_DEPLOYMENT.md)**: Production deployment
- **[frontend/SETUP_GUIDE.md](frontend/SETUP_GUIDE.md)**: React development workflow

### **🔧 Troubleshooting**
- **[docs/troubleshooting/FFMPEG_FIXED_CODE_LEVEL.md](docs/troubleshooting/FFMPEG_FIXED_CODE_LEVEL.md)**: FFmpeg setup
- **[docs/troubleshooting/INSTALL_FFMPEG.md](docs/troubleshooting/INSTALL_FFMPEG.md)**: FFmpeg installation
- **[backend/docs/](backend/docs/)**: Backend-specific documentation

---

## 🌟 **What Makes This Special**

### **🚀 Production Ready**
- Comprehensive error handling and logging
- Automatic infrastructure scaling
- Security best practices implemented
- Performance optimized for large files

### **🎯 User Experience**
- One-command startup for development
- Real-time progress tracking with detailed feedback
- Intuitive 2-step workflow (Transcribe → Process)
- Automatic cleanup and resource management

### **🔬 AI Innovation**
- PDF-first duplicate detection algorithm
- Context-aware text matching
- Precise timestamp-based audio editing
- Keeps the LAST (best) version of repeated content

---

## 🤝 **Contributing**

1. **Fork** the repository
2. **Read** the architecture documentation (ARCHITECTURE.md)
3. **Set up** development environment (this README)
4. **Create** feature branch for your changes
5. **Test** thoroughly including edge cases
6. **Submit** pull request with detailed description

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**🎉 Ready to eliminate duplicate content from your audiobook recordings with AI-powered precision!**