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
  const roomToneInputRef = useRef(null);

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
    while ((match = re.exec(text)) !== null) {
      const blockText = text.slice(prev, match.index).trim();
      if (blockText.length > 40) {
        results.push({
          start_char: prev,
          end_char: match.index,
          preview: blockText.slice(0, 80),
        });
      }
      prev = match.index + match[0].length;
    }
    // Last block
    const lastBlock = text.slice(prev).trim();
    if (lastBlock.length > 40) {
      results.push({ start_char: prev, end_char: text.length, preview: lastBlock.slice(0, 80) });
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

    // Page breaks
    setMappingStatus(`Mapping ${pageBreaks.length} page breaks…`);
    await new Promise(r => setTimeout(r, 20));
    pageBreaks.forEach((pb) => {
      newMarkers.push({
        id:         mkId(),
        type:       'page_break',
        label:      `Page ${pb.page_num}`,
        pdfCharPos: pb.start_char,
        pdfPage:    pb.page_num,
        audioTime:  charToTime(pb.start_char, wordTimeMap, audioDuration),
        gapSeconds: 2,
        useRoomTone: false,
        color:      MARKER_COLORS.page_break,
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

            {viewMode === 'pdf' ? (
              <iframe
                src={pdfUrl}
                title="PDF Viewer"
                style={{ flex: 1, border: 'none', borderRadius: '8px', width: '100%', minHeight: '460px' }}
              />
            ) : (
              <div style={S.textView}>
                {pdfLoading ? (
                  <div style={S.spinner} />
                ) : pdfText ? (
                  pdfText.split('\n').map((line, i) => (
                    <p key={i} style={{
                      margin: line.trim() === '' ? '8px 0' : '0 0 2px',
                      color: line.trim() === '' ? 'transparent' : '#334155',
                      fontSize: '0.88em',
                      lineHeight: 1.6,
                      borderLeft: line.trim() === '' ? '2px dashed #e2e8f0' : 'none',
                      paddingLeft: line.trim() === '' ? '6px' : 0,
                    }}>{line || ' '}</p>
                  ))
                ) : (
                  <p style={{ color: '#94a3b8' }}>No text extracted</p>
                )}
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
                      <div key={marker.id} style={{ ...S.markerRow, borderLeft: `4px solid ${MARKER_LABEL_COLORS[marker.type] || '#6b7280'}` }}>
                        <div style={S.markerMeta}>
                          <span style={{ ...S.typePill, background: marker.color, color: MARKER_LABEL_COLORS[marker.type] }}>
                            {marker.type === 'page_break' ? '🟣' : marker.type === 'paragraph' ? '🟠' : marker.type === 'chapter' ? '🩷' : '🩵'}
                            {' '}{marker.label}
                          </span>
                          <span style={S.markerTime}>⏱ {formatTime(marker.audioTime)}</span>
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
};

export default TabPDFEdit;
