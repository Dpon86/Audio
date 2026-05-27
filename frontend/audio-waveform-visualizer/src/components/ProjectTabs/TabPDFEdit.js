import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import { API_BASE_URL } from '../../config/api';

/* ─── Colour palette for PDF markers ─────────────────────────────────── */
const MARKER_COLORS = {
  page_break: 'rgba(147,51,234,0.35)',   // purple
  paragraph:  'rgba(249,115,22,0.35)',   // orange
  chapter:    'rgba(236,72,153,0.35)',   // pink
  custom:     'rgba(20,184,166,0.35)',   // teal
};
const MARKER_LABEL_COLORS = {
  page_break: '#7c3aed',
  paragraph:  '#c2410c',
  chapter:    '#be185d',
  custom:     '#0f766e',
};

/* ─── Unique ID helper ────────────────────────────────────────────────── */
let _mid = 0;
const mkId = () => `pdfm-${Date.now()}-${++_mid}`;

/**
 * TabPDFEdit
 * Reads the project PDF, detects structural elements (page breaks, paragraphs,
 * chapters), maps them to audio timestamps via the transcript, then pushes
 * coloured markers into TabEdit's waveform via shared context.
 * Also handles gap-duration controls and room-tone upload.
 */
const TabPDFEdit = () => {
  const { token } = useAuth();
  const {
    projectId,
    projectData,
    selectedAudioFile,
    transcriptionData,
    setTranscriptionData,
    pdfEditMarkers,
    setPdfEditMarkers,
    pdfRoomTone,
    setPdfRoomTone,
    pushPdfMarkersUndo,
    undoPdfMarkers,
    pdfMarkersUndoStack,
  } = useProjectTab();

  /* ─── Persistence state ──────────────────────────────────────────── */
  const [saveStatus,          setSaveStatus]          = useState('');  // '', 'saving', 'saved', 'error'
  const [isSaving,            setIsSaving]            = useState(false);
  const [backendHistoryCount, setBackendHistoryCount] = useState(0);
  const [lastSavedMarkers,    setLastSavedMarkers]    = useState(null); // snapshot of last persisted state
  const autoSaveTimerRef = useRef(null);

  /* ─── PDF data state ─────────────────────────────────────────────── */
  const [pdfText,      setPdfText]      = useState('');
  const [pageBreaks,   setPageBreaks]   = useState([]); // [{page_num, start_char, end_char}]
  const [paragraphs,   setParagraphs]   = useState([]); // [{start_char, end_char, preview}]
  const [totalChars,   setTotalChars]   = useState(0);
  const [totalPages,   setTotalPages]   = useState(0);
  const [pdfUrl,       setPdfUrl]       = useState('');
  const [pdfLoading,   setPdfLoading]   = useState(false);
  const [pdfError,     setPdfError]     = useState('');

  /* ─── Mapping state ─────────────────────────────────────────────── */
  const [isMappingAll,  setIsMappingAll]  = useState(false);
  const [mappingStatus, setMappingStatus] = useState('');

  /* ─── UI state ───────────────────────────────────────────────────── */
  const [viewMode,      setViewMode]      = useState('split'); // 'pdf' | 'text' | 'split'
  const [filterType,    setFilterType]    = useState('all');
  const [activeSection, setActiveSection] = useState('markers'); // 'markers' | 'roomtone' | 'custom'
  const roomToneInputRef    = useRef(null);
  const textViewRef         = useRef(null);
  const selectionToolbarRef = useRef(null);

  /* ─── Text tool state ───────────────────────────────────────────── */
  const [activeTextTool,  setActiveTextTool]  = useState('none'); // 'find'|'highlight'|'edit'
  const [findQuery,       setFindQuery]       = useState('');
  const [findMatchIdx,    setFindMatchIdx]    = useState(0);
  const [findMatches,     setFindMatches]     = useState([]);
  const [textAnnotations, setTextAnnotations] = useState([]);   // [{id,start,end,type,text}]
  const [isEditMode,      setIsEditMode]      = useState(false);
  const [editedText,      setEditedText]      = useState('');
  const [isTextSaving,    setIsTextSaving]    = useState(false);
  const [textSaveError,   setTextSaveError]   = useState('');
  const [selectionInfo,   setSelectionInfo]   = useState(null); // {x,y,start,end}
  const [selectedMarkerId, setSelectedMarkerId] = useState(null); // marker id focused in both panels

  /* ─────────────────────────────────────────────────────────────────  */
  /* Derived — PDF file URL                                             */
  /* ─────────────────────────────────────────────────────────────────  */
  useEffect(() => {
    if (projectData?.pdf_file) {
      const raw = projectData.pdf_file;
      const base = (API_BASE_URL || '').replace(/\/$/, '');
      const url = raw.startsWith('http') ? raw : `${base}${raw.startsWith('/') ? '' : '/'}${raw}`;
      setPdfUrl(url);
    } else {
      setPdfUrl('');
    }
  }, [projectData]);

  /* ─────────────────────────────────────────────────────────────────  */
  /* Load PDF structure from backend                                    */
  /* ─────────────────────────────────────────────────────────────────  */
  const loadPDFStructure = useCallback(async () => {
    if (!projectId || !token) return;
    setPdfLoading(true);
    setPdfError('');
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/pdf-text/`, {
        headers: { Authorization: `Token ${token}` }
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        setPdfError(err.error || `HTTP ${resp.status}`);
        return;
      }
      const data = await resp.json();
      if (!data.success) { setPdfError(data.error || 'Failed to load PDF'); return; }

      const text = data.pdf_text || '';
      setPdfText(text);
      setTotalChars(data.total_chars || text.length);
      setTotalPages(data.total_pages || 0);

      // Page breaks from backend
      setPageBreaks(data.page_breaks || []);

      // Detect paragraphs client-side from double-newlines
      const detected = detectParagraphs(text);
      setParagraphs(detected);

    } catch (err) {
      setPdfError(`Network error: ${err.message}`);
    } finally {
      setPdfLoading(false);
    }
  }, [projectId, token]);

  useEffect(() => { loadPDFStructure(); }, [loadPDFStructure]);

  /* ─────────────────────────────────────────────────────────────────  */
  /* Load transcription (so Map All to Timestamps works even if the     */
  /* user hasn't visited the Edit tab yet)                              */
  /* ─────────────────────────────────────────────────────────────────  */
  useEffect(() => {
    if (!selectedAudioFile || !projectId || !token) return;
    if (transcriptionData?.all_segments?.length) return; // already loaded
    (async () => {
      try {
        const resp = await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
          { headers: { Authorization: `Token ${token}` } }
        );
        if (!resp.ok) return;
        const data = await resp.json();
        const rawSegs = data.segments || data.all_segments || [];
        const normalized = rawSegs.map(seg => ({
          ...seg,
          start: seg.start !== undefined ? seg.start : (seg.start_time || 0),
          end:   seg.end   !== undefined ? seg.end   : (seg.end_time   || 0),
        }));
        setTranscriptionData({ ...data, all_segments: normalized });
      } catch (_) {}
    })();
  }, [selectedAudioFile, projectId, token]); // eslint-disable-line

  /* ─────────────────────────────────────────────────────────────────  */
  /* Backend persistence: load, save, revert, undo                      */
  /* ─────────────────────────────────────────────────────────────────  */
  const loadSavedMarkers = useCallback(async () => {
    if (!projectId || !token) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/pdf-edit-markers/`, {
        headers: { Authorization: `Token ${token}` }
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.success && Array.isArray(data.markers) && data.markers.length > 0) {
        setPdfEditMarkers(data.markers);
        setLastSavedMarkers(data.markers);
        setBackendHistoryCount(data.history_count || 0);
      }
    } catch (e) {
      // Non-critical — silently ignore load errors
      console.warn('PDF markers load error:', e);
    }
  }, [projectId, token, setPdfEditMarkers]);

  useEffect(() => { loadSavedMarkers(); }, [loadSavedMarkers]);

  const saveMarkers = useCallback(async (markersToSave) => {
    if (!projectId || !token) return;
    setIsSaving(true);
    setSaveStatus('saving');
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/pdf-edit-markers/`, {
        method: 'POST',
        headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ markers: markersToSave }),
      });
      const data = await resp.json();
      if (data.success) {
        setLastSavedMarkers(markersToSave);
        setBackendHistoryCount(data.history_count || 0);
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus(''), 2500);
      } else {
        setSaveStatus('error');
      }
    } catch (e) {
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  }, [projectId, token]);

  // Auto-save with 2 second debounce whenever markers change
  useEffect(() => {
    if (!projectId || !token) return;
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    // Don't auto-save if markers haven't changed since last save or are empty
    if (pdfEditMarkers.length === 0) return;
    autoSaveTimerRef.current = setTimeout(() => {
      saveMarkers(pdfEditMarkers);
    }, 2000);
    return () => clearTimeout(autoSaveTimerRef.current);
  }, [pdfEditMarkers, projectId, token, saveMarkers]);

  const revertToSaved = useCallback(async () => {
    if (!projectId || !token) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/pdf-edit-markers/`, {
        headers: { Authorization: `Token ${token}` }
      });
      const data = await resp.json();
      if (data.success) {
        pushPdfMarkersUndo(pdfEditMarkers);  // Save current to local undo before reverting
        setPdfEditMarkers(data.markers || []);
        setLastSavedMarkers(data.markers || []);
        setBackendHistoryCount(data.history_count || 0);
        setSaveStatus('Reverted to saved');
        setTimeout(() => setSaveStatus(''), 2500);
      }
    } catch (e) {
      setSaveStatus('error');
    }
  }, [projectId, token, pdfEditMarkers, pushPdfMarkersUndo, setPdfEditMarkers]);

  const undoFromBackend = useCallback(async () => {
    if (!projectId || !token) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/pdf-edit-markers/undo/`, {
        method: 'POST',
        headers: { Authorization: `Token ${token}` },
      });
      const data = await resp.json();
      if (data.success) {
        setPdfEditMarkers(data.markers);
        setLastSavedMarkers(data.markers);
        setBackendHistoryCount(data.history_count || 0);
        setSaveStatus(`Restored ${data.markers.length} markers`);
        setTimeout(() => setSaveStatus(''), 2500);
      } else {
        setSaveStatus(data.error || 'Nothing to undo');
        setTimeout(() => setSaveStatus(''), 2500);
      }
    } catch (e) {
      setSaveStatus('error');
    }
  }, [projectId, token, setPdfEditMarkers]);

  /* ─────────────────────────────────────────────────────────────────  */
  /* Paragraph detection (client-side)                                  */
  /* ─────────────────────────────────────────────────────────────────  */
  const detectParagraphs = (text) => {
    const results = [];
    const re = /\n{2,}/g;
    let match;
    let prev = 0;

    // Advance idx past any leading whitespace to land on the first word character
    const snapToWordStart = (idx, limit) => {
      while (idx < limit && /[\s]/.test(text[idx])) idx++;
      return idx;
    };

    while ((match = re.exec(text)) !== null) {
      const blockText = text.slice(prev, match.index).trim();
      if (blockText.length > 40) {
        results.push({
          start_char: snapToWordStart(prev, match.index),
          end_char: match.index,
          preview: blockText.slice(0, 80),
        });
      }
      prev = match.index + match[0].length;
    }
    // Last block
    const lastBlock = text.slice(prev).trim();
    if (lastBlock.length > 40) {
      results.push({ start_char: snapToWordStart(prev, text.length), end_char: text.length, preview: lastBlock.slice(0, 80) });
    }
    return results;
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Chapter detection (client-side)                                    */
  /* ─────────────────────────────────────────────────────────────────  */
  const detectChapters = (text) => {
    const results = [];
    const re = /\n{2,}/g;
    let match;
    while ((match = re.exec(text)) !== null) {
      const afterBreak = match.index + match[0].length;
      const lineEnd = text.indexOf('\n', afterBreak);
      const lineText = lineEnd === -1 ? text.slice(afterBreak) : text.slice(afterBreak, lineEnd);
      const trimmed = lineText.trim();
      if (!trimmed) continue;

      const isChapter = (
        /^\d{1,3}$/.test(trimmed) ||                                      // lone number: 1, 42
        /^[IVXLC]{1,7}$/.test(trimmed) ||                                 // roman numeral: I, XIV
        /^chapter\s+\S/i.test(trimmed) ||                                 // Chapter 1 / Chapter One
        /^(prologue|epilogue|preface|introduction|part\s+\S)/i.test(trimmed) // Prologue / Part 2
      );

      if (isChapter && trimmed.length <= 80) {
        let startChar = afterBreak;
        while (startChar < text.length && /[ \t]/.test(text[startChar])) startChar++;
        results.push({ start_char: startChar, heading: trimmed });
      }
    }
    return results;
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Character → Audio-time mapping                                     */
  /* ─────────────────────────────────────────────────────────────────  */
  const buildWordTimeMap = useCallback(() => {
    const segments = transcriptionData?.all_segments || [];
    const map = [];
    segments.forEach((seg) => {
      const words = seg.text.trim().split(/\s+/);
      const timePerWord = (seg.end - seg.start) / Math.max(words.length, 1);
      words.forEach((word, i) => {
        const clean = word.toLowerCase().replace(/[^a-z]/g, '');
        if (clean.length >= 3) map.push({ word: clean, time: seg.start + i * timePerWord });
      });
    });
    return map;
  }, [transcriptionData]);

  const charToTime = useCallback((charPos, wordTimeMap, audioDuration) => {
    if (!pdfText || pdfText.length === 0) return 0;

    // Extract a window of text around the char position
    const windowStart = Math.max(0, charPos - 60);
    const windowEnd   = Math.min(pdfText.length, charPos + 60);
    const snippet = pdfText.slice(windowStart, windowEnd);
    const snipWords = snippet.toLowerCase().replace(/[^a-z\s]/g, '').split(/\s+/).filter(w => w.length >= 3);

    // Find first matching word in transcript word-time map
    for (const sw of snipWords) {
      const hit = wordTimeMap.find(w => w.word === sw);
      if (hit) return hit.time;
    }

    // Proportional fallback
    return (charPos / pdfText.length) * (audioDuration || 0);
  }, [pdfText]);

  /* ─────────────────────────────────────────────────────────────────  */
  /* Map ALL structural elements to timestamps                          */
  /* ─────────────────────────────────────────────────────────────────  */
  const mapAllToTimestamps = async () => {
    if (!transcriptionData?.all_segments?.length) {
      alert('No transcript available. Please transcribe the file in Tab 1 first.');
      return;
    }
    if (!pdfText) { alert('PDF structure not loaded yet.'); return; }

    setIsMappingAll(true);
    setMappingStatus('Building word-time index…');

    // Yield to paint the status
    await new Promise(r => setTimeout(r, 50));

    const wordTimeMap   = buildWordTimeMap();
    const audioDuration = selectedAudioFile?.duration || 0;
    const newMarkers    = [];

    // Chapters — detected by looking for standalone numbers / "Chapter N" headings
    const chapterList = detectChapters(pdfText);
    setMappingStatus(`Mapping ${chapterList.length} chapters…`);
    await new Promise(r => setTimeout(r, 20));
    chapterList.forEach((ch) => {
      newMarkers.push({
        id:         mkId(),
        type:       'chapter',
        label:      `Chapter ${ch.heading}`,
        pdfCharPos: ch.start_char,
        pdfPage:    null,
        audioTime:  charToTime(ch.start_char, wordTimeMap, audioDuration),
        gapSeconds: 2,
        useRoomTone: false,
        color:      MARKER_COLORS.chapter,
      });
    });

    // Paragraphs (limit to first 200 for performance)
    const paraSlice = paragraphs.slice(0, 200);
    setMappingStatus(`Mapping ${paraSlice.length} paragraphs…`);
    await new Promise(r => setTimeout(r, 20));
    paraSlice.forEach((para, idx) => {
      newMarkers.push({
        id:         mkId(),
        type:       'paragraph',
        label:      `Para ${idx + 1}`,
        pdfCharPos: para.start_char,
        pdfPage:    null,
        audioTime:  charToTime(para.start_char, wordTimeMap, audioDuration),
        gapSeconds: 0.5,
        useRoomTone: false,
        color:      MARKER_COLORS.paragraph,
      });
    });

    // Sort by audioTime
    newMarkers.sort((a, b) => a.audioTime - b.audioTime);

    pushPdfMarkersUndo(pdfEditMarkers);  // Save current to local undo before replacing
    setPdfEditMarkers(newMarkers);
    setMappingStatus(`✅ ${newMarkers.length} markers mapped`);
    setIsMappingAll(false);
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Add a custom marker at a specific time                             */
  /* ─────────────────────────────────────────────────────────────────  */
  const [customTime,  setCustomTime]  = useState('');
  const [customLabel, setCustomLabel] = useState('');

  const addCustomMarker = () => {
    const t = parseFloat(customTime);
    if (isNaN(t) || t < 0) { alert('Enter a valid time in seconds'); return; }
    const marker = {
      id:         mkId(),
      type:       'custom',
      label:      customLabel || `Custom ${formatTime(t)}`,
      pdfCharPos: null,
      pdfPage:    null,
      audioTime:  t,
      gapSeconds: 2,
      useRoomTone: false,
      color:      MARKER_COLORS.custom,
    };
    pushPdfMarkersUndo(pdfEditMarkers);
    setPdfEditMarkers(prev => [...prev, marker].sort((a, b) => a.audioTime - b.audioTime));
    setCustomTime('');
    setCustomLabel('');
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Update a single marker's gap or roomtone flag                      */
  /* ─────────────────────────────────────────────────────────────────  */
  const updateMarker = (id, patch) => {
    pushPdfMarkersUndo(pdfEditMarkers);
    setPdfEditMarkers(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m));
  };

  const removeMarker = (id) => {
    pushPdfMarkersUndo(pdfEditMarkers);
    setPdfEditMarkers(prev => prev.filter(m => m.id !== id));
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Room tone upload                                                   */
  /* ─────────────────────────────────────────────────────────────────  */
  const handleRoomToneUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const blobUrl = URL.createObjectURL(file);
    setPdfRoomTone({ blobUrl, filename: file.name, duration: null });
  };

  const handleRoomToneDuration = (e) => {
    const dur = e.target.duration;
    if (pdfRoomTone && dur) setPdfRoomTone(prev => ({ ...prev, duration: dur }));
  };

  /* ─────────────────────────────────────────────────────────────────  */
  /* Helpers                                                            */
  /* ─────────────────────────────────────────────────────────────────  */
  const formatTime = (s) => {
    if (!s && s !== 0) return '—';
    const m  = Math.floor(s / 60);
    const ss = (s % 60).toFixed(1).padStart(4, '0');
    return `${m}:${ss}`;
  };

  /* ─── Find-text effect ─────────────────────────────────────────── */
  useEffect(() => {
    if (!findQuery.trim() || !pdfText) { setFindMatches([]); setFindMatchIdx(0); return; }
    const lq = findQuery.toLowerCase();
    const lt = pdfText.toLowerCase();
    const matches = [];
    let idx = 0;
    while ((idx = lt.indexOf(lq, idx)) !== -1) {
      matches.push({ start: idx, end: idx + lq.length });
      idx += lq.length;
    }
    setFindMatches(matches);
    setFindMatchIdx(0);
  }, [findQuery, pdfText]);

  /* ─── Scroll current find match into view ───────────────────────── */
  useEffect(() => {
    if (!findMatches.length || !textViewRef.current) return;
    const el = textViewRef.current.querySelector('[data-find-current="true"]');
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [findMatchIdx, findMatches]);

  /* ─── Scroll text view to selected marker badge ─────────────────── */
  useEffect(() => {
    if (!selectedMarkerId) return;
    const pin = document.getElementById(`mpid-${selectedMarkerId}`);
    if (pin) pin.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [selectedMarkerId]);

  /* ─── Dismiss selection toolbar on outside click ────────────────── */
  useEffect(() => {
    if (!selectionInfo) return;
    const handler = (e) => {
      if (selectionToolbarRef.current && !selectionToolbarRef.current.contains(e.target))
        setSelectionInfo(null);
    };
    const timer = setTimeout(() => document.addEventListener('mousedown', handler), 150);
    return () => { clearTimeout(timer); document.removeEventListener('mousedown', handler); };
  }, [selectionInfo]);

  /* ─── Text tool helpers ─────────────────────────────────────────── */
  const getCharOffset = (container, node, offset) => {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    let total = 0;
    while (walker.nextNode()) {
      if (walker.currentNode === node) return total + offset;
      total += walker.currentNode.textContent.length;
    }
    return -1;
  };

  const buildStyledSegments = (text) => {
    const ranges = [
      ...textAnnotations.map(a => ({ start: a.start, end: a.end, kind: a.type })),
      ...findMatches.map((m, i) => ({ start: m.start, end: m.end, kind: i === findMatchIdx ? 'find-current' : 'find-match' })),
    ];
    const points = new Set([0, text.length]);
    ranges.forEach(r => {
      if (r.start >= 0 && r.start <= text.length) points.add(r.start);
      if (r.end   >= 0 && r.end   <= text.length) points.add(r.end);
    });
    // Add each visible marker's char position as a split point so badges
    // land exactly at segment boundaries and don't break existing spans.
    pdfEditMarkers.forEach(m => {
      if (m.pdfCharPos != null && m.pdfCharPos >= 0 && m.pdfCharPos <= text.length)
        points.add(m.pdfCharPos);
    });
    const sorted = [...points].sort((a, b) => a - b);
    return sorted.slice(0, -1).map((start, i) => {
      const end    = sorted[i + 1];
      const active = ranges.filter(r => r.start <= start && r.end >= end);
      return { text: text.slice(start, end), start, end, active };
    });
  };

  // Build a charPos → marker[] lookup for fast badge insertion
  const markerPinMap = React.useMemo(() => {
    const map = new Map();
    pdfEditMarkers.forEach(m => {
      if (m.pdfCharPos == null) return;
      if (!map.has(m.pdfCharPos)) map.set(m.pdfCharPos, []);
      map.get(m.pdfCharPos).push(m);
    });
    return map;
  }, [pdfEditMarkers]);

  const renderMarkerBadge = (pin) => {
    const labelColor = MARKER_LABEL_COLORS[pin.type] || '#374151';
    const bgColor    = MARKER_COLORS[pin.type]       || '#e5e7eb';
    const icon = pin.type === 'page_break' ? '📄' : pin.type === 'paragraph' ? '¶' : pin.type === 'chapter' ? '📖' : '📍';
    const isSelected = selectedMarkerId === pin.id;
    return (
      <span
        key={`mpid-${pin.id}`}
        id={`mpid-${pin.id}`}
        onClick={() => {
          setSelectedMarkerId(pin.id);
          setActiveSection('markers');
          setFilterType('all');
          // Scroll the right panel card into view
          const card = document.getElementById(`mcard-${pin.id}`);
          if (card) card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }}
        title={`${pin.label} · ${formatTime(pin.audioTime)} — click to select in panel`}
        style={{
          display: 'inline-block',
          background: bgColor,
          color: labelColor,
          fontSize: '0.68em',
          fontWeight: 700,
          padding: '1px 4px',
          borderRadius: '4px',
          cursor: 'pointer',
          margin: '0 2px',
          border: isSelected ? `1.5px solid ${labelColor}` : '1.5px solid transparent',
          boxShadow: isSelected ? `0 0 0 2px ${bgColor}` : 'none',
          verticalAlign: 'middle',
          lineHeight: '1.3',
          userSelect: 'none',
          whiteSpace: 'nowrap',
        }}
      >
        {icon}{pin.type !== 'paragraph' ? ` ${pin.label}` : ''}
      </span>
    );
  };

  const renderAnnotatedText = (text) => {
    const segs = buildStyledSegments(text);
    const els  = [];
    segs.forEach((seg, si) => {
      // Insert marker badges at this segment's start position
      if (markerPinMap.has(seg.start)) {
        markerPinMap.get(seg.start).forEach(pin => els.push(renderMarkerBadge(pin)));
      }

      let bg = null, td = null, color = null, isCurrent = false;
      seg.active.forEach(r => {
        if      (r.kind === 'find-current')              { bg = '#fbbf24'; isCurrent = true; }
        else if (r.kind === 'find-match' && !isCurrent)  { bg = '#fef9c3'; }
        else if (r.kind === 'room_tone')                 { bg = 'rgba(20,184,166,0.28)'; }
        else if (r.kind === 'not_included')              { td = 'line-through'; color = '#94a3b8'; }
      });
      const style = {};
      if (bg)       style.background     = bg;
      if (td)       style.textDecoration = td;
      if (color)    style.color          = color;
      if (bg || td) style.borderRadius   = '3px';
      const parts = seg.text.split('\n');
      parts.forEach((part, pi) => {
        if (pi > 0) els.push(<br key={`br-${si}-${pi}`} />);
        const hasStyle = Object.keys(style).length > 0;
        els.push(
          hasStyle
            ? <span key={`s-${si}-${pi}`} style={style} {...(isCurrent ? { 'data-find-current': 'true' } : {})}>{part || '\u00a0'}</span>
            : <React.Fragment key={`s-${si}-${pi}`}>{part}</React.Fragment>
        );
      });
    });
    return els;
  };

  const handleTextMouseUp = (e) => {
    if (activeTextTool !== 'highlight') return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !textViewRef.current) { setSelectionInfo(null); return; }
    if (!textViewRef.current.contains(sel.anchorNode) || !textViewRef.current.contains(sel.focusNode)) {
      setSelectionInfo(null); return;
    }
    let s  = getCharOffset(textViewRef.current, sel.anchorNode, sel.anchorOffset);
    let en = getCharOffset(textViewRef.current, sel.focusNode,  sel.focusOffset);
    if (s < 0 || en < 0) { setSelectionInfo(null); return; }
    if (s > en) [s, en] = [en, s];
    if (en <= s) { setSelectionInfo(null); return; }
    setSelectionInfo({ x: e.clientX, y: e.clientY, start: s, end: en });
  };

  const addTextAnnotation = (type) => {
    if (!selectionInfo) return;
    const { start, end } = selectionInfo;
    const annText = pdfText.slice(start, Math.min(end, start + 60));
    setTextAnnotations(prev => [...prev, { id: mkId(), start, end, type, text: annText }]);
    if (type === 'room_tone') {
      const wm  = buildWordTimeMap();
      const dur = selectedAudioFile?.duration || 0;
      const audioTime = charToTime(start, wm, dur);
      const marker = {
        id: mkId(), type: 'custom',
        label: `Room Tone: "${annText.slice(0, 25).trim()}\u2026"`,
        pdfCharPos: start, pdfPage: null, audioTime,
        gapSeconds: 3, useRoomTone: true, color: MARKER_COLORS.custom,
      };
      pushPdfMarkersUndo(pdfEditMarkers);
      setPdfEditMarkers(prev => [...prev, marker].sort((a, b) => a.audioTime - b.audioTime));
    }
    setSelectionInfo(null);
    window.getSelection()?.removeAllRanges();
  };

  const filteredMarkers = pdfEditMarkers.filter(m =>
    filterType === 'all' || m.type === filterType
  );

  const hasPDF = !!projectData?.pdf_file;

  /* ─────────────────────────────────────────────────────────────────  */
  /* Render                                                             */
  /* ─────────────────────────────────────────────────────────────────  */
  return (
    <div style={S.root}>

      {/* ── Page Header ───────────────────────────────────────────── */}
      <div style={S.pageHeader}>
        <div>
          <h2 style={S.pageTitle}>📄✂️ PDF Edit</h2>
          <p style={S.pageSub}>
            {hasPDF
              ? `PDF loaded · ${totalPages} pages · ${totalChars.toLocaleString()} chars · ${pdfEditMarkers.length} markers in Edit tab`
              : 'No PDF attached to this project'}
          </p>
        </div>
        <div style={S.headerActions}>
          {/* Save status pill */}
          {saveStatus && (
            <span style={{
              ...S.resultPill,
              background: saveStatus === 'error' ? '#fef2f2' : saveStatus === 'saving' ? '#eff6ff' : '#f0fdf4',
              color: saveStatus === 'error' ? '#b91c1c' : saveStatus === 'saving' ? '#1d4ed8' : '#059669',
              border: saveStatus === 'error' ? '1px solid #fecaca' : saveStatus === 'saving' ? '1px solid #bfdbfe' : '1px solid #bbf7d0',
            }}>
              {saveStatus === 'saving' ? '💾 Saving…' : saveStatus === 'error' ? '⚠️ Save failed' : `✅ ${saveStatus === 'saved' ? 'Saved' : saveStatus}`}
            </span>
          )}

          {hasPDF && (
            <>
              {/* Undo — local stack first, then backend */}
              <button
                style={pdfMarkersUndoStack.length > 0 || backendHistoryCount > 0 ? S.btnGhost : S.btnGhostDisabled}
                disabled={pdfMarkersUndoStack.length === 0 && backendHistoryCount === 0}
                onClick={() => {
                  if (pdfMarkersUndoStack.length > 0) undoPdfMarkers();
                  else undoFromBackend();
                }}
                title={`Undo (${pdfMarkersUndoStack.length} local, ${backendHistoryCount} saved)`}
              >
                ↩ Undo ({pdfMarkersUndoStack.length + backendHistoryCount})
              </button>

              {/* Revert to last saved */}
              <button
                style={lastSavedMarkers ? S.btnGhost : S.btnGhostDisabled}
                disabled={!lastSavedMarkers}
                onClick={revertToSaved}
                title="Reload the last version saved to the server"
              >
                🔄 Revert to Saved
              </button>

              {/* Explicit save */}
              <button
                style={isSaving ? S.btnGray : S.btnSuccess}
                onClick={() => saveMarkers(pdfEditMarkers)}
                disabled={isSaving}
                title="Save markers to server now"
              >
                {isSaving ? '💾 Saving…' : '💾 Save'}
              </button>

              <button style={S.btnGhost} onClick={() => setViewMode(viewMode === 'pdf' ? 'text' : 'pdf')}>
                {viewMode === 'pdf' ? '📝 Text View' : '📄 PDF View'}
              </button>
              <button
                style={isMappingAll ? S.btnGray : S.btnIndigo}
                onClick={mapAllToTimestamps}
                disabled={isMappingAll || pdfLoading}
              >
                {isMappingAll ? `⏳ ${mappingStatus}` : '🗺 Map All to Timestamps'}
              </button>
            </>
          )}
        </div>
      </div>

      {pdfError && (
        <div style={S.alertRed}><strong>⚠️ {pdfError}</strong></div>
      )}

      {!hasPDF && (
        <div style={S.emptyCard}>
          <div style={{ fontSize: '3em', marginBottom: '12px' }}>📄</div>
          <h3 style={{ margin: '0 0 8px' }}>No PDF attached</h3>
          <p style={{ margin: 0, color: '#94a3b8' }}>
            Upload a PDF in the <strong>Upload & Transcribe</strong> tab first, then return here.
          </p>
        </div>
      )}

      {hasPDF && (
        <div style={{ display: 'flex', gap: '16px', flex: 1, minHeight: 0 }}>

          {/* ── Left: PDF/Text Viewer ─────────────────────────────── */}
          <div style={{ ...S.card, flex: '0 0 48%', display: 'flex', flexDirection: 'column', minHeight: '520px' }}>
            <div style={S.cardHead}>
              <h3 style={S.cardTitle}>
                {viewMode === 'pdf' ? '📄 PDF Viewer' : '📝 Extracted Text'}
              </h3>
              <span style={S.cardMeta}>{pdfLoading ? '⏳ Loading…' : `${totalPages} pages`}</span>
            </div>

            {/* ── Text tool bar (text mode only) ─────────────────── */}
            {viewMode !== 'pdf' && !pdfLoading && pdfText && (
              <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                {[
                  { id: 'find',      label: '🔍 Find'     },
                  { id: 'highlight', label: '🖌 Highlight' },
                  { id: 'edit',      label: '✏️ Edit Text' },
                ].map(tool => (
                  <button
                    key={tool.id}
                    style={activeTextTool === tool.id ? S.toolBtnActive : S.toolBtn}
                    onClick={() => {
                      if (tool.id === 'edit') {
                        setEditedText(pdfText);
                        setIsEditMode(true);
                        setActiveTextTool('edit');
                      } else if (activeTextTool === tool.id) {
                        setActiveTextTool('none');
                        setIsEditMode(false);
                      } else {
                        setActiveTextTool(tool.id);
                        setIsEditMode(false);
                      }
                    }}
                  >
                    {tool.label}
                  </button>
                ))}
                {textAnnotations.length > 0 && (
                  <button style={S.btnXS} onClick={() => setTextAnnotations([])}>
                    Clear {textAnnotations.length} highlights
                  </button>
                )}
              </div>
            )}

            {/* ── Find bar ──────────────────────────────────────── */}
            {viewMode !== 'pdf' && activeTextTool === 'find' && (
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '8px' }}>
                <input
                  type="text"
                  placeholder="Search in text…"
                  value={findQuery}
                  onChange={e => setFindQuery(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter')  setFindMatchIdx(p => findMatches.length ? (p + 1) % findMatches.length : 0);
                    if (e.key === 'Escape') { setFindQuery(''); setActiveTextTool('none'); }
                  }}
                  autoFocus
                  style={{ flex: 1, padding: '5px 10px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.88em' }}
                />
                <span style={{ fontSize: '0.78em', color: '#6b7280', whiteSpace: 'nowrap', minWidth: '56px' }}>
                  {findMatches.length ? `${findMatchIdx + 1} / ${findMatches.length}` : findQuery ? '0 results' : ''}
                </span>
                <button style={S.btnXS} disabled={!findMatches.length} onClick={() => setFindMatchIdx(p => (p - 1 + findMatches.length) % findMatches.length)}>▲</button>
                <button style={S.btnXS} disabled={!findMatches.length} onClick={() => setFindMatchIdx(p => (p + 1) % findMatches.length)}>▼</button>
              </div>
            )}

            {/* ── Highlight hint ─────────────────────────────────── */}
            {viewMode !== 'pdf' && activeTextTool === 'highlight' && !isEditMode && (
              <div style={{ fontSize: '0.8em', color: '#4f46e5', background: '#eef2ff', padding: '5px 10px', borderRadius: '6px', marginBottom: '8px' }}>
                Select text → choose <strong>Room Tone</strong> (adds a gap marker) or <strong>Not Included</strong> (marks text to skip).
              </div>
            )}

            {viewMode === 'pdf' ? (
              <iframe
                src={pdfUrl}
                title="PDF Viewer"
                style={{ flex: 1, border: 'none', borderRadius: '8px', width: '100%', minHeight: '460px' }}
              />
            ) : isEditMode ? (
              /* ── Edit mode ───────────────────────────────────── */
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px', minHeight: 0 }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.78em', color: '#64748b', flex: 1 }}>
                    Edit extracted text — changes are saved to the server
                  </span>
                  {textSaveError && (
                    <span style={{ fontSize: '0.78em', color: '#b91c1c' }}>{textSaveError}</span>
                  )}
                  <button
                    style={isTextSaving ? S.btnGray : S.btnSuccess}
                    disabled={isTextSaving}
                    onClick={async () => {
                      setIsTextSaving(true);
                      setTextSaveError('');
                      try {
                        const resp = await fetch(
                          `${API_BASE_URL}/api/projects/${projectId}/pdf-text/`,
                          {
                            method: 'PATCH',
                            headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
                            body: JSON.stringify({ pdf_text: editedText }),
                          }
                        );
                        if (!resp.ok) throw new Error(`Server error ${resp.status}`);
                        setPdfText(editedText);
                        setIsEditMode(false);
                        setActiveTextTool('none');
                      } catch (err) {
                        setTextSaveError('Save failed: ' + err.message);
                      } finally {
                        setIsTextSaving(false);
                      }
                    }}
                  >
                    {isTextSaving ? '⏳ Saving…' : '✅ Apply & Save'}
                  </button>
                  <button style={S.btnGhost} onClick={() => { setIsEditMode(false); setActiveTextTool('none'); setTextSaveError(''); }}>
                    Cancel
                  </button>
                </div>
                <textarea
                  value={editedText}
                  onChange={e => setEditedText(e.target.value)}
                  spellCheck={false}
                  style={{ flex: 1, minHeight: '400px', padding: '10px 12px', fontFamily: 'ui-monospace, monospace', fontSize: '0.84em', lineHeight: 1.65, border: '1px solid #d1d5db', borderRadius: '8px', resize: 'none', color: '#334155' }}
                />
              </div>
            ) : (
              /* ── Text view with find + annotation highlighting ── */
              <div ref={textViewRef} style={S.textView} onMouseUp={handleTextMouseUp}>
                {pdfLoading ? (
                  <div style={S.spinner} />
                ) : pdfText ? (
                  <div style={{ fontSize: '0.88em', lineHeight: 1.65, color: '#334155', userSelect: 'text' }}>
                    {renderAnnotatedText(pdfText)}
                  </div>
                ) : (
                  <p style={{ color: '#94a3b8' }}>No text extracted</p>
                )}
              </div>
            )}

            {/* ── Annotation legend ─────────────────────────────── */}
            {viewMode !== 'pdf' && textAnnotations.length > 0 && !isEditMode && (
              <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '100px', overflowY: 'auto' }}>
                <span style={{ fontSize: '0.72em', color: '#94a3b8', fontWeight: 700, letterSpacing: '0.05em' }}>HIGHLIGHTS</span>
                {textAnnotations.map(ann => (
                  <div key={ann.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78em' }}>
                    <span style={{ background: ann.type === 'room_tone' ? 'rgba(20,184,166,0.25)' : 'rgba(148,163,184,0.25)', padding: '1px 6px', borderRadius: '4px', color: ann.type === 'room_tone' ? '#0f766e' : '#64748b', fontWeight: 600 }}>
                      {ann.type === 'room_tone' ? '🎙' : '🚫'}
                    </span>
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#475569' }}>"{ann.text}"</span>
                    <button style={{ ...S.btnXS, padding: '1px 5px' }} onClick={() => setTextAnnotations(prev => prev.filter(a => a.id !== ann.id))}>✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Right: Controls ───────────────────────────────────── */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '14px', minWidth: 0 }}>

            {/* Section tabs */}
            <div style={S.sectionTabs}>
              {['markers', 'roomtone', 'custom'].map(s => (
                <button
                  key={s}
                  style={activeSection === s ? S.sectionTabActive : S.sectionTab}
                  onClick={() => setActiveSection(s)}
                >
                  {s === 'markers' ? `📍 Markers (${pdfEditMarkers.length})` : s === 'roomtone' ? '🎙 Room Tone' : '➕ Add Custom'}
                </button>
              ))}
            </div>

            {/* ── Markers Panel ──────────────────────────────────── */}
            {activeSection === 'markers' && (
              <div style={{ ...S.card, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div style={S.cardHead}>
                  <h3 style={S.cardTitle}>📍 Structural Markers</h3>
                  <span style={S.cardMeta}>These appear as coloured regions in the Edit tab</span>
                  {pdfEditMarkers.length > 0 && (
                    <button style={S.btnDanger} onClick={() => { pushPdfMarkersUndo(pdfEditMarkers); setPdfEditMarkers([]); }}>Clear All</button>
                  )}
                </div>

                {/* Filter */}
                <div style={{ display: 'flex', gap: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
                  {['all', 'page_break', 'paragraph', 'chapter', 'custom'].map(t => (
                    <button
                      key={t}
                      style={filterType === t ? { ...S.filterBtn, ...S.filterBtnActive } : S.filterBtn}
                      onClick={() => setFilterType(t)}
                    >
                      {t === 'all' ? `All (${pdfEditMarkers.length})`
                        : t === 'page_break' ? `🟣 Pages (${pdfEditMarkers.filter(m => m.type === 'page_break').length})`
                        : t === 'paragraph' ? `🟠 Paras (${pdfEditMarkers.filter(m => m.type === 'paragraph').length})`
                        : t === 'chapter' ? `🩷 Chapters (${pdfEditMarkers.filter(m => m.type === 'chapter').length})`
                        : `🩵 Custom (${pdfEditMarkers.filter(m => m.type === 'custom').length})`}
                    </button>
                  ))}
                </div>

                {mappingStatus && !isMappingAll && (
                  <div style={S.resultPill}>{mappingStatus}</div>
                )}

                {filteredMarkers.length === 0 ? (
                  <div style={S.emptyBox}>
                    <p style={{ margin: '0 0 8px' }}>No markers yet.</p>
                    <p style={{ margin: 0, fontSize: '0.85em', color: '#9ca3af' }}>
                      Click <strong>"Map All to Timestamps"</strong> to auto-detect page breaks and paragraphs.
                    </p>
                  </div>
                ) : (
                  <div style={S.markerList}>
                    {filteredMarkers.map((marker) => (
                      <div
                        key={marker.id}
                        id={`mcard-${marker.id}`}
                        style={{
                          ...S.markerRow,
                          borderLeft: `4px solid ${MARKER_LABEL_COLORS[marker.type] || '#6b7280'}`,
                          background: selectedMarkerId === marker.id ? 'rgba(99,102,241,0.07)' : undefined,
                        }}
                      >
                        <div style={S.markerMeta}>
                          <span style={{ ...S.typePill, background: marker.color, color: MARKER_LABEL_COLORS[marker.type] }}>
                            {marker.type === 'page_break' ? '🟣' : marker.type === 'paragraph' ? '🟠' : marker.type === 'chapter' ? '🩷' : '🩵'}
                            {' '}{marker.label}
                          </span>
                          <span style={S.markerTime}>⏱ {formatTime(marker.audioTime)}</span>
                          {marker.pdfCharPos != null && (
                            <button
                              style={{ ...S.btnXS, fontSize: '0.72em' }}
                              title="Jump to this position in the extracted text"
                              onClick={() => {
                                setSelectedMarkerId(marker.id);
                                if (viewMode === 'pdf') setViewMode('text');
                                // scroll text panel to the badge
                                setTimeout(() => {
                                  const pin = document.getElementById(`mpid-${marker.id}`);
                                  if (pin) pin.scrollIntoView({ block: 'center', behavior: 'smooth' });
                                }, 50);
                              }}
                            >📝</button>
                          )}
                          <button style={S.btnXS} onClick={() => removeMarker(marker.id)}>✕</button>
                        </div>

                        <div style={S.markerControls}>
                          <label style={S.controlLabel}>
                            Gap:
                            <input
                              type="number" min="0" max="60" step="0.5"
                              value={marker.gapSeconds}
                              onChange={(e) => updateMarker(marker.id, { gapSeconds: parseFloat(e.target.value) || 0 })}
                              style={S.numInput}
                            />
                            s
                          </label>
                          <label style={S.controlLabel}>
                            <input
                              type="checkbox"
                              checked={marker.useRoomTone}
                              onChange={(e) => updateMarker(marker.id, { useRoomTone: e.target.checked })}
                              disabled={!pdfRoomTone}
                              style={{ accentColor: '#6366f1' }}
                            />
                            {pdfRoomTone ? '🎙 Room Tone' : '🎙 Room Tone (not loaded)'}
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Summary */}
                {pdfEditMarkers.length > 0 && (
                  <div style={S.summaryBar}>
                    <span>Total gap time: <strong>{pdfEditMarkers.reduce((s, m) => s + (m.gapSeconds || 0), 0).toFixed(1)}s</strong></span>
                    <span style={{ color: '#6366f1' }}>{pdfEditMarkers.filter(m => m.useRoomTone).length} using room tone</span>
                  </div>
                )}
              </div>
            )}

            {/* ── Room Tone Panel ────────────────────────────────── */}
            {activeSection === 'roomtone' && (
              <div style={S.card}>
                <div style={S.cardHead}>
                  <h3 style={S.cardTitle}>🎙 Room Tone</h3>
                  <span style={S.cardMeta}>Upload a short ambient/room-tone recording to fill gaps</span>
                </div>

                <div style={S.roomToneArea}>
                  {pdfRoomTone ? (
                    <div style={S.roomToneLoaded}>
                      <div style={{ fontWeight: 600, color: '#334155', marginBottom: '8px' }}>
                        ✅ {pdfRoomTone.filename}
                        {pdfRoomTone.duration && <span style={{ fontWeight: 400, color: '#94a3b8' }}> ({pdfRoomTone.duration.toFixed(2)}s)</span>}
                      </div>
                      <audio
                        src={pdfRoomTone.blobUrl}
                        controls
                        onLoadedMetadata={handleRoomToneDuration}
                        style={{ width: '100%', marginBottom: '10px' }}
                      />
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button style={S.btnGhost} onClick={() => roomToneInputRef.current?.click()}>
                          🔄 Replace
                        </button>
                        <button style={S.btnDanger} onClick={() => { setPdfRoomTone(null); pushPdfMarkersUndo(pdfEditMarkers); setPdfEditMarkers(prev => prev.map(m => ({ ...m, useRoomTone: false }))); }}>
                          🗑 Remove
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div
                      style={S.dropZone}
                      onClick={() => roomToneInputRef.current?.click()}
                    >
                      <div style={{ fontSize: '2em', marginBottom: '8px' }}>🎙</div>
                      <p style={{ margin: '0 0 6px', fontWeight: 600, color: '#334155' }}>Upload Room Tone</p>
                      <p style={{ margin: 0, fontSize: '0.85em', color: '#94a3b8' }}>
                        Click to select a WAV/MP3 recording of ambient room sound.
                        This will be looped to fill the gap duration at each marked position.
                      </p>
                    </div>
                  )}
                  <input
                    ref={roomToneInputRef}
                    type="file"
                    accept="audio/*"
                    style={{ display: 'none' }}
                    onChange={handleRoomToneUpload}
                  />
                </div>

                <div style={{ marginTop: '16px', padding: '12px', background: '#f8fafc', borderRadius: '8px', fontSize: '0.85em', color: '#64748b' }}>
                  <strong>How it works:</strong><br />
                  When you check "Room Tone" on a marker, the gap at that position will be filled with this recording (looped if needed) instead of silence. This creates a natural transition rather than a dead-silent cut.
                </div>
              </div>
            )}

            {/* ── Custom Marker Panel ────────────────────────────── */}
            {activeSection === 'custom' && (
              <div style={S.card}>
                <div style={S.cardHead}>
                  <h3 style={S.cardTitle}>➕ Add Custom Gap</h3>
                  <span style={S.cardMeta}>Manually place a gap at any audio position</span>
                </div>

                <div style={S.customForm}>
                  <label style={S.formLabel}>
                    Audio Time (seconds)
                    <input
                      type="number" min="0" step="0.1"
                      placeholder="e.g. 123.5"
                      value={customTime}
                      onChange={(e) => setCustomTime(e.target.value)}
                      style={S.formInput}
                    />
                  </label>
                  <label style={S.formLabel}>
                    Label (optional)
                    <input
                      type="text"
                      placeholder="e.g. Chapter 3 Start"
                      value={customLabel}
                      onChange={(e) => setCustomLabel(e.target.value)}
                      style={S.formInput}
                    />
                  </label>
                  <button style={S.btnIndigo} onClick={addCustomMarker}>➕ Add Marker</button>
                </div>

                <div style={{ marginTop: '16px', padding: '12px', background: '#f8fafc', borderRadius: '8px', fontSize: '0.85em', color: '#64748b' }}>
                  <strong>Tip:</strong> After adding the marker, switch to the <strong>Edit tab</strong> to see it as a teal region on the waveform. You can also see the exact playhead time there to pick precise positions.
                </div>
              </div>
            )}

          </div>
        </div>
      )}

      {/* ── Floating selection toolbar ──────────────────────────────── */}
      {selectionInfo && (
        <div
          ref={selectionToolbarRef}
          style={{
            position: 'fixed',
            left: `${Math.min(selectionInfo.x, (window.innerWidth || 1200) - 330)}px`,
            top:  `${Math.max(8, selectionInfo.y - 74)}px`,
            background: '#1e293b',
            borderRadius: '10px',
            padding: '6px 8px',
            display: 'flex',
            gap: '6px',
            alignItems: 'center',
            zIndex: 9999,
            boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          }}
        >
          <span style={{ fontSize: '0.72em', color: '#94a3b8', marginRight: '2px' }}>Tag as:</span>
          <button
            style={{ background: 'rgba(20,184,166,0.85)', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82em', fontWeight: 600 }}
            onClick={() => addTextAnnotation('room_tone')}
          >
            🎙 Room Tone
          </button>
          <button
            style={{ background: 'rgba(100,116,139,0.85)', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.82em', fontWeight: 600 }}
            onClick={() => addTextAnnotation('not_included')}
          >
            🚫 Not Included
          </button>
          <button
            style={{ background: 'transparent', color: '#64748b', border: 'none', padding: '4px 6px', cursor: 'pointer', fontSize: '0.9em' }}
            onClick={() => { setSelectionInfo(null); window.getSelection()?.removeAllRanges(); }}
          >✕</button>
        </div>
      )}

    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────── */
/* Style constants                                                         */
/* ─────────────────────────────────────────────────────────────────────── */
const S = {
  root:       { display:'flex', flexDirection:'column', gap:'16px', padding:'20px', background:'#f8fafc', minHeight:'100%' },
  pageHeader: { display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:'12px' },
  pageTitle:  { margin:0, fontSize:'1.4em', fontWeight:700, color:'#1e293b' },
  pageSub:    { margin:'4px 0 0', fontSize:'0.9em', color:'#64748b' },
  headerActions:{ display:'flex', gap:'8px', flexWrap:'wrap' },
  alertRed:   { background:'#fef2f2', border:'1px solid #fecaca', color:'#991b1b', padding:'10px 14px', borderRadius:'8px', fontSize:'0.9em' },
  emptyCard:  { display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', background:'#fff', borderRadius:'12px', border:'1px solid #e2e8f0', padding:'40px', textAlign:'center', color:'#64748b' },
  card:       { background:'#fff', borderRadius:'12px', border:'1px solid #e2e8f0', padding:'16px 20px', boxShadow:'0 1px 4px rgba(0,0,0,0.06)' },
  cardHead:   { display:'flex', alignItems:'center', gap:'10px', marginBottom:'14px', flexWrap:'wrap' },
  cardTitle:  { margin:0, fontSize:'1em', fontWeight:700, color:'#334155' },
  cardMeta:   { fontSize:'0.8em', color:'#94a3b8', flex:1 },
  textView:   { flex:1, overflowY:'auto', maxHeight:'460px', padding:'10px 4px', lineHeight:1.6 },
  spinner:    { width:'32px', height:'32px', border:'3px solid #e2e8f0', borderTopColor:'#6366f1', borderRadius:'50%', animation:'tabedit-spin 0.8s linear infinite', margin:'40px auto' },
  sectionTabs:{ display:'flex', gap:'6px', flexWrap:'wrap' },
  sectionTab: { background:'#f1f5f9', color:'#64748b', border:'1px solid #e2e8f0', padding:'7px 14px', borderRadius:'8px', cursor:'pointer', fontWeight:500, fontSize:'0.85em' },
  sectionTabActive:{ background:'#6366f1', color:'#fff', border:'1px solid #4f46e5', padding:'7px 14px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.85em' },
  filterBtn:  { background:'#f8fafc', color:'#64748b', border:'1px solid #e2e8f0', padding:'4px 10px', borderRadius:'16px', cursor:'pointer', fontSize:'0.78em', fontWeight:500 },
  filterBtnActive:{ background:'#eff6ff', color:'#1e40af', border:'1px solid #bfdbfe' },
  markerList: { overflowY:'auto', maxHeight:'320px', display:'flex', flexDirection:'column', gap:'8px' },
  markerRow:  { background:'#f8fafc', borderRadius:'8px', padding:'10px 12px', display:'flex', flexDirection:'column', gap:'6px' },
  markerMeta: { display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap' },
  markerTime: { fontSize:'0.82em', color:'#6b7280', fontFamily:'monospace', marginLeft:'auto' },
  typePill:   { padding:'2px 8px', borderRadius:'12px', fontSize:'0.78em', fontWeight:600 },
  markerControls:{ display:'flex', gap:'16px', alignItems:'center', flexWrap:'wrap', fontSize:'0.85em' },
  controlLabel:  { display:'flex', alignItems:'center', gap:'5px', cursor:'pointer', color:'#475569' },
  numInput:   { width:'55px', padding:'3px 6px', borderRadius:'5px', border:'1px solid #d1d5db', fontSize:'0.9em', textAlign:'right' },
  summaryBar: { marginTop:'12px', paddingTop:'10px', borderTop:'1px solid #e2e8f0', display:'flex', justifyContent:'space-between', fontSize:'0.85em', color:'#64748b' },
  emptyBox:   { color:'#94a3b8', textAlign:'center', padding:'24px 0', fontSize:'0.9em' },
  resultPill: { fontSize:'0.8em', color:'#059669', background:'#f0fdf4', padding:'4px 10px', borderRadius:'6px', border:'1px solid #bbf7d0', marginBottom:'8px' },
  roomToneArea:{ display:'flex', flexDirection:'column', gap:'10px' },
  roomToneLoaded:{ background:'#f0fdf4', border:'1px solid #bbf7d0', borderRadius:'8px', padding:'14px' },
  dropZone:   { background:'#f8fafc', border:'2px dashed #d1d5db', borderRadius:'10px', padding:'30px 20px', textAlign:'center', cursor:'pointer', transition:'border-color 0.15s' },
  customForm: { display:'flex', flexDirection:'column', gap:'14px' },
  formLabel:  { display:'flex', flexDirection:'column', gap:'5px', fontSize:'0.9em', fontWeight:600, color:'#475569' },
  formInput:  { padding:'8px 12px', borderRadius:'7px', border:'1px solid #d1d5db', fontSize:'0.95em', marginTop:'2px' },
  btnIndigo:  { background:'#6366f1', color:'#fff', border:'none', padding:'9px 18px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em', whiteSpace:'nowrap' },
  btnGhost:   { background:'#f1f5f9', color:'#334155', border:'1px solid #e2e8f0', padding:'8px 14px', borderRadius:'8px', cursor:'pointer', fontWeight:500, fontSize:'0.9em' },
  btnGhostDisabled: { background:'#f8fafc', color:'#cbd5e1', border:'1px solid #e2e8f0', padding:'8px 14px', borderRadius:'8px', cursor:'not-allowed', fontWeight:500, fontSize:'0.9em' },
  btnSuccess: { background:'#059669', color:'#fff', border:'none', padding:'9px 18px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em', whiteSpace:'nowrap' },
  btnGray:    { background:'#9ca3af', color:'#fff', border:'none', padding:'9px 18px', borderRadius:'8px', cursor:'not-allowed', fontWeight:600, fontSize:'0.9em' },
  btnDanger:  { background:'#fef2f2', color:'#b91c1c', border:'1px solid #fecaca', padding:'6px 12px', borderRadius:'7px', cursor:'pointer', fontWeight:500, fontSize:'0.82em' },
  btnXS:      { background:'#f1f5f9', color:'#6b7280', border:'none', padding:'2px 7px', borderRadius:'5px', cursor:'pointer', fontSize:'0.8em', marginLeft:'auto' },
  toolBtn:       { background:'#f1f5f9', color:'#475569', border:'1px solid #e2e8f0', padding:'5px 12px', borderRadius:'7px', cursor:'pointer', fontSize:'0.82em', fontWeight:500 },
  toolBtnActive: { background:'#6366f1', color:'#fff', border:'1px solid #4f46e5', padding:'5px 12px', borderRadius:'7px', cursor:'pointer', fontSize:'0.82em', fontWeight:600 },
};

export default TabPDFEdit;
