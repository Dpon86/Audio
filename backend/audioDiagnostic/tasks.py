from celery import shared_task
import whisper
import difflib

import os
import redis
from collections import defaultdict
import re
from pydub import AudioSegment, silence

r = redis.Redis(host='localhost', port=6379, db=0)  # Adjust if needed


def normalize(text):
    # Remove leading [number] or [-1], lowercase, strip, and collapse whitespace
    text = re.sub(r'^\[\-?\d+\]\s*', '', text)
    return ' '.join(text.strip().lower().split())

@shared_task(bind=True)
def transcribe_audio_task(self, audio_path, audio_url):
    import pprint
    task_id = self.request.id
    r.set(f"progress:{task_id}", 0)

    model = whisper.load_model("base")
    r.set(f"progress:{task_id}", 10)

    # Transcribe with word timestamps
    result = model.transcribe(audio_path, word_timestamps=True)
    r.set(f"progress:{task_id}", 80)

    segments = result.get("segments", [])

    # Split segments into sentences with approximate timestamps
    all_sentences = []
    for seg in segments:
        all_sentences.extend(split_segment_to_sentences(seg))

    # Group sentences by normalized text (exact matches)
    sentence_map = defaultdict(list)
    for idx, sent in enumerate(all_sentences):
        norm = normalize(sent['text'])
        if norm:  # skip empty lines
            sentence_map[norm].append({**sent, 'index': idx})

    # Only keep groups with more than one occurrence (exact repeats)
    repetitive = [group for group in sentence_map.values() if len(group) > 1]

    # --- Fuzzy matching for potential repeats ---
    norm_sentences = [(normalize(s['text']), i, s) for i, s in enumerate(all_sentences)]
    fuzzy_groups = []
    threshold = 0.85  # Adjust as needed

    # Build a set of all indices in exact repeats to exclude from fuzzy
    exact_indices = set()
    for group in repetitive:
        for item in group:
            exact_indices.add(item['index'])

    # For each sentence, compare to all others (excluding exact repeats)
    visited_pairs = set()
    for i, (norm_i, idx_i, sent_i) in enumerate(norm_sentences):
        if idx_i in exact_indices or not norm_i:
            continue
        group = [{**sent_i, 'index': idx_i}]
        for j, (norm_j, idx_j, sent_j) in enumerate(norm_sentences):
            if i == j or idx_j in exact_indices or not norm_j:
                continue
            pair_key = tuple(sorted([idx_i, idx_j]))
            if pair_key in visited_pairs:
                continue
            ratio = difflib.SequenceMatcher(None, norm_i, norm_j).ratio()
            if ratio >= threshold:
                group.append({**sent_j, 'index': idx_j})
                visited_pairs.add(pair_key)
        unique_texts = set(s['text'] for s in group)
        if len(group) > 1 and len(unique_texts) > 1:
            group_indices = set(s['index'] for s in group)
            if not any(group_indices <= set(s['index'] for s in g) for g in fuzzy_groups):
                fuzzy_groups.append(group)

    # Find noise regions (non-speech)
    noise_regions = find_noise_regions(audio_path, all_sentences)

    r.set(f"progress:{task_id}", 100)

    pprint.pprint({
        'audio_url': audio_url,
        'all_segments': all_sentences,
        'repetitive_groups': repetitive,
        'potential_repetitive_groups': fuzzy_groups,
        'noise_regions': noise_regions,
    })

    return {
        'audio_url': audio_url,
        'all_segments': all_sentences,
        'repetitive_groups': repetitive,
        'potential_repetitive_groups': fuzzy_groups,
        'noise_regions': noise_regions,
    }

def split_segment_to_sentences(seg, next_segment_start=None, audio_end=None):
    import logging
    logger = logging.getLogger("audioDiagnostic.tasks")
    text = seg['text']
    words = seg.get('words', [])
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) == 1 or not words:
        buffer = 0.5  # 200 ms
        # Don't go past the next segment or audio end
        max_end = seg['end']
        if next_segment_start:
            max_end = min(max_end + buffer, next_segment_start)
        elif audio_end:
            max_end = min(max_end + buffer, audio_end)
        else:
            max_end = max_end + buffer
        logger.info(f"Only one sentence or no words. Returning segment as is, but with padded end: {max_end:.2f}")
        return [{
            'text': sentences[0],
            'start': seg['start'],
            'end': max_end,
            'words': words
        }]

    total_words = len(words)
    avg_words = total_words // len(sentences)
    result = []
    word_idx = 0
    for i, sent in enumerate(sentences):
        if i == len(sentences) - 1:
            sent_words = words[word_idx:]
        else:
            sent_words = words[word_idx:word_idx+avg_words]
        if sent_words:
            start = sent_words[0]['start']
            if i == len(sentences) - 1:
                end = seg['end']
                logger.info(
                    f"Sentence {i+1}/{len(sentences)} (LAST): '{sent}' | "
                    f"Start: {start:.2f}, End: {end:.2f} (using seg['end']: {seg['end']}) | "
                    f"First word: {sent_words[0]['word']}, Last word: {sent_words[-1]['word']}"
                )
            else:
                buffer = 0.5
                end = sent_words[-1]['end'] + buffer
                logger.info(
                    f"Sentence {i+1}/{len(sentences)}: '{sent}' | "
                    f"Start: {start:.2f}, End: {end:.2f} (last word end: {sent_words[-1]['end']}, buffer: {buffer}) | "
                    f"First word: {sent_words[0]['word']}, Last word: {sent_words[-1]['word']}"
                )
        else:
            start = seg['start']
            end = seg['end']
            logger.info(
                f"Sentence {i+1}/{len(sentences)}: '{sent}' | "
                f"Start: {start:.2f}, End: {end:.2f} (no words fallback)"
            )
        result.append({
            'text': sent,
            'start': start,
            'end': end,
            'words': sent_words
        })
        word_idx += avg_words
    return result



def find_noise_regions(audio_path, speech_segments, min_silence_len=300, silence_thresh=-40):
    """
    Returns a list of noise regions (start, end in seconds) not covered by speech_segments.
    """
    audio = AudioSegment.from_file(audio_path)
    duration = len(audio) / 1000.0  # seconds

    # Get all non-silent (speech) regions from your speech_segments
    speech_times = []
    for seg in speech_segments:
        speech_times.append((seg['start'], seg['end']))

    # Merge overlapping speech regions
    speech_times.sort()
    merged = []
    for start, end in speech_times:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    # Find noise regions between speech
    noise_regions = []
    prev_end = 0.0
    for start, end in merged:
        if start > prev_end:
            noise_regions.append({'start': prev_end, 'end': start, 'label': 'Noise'})
        prev_end = end
    if prev_end < duration:
        noise_regions.append({'start': prev_end, 'end': duration, 'label': 'Noise'})
    return noise_regions



#---------------------------------n8n integration---------------------------------

@shared_task(bind=True)
def transcribe_audio_words_task(self, audio_path, audio_url):
    """
    Transcribe the audio and return:
      - a list of words with their start and end times,
      - the full transcript,
      - the segments (phrases/sentences with timings).
    """
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, word_timestamps=True)

    # Collect all words with timestamps
    words = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            words.append({
                "word": word["word"],
                "start": word["start"],
                "end": word["end"],
                "probability": word.get("probability")
            })

    # Use segments as sentences/phrases
    segments = []
    for segment in result.get("segments", []):
        segments.append({
            "text": segment.get("text", ""),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "words": segment.get("words", [])
        })

    # Full transcript as a string
    transcript = result.get("text", "")

    # Repeat detection using normalized segment texts
    from collections import defaultdict
    def normalize(text):
        import re
        text = re.sub(r'^\[\-?\d+\]\s*', '', text)
        return ' '.join(text.strip().lower().split())

    sentence_map = defaultdict(list)
    for idx, seg in enumerate(segments):
        norm = normalize(seg['text'])
        if norm:
            sentence_map[norm].append({**seg, 'index': idx})

    repetitive = [group for group in sentence_map.values() if len(group) > 1]

    return {
        "audio_url": audio_url,
        "transcript": transcript,
        "segments": segments,
        "words": words,
        "repetitive_groups": repetitive
    }





from celery import shared_task
import difflib
import re
from PyPDF2 import PdfReader

@shared_task(bind=True)
def analyze_transcription_vs_pdf(self, pdf_path, transcript, segments, words):
    # 1. Extract PDF text
    reader = PdfReader(pdf_path)
    pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

    # 2. Find the section of the book being covered (simple fuzzy match)
    transcript_snippet = transcript[:500]  # Use first 500 chars for matching
    match_start = pdf_text.lower().find(transcript_snippet[:100].lower())
    if match_start == -1:
        # Fallback: use difflib to find best matching section
        seq = difflib.SequenceMatcher(None, pdf_text.lower(), transcript.lower())
        match_start = seq.find_longest_match(0, len(pdf_text), 0, len(transcript)).a
    match_end = match_start + len(transcript)
    pdf_section = pdf_text[match_start:match_end]

    # 3. Identify missing words
    pdf_words = re.findall(r'\w+', pdf_section.lower())
    transcript_words = re.findall(r'\w+', transcript.lower())
    missing_words = []
    pdf_idx = 0
    for word in pdf_words:
        while pdf_idx < len(transcript_words) and transcript_words[pdf_idx] != word:
            pdf_idx += 1
        if pdf_idx == len(transcript_words):
            missing_words.append(word)
        else:
            pdf_idx += 1

    # 4. Identify repeated sentences and their timestamps
    norm = lambda s: ' '.join(s.strip().lower().split())
    sentence_map = {}
    for idx, seg in enumerate(segments):
        text = norm(seg['text'])
        if text:
            sentence_map.setdefault(text, []).append(idx)
    repeated = {k: v for k, v in sentence_map.items() if len(v) > 1}
    repeated_sections = []
    for sent, idxs in repeated.items():
        for i in idxs[:-1]:  # All but last
            repeated_sections.append({
                "sentence": segments[i]['text'],
                "start": segments[i]['start'],
                "end": segments[i]['end']
            })

    # Only keep the last occurrence of each repeated sentence
    kept_sentences = [segments[idxs[-1]] for idxs in repeated.values()]

    return {
        "pdf_section": pdf_section,
        "missing_words": missing_words,
        "repeated_sections": repeated_sections,
        "kept_sentences": kept_sentences,
    }