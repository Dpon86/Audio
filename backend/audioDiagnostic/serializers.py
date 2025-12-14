"""
Serializers for the audioDiagnostic app.
Provides input validation and serialization for API endpoints.
"""
from rest_framework import serializers
from .models import AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord, ProcessingResult


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
    
    class Meta:
        model = AudioFile
        fields = [
            'id', 'project', 'audio_file', 'title', 'order_index', 'duration',
            'status', 'transcription', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'duration', 'status', 'transcription', 'created_at', 'updated_at']
    
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
