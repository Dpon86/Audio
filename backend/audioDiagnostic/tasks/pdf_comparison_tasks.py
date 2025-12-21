"""
PDF Comparison Tasks for Tab 4
Compare individual transcriptions against project PDF
"""
from ._base import *
from audioDiagnostic.tasks.utils import normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import fitz  # PyMuPDF


@shared_task(bind=True)
def compare_transcription_to_pdf_task(self, transcription_id, project_id, custom_settings=None):
    """
    Compare a single transcription against the project's PDF.
    Calculate match percentage and store results.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    # Set up infrastructure
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioProject, Transcription
        import json
        
        # Get transcription and project
        transcription = Transcription.objects.get(id=transcription_id)
        project = AudioProject.objects.get(id=project_id)
        audio_file = transcription.audio_file
        
        if not project.pdf_file:
            raise ValueError("Project does not have a PDF file")
        
        # Update task ID
        audio_file.task_id = task_id
        audio_file.save()
        
        r.set(f"progress:{task_id}", 10)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Loading PDF...'})
        logger.info(f"Comparing transcription {transcription_id} against PDF for project {project_id}")
        
        # Extract PDF text
        pdf_path = project.pdf_file.path
        pdf_doc = fitz.open(pdf_path)
        
        # Get page range if specified in custom settings
        custom_settings = custom_settings or {}
        pdf_page_range = custom_settings.get('pdf_page_range', None)
        
        if pdf_page_range and len(pdf_page_range) == 2:
            start_page, end_page = pdf_page_range
            pages_to_process = range(max(0, start_page), min(len(pdf_doc), end_page))
        else:
            pages_to_process = range(len(pdf_doc))
        
        pdf_text = ""
        for page_num in pages_to_process:
            page = pdf_doc[page_num]
            pdf_text += page.get_text()
        
        pdf_doc.close()
        
        r.set(f"progress:{task_id}", 30)
        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Normalizing texts...'})
        
        # Normalize both texts
        transcription_text = normalize(transcription.full_text)
        pdf_text_normalized = normalize(pdf_text)
        
        r.set(f"progress:{task_id}", 50)
        self.update_state(state='PROGRESS', meta={'progress': 50, 'message': 'Calculating similarity...'})
        
        # Calculate similarity using TF-IDF and cosine similarity
        vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1)
        
        try:
            tfidf_matrix = vectorizer.fit_transform([transcription_text, pdf_text_normalized])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            match_percentage = round(similarity * 100, 2)
        except Exception as e:
            logger.warning(f"TF-IDF similarity calculation failed: {str(e)}, using SequenceMatcher")
            # Fallback to SequenceMatcher
            from difflib import SequenceMatcher
            matcher = SequenceMatcher(None, transcription_text, pdf_text_normalized)
            match_percentage = round(matcher.ratio() * 100, 2)
        
        r.set(f"progress:{task_id}", 70)
        self.update_state(state='PROGRESS', meta={'progress': 70, 'message': 'Analyzing differences...'})
        
        # Detailed analysis using SequenceMatcher for segments
        from difflib import SequenceMatcher
        matcher = SequenceMatcher(None, transcription_text, pdf_text_normalized)
        matching_blocks = matcher.get_matching_blocks()
        
        # Calculate matched/unmatched character counts
        matched_chars = sum(block.size for block in matching_blocks)
        transcription_length = len(transcription_text)
        pdf_length = len(pdf_text_normalized)
        
        # Determine validation status
        similarity_threshold = custom_settings.get('similarity_threshold', 0.9)
        threshold_percentage = similarity_threshold * 100
        
        if match_percentage >= threshold_percentage:
            validation_status = 'excellent'
        elif match_percentage >= 80:
            validation_status = 'good'
        elif match_percentage >= 70:
            validation_status = 'acceptable'
        else:
            validation_status = 'poor'
        
        r.set(f"progress:{task_id}", 90)
        self.update_state(state='PROGRESS', meta={'progress': 90, 'message': 'Saving results...'})
        
        # Store validation results
        validation_result = {
            'match_percentage': match_percentage,
            'validation_status': validation_status,
            'transcription_length': transcription_length,
            'pdf_length': pdf_length,
            'matched_characters': matched_chars,
            'transcription_coverage': round((matched_chars / transcription_length * 100), 2) if transcription_length > 0 else 0,
            'pdf_coverage': round((matched_chars / pdf_length * 100), 2) if pdf_length > 0 else 0,
            'matching_blocks_count': len(matching_blocks),
            'pdf_text': pdf_text[:5000],  # Store first 5000 chars for review
            'comparison_settings': custom_settings,
            'pdf_page_range': f"{pages_to_process.start}-{pages_to_process.stop}" if pdf_page_range else f"0-{len(pdf_doc)}"
        }
        
        # Update transcription
        transcription.pdf_match_percentage = match_percentage
        transcription.pdf_validation_status = validation_status
        transcription.pdf_validation_result = json.dumps(validation_result)
        transcription.save()
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"PDF comparison complete for transcription {transcription_id}: {match_percentage}% match ({validation_status})")
        
        return {
            'success': True,
            'transcription_id': transcription_id,
            'match_percentage': match_percentage,
            'validation_status': validation_status,
            'validation_result': validation_result
        }
        
    except Exception as e:
        logger.error(f"Error in compare_transcription_to_pdf_task: {str(e)}")
        try:
            from audioDiagnostic.models import Transcription
            transcription = Transcription.objects.get(id=transcription_id)
            transcription.pdf_validation_status = 'failed'
            transcription.pdf_validation_result = json.dumps({'error': str(e)})
            transcription.save()
        except:
            pass
        raise
    finally:
        docker_celery_manager.unregister_task(task_id)


@shared_task(bind=True)
def batch_compare_transcriptions_to_pdf_task(self, project_id, audio_file_ids=None):
    """
    Compare multiple transcriptions against PDF in batch.
    Used when user wants to validate all files at once.
    """
    task_id = self.request.id
    r = get_redis_connection()
    
    if not docker_celery_manager.setup_infrastructure():
        raise Exception("Failed to set up Docker and Celery infrastructure")
    
    docker_celery_manager.register_task(task_id)
    
    try:
        from audioDiagnostic.models import AudioProject, AudioFile
        
        project = AudioProject.objects.get(id=project_id)
        
        if not project.pdf_file:
            raise ValueError("Project does not have a PDF file")
        
        # Get audio files to compare
        if audio_file_ids:
            audio_files = project.audio_files.filter(id__in=audio_file_ids)
        else:
            audio_files = project.audio_files.filter(status__in=['transcribed', 'processed'])
        
        total_files = audio_files.count()
        
        if total_files == 0:
            return {
                'success': False,
                'error': 'No transcribed audio files found'
            }
        
        r.set(f"progress:{task_id}", 5)
        self.update_state(state='PROGRESS', meta={'progress': 5, 'message': f'Processing {total_files} files...'})
        logger.info(f"Batch comparing {total_files} transcriptions for project {project_id}")
        
        results = []
        for i, audio_file in enumerate(audio_files):
            if not hasattr(audio_file, 'transcription'):
                continue
            
            progress = int(5 + (i / total_files * 90))
            r.set(f"progress:{task_id}", progress)
            self.update_state(state='PROGRESS', meta={
                'progress': progress,
                'message': f'Comparing {audio_file.filename} ({i+1}/{total_files})...'
            })
            
            # Run comparison for this file
            try:
                result = compare_transcription_to_pdf_task(
                    audio_file.transcription.id,
                    project_id
                )
                results.append({
                    'audio_file_id': audio_file.id,
                    'filename': audio_file.filename,
                    'success': True,
                    'match_percentage': result['match_percentage'],
                    'validation_status': result['validation_status']
                })
            except Exception as e:
                results.append({
                    'audio_file_id': audio_file.id,
                    'filename': audio_file.filename,
                    'success': False,
                    'error': str(e)
                })
        
        r.set(f"progress:{task_id}", 100)
        logger.info(f"Batch comparison complete for project {project_id}: {len(results)} files processed")
        
        return {
            'success': True,
            'project_id': project_id,
            'total_files': total_files,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in batch_compare_transcriptions_to_pdf_task: {str(e)}")
        raise
    finally:
        docker_celery_manager.unregister_task(task_id)
