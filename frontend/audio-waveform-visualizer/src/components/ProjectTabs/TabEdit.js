import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import { getApiUrl, API_BASE_URL, resolveMediaUrl } from '../../config/api';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js';
import './ProjectTabs.css';

/**
 * TabEdit — Professional Audio Editor
 * Full DAW-style editor with waveform, word-level transcript, duplicate regions,
 * align-to-silence, skip-deleted playback and professional tooling.
 */
const TabEdit = () => {
  const { token } = useAuth();
  const {
    projectId,
    selectedAudioFile,
    audioFiles,
    selectAudioFile,
    transcriptionData,
    setTranscriptionData,
    pdfEditMarkers,
  } = useProjectTab();

  /* ─── Refs ──────────────────────────────────────────────────────── */
  const waveformRef      = useRef(null);
  const timelineRef      = useRef(null);
  const transcriptRef    = useRef(null);
  const regionsMapRef    = useRef(new Map());
  const overlayScrollRef = useRef(null);

  /* ─── WaveSurfer state ───────────────────────────────────────────── */
  const [wavesurfer,       setWavesurfer]       = useState(null);
  const [wsRegions,        setWsRegions]         = useState(null);
  const [isPlaying,        setIsPlaying]         = useState(false);
  const [currentTime,      setCurrentTime]       = useState(0);
  const [duration,         setDuration]          = useState(0);
  const [isReady,          setIsReady]           = useState(false);
  const [isWaveformLoading,setIsWaveformLoading] = useState(false);
  const [zoom,             setZoom]              = useState(1);
  const [skipDeleted,      setSkipDeleted]       = useState(true);

  /* ─── Data state ─────────────────────────────────────────────────── */
  const [loading,    setLoading]    = useState(false);
  const [duplicates, setDuplicates] = useState([]);

  /* ─── Align-to-Silence state ─────────────────────────────────────── */
  const [isAligningToSilence, setIsAligningToSilence] = useState(false);
  const [alignResult,         setAlignResult]          = useState(null);
  const [silenceThreshold,   setSilenceThreshold]   = useState(-40);
  const [silenceSearchRange, setSilenceSearchRange] = useState(0.6);
  const [silenceMinDuration, setSilenceMinDuration] = useState(0.08);

  /* ────────────────────────────────────────────────────────────────── */
  /* Load transcription from API (mirrors Tab2 logic)                  */
  /* ────────────────────────────────────────────────────────────────── */
  const loadTranscription = useCallback(async () => {
    if (!selectedAudioFile || !projectId || !token) return;
    try {
      const resp = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
        { headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' } }
      );
      if (resp.ok) {
        const data = await resp.json();
        // Normalize segment keys: API returns start_time/end_time, context may use start/end
        const rawSegs = data.segments || data.all_segments || [];
        const normalized = rawSegs.map(seg => ({
          ...seg,
          start: seg.start !== undefined ? seg.start : (seg.start_time || 0),
          end:   seg.end   !== undefined ? seg.end   : (seg.end_time   || 0),
        }));
        setTranscriptionData({
          ...data,
          all_segments: normalized,
          word_count: data.transcription?.word_count || data.word_count || 0,
          text: data.transcription?.full_text || data.text || '',
        });
      }
    } catch (err) {
      console.error('TabEdit: failed to load transcription', err);
    }
  }, [selectedAudioFile, projectId, token, setTranscriptionData]);

  useEffect(() => {
    if (selectedAudioFile) {
      loadTranscription();
    }
  }, [selectedAudioFile]); // eslint-disable-line

  /* ────────────────────────────────────────────────────────────────── */
  /* Fetch duplicates                                                   */
  /* ────────────────────────────────────────────────────────────────── */
  const fetchDuplicates = useCallback(async () => {
    if (!projectId || !selectedAudioFile?.id || !token) return;
    setLoading(true);
    try {
      const resp = await fetch(
        getApiUrl(`/api/projects/${projectId}/files/${selectedAudioFile.id}/duplicates/`),
        { headers: { Authorization: `Token ${token}` } }
      );
      if (resp.ok) {
        const data = await resp.json();
        setDuplicates(data.duplicate_groups || []);
      }
    } catch (err) {
      console.error('TabEdit: failed to fetch duplicates', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedAudioFile, token]);

  useEffect(() => { fetchDuplicates(); }, [fetchDuplicates]);

  /* ────────────────────────────────────────────────────────────────── */
  /* WaveSurfer initialization                                         */
  /* ────────────────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!selectedAudioFile || !waveformRef.current) return;

    setIsReady(false);
    setIsWaveformLoading(true);
    regionsMapRef.current.clear();

    let audioUrl = '';
    if (selectedAudioFile.local_file) {
      audioUrl = URL.createObjectURL(selectedAudioFile.local_file);
    } else {
      const raw = selectedAudioFile.file || selectedAudioFile.audio_file || '';
      if (typeof raw === 'string' && raw) {
        const base = (API_BASE_URL || '').replace(/\/$/, '');
        audioUrl = raw.startsWith('http') ? raw : `${base}${raw.startsWith('/') ? '' : '/'}${raw}`;
      }
    }
    if (!audioUrl) { setIsWaveformLoading(false); return; }

    if (wavesurfer) { wavesurfer.destroy(); }

    const ws = WaveSurfer.create({
      container:     waveformRef.current,
      waveColor:     '#4a90e2',
      progressColor: '#1e40af',
      cursorColor:   '#ef4444',
      barWidth:      2,
      barGap:        2,
      barRadius:     3,
      height:        120,
      normalize:     true,
      minPxPerSec:   10 * zoom,
    });

    const regions  = ws.registerPlugin(RegionsPlugin.create());
    ws.registerPlugin(TimelinePlugin.create({ container: timelineRef.current }));

    setWavesurfer(ws);
    setWsRegions(regions);
    ws.load(audioUrl);

    ws.on('ready',        () => { setDuration(ws.getDuration()); setIsReady(true); setIsWaveformLoading(false); });
    ws.on('audioprocess', (t) => setCurrentTime(t));
    ws.on('play',         () => setIsPlaying(true));
    ws.on('pause',        () => setIsPlaying(false));
    ws.on('finish',       () => setIsPlaying(false));

    return () => { ws.destroy(); };
    // eslint-disable-next-line
  }, [selectedAudioFile]);

  /* ─── Zoom ──────────────────────────────────────────────────────── */
  useEffect(() => {
    if (wavesurfer && isReady) {
      try { wavesurfer.zoom(10 * zoom); } catch (e) { /* ignore pre-load */ }
    }
  }, [zoom, wavesurfer, isReady]);

  /* ─── Draw duplicate regions ────────────────────────────────────── */
  useEffect(() => {
    if (!wsRegions || !isReady) return;
    wsRegions.clearRegions();
    regionsMapRef.current.clear();
    duplicates.forEach((group) => {
      if (!group.occurrences) return;
      group.occurrences.forEach((occ) => {
        const isDeleted = !occ.is_kept;
        const region = wsRegions.addRegion({
          start: occ.start_time,
          end:   occ.end_time,
          color: isDeleted ? 'rgba(239,68,68,0.35)' : 'rgba(34,197,94,0.3)',
          drag:  true,
          resize: true,
          data: {
            isDeleted,
            isDelete:  isDeleted,
            groupId:   group.group_id,
            segmentId: occ.segment_index,
          },
        });
        regionsMapRef.current.set(region.id, region);
      });
    });
  }, [wsRegions, duplicates, isReady]);

  /* ─── Draw PDF structure markers (purple / orange / pink) ───────── */
  useEffect(() => {
    if (!wsRegions || !isReady) return;
    // Remove any previously drawn PDF marker regions
    regionsMapRef.current.forEach((region, id) => {
      if (region.data?.isPdfMarker) {
        try { region.remove(); } catch (e) {}
        regionsMapRef.current.delete(id);
      }
    });
    if (!pdfEditMarkers || pdfEditMarkers.length === 0) return;
    pdfEditMarkers.forEach((marker) => {
      const gapDur = Math.max(marker.gapSeconds || 0.3, 0.1);
      const region = wsRegions.addRegion({
        start: marker.audioTime,
        end:   marker.audioTime + gapDur,
        color: marker.color || 'rgba(147,51,234,0.35)',
        drag:  false,
        resize: false,
        data:  { isPdfMarker: true, type: marker.type, label: marker.label },
      });
      regionsMapRef.current.set(region.id, region);
    });
  }, [wsRegions, isReady, pdfEditMarkers]);

  /* ─── Skip deleted during playback ─────────────────────────────── */
  useEffect(() => {
    if (!wsRegions || !wavesurfer || !skipDeleted) return;
    const onRegionIn = (region) => {
      if (region.data?.isDeleted) wavesurfer.setTime(region.end);
    };
    wsRegions.on('region-in', onRegionIn);
    return () => { try { wsRegions.un('region-in', onRegionIn); } catch(e){} };
  }, [wsRegions, wavesurfer, skipDeleted]);

  /* ─── Auto-scroll transcript ────────────────────────────────────── */
  useEffect(() => {
    if (!transcriptRef.current) return;
    const active = transcriptRef.current.querySelector('.tabedit-seg-active');
    if (active) active.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [currentTime]);

  /* ─── Sync waveform scroll → transcript overlay ─────────────────── */
  useEffect(() => {
    if (!wavesurfer || !isReady || !overlayScrollRef.current || !waveformRef.current) return;
    const container = waveformRef.current;
    const handleScroll = (e) => {
      if (overlayScrollRef.current) {
        overlayScrollRef.current.scrollLeft = e.target.scrollLeft;
      }
    };
    // Use capture so we catch scroll on any child element (WaveSurfer shadow container)
    container.addEventListener('scroll', handleScroll, true);
    return () => container.removeEventListener('scroll', handleScroll, true);
  }, [wavesurfer, isReady]);

  /* ────────────────────────────────────────────────────────────────── */
  /* Align to Silence                                                   */
  /* ────────────────────────────────────────────────────────────────── */
  const calcRMS = (buf, s, e) => {
    const ch = buf.getChannelData(0);
    let sum = 0, n = 0;
    for (let i = s; i < e && i < ch.length; i++) { sum += ch[i] * ch[i]; n++; }
    if (n === 0) return -100;
    return 20 * Math.log10(Math.sqrt(sum / n));
  };

  const isInSilence = (buf, time) => {
    const sr = buf.sampleRate;
    const c  = Math.floor(time * sr);
    const w  = Math.floor(0.05 * sr);
    return calcRMS(buf, Math.max(0, c - w / 2), Math.min(buf.length, c + w / 2)) < silenceThreshold;
  };

  const findSilenceCenter = (buf, targetTime) => {
    const sr  = buf.sampleRate;
    const tgt = Math.floor(targetTime * sr);
    const rng = Math.floor(silenceSearchRange * sr);
    const min = Math.floor(silenceMinDuration * sr);
    const s0  = Math.max(0, tgt - rng);
    const s1  = Math.min(buf.length, tgt + rng);
    const win = Math.floor(0.02 * sr);
    const sections = [];
    let silStart = null;
    for (let i = s0; i < s1; i += win) {
      const silent = calcRMS(buf, i, i + win) < silenceThreshold;
      if (silent && silStart === null) silStart = i;
      else if (!silent && silStart !== null) {
        if (i - silStart >= min) sections.push({ center: (silStart + i) / 2 / sr });
        silStart = null;
      }
    }
    if (silStart !== null && s1 - silStart >= min) sections.push({ center: (silStart + s1) / 2 / sr });
    if (!sections.length) return targetTime;
    return sections.reduce((a, b) => Math.abs(a.center - targetTime) <= Math.abs(b.center - targetTime) ? a : b).center;
  };

  const handleAlignToSilence = async () => {
    if (!wavesurfer || !isReady || regionsMapRef.current.size === 0) {
      alert('No regions loaded — run duplicate detection in Tab 3 first.');
      return;
    }
    setIsAligningToSilence(true);
    setAlignResult(null);
    try {
      const buf = wavesurfer.getDecodedData();
      if (!buf) throw new Error('Audio buffer not ready.');
      let adjusted = 0, skipped = 0;
      regionsMapRef.current.forEach((region) => {
        if (!region?.data?.isDelete) return;
        const { start: s, end: e } = region;
        if (isInSilence(buf, s) && isInSilence(buf, e)) { skipped++; return; }
        const ns = isInSilence(buf, s) ? s : findSilenceCenter(buf, s);
        const ne = isInSilence(buf, e) ? e : findSilenceCenter(buf, e);
        if (ns < ne && ne - ns >= 0.1) { region.setOptions({ start: ns, end: ne }); adjusted++; }
      });
      setAlignResult({ adjusted, skipped });
    } catch (err) {
      alert(`Align to silence failed: ${err.message}`);
    } finally {
      setIsAligningToSilence(false);
    }
  };

  /* ─── Helpers ───────────────────────────────────────────────────── */
  const formatTime = (s) => {
    const m  = Math.floor(s / 60);
    const ss = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 100);
    return `${m}:${ss.toString().padStart(2,'0')}.${ms.toString().padStart(2,'0')}`;
  };

  const seekTo = (time) => {
    if (wavesurfer && duration > 0) { wavesurfer.seekTo(time / duration); setCurrentTime(time); }
  };

  /* ─── Derived data ──────────────────────────────────────────────── */
  // Normalize segments from context (may use start/end or start_time/end_time)
  const rawSegments = transcriptionData?.all_segments || transcriptionData?.segments || [];
  const segments = rawSegments.map(seg => ({
    ...seg,
    start: seg.start !== undefined ? seg.start : (seg.start_time || 0),
    end:   seg.end   !== undefined ? seg.end   : (seg.end_time   || 0),
  }));
  const activeSegIdx = segments.findIndex((seg) => currentTime >= seg.start && currentTime < seg.end);
  const totalRegions   = duplicates.reduce((n, g) => n + (g.occurrences?.length || 0), 0);
  const deletedRegions = duplicates.reduce((n, g) => n + (g.occurrences?.filter(o => !o.is_kept).length || 0), 0);
  const keptRegions    = totalRegions - deletedRegions;

  /* ────────────────────────────────────────────────────────────────── */
  /* Render — empty state                                               */
  /* ────────────────────────────────────────────────────────────────── */
  if (!selectedAudioFile) {
    return (
      <div style={S.emptyState}>
        <div style={{ fontSize: '3em', marginBottom: '12px' }}>🎧</div>
        <h2 style={{ margin: '0 0 8px', color: '#64748b' }}>Audio Editor</h2>
        <p style={{ margin: 0, color: '#94a3b8' }}>Select an audio file from the sidebar to begin editing.</p>
      </div>
    );
  }

  /* ────────────────────────────────────────────────────────────────── */
  /* Main render                                                        */
  /* ────────────────────────────────────────────────────────────────── */
  return (
    <div style={S.root}>

      {/* ── Page Header ─────────────────────────────────────────────── */}
      <div style={S.pageHeader}>
        <div>
          <h2 style={S.pageTitle}>✂️ Audio Editor</h2>
          <p style={S.pageSub}>
            {selectedAudioFile.title || selectedAudioFile.filename}
            {loading && <span style={{ color: '#f59e0b' }}> · syncing…</span>}
          </p>
        </div>
        <div style={S.badges}>
          <span style={{ ...S.badge, ...S.badgeGreen }}>✅ {keptRegions} Kept</span>
          <span style={{ ...S.badge, ...S.badgeRed }}>🗑️ {deletedRegions} Deleted</span>
          {segments.length > 0 && <span style={{ ...S.badge, ...S.badgeBlue }}>📝 {segments.length} Segments</span>}
        </div>
      </div>

      {/* ── Waveform Card ───────────────────────────────────────────── */}
      <div style={S.card}>

        {/* Toolbar */}
        <div style={S.toolbar}>
          <div style={S.toolbarLeft}>
            <button style={isPlaying ? S.btnAmber : S.btnBlue} onClick={() => wavesurfer?.playPause()} disabled={!isReady}>
              {isPlaying ? '⏸ Pause' : '▶ Play'}
            </button>
            <button style={S.btnGhost} onClick={() => wavesurfer?.stop()} disabled={!isReady}>⏹ Stop</button>
            <code style={S.timeCode}>{formatTime(currentTime)} / {formatTime(duration)}</code>
          </div>
          <div style={S.toolbarRight}>
            <label style={S.checkLabel}>
              <input type="checkbox" checked={skipDeleted} onChange={(e) => setSkipDeleted(e.target.checked)} style={{ accentColor: '#3b82f6' }} />
              <span>⏭ Skip Deleted</span>
            </label>
            <div style={S.zoomRow}>
              🔍
              <input type="range" min="0.5" max="15" step="0.5" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} style={S.slider} />
              <span style={S.zoomLabel}>{zoom}x</span>
            </div>
          </div>
        </div>

        {/* Waveform with loading spinner */}
        <div style={S.waveOuter}>
          {isWaveformLoading && (
            <div style={S.loadOverlay}>
              <div style={S.spinner} />
              <p style={{ margin: 0, color: '#64748b', fontSize: '0.9em' }}>Loading waveform…</p>
            </div>
          )}
          <div ref={timelineRef} style={{ borderBottom: '1px solid #e2e8f0' }} />
          <div ref={waveformRef} style={{ width: '100%' }} />

          {/* ── Transcript overlay: time-aligned text beneath the waveform ── */}
          {segments.length > 0 && isReady && (
            <div
              ref={overlayScrollRef}
              style={{
                overflowX: 'hidden',
                overflowY: 'hidden',
                width: '100%',
                height: `${Math.max(22, 13 + zoom * 1.5)}px`,
                borderTop: '1px solid #e2e8f0',
                background: '#f8fafc',
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'relative',
                  width: `${Math.max(100, duration * 10 * zoom)}px`,
                  height: '100%',
                  minWidth: '100%',
                }}
              >
                {segments.map((seg, idx) => {
                  const pxPerSec = 10 * zoom;
                  const left     = seg.start * pxPerSec;
                  const segWidth = Math.max(1, (seg.end - seg.start) * pxPerSec);
                  const fontSize = Math.max(7, Math.min(16, 5 + zoom * 0.75));
                  const isActive = idx === activeSegIdx;
                  return (
                    <div
                      key={idx}
                      onClick={() => seekTo(seg.start)}
                      title={`${formatTime(seg.start)} → ${formatTime(seg.end)}: ${seg.text}`}
                      style={{
                        position:   'absolute',
                        left:       `${left}px`,
                        width:      `${segWidth}px`,
                        height:     '100%',
                        overflow:   'hidden',
                        whiteSpace: 'nowrap',
                        textOverflow: 'ellipsis',
                        fontSize:   `${fontSize}px`,
                        lineHeight: 1,
                        display:    'flex',
                        alignItems: 'center',
                        padding:    '0 3px',
                        background: isActive ? 'rgba(254,249,195,0.95)' : 'transparent',
                        color:      isActive ? '#92400e' : '#475569',
                        fontWeight: isActive ? 600 : 400,
                        cursor:     'pointer',
                        boxSizing:  'border-box',
                        transition: 'background 0.15s',
                      }}
                    >
                      {seg.text?.trim()}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Legend */}
        <div style={S.legend}>
          <span style={S.legendItem}><span style={{ ...S.swatch, background: 'rgba(34,197,94,0.5)' }} /> Kept Section</span>
          <span style={S.legendItem}><span style={{ ...S.swatch, background: 'rgba(239,68,68,0.5)' }} /> Deleted Section</span>
          {isReady && totalRegions === 0 && (
            <span style={{ color: '#f59e0b', fontSize: '0.82em', marginLeft: 'auto' }}>
              ⚠️ No regions found — run duplicate detection in Tab 3 first.
            </span>
          )}
        </div>
      </div>

      {/* ── Transcript Card ──────────────────────────────────────────── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <h3 style={S.cardTitle}>📝 Transcript</h3>
          <span style={S.cardMeta}>
            {segments.length > 0
              ? `${transcriptionData?.word_count || 0} words · ${segments.length} segments — click any segment to seek`
              : 'No timed segments available'}
          </span>
          <button style={S.btnTiny} onClick={loadTranscription} title="Reload from server">↻ Refresh</button>
        </div>

        {segments.length > 0 ? (
          <div ref={transcriptRef} style={S.transcriptBox}>
            {segments.map((seg, idx) => {
              const active = idx === activeSegIdx;
              return (
                <span
                  key={idx}
                  onClick={() => seekTo(seg.start)}
                  title={`${formatTime(seg.start)} → ${formatTime(seg.end)}`}
                  className={active ? 'tabedit-seg-active' : ''}
                  style={{ ...S.seg, ...(active ? S.segActive : {}) }}
                >
                  {seg.text?.trim()}{' '}
                </span>
              );
            })}
          </div>
        ) : transcriptionData?.text ? (
          <div style={S.transcriptBox}>
            <p style={{ margin: 0, lineHeight: 1.7, color: '#475569' }}>{transcriptionData.text}</p>
          </div>
        ) : (
          <div style={S.emptyBox}>
            <p style={{ margin: '0 0 6px' }}>No transcription loaded.</p>
            <p style={{ margin: 0, fontSize: '0.85em', color: '#9ca3af' }}>
              Go to the <strong>Transcribe</strong> tab and transcribe this file first.
            </p>
          </div>
        )}
      </div>

      {/* ── Editing Tools Card ───────────────────────────────────────── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <h3 style={S.cardTitle}>🛠 Editing Tools</h3>
          <span style={S.cardMeta}>Drag region edges on the waveform above to fine-tune boundaries</span>
        </div>

        <div style={S.toolsGrid}>

          {/* Align to Silence */}
          <div style={{ ...S.toolGroup, gridColumn: '1 / -1' }}>
            <div style={S.toolGroupLabel}>Boundary Alignment</div>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1.5rem',
              alignItems: 'flex-end',
              background: '#f8fafc',
              padding: '1.25rem',
              borderRadius: '8px',
              border: '1px solid #f1f5f9',
            }}>
              <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'180px' }}>
                <label style={{ fontSize:'0.875rem', fontWeight:600, color:'#334155', marginBottom:'0.4rem' }}>
                  Silence Threshold: {silenceThreshold} dB
                </label>
                <input type="range" min="-60" max="-20" value={silenceThreshold}
                  onChange={(e) => setSilenceThreshold(Number(e.target.value))}
                  style={{ width:'100%', accentColor:'#0ea5e9' }} />
                <span style={{ fontSize:'0.75rem', color:'#64748b', marginTop:'0.25rem' }}>Lower = stricter silence requirement</span>
              </div>
              <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'180px' }}>
                <label style={{ fontSize:'0.875rem', fontWeight:600, color:'#334155', marginBottom:'0.4rem' }}>
                  Search Range: {silenceSearchRange}s
                </label>
                <input type="range" min="0.1" max="2.0" step="0.1" value={silenceSearchRange}
                  onChange={(e) => setSilenceSearchRange(Number(e.target.value))}
                  style={{ width:'100%', accentColor:'#0ea5e9' }} />
                <span style={{ fontSize:'0.75rem', color:'#64748b', marginTop:'0.25rem' }}>How far to look from current boundary</span>
              </div>
              <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'180px' }}>
                <label style={{ fontSize:'0.875rem', fontWeight:600, color:'#334155', marginBottom:'0.4rem' }}>
                  Min Silence Duration: {silenceMinDuration}s
                </label>
                <input type="range" min="0.01" max="0.5" step="0.01" value={silenceMinDuration}
                  onChange={(e) => setSilenceMinDuration(Number(e.target.value))}
                  style={{ width:'100%', accentColor:'#0ea5e9' }} />
                <span style={{ fontSize:'0.75rem', color:'#64748b', marginTop:'0.25rem' }}>Required length of silent section</span>
              </div>
              <button
                onClick={handleAlignToSilence}
                disabled={isAligningToSilence || !isReady}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: (isAligningToSilence || !isReady) ? '#9ca3af' : '#0ea5e9',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 'bold',
                  cursor: (isAligningToSilence || !isReady) ? 'not-allowed' : 'pointer',
                  opacity: (isAligningToSilence || !isReady) ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  whiteSpace: 'nowrap',
                  height: '42px',
                  fontSize: '0.95rem',
                }}
              >
                {isAligningToSilence ? '⏳ Aligning…' : '🎯 Align to Silence'}
              </button>
            </div>
            {alignResult && (
              <div style={S.resultPill}>
                ✅ {alignResult.adjusted} adjusted · {alignResult.skipped} already aligned
              </div>
            )}
          </div>

          {/* Edit Ops */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>Edit Operations</div>
            <div style={S.btnRow}>
              <button style={S.btnMuted} disabled title="Coming soon">✂️ Cut</button>
              <button style={S.btnMuted} disabled title="Coming soon">📋 Paste</button>
              <button style={S.btnMuted} disabled title="Coming soon">🔊 Volume</button>
            </div>
          </div>

          {/* History */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>History</div>
            <div style={S.btnRow}>
              <button style={S.btnMuted} disabled title="Coming soon">↩️ Undo</button>
              <button style={S.btnMuted} disabled title="Coming soon">↪️ Redo</button>
            </div>
          </div>

          {/* Sync */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>Sync</div>
            <button style={S.btnGreen} onClick={fetchDuplicates} title="Re-fetch duplicate regions from server">
              🔄 Sync Regions
            </button>
          </div>

        </div>
      </div>

    </div>
  );
};

/* ─────────────────────────────────────────────────────────────────────── */
/* Style constants                                                         */
/* ─────────────────────────────────────────────────────────────────────── */
const S = {
  root: { display:'flex', flexDirection:'column', gap:'16px', padding:'20px', background:'#f8fafc', minHeight:'100%' },

  /* Header */
  pageHeader: { display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:'12px' },
  pageTitle:  { margin:0, fontSize:'1.4em', fontWeight:700, color:'#1e293b' },
  pageSub:    { margin:'4px 0 0', fontSize:'0.9em', color:'#64748b' },
  badges:     { display:'flex', gap:'8px', flexWrap:'wrap' },
  badge:      { padding:'4px 12px', borderRadius:'20px', fontSize:'0.8em', fontWeight:600 },
  badgeGreen: { background:'#f0fdf4', color:'#166534', border:'1px solid #bbf7d0' },
  badgeRed:   { background:'#fef2f2', color:'#991b1b', border:'1px solid #fecaca' },
  badgeBlue:  { background:'#eff6ff', color:'#1e40af', border:'1px solid #bfdbfe' },

  /* Card */
  card:     { background:'#fff', borderRadius:'12px', border:'1px solid #e2e8f0', padding:'16px 20px', boxShadow:'0 1px 4px rgba(0,0,0,0.06)' },
  cardHead: { display:'flex', alignItems:'center', gap:'10px', marginBottom:'14px', flexWrap:'wrap' },
  cardTitle:{ margin:0, fontSize:'1em', fontWeight:700, color:'#334155' },
  cardMeta: { fontSize:'0.8em', color:'#94a3b8', flex:1 },

  /* Toolbar */
  toolbar:     { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'12px', flexWrap:'wrap', gap:'10px' },
  toolbarLeft: { display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap' },
  toolbarRight:{ display:'flex', alignItems:'center', gap:'16px', flexWrap:'wrap' },
  timeCode:    { fontFamily:'monospace', fontSize:'1.05em', background:'#f1f5f9', padding:'4px 10px', borderRadius:'6px', color:'#334155' },
  checkLabel:  { display:'flex', alignItems:'center', gap:'6px', cursor:'pointer', fontSize:'0.9em', fontWeight:500, userSelect:'none' },
  zoomRow:     { display:'flex', alignItems:'center', gap:'6px', fontSize:'0.9em' },
  slider:      { width:'100px', cursor:'pointer', accentColor:'#3b82f6' },
  zoomLabel:   { fontSize:'0.8em', color:'#6b7280', minWidth:'28px' },

  /* Waveform */
  waveOuter:   { position:'relative', borderRadius:'8px', overflow:'hidden', background:'#f8fafc', border:'1px solid #e2e8f0' },
  loadOverlay: { position:'absolute', inset:0, background:'rgba(248,250,252,0.93)', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', zIndex:10, gap:'10px' },
  spinner:     { width:'34px', height:'34px', border:'4px solid #e2e8f0', borderTopColor:'#3b82f6', borderRadius:'50%', animation:'tabedit-spin 0.8s linear infinite' },

  /* Legend */
  legend:     { display:'flex', gap:'16px', marginTop:'10px', fontSize:'0.82em', color:'#64748b', flexWrap:'wrap', alignItems:'center' },
  legendItem: { display:'flex', alignItems:'center', gap:'5px' },
  swatch:     { display:'inline-block', width:'14px', height:'14px', borderRadius:'3px' },

  /* Transcript */
  transcriptBox: { maxHeight:'180px', overflowY:'auto', lineHeight:1.9, fontSize:'0.92em', padding:'2px 0' },
  seg:           { display:'inline', cursor:'pointer', padding:'1px 3px', borderRadius:'3px', color:'#334155', transition:'background 0.15s' },
  segActive:     { background:'#fef9c3', color:'#92400e', fontWeight:600, outline:'1px solid #fde047' },
  emptyBox:      { color:'#94a3b8', fontSize:'0.9em', textAlign:'center', padding:'20px 0' },

  /* Tools */
  toolsGrid:      { display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(180px, 1fr))', gap:'18px' },
  toolGroup:      { display:'flex', flexDirection:'column', gap:'8px' },
  toolGroupLabel: { fontSize:'0.72em', fontWeight:700, color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.06em' },
  btnRow:         { display:'flex', gap:'6px', flexWrap:'wrap' },
  resultPill:     { fontSize:'0.8em', color:'#059669', background:'#f0fdf4', padding:'4px 8px', borderRadius:'6px', border:'1px solid #bbf7d0' },

  /* Buttons */
  btnBlue:  { background:'#3b82f6', color:'#fff', border:'none', padding:'7px 18px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em' },
  btnAmber: { background:'#f59e0b', color:'#fff', border:'none', padding:'7px 18px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em' },
  btnGhost: { background:'#f1f5f9', color:'#334155', border:'1px solid #e2e8f0', padding:'7px 14px', borderRadius:'8px', cursor:'pointer', fontWeight:500, fontSize:'0.9em' },
  btnIndigo:{ background:'#6366f1', color:'#fff', border:'none', padding:'8px 16px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em', whiteSpace:'nowrap' },
  btnGray:  { background:'#9ca3af', color:'#fff', border:'none', padding:'8px 16px', borderRadius:'8px', cursor:'not-allowed', fontWeight:600, fontSize:'0.9em' },
  btnGreen: { background:'#10b981', color:'#fff', border:'none', padding:'8px 16px', borderRadius:'8px', cursor:'pointer', fontWeight:600, fontSize:'0.9em' },
  btnMuted: { background:'#f1f5f9', color:'#94a3b8', border:'1px solid #e2e8f0', padding:'6px 12px', borderRadius:'7px', cursor:'not-allowed', fontWeight:500, fontSize:'0.85em' },
  btnTiny:  { background:'transparent', color:'#3b82f6', border:'1px solid #bfdbfe', padding:'3px 10px', borderRadius:'6px', cursor:'pointer', fontSize:'0.8em', fontWeight:500 },

  /* Empty */
  emptyState: { display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'300px', color:'#94a3b8' },
};

/* Inject spinner keyframes */
if (typeof document !== 'undefined' && !document.getElementById('tabedit-css')) {
  const s = document.createElement('style');
  s.id = 'tabedit-css';
  s.textContent = '@keyframes tabedit-spin { to { transform: rotate(360deg); } }';
  document.head.appendChild(s);
}

export default TabEdit;
