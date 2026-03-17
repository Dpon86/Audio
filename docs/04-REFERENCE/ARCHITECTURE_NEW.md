# Code Architecture After Refactoring

## Directory Structure

```
backend/audioDiagnostic/
│
├── views/                          # View modules (2,478 lines total)
│   ├── __init__.py                 # Exports all views
│   ├── _base.py                    # Common imports
│   ├── project_views.py            # Project CRUD (List, Detail, Transcript, Status, Download)
│   ├── upload_views.py             # PDF & Audio uploads
│   ├── transcription_views.py      # Transcription operations
│   ├── processing_views.py         # Processing operations
│   ├── duplicate_views.py          # Duplicate detection & cleanup
│   ├── pdf_matching_views.py       # PDF matching & validation
│   ├── infrastructure_views.py     # Infrastructure & task status
│   └── legacy_views.py             # Legacy/deprecated endpoints
│
├── tasks/                          # Task modules (2,773 lines total)
│   ├── __init__.py                 # Exports all tasks
│   ├── _base.py                    # Common imports
│   ├── transcription_tasks.py      # Whisper transcription tasks
│   ├── duplicate_tasks.py          # Duplicate detection tasks
│   ├── pdf_tasks.py                # PDF matching tasks
│   ├── audio_processing_tasks.py   # Audio processing tasks
│   └── utils.py                    # Shared utility functions
│
├── models.py                       # Database models (unchanged)
├── serializers.py                  # API serializers (unchanged)
├── throttles.py                    # Rate limiting (unchanged)
├── urls.py                         # URL routing (updated imports)
├── admin.py                        # Django admin (unchanged)
│
├── views_old.py                    # BACKUP: Original views.py
└── tasks_old.py                    # BACKUP: Original tasks.py
```

## Module Dependencies

### Views Dependencies
```
urls.py
   ↓ imports
views/__init__.py
   ↓ imports
┌──────────────────┬────────────────────┬──────────────────────┐
│                  │                    │                      │
project_views     upload_views    transcription_views    ...etc
   ↓                  ↓                   ↓
_base.py (common imports)
   ↓
models, serializers, throttles
   ↓
tasks/ (via __init__.py)
```

### Tasks Dependencies
```
views/
   ↓ imports tasks via
tasks/__init__.py
   ↓ imports
┌──────────────────┬────────────────────┬──────────────────────┐
│                  │                    │                      │
transcription_    duplicate_tasks    pdf_tasks    audio_processing_
tasks.py                                           tasks.py
   ↓                  ↓                   ↓            ↓
   └──────────────────┴───────────────────┴────────────┘
                         ↓
                    utils.py (shared functions)
                         ↓
                    _base.py (common imports)
                         ↓
                models, services, utils
```

## Import Patterns

### Views Import Pattern
```python
# In any view file
from ._base import *  # Gets APIView, Response, status, etc.
from ..tasks import transcribe_all_project_audio_task  # Task imports

class ProjectTranscribeView(APIView):
    def post(self, request, project_id):
        task = transcribe_all_project_audio_task.delay(project.id)
        # ...
```

### Tasks Import Pattern
```python
# In task files
from ._base import *  # Gets shared_task, whisper, models, etc.
from .utils import save_transcription_to_db, normalize  # Utility imports
from .pdf_tasks import find_pdf_section_match  # Cross-module imports

@shared_task(bind=True)
def process_project_duplicates_task(self, project_id):
    # ...
```

## Cross-Module References

### Duplicate Tasks → Utils + Audio Processing
```python
# duplicate_tasks.py
from .utils import (
    get_final_transcript_without_duplicates,
    get_audio_duration,
    save_transcription_to_db,
    normalize
)
from .audio_processing_tasks import assemble_final_audio
```

### Audio Processing → PDF Tasks + Utils
```python
# audio_processing_tasks.py
from .pdf_tasks import (
    find_pdf_section_match,
    identify_pdf_based_duplicates
)
from .utils import (
    save_transcription_to_db,
    get_audio_duration,
    normalize
)
```

## Module Responsibilities

### Views Modules

| Module | Lines | Responsibility | Key Views |
|--------|-------|----------------|-----------|
| `project_views.py` | 417 | Project lifecycle management | List, Detail, Transcript, Status, Download |
| `upload_views.py` | 89 | File upload handling | PDF Upload, Audio Upload |
| `transcription_views.py` | 256 | Transcription operations | Transcribe, AudioFile management |
| `processing_views.py` | 89 | Processing workflow | Process duplicates |
| `duplicate_views.py` | 577 | Duplicate detection & cleanup | Detect, Review, Confirm, Verify |
| `pdf_matching_views.py` | 523 | PDF matching & validation | Match, Validate, Progress |
| `infrastructure_views.py` | 117 | System status & health | Infrastructure, Task status |
| `legacy_views.py` | 262 | Deprecated endpoints | Chunk upload, legacy views |

### Tasks Modules

| Module | Lines | Responsibility | Key Tasks |
|--------|-------|----------------|-----------|
| `transcription_tasks.py` | 511 | Whisper transcription | Transcribe project, Transcribe file |
| `duplicate_tasks.py` | 797 | Duplicate detection | Process duplicates, Detect, Delete |
| `pdf_tasks.py` | 930 | PDF text matching | Match PDF, Validate, Similarity |
| `audio_processing_tasks.py` | 352 | Audio generation | Process file, Generate clean audio |
| `utils.py` | 61 | Shared utilities | Save transcription, Get duration |

## Benefits of New Structure

### 1. **Discoverability**
- Easy to find where functionality lives
- Clear naming conventions
- Logical domain separation

### 2. **Maintainability**
- Smaller files are easier to understand
- Changes isolated to specific domains
- Reduced merge conflicts

### 3. **Testability**
- Can test individual modules in isolation
- Clear boundaries for mocking
- Easier to achieve high coverage

### 4. **Scalability**
- Easy to add new domains
- Clear patterns to follow
- Won't outgrow structure

### 5. **Collaboration**
- Multiple developers can work on different domains
- Clearer code ownership
- Better code review process

## Migration Path

If you need to rollback:
```bash
cd backend/audioDiagnostic
rm -rf views/ tasks/
mv views_old.py views.py
mv tasks_old.py tasks.py
git checkout urls.py  # Restore original imports
```

## Testing Checklist

- [ ] All views import successfully
- [ ] All tasks import successfully
- [ ] URLs route to correct views
- [ ] Task queue works correctly
- [ ] All tests pass
- [ ] No circular import errors
- [ ] Production deployment verified

## Future Improvements

1. **Further Modularization**: Could split `pdf_tasks.py` (930 lines) into sub-modules
2. **Service Layer**: Extract business logic from views into service classes
3. **Type Hints**: Add type annotations for better IDE support
4. **Documentation**: Add docstrings to all modules
5. **Dependency Injection**: Consider using Django's dependency injection for services
