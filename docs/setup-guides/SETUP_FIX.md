# Quick Setup Fix for Audio Development Environment

## The Issues You're Experiencing

1. **"Python was not found"** - Your scripts are using `python` but Windows requires `py`
2. **"'celery' is not recognized"** - Dependencies need to be installed in a virtual environment

## Quick Fix Steps

### Option 1: Automated Setup (Recommended)
```bash
# Run this from the project root:
./setup-environment.bat
```

This will:
- Create a Python virtual environment
- Install all required dependencies
- Test that everything works

### Option 2: Manual Setup
```bash
# 1. Go to backend directory
cd backend

# 2. Create virtual environment
py -m venv venv

# 3. Activate virtual environment
venv\Scripts\activate.bat

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start development environment
start-dev-venv.bat
```

## After Setup

### Starting the Development Environment

**With Virtual Environment (Recommended):**
```bash
cd backend
start-dev-venv.bat
```

**Original Method (Fixed):**
```bash
start-dev.bat
```

## Troubleshooting

### If Python is still not found:
- Make sure Python is installed from python.org
- Use `py` instead of `python` in commands
- Check that Python is in your PATH

### If Celery is still not found:
- Make sure you're using the virtual environment
- Run `pip install celery` in the activated environment
- Check that the virtual environment is activated (you should see `(venv)` in your prompt)

### If Docker issues occur:
- Make sure Docker Desktop is running
- Try `docker --version` to verify installation
- Restart Docker Desktop if needed

## File Changes Made

1. **setup-environment.bat** - New automated setup script
2. **backend/setup-venv.bat** - Virtual environment setup
3. **backend/start-dev-venv.bat** - Development startup with virtual environment
4. **start-dev.bat** - Fixed to use `py` instead of `python`
5. **backend/start-dev.bat** - Fixed to use `py` instead of `python`

## Virtual Environment Benefits

- Isolated dependencies (no conflicts with system Python)
- Reproducible environment
- Easy to clean up and recreate if needed
- Matches production deployment better

## Next Steps

1. Run `setup-environment.bat` from the project root
2. Wait for setup to complete
3. Use `start-dev-venv.bat` to start development
4. Your Django API will be at http://localhost:8000
5. Redis and Celery will run in Docker containers
