from django.contrib import admin
from .models import (
    AudioProject, AudioFile, Transcription, DuplicateGroup,
    TranscriptionSegment, TranscriptionWord, ProcessingResult,
    ClientTranscription, DuplicateAnalysis
)


@admin.register(AudioProject)
class AudioProjectAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'user', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'project', 'status', 'duration_seconds', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'filename', 'project__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ClientTranscription)
class ClientTranscriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'project', 'processing_method', 'model_used', 'duration_seconds', 'segment_count', 'created_at']
    list_filter = ['processing_method', 'model_used', 'language', 'created_at']
    search_fields = ['filename', 'project__title']
    readonly_fields = ['created_at', 'updated_at', 'segment_count', 'full_text']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('project', 'audio_file', 'filename', 'file_size_bytes')
        }),
        ('Processing Details', {
            'fields': ('processing_method', 'model_used', 'duration_seconds', 'language')
        }),
        ('Transcription Data', {
            'fields': ('transcription_data', 'segment_count', 'full_text')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DuplicateAnalysis)
class DuplicateAnalysisAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'project', 'algorithm', 'total_segments', 'duplicate_count', 'duplicate_groups_count', 'deletion_percentage', 'created_at']
    list_filter = ['algorithm', 'created_at']
    search_fields = ['filename', 'project__title']
    readonly_fields = ['created_at', 'updated_at', 'deletion_percentage']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('project', 'audio_file', 'filename', 'algorithm')
        }),
        ('Statistics', {
            'fields': ('total_segments', 'duplicate_count', 'duplicate_groups_count', 'deletion_percentage')
        }),
        ('Detection Results', {
            'fields': ('duplicate_groups', 'selected_deletions', 'assembly_info')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Register other models with simple admin
admin.site.register(Transcription)
admin.site.register(DuplicateGroup)
admin.site.register(TranscriptionSegment)
admin.site.register(TranscriptionWord)
admin.site.register(ProcessingResult)
