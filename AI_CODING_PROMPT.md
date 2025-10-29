# AI Coding Prompt: Audio Repetition Detection Software

## 🎯 Project Overview

**Software Purpose:** A user authentication-based system that allows users to upload PDF books and multiple audio recordings of reading those books, then automatically detects and removes repetitive words, sentences, or paragraphs keeping the LAST occurrence of each repeated element.

**Enhanced Interactive Workflow Requirements:**
1. Have the user login and keep their projects tied to their user account
2. Have the user create a project that allows them to upload the PDF for the book
3. Have the ability to upload multiple audio files of them reading the book  
4. Then transcribe all of these audio files with each word timestamped
5. Store all of the above for editing
6. **Interactive PDF Matching**: Compare transcribed writing to PDF book with side-by-side comparison interface for user confirmation
7. **Smart Duplicate Detection**: Compare both and locate repeated words, sentences or paragraphs with detailed analysis and statistics
8. **User-Controlled Review**: Present duplicates to user with audio playback capabilities for each segment
9. **Confirmation-Based Processing**: Only delete segments explicitly confirmed by user, keeping LAST occurrence by default
10. **Final Assembly**: Generate clean audio file with only user-confirmed deletions and provide comprehensive analysis report

**🎯 Enhanced User Control Features:**
- **Side-by-side PDF comparison** with text highlighting
- **Interactive duplicate review** with audio segment playback  
- **User confirmation required** before any deletions
- **Smart recommendations** (keep last occurrence) with override capability
- **Visual feedback** and progress tracking throughout process
- **Comprehensive analytics** and processing summaries

**Example:** "I went to the store, I went to the store" → deletes the FIRST occurrence, keeps the LAST one.

## 🏗️ Architecture Requirements

### Backend: Django (Production-Ready)
- **Framework:** Django 5.2+ with Django REST Framework
- **Authentication:** Full Django authentication system with user management
- **Security:** CSRF protection, proper CORS handling, secure file uploads
- **Database:** SQLite for development, PostgreSQL for production
- **Task Processing:** Celery with Redis for background audio processing
- **File Storage:** Secure media handling with proper file validation
- **API Design:** RESTful endpoints with proper serialization and validation

### Frontend: React (Production-Ready) 
- **Framework:** React 18+ with modern hooks and functional components
- **State Management:** Context API or Redux Toolkit for complex state
- **UI/UX:** Professional, accessible interface with loading states and error handling
- **File Upload:** Drag-and-drop interface with progress indicators
- **Audio Playback:** Custom audio player with waveform visualization
- **Responsive:** Mobile-friendly design with proper breakpoints

### Processing Pipeline: Docker-Based Microservice
- **Containerization:** Separate Docker container for CPU-intensive processing
- **Transcription:** OpenAI Whisper or similar for accurate speech-to-text with timestamps
- **PDF Processing:** PyMuPDF or similar for reliable text extraction
- **Audio Processing:** pydub, librosa for audio manipulation and timestamp mapping
- **Communication:** REST API or message queue communication with main Django app

## 🔄 Exact 10-Step Processing Workflow

### Phase 1: Setup and Transcription (Steps 1-5)
```
1. User Authentication & Project Management:
   ├── User login/registration system
   ├── Project creation with user ownership
   └── Secure project access control

2. PDF Book Upload:
   ├── Upload PDF file for the book/document
   ├── Extract and store PDF text content
   └── Validate PDF file integrity

3. Multiple Audio File Upload:
   ├── Upload multiple audio files of reading sessions
   ├── Support various formats (MP3, WAV, M4A, FLAC, OGG)
   ├── Organize files by upload order/chapter
   └── Store original audio files securely

4. Audio Transcription with Word Timestamps:
   ├── Transcribe ALL audio files using OpenAI Whisper
   ├── Generate precise word-level timestamps for each word
   ├── Create transcript segments with start/end times
   └── Store transcription data in database

5. Store All Data for Editing:
   ├── Save all transcriptions with metadata
   ├── Link transcripts to specific audio files
   ├── Maintain word-level timestamp precision
   └── Preserve original file references
```

### Phase 2: Interactive Analysis and User-Controlled Processing (Steps 6-10)
```
6. Interactive PDF Section Matching:
   ├── Compare each transcribed segment to PDF content with intelligent chapter detection
   ├── Present side-by-side comparison interface with text highlighting
   ├── Show confidence scores and matching quality indicators
   ├── Require user confirmation before proceeding
   └── Allow user to reject match and retry with different parameters

7. Smart Duplicate Detection with User Review:
   ├── Analyze ALL transcribed audio files together with advanced algorithms
   ├── Find repeated WORDS, SENTENCES, and PARAGRAPHS with confidence scores
   ├── Group duplicates and identify last occurrences automatically
   ├── Present interactive review interface with audio playback capabilities
   └── Generate comprehensive statistics and duplicate analysis

8. User-Controlled Duplicate Confirmation:
   ├── Display each duplicate group with all occurrences
   ├── Provide audio playback for each duplicate segment
   ├── Pre-select recommended deletions (keep LAST occurrence)
   ├── Allow user to confirm, reject, or modify deletion selections
   ├── Show visual indicators for recommended vs custom choices
   └── Require explicit user confirmation before any processing

9. Comprehensive Content Analysis:
   ├── Compare final user-confirmed transcript against original PDF
   ├── Identify PDF sentences/paragraphs NOT found in audio
   ├── Generate detailed missing content report with statistics
   ├── Calculate PDF coverage percentage and completeness metrics
   └── Provide recommendations for additional recording sessions

10. User-Confirmed Audio Assembly:
    ├── Process ONLY user-confirmed deletions with precise timestamps
    ├── Combine segments from multiple audio files maintaining chronological order
    ├── Apply professional audio transitions (fade in/out, crossfades)
    ├── Generate high-quality clean audio file with user-approved modifications
    ├── Preserve original audio quality and provide processing summary
    └── Include comprehensive analytics report of all changes made

11. Post-Processing Verification ⭐ New:
    ├── Automatically transcribe the generated clean audio file
    ├── Save verification transcript with is_verification=True flag
    ├── Compare clean audio transcript against original PDF matched section
    ├── Calculate similarity score and identify any remaining duplicates
    ├── Display side-by-side comparison interface
    ├── Alert user if repeated sentences still exist
    ├── Provide statistics: similarity percentage, common words, repeated phrases
    └── Allow user to re-process if issues are found

12. PDF Word-by-Word Validation ⭐ New:
    ├── Remove all suggested text from transcript (apply confirmed deletions)
    ├── Display cleaned transcript next to original PDF section
    ├── For each word in PDF, sequentially match against clean transcript
    ├── If word found: Highlight GREEN in both PDF and transcript
    ├── If word not found: Continue to next transcript word until match found
    ├── If PDF word not in transcript: Highlight RED in PDF
    ├── Move to next PDF word and continue from last matched position
    ├── Repeat for entire PDF section
    ├── Calculate match percentage and provide detailed statistics
    ├── Display side-by-side color-coded comparison with scrollable panels
    ├── Show progress bar during processing for user feedback
    └── Alert if match percentage is below 90% for quality assurance
```

### Duplicate Detection Algorithm Implementation
```python
def identify_all_duplicates(all_audio_segments):
    """
    Step 7: Find repeated words, sentences, paragraphs across ALL audio files
    """
    # Group by normalized text
    text_groups = defaultdict(list)
    for segment in all_audio_segments:
        normalized_text = normalize(segment.text)
        text_groups[normalized_text].append(segment)
    
    # Find groups with multiple occurrences
    duplicates = {text: segments for text, segments in text_groups.items() 
                 if len(segments) > 1}
    return duplicates

def mark_duplicates_for_removal(duplicates):
    """
    Step 8: Keep LAST occurrence, mark others for removal
    """
    removed = []
    for text, occurrences in duplicates.items():
        # Sort by file order, then by timestamp
        sorted_occurrences = sorted(occurrences, 
            key=lambda x: (x.audio_file.order_index, x.start_time))
        
        # Keep LAST, remove all others
        for segment in sorted_occurrences[:-1]:  # All but last
            segment.is_kept = False
            removed.append(segment)
        
        # Keep the last one
        sorted_occurrences[-1].is_kept = True
    
    return removed
```

## 🛠️ Implementation Guidelines

### Django Backend Structure
```
backend/
├── audioDiagnostic/           # Main Django app
│   ├── models.py             # AudioProject, ProcessingTask models
│   ├── serializers.py        # DRF serializers
│   ├── views.py              # API endpoints
│   ├── tasks.py              # Celery background tasks
│   └── services/             # Business logic separation
│       ├── pdf_processor.py
│       ├── audio_processor.py
│       └── duplicate_detector.py
├── media/                    # File storage
├── docker_service/           # Processing microservice
└── requirements.txt          # Dependencies
```

### Key Django Models
```python
class AudioProject(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='pdfs/')
    audio_file = models.FileField(upload_to='audio/')
    processed_audio = models.FileField(upload_to='processed/', null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
class TranscriptionSegment(models.Model):
    project = models.ForeignKey(AudioProject, on_delete=models.CASCADE)
    text = models.TextField()
    start_time = models.FloatField()  # seconds
    end_time = models.FloatField()
    is_duplicate = models.BooleanField(default=False)
    confidence_score = models.FloatField()
```

### Enhanced React Frontend Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── Upload/                    # File upload components
│   │   ├── AudioPlayer/               # Custom audio player with segment playback
│   │   ├── ProjectDashboard/          # Project management
│   │   ├── ProcessingStatus/          # Real-time status updates
│   │   ├── PDFMatchComparison/        # Side-by-side PDF vs Audio comparison ⭐ New
│   │   ├── DuplicateReviewComponent/  # Interactive duplicate confirmation ⭐ New
│   │   ├── TextHighlighting/          # Visual text comparison tools ⭐ New
│   │   └── AudioSegmentPlayer/        # Precise segment playback ⭐ New
│   ├── hooks/               # Custom React hooks
│   ├── services/            # Enhanced API communication
│   ├── utils/               # Helper functions including audio processing
│   └── contexts/            # React context providers with enhanced state
└── package.json
```

## 🔧 Technical Specifications

### Audio Processing Requirements
- **Input Formats:** MP3, WAV, M4A, FLAC
- **Output Quality:** Maintain original audio quality
- **Timestamping:** Precise word-level timestamps for accurate editing
- **Transition Handling:** Smooth audio cuts to avoid clicks/pops

### PDF Processing Requirements
- **Text Extraction:** Handle various PDF formats (text-based, OCR if needed)
- **Layout Preservation:** Maintain paragraph and section structure
- **Error Handling:** Graceful handling of corrupted/protected PDFs

### Performance Requirements
- **File Size Limits:** Support large files (500MB+ audio, 100MB+ PDF)
- **Processing Time:** Show progress indicators for long operations
- **Memory Management:** Stream processing for large files
- **Concurrent Users:** Handle multiple simultaneous processing tasks

## 🚀 User Experience Flow

### 1. Project Creation
```
1. User logs in/registers
2. Creates new project with title
3. Uploads PDF and audio files
4. Optionally specifies section to process
5. Initiates processing
```

### 2. Processing Feedback
```
1. Real-time progress updates
2. Visual representation of processing stages
3. Error handling with clear messages
4. Ability to cancel long-running tasks
```

### 3. Results Review
```
1. Side-by-side comparison (original vs. processed)
2. Waveform visualization showing removed segments
3. Transcript with highlighted duplicates
4. Audio player with playback controls
5. Download processed audio file
```

## 🔒 Security & Best Practices

### Django Security
- CSRF protection on all forms
- Proper file type validation and scanning
- User authentication and authorization
- Rate limiting on API endpoints
- Secure file storage with access controls

### React Security
- Input sanitization and validation
- Secure file upload handling
- Environment variable management
- CSP headers for XSS protection

### Docker Security
- Non-root user execution
- Minimal base images
- Resource limits and monitoring
- Network isolation between services

## 🧪 Testing Strategy

### Backend Testing
- Unit tests for all business logic
- Integration tests for API endpoints
- Celery task testing
- File processing pipeline tests

### Frontend Testing
- Component unit tests with Jest/React Testing Library
- Integration tests for user workflows
- E2E tests with Cypress/Playwright

## 📦 Deployment Considerations

### Development Setup
- Docker Compose for local development
- Hot reload for both Django and React
- Shared volumes for file processing
- Redis for Celery task queue

### Production Setup
- Container orchestration (Kubernetes/Docker Swarm)
- Load balancing for processing services
- Persistent storage for user files
- Monitoring and logging solutions

## 🎯 Success Criteria

1. **Accuracy:** >95% accuracy in detecting actual duplicates
2. **Performance:** Process 1-hour audio file in <10 minutes
3. **Usability:** Non-technical users can complete workflow easily
4. **Reliability:** Handle edge cases gracefully without data loss
5. **Scalability:** Support multiple concurrent users processing files

## 📋 Development Phases

### Phase 1: MVP (Minimum Viable Product)
- Basic file upload and processing
- Simple duplicate detection algorithm
- Basic audio playback and download

### Phase 2: Enhanced Features
- Advanced duplicate detection with confidence scores
- Waveform visualization
- Batch processing capabilities

### Phase 3: Production Ready
- Performance optimization
- Advanced UI/UX improvements
- Comprehensive error handling and monitoring

---

**Note for AI Assistants:** This document provides the complete specification for building a production-ready audio repetition detection system. Follow Django and React best practices, implement proper error handling, and ensure the user experience is intuitive and reliable.