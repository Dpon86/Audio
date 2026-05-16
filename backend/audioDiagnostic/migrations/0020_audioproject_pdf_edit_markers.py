from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audioDiagnostic', '0018_add_client_transcription_duplicate_analysis_ai_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='audioproject',
            name='pdf_edit_markers',
            field=models.JSONField(blank=True, null=True, help_text='Saved PDF Edit tab marker array [{id, type, label, audioTime, gapSeconds, useRoomTone, color}]'),
        ),
        migrations.AddField(
            model_name='audioproject',
            name='pdf_edit_markers_history',
            field=models.JSONField(blank=True, null=True, help_text='Rolling history of last 20 marker snapshots for undo/revert'),
        ),
    ]
