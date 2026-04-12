"""
Serializers for the audioDiagnostic app.
Provides input validation and serialization for API endpoints.
"""
from rest_framework import serializers
from .models import (
    AudioProject, AudioFile, TranscriptionSegment, TranscriptionWord, 
    ProcessingResult, Transcription, DuplicateGroup, ClientTranscription, 
    DuplicateAnalysis, AIDuplicateDetectionResult, AIPDFComparisonResult
)


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
        return obj.audio_files.count()
    
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


class ClientTranscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for client-side transcription metadata.
    Used to save/load transcription results from browser-based Whisper processing.
    """
    segment_count = serializers.IntegerField(read_only=True)
    full_text = serializers.CharField(read_only=True)
    
    class Meta:
        model = ClientTranscription
        fields = [
            'id', 'project', 'audio_file', 'filename', 'file_size_bytes',
            'transcription_data', 'processing_method', 'model_used',
            'duration_seconds', 'language', 'created_at', 'updated_at',
            'metadata', 'segment_count', 'full_text'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'segment_count', 'full_text']
    
    def validate_transcription_data(self, value):
        """Validate transcription data is valid JSON with expected structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Transcription data must be a JSON object")
        
        # Check for required keys
        if 'segments' not in value:
            raise serializers.ValidationError("Transcription data must contain 'segments' array")
        
        segments = value.get('segments', [])
        if not isinstance(segments, list):
            raise serializers.ValidationError("'segments' must be an array")
        
        # Validate each segment has required fields
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise serializers.ValidationError(f"Segment {i} must be an object")
            
            required_fields = ['text']
            for field in required_fields:
                if field not in segment:
                    raise serializers.ValidationError(f"Segment {i} missing required field: {field}")
        
        return value
    
    def validate_filename(self, value):
        """Validate filename"""
        if not value or len(value.strip()) < 1:
            raise serializers.ValidationError("Filename is required")
        if len(value) > 255:
            raise serializers.ValidationError("Filename cannot exceed 255 characters")
        return value.strip()
    
    def validate_duration_seconds(self, value):
        """Validate duration is positive"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Duration cannot be negative")
        return value


class DuplicateAnalysisSerializer(serializers.ModelSerializer):
    """
    Serializer for client-side duplicate detection results.
    Preserves duplicate groups, user selections, and assembly information.
    """
    deletion_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DuplicateAnalysis
        fields = [
            'id', 'project', 'audio_file', 'filename', 'duplicate_groups',
            'algorithm', 'total_segments', 'duplicate_count', 'duplicate_groups_count',
            'selected_deletions', 'assembly_info', 'created_at', 'updated_at',
            'metadata', 'deletion_percentage'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'deletion_percentage']
    
    def validate_duplicate_groups(self, value):
        """Validate duplicate groups is valid JSON array"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Duplicate groups must be an array")
        
        # Validate each group has expected structure
        for i, group in enumerate(value):
            if not isinstance(group, dict):
                raise serializers.ValidationError(f"Duplicate group {i} must be an object")
            
            # Check expected fields
            expected_fields = ['group_id']
            for field in expected_fields:
                if field not in group:
                    raise serializers.ValidationError(f"Duplicate group {i} missing field: {field}")
        
        return value


# ============================================================================
# AI-POWERED DUPLICATE DETECTION SERIALIZERS
# ============================================================================

class AIDuplicateDetectionResultSerializer(serializers.ModelSerializer):
    """Serializer for AI duplicate detection results"""
    
    audio_file_title = serializers.CharField(source='audio_file.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = AIDuplicateDetectionResult
        fields = [
            'id', 'audio_file', 'audio_file_title', 'user', 'user_username',
            'ai_provider', 'ai_model', 'processing_date', 'processing_time_seconds',
            'input_tokens', 'output_tokens', 'total_tokens', 'api_cost_usd',
            'duplicate_groups', 'duplicate_count', 'occurrences_to_delete',
            'estimated_time_saved_seconds', 'average_confidence', 'high_confidence_count',
            'detection_settings', 'paragraph_expansion_performed', 'expanded_groups',
            'user_confirmed', 'user_modified', 'user_modifications'
        ]
        read_only_fields = [
            'id', 'audio_file_title', 'user_username', 'processing_date',
            'processing_time_seconds', 'input_tokens', 'output_tokens', 'total_tokens',
            'api_cost_usd', 'duplicate_count', 'occurrences_to_delete',
            'estimated_time_saved_seconds', 'average_confidence', 'high_confidence_count',
            'paragraph_expansion_performed'
        ]
    
    def validate_duplicate_groups(self, value):
        """Validate duplicate groups JSON structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("duplicate_groups must be an array")
        return value
    
    def validate_detection_settings(self, value):
        """Validate detection settings JSON structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("detection_settings must be an object")
        return value


class AIPDFComparisonResultSerializer(serializers.ModelSerializer):
    """Serializer for AI PDF comparison results"""
    
    audio_file_title = serializers.CharField(source='audio_file.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = AIPDFComparisonResult
        fields = [
            'id', 'audio_file', 'audio_file_title', 'user', 'user_username',
            'project', 'project_title', 'ai_provider', 'ai_model',
            'processing_date', 'processing_time_seconds',
            'input_tokens', 'output_tokens', 'total_tokens', 'api_cost_usd',
            'alignment_result', 'discrepancies', 'coverage_percentage',
            'total_discrepancies', 'missing_in_audio_count', 'extra_in_audio_count',
            'paraphrased_count', 'high_severity_count', 'medium_severity_count',
            'low_severity_count', 'overall_quality', 'confidence_score',
            'clean_transcript_marked', 'reviewed', 'review_notes'
        ]
        read_only_fields = [
            'id', 'audio_file_title', 'user_username', 'project_title',
            'processing_date', 'processing_time_seconds', 'input_tokens',
            'output_tokens', 'total_tokens', 'api_cost_usd', 'coverage_percentage',
            'total_discrepancies', 'missing_in_audio_count', 'extra_in_audio_count',
            'paraphrased_count', 'high_severity_count', 'medium_severity_count',
            'low_severity_count', 'overall_quality', 'confidence_score'
        ]


class AIProcessingLogSerializer(serializers.ModelSerializer):
    """Serializer for AI processing logs"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    audio_file_title = serializers.CharField(source='audio_file.title', read_only=True)
    
    class Meta:
        model = AIProcessingLog
        fields = [
            'id', 'user', 'user_username', 'audio_file', 'audio_file_title',
            'project', 'ai_provider', 'ai_model', 'task_type', 'timestamp',
            'input_tokens', 'output_tokens', 'total_tokens',
            'processing_time_seconds', 'cost_usd', 'status', 'error_message',
            'user_consented', 'data_sanitized'
        ]
        read_only_fields = ['id', 'user_username', 'audio_file_title', 'timestamp']


class AIDetectionRequestSerializer(serializers.Serializer):
    """Serializer for AI duplicate detection request"""
    
    audio_file_id = serializers.IntegerField(required=True)
    min_words = serializers.IntegerField(default=3, min_value=1, max_value=20)
    similarity_threshold = serializers.FloatField(default=0.85, min_value=0.5, max_value=1.0)
    keep_occurrence = serializers.ChoiceField(choices=['first', 'last', 'best'], default='last')
    enable_paragraph_expansion = serializers.BooleanField(default=False)
    
    def validate_audio_file_id(self, value):
        """Validate audio file exists and belongs to the user"""
        try:
            from .models import AudioFile
            audio_file = AudioFile.objects.get(id=value)
            
            # Check if audio file has transcription
            if not hasattr(audio_file, 'transcription'):
                raise serializers.ValidationError(
                    "Audio file must be transcribed before AI detection can be performed"
                )
            
            return value
        except AudioFile.DoesNotExist:
            raise serializers.ValidationError(f"Audio file with id {value} does not exist")


class AIPDFComparisonRequestSerializer(serializers.Serializer):
    """Serializer for AI PDF comparison request"""
    
    audio_file_id = serializers.IntegerField(required=True)
    
    def validate_audio_file_id(self, value):
        """Validate audio file exists and has transcript"""
        try:
            from .models import AudioFile
            audio_file = AudioFile.objects.get(id=value)
            
            # Check transcription
            if not hasattr(audio_file, 'transcription'):
                raise serializers.ValidationError(
                    "Audio file must be transcribed before PDF comparison"
                )
            
            # Check project has PDF
            if not audio_file.project.pdf_text:
                raise serializers.ValidationError(
                    "Project must have PDF text extracted before comparison"
                )
            
            return value
        except AudioFile.DoesNotExist:
            raise serializers.ValidationError(f"Audio file with id {value} does not exist")


class AICostEstimateRequestSerializer(serializers.Serializer):
    """Serializer for cost estimation request"""
    
    audio_duration_seconds = serializers.FloatField(required=True, min_value=1)
    task_type = serializers.ChoiceField(
        choices=['duplicate_detection', 'pdf_comparison'],
        default='duplicate_detection'
    )

    def validate_selected_deletions(self, value):
        """Validate selected deletions is an array"""
        if value is not None and not isinstance(value, list):
            raise serializers.ValidationError("Selected deletions must be an array")
        return value
    
    def validate_assembly_info(self, value):
        """Validate assembly info is a JSON object"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Assembly info must be a JSON object")
        return value
    
    def validate_total_segments(self, value):
        """Validate total segments is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Total segments cannot be negative")
        return value
    
    def validate_duplicate_count(self, value):
        """Validate duplicate count is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Duplicate count cannot be negative")
        return value