"""
Advanced transcription utilities with forced alignment and post-processing.
Memory-optimized for 4GB servers.
"""
import re
import gc
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class TimestampAligner:
    """
    Forced alignment to improve timestamp accuracy.
    Uses heuristic approach for memory efficiency (no external libs initially).
    """
    
    @staticmethod
    def align_timestamps(segments: List[Dict], audio_duration: float) -> List[Dict]:
        """
        Improve Whisper timestamps using heuristics.
        More accurate alignment libraries (gentle/aeneas) can be added later.
        
        Args:
            segments: List of Whisper segments with text and timestamps
            audio_duration: Total audio duration in seconds
            
        Returns:
            List of segments with corrected timestamps
        """
        if not segments:
            return segments
        
        aligned_segments = []
        
        for i, seg in enumerate(segments):
            segment = seg.copy()
            text = segment.get('text', '').strip()
            start = segment.get('start', 0)
            end = segment.get('end', 0)
            
            if not text:
                continue
            
            # 1. Ensure minimum duration based on word count
            word_count = len(text.split())
            min_duration = word_count * 0.15  # ~150ms per word minimum
            actual_duration = end - start
            
            if actual_duration < min_duration:
                # Extend end time
                end = min(audio_duration, start + min_duration)
                logger.debug(f"Extended segment {i} duration from {actual_duration:.2f}s to {end - start:.2f}s")
            
            # 2. Prevent overlaps with next segment
            if i < len(segments) - 1:
                next_start = segments[i + 1].get('start', audio_duration)
                if end > next_start:
                    # Split the gap evenly
                    gap_midpoint = (end + next_start) / 2
                    end = gap_midpoint
                    logger.debug(f"Fixed overlap at segment {i}, adjusted end to {end:.2f}s")
            
            # 3. Add small buffer for sentence starts (capital letter = new sentence)
            if i > 0 and text and text[0].isupper():
                # Likely sentence start, add 100ms buffer
                start = max(aligned_segments[-1]['end'], start - 0.1)
            
            # 4. Ensure non-negative durations
            if end <= start:
                end = start + 0.5  # Minimum 500ms segment
            
            # 5. Ensure within audio bounds
            start = max(0, start)
            end = min(audio_duration, end)
            
            segment['start'] = start
            segment['end'] = end
            aligned_segments.append(segment)
        
        logger.info(f"Aligned {len(aligned_segments)} segments")
        return aligned_segments
    
    @staticmethod
    def remove_silence_padding(segments: List[Dict], padding: float = 0.1) -> List[Dict]:
        """
        Remove likely silence from segment boundaries (heuristic).
        
        Args:
            segments: List of segments
            padding: Amount to trim from start/end (seconds)
            
        Returns:
            Segments with trimmed silence
        """
        for seg in segments:
            # Trim padding from start and end
            duration = seg['end'] - seg['start']
            if duration > padding * 2:
                seg['start'] += padding
                seg['end'] -= padding
        
        return segments


class TranscriptionPostProcessor:
    """
    Clean up Whisper transcription output.
    Handles hallucinations, punctuation, formatting.
    """
    
    def __init__(self):
        self.filler_words = ['um', 'uh', 'er', 'ah', 'like', 'you know', 'i mean']
    
    def process(self, text: str) -> str:
        """
        Apply all post-processing steps.
        
        Args:
            text: Raw Whisper transcription
            
        Returns:
            Cleaned transcription
        """
        # Apply each processing step
        text = self.remove_repetitions(text)
        text = self.fix_punctuation(text)
        text = self.fix_capitalization(text)
        text = self.normalize_spacing(text)
        
        return text
    
    def remove_repetitions(self, text: str) -> str:
        """
        Remove Whisper hallucinations (repeated phrases).
        
        Common issue: Whisper repeats the same phrase 3+ times when uncertain.
        Example: "the the the cat sat" → "the cat sat"
        """
        # Remove 3+ consecutive identical words
        text = re.sub(r'\b(\w+)(\s+\1){2,}\b', r'\1', text)
        
        # Remove 3+ consecutive identical 2-word phrases
        text = re.sub(r'\b(\w+\s+\w+)(\s+\1){2,}\b', r'\1', text)
        
        # Remove 3+ consecutive identical 3-word phrases
        text = re.sub(r'\b(\w+\s+\w+\s+\w+)(\s+\1){2,}\b', r'\1', text)
        
        logger.debug("Removed repetitions from text")
        return text
    
    def fix_punctuation(self, text: str) -> str:
        """
        Normalize punctuation spacing and placement.
        """
        # Fix spacing before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Fix spacing after punctuation
        text = re.sub(r'([.,!?;:])\s*', r'\1 ', text)
        
        # Remove space before closing quotes/brackets
        text = re.sub(r'\s+([)\]"\'])', r'\1', text)
        
        # Add space after opening quotes/brackets
        text = re.sub(r'([(["\'"])\s*', r'\1 ', text)
        
        # Fix multiple punctuation marks
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        
        return text
    
    def fix_capitalization(self, text: str) -> str:
        """
        Ensure proper sentence capitalization.
        """
        # Split into sentences
        sentences = re.split(r'([.!?]\s+)', text)
        
        # Capitalize first letter of each sentence
        result = []
        for i, part in enumerate(sentences):
            if i % 2 == 0:  # Sentence text, not delimiter
                part = part.strip()
                if part:
                    part = part[0].upper() + part[1:] if len(part) > 1 else part.upper()
            result.append(part)
        
        text = ''.join(result)
        
        # Ensure text starts with capital
        if text:
            text = text[0].upper() + text[1:]
        
        return text
    
    def normalize_spacing(self, text: str) -> str:
        """
        Collapse multiple spaces, normalize whitespace.
        """
        # Collapse multiple spaces to single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def mark_filler_words(self, text: str) -> str:
        """
        Mark filler words for user review (optional, not applied by default).
        
        Returns text with filler words in [brackets] for easy identification.
        """
        for filler in self.filler_words:
            pattern = r'\b' + re.escape(filler) + r'\b'
            text = re.sub(pattern, f'[{filler}]', text, flags=re.IGNORECASE)
        
        return text
    
    def remove_filler_words(self, text: str) -> str:
        """
        Remove filler words entirely (optional, aggressive).
        """
        for filler in self.filler_words:
            pattern = r'\b' + re.escape(filler) + r'\b'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up double spaces left by removals
        text = re.sub(r'\s+', ' ', text)
        
        return text


class MemoryManager:
    """
    Manage memory during transcription to prevent OOM on small servers.
    """
    
    @staticmethod
    def cleanup():
        """
        Force garbage collection and clear caches.
        Call after each major processing step.
        """
        import gc
        collected = gc.collect()
        logger.debug(f"Garbage collection freed {collected} objects")
        
        # Clear torch cache if using GPU
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache")
        except ImportError:
            pass
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """
        Get current memory usage (if psutil available).
        
        Returns:
            Dict with memory stats in MB
        """
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            
            return {
                'rss_mb': mem_info.rss / 1024 / 1024,  # Resident Set Size
                'vms_mb': mem_info.vms / 1024 / 1024,  # Virtual Memory Size
            }
        except ImportError:
            return {'rss_mb': 0, 'vms_mb': 0}
    
    @staticmethod
    def log_memory_usage(step: str):
        """
        Log current memory usage with step label.
        """
        mem = MemoryManager.get_memory_usage()
        if mem['rss_mb'] > 0:
            logger.info(f"[{step}] Memory usage: {mem['rss_mb']:.1f} MB RSS, {mem['vms_mb']:.1f} MB VMS")


def calculate_transcription_quality_metrics(segments: List[Dict]) -> Dict:
    """
    Calculate quality metrics for transcription.
    
    Args:
        segments: List of transcription segments with confidence scores
        
    Returns:
        Dict with quality metrics
    """
    if not segments:
        return {
            'overall_confidence': 0.0,
            'low_confidence_count': 0,
            'medium_confidence_count': 0,
            'high_confidence_count': 0,
            'avg_segment_length': 0,
            'total_segments': 0,
            'estimated_accuracy': 'N/A',
        }
    
    confidences = []
    low_confidence = 0
    medium_confidence = 0
    high_confidence = 0
    segment_lengths = []
    
    for seg in segments:
        # Whisper avg_logprob ranges from ~-1.5 (good) to -5.0 (poor)
        # Convert to 0-1 scale
        logprob = seg.get('avg_logprob', -2.5)
        confidence = max(0.0, min(1.0, (logprob + 4.0) / 3.0))  # Map -4.0 to 0, -1.0 to 1.0
        confidences.append(confidence)
        
        if confidence < 0.5:
            low_confidence += 1
        elif confidence < 0.8:
            medium_confidence += 1
        else:
            high_confidence += 1
        
        segment_lengths.append(len(seg.get('text', '').split()))
    
    return {
        'overall_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
        'low_confidence_count': low_confidence,
        'medium_confidence_count': medium_confidence,
        'high_confidence_count': high_confidence,
        'avg_segment_length': sum(segment_lengths) / len(segment_lengths) if segment_lengths else 0,
        'total_segments': len(segments),
        'estimated_accuracy': f"{int((sum(confidences) / len(confidences)) * 100)}%" if confidences else "N/A",
    }
