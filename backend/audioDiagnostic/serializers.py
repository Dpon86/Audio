"""
Serializers for the audioDiagnostic app.
Provides input validation and serialization for API endpoints.
"""
from rest_framework import serializers
from .models import AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord, ProcessingResult, Transcription, DuplicateGroup


class AudioProjectSerializer(serializers.ModelSerializer):
    """Serializer for AudioProject model with validation"""
    
    audio_files_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioProject
        fields = [
            'id', 'title', 'description', 'status', 'created_at', 'updated_at',
            'pdf_file', 'pdf_text', 'pdf_section_matched', 'combined_transcript',
            'duplicates_detected', 'duplicates_confirmed_for_deletion',
            'processing_summary', 'verification_results', 'parent_project',
            'audio_files_count'
        ]
        read_only_fields = [
            'id', 'status', 'created_at', 'updated_at', 'combined_transcript',
            'duplicates_detected', 'duplicates_confirmed_for_deletion',
            'processing_summary', 'verification_results', 'audio_files_count'
        ]
    
    def get_audio_files_count(self, obj):
        """Get count of audio files in project"""
        return obj.audiofile_set.count()
    
    def validate_title(self, value):
        """Validate project title"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Title must be at least 3 characters long")
        if len(value) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters")
        return value.strip()
    
    def validate_description(self, value):
        """Validate project description"""
        if value and len(value) > 1000:
            raise serializers.ValidationError("Description cannot exceed 1000 characters")
        return value.strip() if value else ""


class AudioFileSerializer(serializers.ModelSerializer):
    """Serializer for AudioFile model"""
    transcription = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioFile
        fields = [
            'id', 'project', 'audio_file', 'title', 'order_index', 'duration',
            'status', 'transcription', 'created_at', 'updated_at', 'filename',
            'file_size_bytes', 'duration_seconds', 'error_message',
            'transcript_text', 'transcript_adjusted', 'transcript_source',
            'retranscription_status', 'processed_audio', 'processed_duration_seconds'
        ]
        read_only_fields = ['id', 'duration', 'status', 'transcription', 'created_at', 'updated_at', 
                            'transcript_adjusted', 'transcript_source', 'retranscription_status']
    
    def get_transcription(self, obj):
        """Get nested transcription data if exists"""
        try:
            if hasattr(obj, 'transcription') and obj.transcription:
                return {
                    'id': obj.transcription.id,
                    'text': obj.transcription.full_text,
                    'word_count': obj.transcription.word_count,
                    'confidence_score': obj.transcription.confidence_score
                }
        except Transcription.DoesNotExist:
            pass
        return None
    
    def validate_title(self, value):
        """Validate audio file title"""
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError("Title is required")
        if len(value) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters")
        return value.strip()
    
    def validate_order_index(self, value):
        """Validate order index is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Order index must be non-negative")
        return value


class TranscriptionSegmentSerializer(serializers.ModelSerializer):
    """Serializer for TranscriptionSegment model"""
    
    class Meta:
        model = TranscriptionSegment
        fields = [
            'id', 'audio_file', 'start_time', 'end_time', 'text',
            'is_duplicate', 'duplicate_group_id', 'keep_segment', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        """Validate segment timing"""
        if 'start_time' in data and 'end_time' in data:
            if data['start_time'] < 0:
                raise serializers.ValidationError("Start time cannot be negative")
            if data['end_time'] < 0:
                raise serializers.ValidationError("End time cannot be negative")
            if data['end_time'] <= data['start_time']:
                raise serializers.ValidationError("End time must be after start time")
        return data


class TranscriptionWordSerializer(serializers.ModelSerializer):
    """Serializer for TranscriptionWord model"""
    
    class Meta:
        model = TranscriptionWord
        fields = [
            'id', 'segment', 'word', 'start_time', 'end_time',
            'confidence', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_confidence(self, value):
        """Validate confidence is between 0 and 1"""
        if value is not None and (value < 0 or value > 1):
            raise serializers.ValidationError("Confidence must be between 0 and 1")
        return value


class ProcessingResultSerializer(serializers.ModelSerializer):
    """Serializer for ProcessingResult model"""
    
    class Meta:
        model = ProcessingResult
        fields = [
            'id', 'project', 'total_segments', 'duplicate_segments',
            'unique_segments', 'total_duration', 'duplicate_duration',
            'unique_duration', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        """Validate processing result counts and durations"""
        if 'total_segments' in data and data['total_segments'] < 0:
            raise serializers.ValidationError("Total segments cannot be negative")
        if 'duplicate_segments' in data and data['duplicate_segments'] < 0:
            raise serializers.ValidationError("Duplicate segments cannot be negative")
        if 'unique_segments' in data and data['unique_segments'] < 0:
            raise serializers.ValidationError("Unique segments cannot be negative")
        
        # Validate durations are non-negative
        for field in ['total_duration', 'duplicate_duration', 'unique_duration']:
            if field in data and data[field] is not None and data[field] < 0:
                raise serializers.ValidationError(f"{field.replace('_', ' ').title()} cannot be negative")
        
        return data


class ProjectCreateSerializer(serializers.Serializer):
    """Serializer for creating a new project"""
    
    title = serializers.CharField(max_length=200, min_length=3, trim_whitespace=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)
    
    def create(self, validated_data):
        """Create a new AudioProject instance"""
        validated_data['user'] = self.context['request'].user
        validated_data['status'] = 'setup'
        return AudioProject.objects.create(**validated_data)


class FileUploadSerializer(serializers.Serializer):
    """Serializer for file upload validation"""
    
    file = serializers.FileField()
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Max file size: 500MB
        max_size = 500 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File size cannot exceed 500MB. Current size: {value.size / (1024*1024):.2f}MB")
        return value


class PDFUploadSerializer(FileUploadSerializer):
    """Serializer for PDF upload validation"""
    
    def validate_file(self, value):
        """Validate PDF file"""
        value = super().validate_file(value)
        
        # Check file extension
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed")
        
        # Check MIME type
        if value.content_type and value.content_type not in ['application/pdf']:
            raise serializers.ValidationError(f"Invalid file type: {value.content_type}. Expected application/pdf")
        
        return value


class AudioUploadSerializer(FileUploadSerializer):
    """Serializer for audio upload validation"""
    
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, trim_whitespace=True)
    order_index = serializers.IntegerField(required=False, min_value=0)
    
    def validate_file(self, value):
        """Validate audio file"""
        value = super().validate_file(value)
        
        # Allowed audio formats
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma']
        allowed_mime_types = [
            'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/m4a',
            'audio/flac', 'audio/ogg', 'audio/aac', 'audio/x-ms-wma'
        ]
        
        # Check file extension
        file_ext = '.' + value.name.lower().split('.')[-1] if '.' in value.name else ''
        if file_ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Invalid audio format. Allowed formats: {', '.join(allowed_extensions)}"
            )
        
        # Check MIME type if available
        if value.content_type and not any(mime in value.content_type for mime in allowed_mime_types):
            raise serializers.ValidationError(f"Invalid file type: {value.content_type}")
        
        return value


class DuplicateConfirmationSerializer(serializers.Serializer):
    """Serializer for duplicate confirmation data"""
    
    confirmed_deletions = serializers.JSONField()
    use_clean_audio = serializers.BooleanField(default=False)
    
    def validate_confirmed_deletions(self, value):
        """Validate confirmed deletions structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("confirmed_deletions must be a list")
        
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each deletion item must be a dictionary")
            
            required_fields = ['segment_id', 'duplicate_group_id']
            for field in required_fields:
                if field not in item:
                    raise serializers.ValidationError(f"Each deletion item must have '{field}' field")
        
        return value

# ============================================================================
# NEW SERIALIZERS FOR TAB-BASED ARCHITECTURE
# ============================================================================

class AudioFileDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for AudioFile with tab-based workflow info"""
    has_transcription = serializers.SerializerMethodField()
    has_processed_audio = serializers.SerializerMethodField()
    transcription_id = serializers.SerializerMethodField()
    transcription = serializers.SerializerMethodField()
    
    class Meta:
        model = AudioFile
        fields = [
            'id', 'project', 'filename', 'title', 'file', 'status',
            'duration_seconds', 'processed_duration_seconds', 'file_size_bytes', 'format', 'processed_audio',
            'order_index', 'chapter_number', 'section_number',
            'has_transcription', 'has_processed_audio', 'transcription_id', 'transcription',
            'transcript_text', 'transcript_adjusted', 'transcript_source', 
            'retranscription_status', 'retranscription_task_id',
            'error_message', 'created_at', 'updated_at', 'last_processed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'has_transcription', 
                            'has_processed_audio', 'transcription_id', 'transcription',
                            'transcript_adjusted', 'transcript_source', 'retranscription_status']
    
    def get_has_transcription(self, obj):
        return obj.has_transcription
    
    def get_has_processed_audio(self, obj):
        return obj.has_processed_audio
    
    def get_transcription_id(self, obj):
        """Get transcription ID if exists"""
        try:
            if hasattr(obj, 'transcription') and obj.transcription:
                return obj.transcription.id
        except (Transcription.DoesNotExist, AttributeError):
            pass
        return None
    
    def get_transcription(self, obj):
        """Get nested transcription data if exists"""
        try:
            if hasattr(obj, 'transcription') and obj.transcription:
                return {
                    'id': obj.transcription.id,
                    'text': obj.transcription.full_text,
                    'word_count': obj.transcription.word_count,
                    'confidence_score': obj.transcription.confidence_score
                }
        except (Transcription.DoesNotExist, AttributeError):
            pass
        # Fall back to legacy transcript_text if available
        if hasattr(obj, 'transcript_text') and obj.transcript_text:
            return {
                'id': None,
                'text': obj.transcript_text,
                'word_count': len(obj.transcript_text.split()) if obj.transcript_text else 0,
                'confidence_score': None
            }
        return None


class TranscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Transcription model"""
    audio_file_filename = serializers.SerializerMethodField()
    
    class Meta:
        model = Transcription
        fields = [
            'id', 'audio_file', 'audio_file_filename', 'full_text', 'word_count',
            'confidence_score', 'matched_pdf_section', 'pdf_start_page', 'pdf_end_page',
            'pdf_match_percentage', 'pdf_match_confidence', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'audio_file_filename']
    
    def get_audio_file_filename(self, obj):
        return obj.audio_file.filename


class DuplicateGroupSerializer(serializers.ModelSerializer):
    """Serializer for DuplicateGroup model"""
    
    class Meta:
        model = DuplicateGroup
        fields = [
            'id', 'audio_file', 'group_id', 'duplicate_text', 'occurrence_count',
            'total_duration_seconds', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AudioFileUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading audio files"""
    
    class Meta:
        model = AudioFile
        fields = ['project', 'file', 'title', 'order_index']
    
    def validate_file(self, value):
        """Validate audio file format and size"""
        allowed_formats = ['mp3', 'wav', 'm4a', 'flac', 'ogg']
        file_ext = value.name.split('.')[-1].lower()
        
        if file_ext not in allowed_formats:
            raise serializers.ValidationError(
                f"Invalid file format. Allowed: {', '.join(allowed_formats)}"
            )
        
        # Check file size (max 500MB)
        max_size = 500 * 1024 * 1024  # 500MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size cannot exceed 500MB. Current size: {value.size / (1024 * 1024):.2f}MB"
            )
        
        return value
    
    def create(self, validated_data):
        """Create AudioFile and extract metadata"""
        audio_file = super().create(validated_data)
        
        # Extract file metadata
        audio_file.filename = validated_data['file'].name
        audio_file.file_size_bytes = validated_data['file'].size
        audio_file.format = validated_data['file'].name.split('.')[-1].lower()
        
        # Extract audio duration (using pydub or similar)
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_file.file.path)
            audio_file.duration_seconds = len(audio) / 1000.0  # Convert to seconds
        except Exception as e:
            # If duration extraction fails, set to None
            audio_file.duration_seconds = None
        
        audio_file.save()
        return audio_file