# Audio Repetitive Detection

A Django-based web application for detecting repetitive content in audio files using Whisper AI transcription and fuzzy text matching.

## System Requirements

- Python 3.12+
- Node.js 16+
- Docker (for Redis)
- Git

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/Dpon86/Audio.git
cd "Audio repetative detection"
```

### 2. Backend Setup (Django)

Navigate to the backend directory:
```bash
cd backend
```

#### Install Python Dependencies

**Option A: Using the complete requirements file**
```bash
pip install -r requirements.txt
```

**Option B: Using minimal requirements (recommended for new setups)**
```bash
pip install -r requirements-minimal.txt
```

#### Set up Database
```bash
python manage.py migrate
python manage.py createsuperuser  # Optional: create admin user
```

### 3. Frontend Setup (React)

Navigate to the frontend directory:
```bash
cd ../frontend/audio-waveform-visualizer
```

Install Node.js dependencies:
```bash
npm install
```

### 4. Redis Setup (Required for Celery)

Make sure Docker is running, then start Redis:
```bash
docker run -p 6379:6379 redis
```

## Running the Application

You need to run multiple processes. Open separate terminal windows:

### Terminal 1: Redis (if not already running)
```bash
docker run -p 6379:6379 redis
```

### Terminal 2: Django Backend
```bash
cd backend
python manage.py runserver
```
The Django server will be available at `http://127.0.0.1:8000`

### Terminal 3: Celery Worker
```bash
cd backend
celery -A myproject worker --loglevel=info --pool=solo
```

### Terminal 4: React Frontend
```bash
cd frontend/audio-waveform-visualizer
npm start
```
The React app will be available at `http://localhost:3000`

## Project Structure

```
Audio repetative detection/
├── backend/                    # Django backend
│   ├── audioDiagnostic/       # Main Django app
│   ├── myproject/             # Django project settings
│   ├── media/                 # Media files (excluded from git)
│   ├── requirements.txt       # Complete Python dependencies
│   ├── requirements-minimal.txt # Minimal Python dependencies
│   └── How_to_guide           # Setup instructions
├── frontend/                  # React frontend
│   └── audio-waveform-visualizer/
└── .gitignore                # Git ignore rules
```

## Key Features

- **Audio Transcription**: Uses OpenAI Whisper for accurate speech-to-text
- **Repetition Detection**: Identifies exact and fuzzy text matches
- **Background Processing**: Uses Celery for async audio processing
- **Real-time Progress**: Redis-based progress tracking
- **Web Interface**: React-based user interface
- **File Management**: Automatic media file organization

## Dependencies

### Backend (Python)
- **Django 5.2.1**: Web framework
- **djangorestframework 3.16.0**: API framework
- **celery 5.5.2**: Background task processing
- **redis 6.1.0**: In-memory data store
- **openai-whisper 20240930**: AI transcription
- **pydub 0.25.1**: Audio processing
- **numpy 2.2.6**: Numerical computations

### Frontend (Node.js)
- **React 19.1.0**: UI framework
- **react-router-dom 7.6.0**: Routing
- **react-scripts 5.0.1**: Build tools

## Development Notes

- Large media files are excluded from git via `.gitignore`
- The frontend proxy is configured to communicate with Django backend
- Celery uses Redis as both broker and result backend
- Audio files are processed in the `backend/media/` directory

## Troubleshooting

1. **Redis Connection Error**: Ensure Docker is running and Redis container is started
2. **Celery Import Error**: Make sure you're in the backend directory when running celery
3. **Audio Processing Issues**: Ensure ffmpeg is installed on your system
4. **Port Conflicts**: Check that ports 3000, 6379, and 8000 are available

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request