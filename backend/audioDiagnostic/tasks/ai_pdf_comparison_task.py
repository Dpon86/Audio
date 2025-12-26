"""
AI-Powered PDF-to-Transcript Comparison using OpenAI GPT-4
This uses LLM intelligence to understand context and handle the comparison better than algorithms.
"""
import json
import re
import logging
from celery import shared_task
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def ai_compare_transcription_to_pdf_task(self, audio_file_id):
    """
    Compare transcription to PDF using OpenAI's GPT-4.
    
    The AI understands:
    - Context and meaning (not just word matching)
    - Natural language variations
    - What's a chapter marker vs actual content
    - What's narrator info vs story content
    - Sequential ordering and gaps
    
    Returns structured comparison results compatible with existing API.
    """
    task_id = self.request.id
    
    try:
        from ..models import AudioFile, AudioProject, TranscriptionSegment
        from ..utils import get_redis_connection
        from PyPDF2 import PdfReader
        import openai
        
        # Check if OpenAI API key is configured
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured in environment variables")
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        r = get_redis_connection()
        r.set(f"progress:{task_id}", 5)
        
        # Get audio file and project
        audio_file = AudioFile.objects.select_related('project').get(id=audio_file_id)
        project = audio_file.project
        
        if not project.pdf_file:
            raise ValueError("No PDF file found for this project")
        
        if not audio_file.transcript_text:
            raise ValueError("Audio file has not been transcribed yet")
        
        logger.info(f"Starting AI-powered PDF comparison for audio file {audio_file_id}")
        
        r.set(f"progress:{task_id}", 10)
        
        # Load PDF text
        if not project.pdf_text:
            logger.info("Extracting PDF text")
            reader = PdfReader(project.pdf_file.path)
            pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            project.pdf_text = pdf_text
            project.save(update_fields=['pdf_text'])
        else:
            pdf_text = project.pdf_text
        
        transcript = audio_file.transcript_text
        
        r.set(f"progress:{task_id}", 30)
        
        # Get ignored sections
        ignored_sections = audio_file.pdf_ignored_sections or []
        
        # Phase 1: Find starting point using AI
        logger.info("Phase 1: AI finding starting point in PDF")
        start_result = ai_find_start_position(client, pdf_text, transcript, ignored_sections)
        
        r.set(f"progress:{task_id}", 50)
        
        # Phase 2: Detailed comparison using AI
        logger.info("Phase 2: AI performing detailed comparison")
        comparison_result = ai_detailed_comparison(
            client,
            pdf_text, 
            transcript, 
            start_result['start_position'],
            start_result['matched_section'],
            ignored_sections
        )
        
        r.set(f"progress:{task_id}", 75)
        
        # Phase 3: Match extra content to timestamps
        logger.info("Phase 3: Matching extra content to timestamps")
        segments = list(TranscriptionSegment.objects.filter(audio_file=audio_file).order_by('start_time'))
        
        for item in comparison_result['extra_content']:
            timestamps = find_matching_segments(item['text'], segments)
            item['timestamps'] = timestamps
            item['start_time'] = timestamps[0]['start_time'] if timestamps else None
            item['end_time'] = timestamps[-1]['end_time'] if timestamps else None
        
        r.set(f"progress:{task_id}", 90)
        
        # Build final results
        final_results = {
            'match_result': {
                'start_position': start_result['start_position'],
                'confidence': start_result['confidence'],
                'matched_section': start_result['matched_section'][:1000],
                'start_char': 0,
                'end_char': len(start_result['matched_section']),
                'start_preview': start_result['matched_section'][:100],
                'end_preview': start_result['matched_section'][-100:] if len(start_result['matched_section']) > 100 else start_result['matched_section'],
            },
            'missing_content': comparison_result['missing_content'],
            'extra_content': comparison_result['extra_content'],
            'statistics': comparison_result['statistics'],
            'ignored_sections_count': len(ignored_sections),
            'algorithm': 'ai_gpt4_v1',
            'ai_analysis': comparison_result.get('ai_analysis', '')
        }
        
        # Save results
        audio_file.pdf_comparison_results = final_results
        audio_file.pdf_comparison_completed = True
        audio_file.save(update_fields=['pdf_comparison_results', 'pdf_comparison_completed'])
        
        r.set(f"progress:{task_id}", 100)
        
        logger.info(f"AI PDF comparison completed for audio file {audio_file_id}")
        
        return {
            'status': 'completed',
            'audio_file_id': audio_file_id,
            'comparison_results': final_results
        }
        
    except Exception as e:
        logger.error(f"AI PDF comparison failed for audio file {audio_file_id}: {str(e)}")
        r = get_redis_connection()
        r.set(f"progress:{task_id}", -1)
        raise


def ai_find_start_position(client, pdf_text, transcript, ignored_sections):
    """
    Use AI to find where the transcript starts in the PDF.
    """
    
    # Take first 2000 chars of transcript and first 20000 of PDF
    transcript_sample = transcript[:2000]
    pdf_sample = pdf_text[:20000]
    
    prompt = f"""You are analyzing a book PDF and an audio transcript of someone reading part of that book.

TASK: Find where the transcript begins in the PDF.

PDF TEXT (first 20,000 characters):
{pdf_sample}

TRANSCRIPT (first 2,000 characters):
{transcript_sample}

The transcript may start with narrator information like "Chapter One" or "Narrated by [name]" - these are NOT in the PDF.

INSTRUCTIONS:
1. Identify where the actual story/content from the transcript begins in the PDF
2. Ignore any narrator additions in the transcript
3. Return a JSON object with:
   - "start_position": character position in PDF where match starts (integer)
   - "confidence": 0.0-1.0 how confident you are
   - "matched_text": the first 500 characters of the matched section from PDF
   - "reasoning": brief explanation of how you found it

Return ONLY valid JSON, no other text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing text and finding matching sections between documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        result_text = response.choices[0].message.content.strip()
        logger.info(f"AI start position raw response: {result_text[:500]}...")
        
        # Parse JSON response
        # Remove markdown code blocks if present
        if result_text.startswith('```'):
            result_text = re.sub(r'^```json?\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
        
        result = json.loads(result_text)
        
        # Extract matched section from PDF
        start_pos = result['start_position']
        section_length = len(transcript) * 2  # Get 2x transcript length
        matched_section = pdf_text[start_pos:start_pos + section_length]
        
        logger.info(f"AI found start at position {start_pos} with confidence {result['confidence']}")
        logger.info(f"AI reasoning: {result.get('reasoning', 'N/A')}")
        
        return {
            'start_position': start_pos,
            'confidence': result['confidence'],
            'matched_section': matched_section,
            'ai_reasoning': result.get('reasoning', '')
        }
        
    except Exception as e:
        logger.error(f"AI start position finding failed: {str(e)}")
        # Fallback to beginning
        return {
            'start_position': 0,
            'confidence': 0.5,
            'matched_section': pdf_text[:len(transcript) * 2],
            'ai_reasoning': f'Fallback to start due to error: {str(e)}'
        }


def ai_detailed_comparison(client, pdf_text, transcript, start_pos, matched_section, ignored_sections):
    """
    Use AI to perform detailed comparison and identify missing/extra content.
    """
    
    # Build ignored sections text
    ignored_text = ""
    if ignored_sections:
        ignored_items = [item.get('text', '') for item in ignored_sections]
        ignored_text = f"\n\nIGNORED SECTIONS (user marked as acceptable, skip these):\n" + "\n---\n".join(ignored_items)
    
    prompt = f"""You are comparing a book's PDF text to an audio transcript to identify differences.

PDF SECTION (what should be read):
{matched_section[:15000]}

TRANSCRIPT (what was actually recorded):
{transcript[:15000]}
{ignored_text}

INSTRUCTIONS:
1. MISSING CONTENT: Text in PDF but NOT in the transcript (skipped during reading)
   - Only include if >10 words
   - Ignore minor differences (punctuation, articles)
   
2. EXTRA CONTENT: Text in transcript but NOT in PDF
   - Chapter markers: "Chapter One", "Part Two", etc.
   - Narrator info: "Narrated by...", "Read by...", "Audiobook production..."
   - Repeated text (duplicates from re-reading)
   - Other additions
   
3. Classify each extra item as: "chapter_marker", "narrator_info", "duplicate", or "other"

4. Calculate statistics:
   - Approximate word counts
   - Accuracy percentage (how much matches)
   - Match quality: "excellent" (95%+), "good" (85-94%), "fair" (70-84%), "poor" (<70%)

Return JSON:
{{
  "missing_content": [
    {{"text": "...", "word_count": 50, "position_in_pdf": "chapter 3 paragraph 2"}}
  ],
  "extra_content": [
    {{"text": "Chapter One", "word_count": 2, "possible_type": "chapter_marker", "position_in_transcript": "beginning"}}
  ],
  "statistics": {{
    "transcript_word_count": 1000,
    "pdf_word_count": 1200,
    "matching_word_count": 950,
    "missing_word_count": 250,
    "extra_word_count": 50,
    "accuracy_percentage": 95.0,
    "coverage_percentage": 79.2,
    "match_quality": "excellent"
  }},
  "ai_analysis": "Brief summary of findings"
}}

Return ONLY valid JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at comparing documents and identifying differences with high accuracy."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content.strip()
        logger.info(f"AI detailed comparison raw response: {result_text[:500]}...")
        
        # Parse JSON
        if result_text.startswith('```'):
            result_text = re.sub(r'^```json?\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
        
        result = json.loads(result_text)
        
        logger.info(f"AI comparison complete: {result['statistics']['accuracy_percentage']:.1f}% accuracy")
        logger.info(f"Found {len(result['missing_content'])} missing, {len(result['extra_content'])} extra sections")
        
        return result
        
    except Exception as e:
        logger.error(f"AI detailed comparison failed: {str(e)}")
        # Return empty results
        return {
            'missing_content': [],
            'extra_content': [],
            'statistics': {
                'transcript_word_count': len(transcript.split()),
                'pdf_word_count': len(matched_section.split()),
                'matching_word_count': 0,
                'missing_word_count': 0,
                'extra_word_count': 0,
                'accuracy_percentage': 0.0,
                'coverage_percentage': 0.0,
                'match_quality': 'poor'
            },
            'ai_analysis': f'AI comparison failed: {str(e)}'
        }


def find_matching_segments(text, segments):
    """
    Find TranscriptionSegments that contain this text using word overlap.
    """
    def normalize(t):
        return set(re.sub(r'[^\w\s]', ' ', t.lower()).split())
    
    text_words = normalize(text)
    matching_segments = []
    
    for segment in segments:
        segment_words = normalize(segment.text)
        
        if not text_words or not segment_words:
            continue
        
        overlap = len(text_words.intersection(segment_words))
        overlap_ratio = overlap / min(len(text_words), len(segment_words))
        
        if overlap_ratio > 0.4:
            matching_segments.append({
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'segment_id': segment.id
            })
    
    return matching_segments
