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
  const regionsMapRef    = useRef(new Map());
  const deletedRegionIdsRef = useRef(new Set());
  const overlayScrollRef   = useRef(null);
  const wsScrollRef        = useRef(null);
  const isUserScrollingRef = useRef(false);
  const userScrollTimerRef = useRef(null);
  const isPlayingRef       = useRef(false);  // mirror of isPlaying state for RAF closures
  const wavesurferRef      = useRef(null);   // mirror of wavesurfer state for RAF closures
  const zoomRef            = useRef(1);      // mirror of zoom state for RAF closures
  const isSeekingRef       = useRef(false);  // throttle skip-deleted seeks
  const regionMetaRef      = useRef(new Map()); // region.id → { segmentId (DB pk), groupId }

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
  const [showKeptSections, setShowKeptSections]  = useState(true);
  const [showPdfMarkers,   setShowPdfMarkers]    = useState(true);

  /* ─── Data state ─────────────────────────────────────────────────── */
  const [loading,    setLoading]    = useState(false);
  const [duplicates, setDuplicates] = useState([]);

  /* ─── Align-to-Silence state ─────────────────────────────────────── */
  const [isAligningToSilence, setIsAligningToSilence] = useState(false);
  const [alignResult,         setAlignResult]          = useState(null);
  const [silenceThreshold,   setSilenceThreshold]   = useState(-40);
  const [silenceSearchRange, setSilenceSearchRange] = useState(0.6);
  const [silenceMinDuration, setSilenceMinDuration] = useState(0.08);

  /* ─── Save state ─────────────────────────────────────────────────── */
  const [isSaving,    setIsSaving]    = useState(false);
  const [saveResult,  setSaveResult]  = useState(null);

  /* ─── UI toggle state ────────────────────────────────────────────── */
  const [showAlignPanel, setShowAlignPanel] = useState(false);

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

    wavesurferRef.current = ws;
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
    // Remove only duplicate/kept regions — preserve PDF markers so they
    // survive a fetchDuplicates() refresh without needing their own re-run.
    const toRemove = [];
    regionsMapRef.current.forEach((region, id) => {
      if (!region.data?.isPdfMarker) toRemove.push([region, id]);
    });
    toRemove.forEach(([region, id]) => {
      try { region.remove(); } catch (_) {}
      regionsMapRef.current.delete(id);
    });
    deletedRegionIdsRef.current.clear();
    regionMetaRef.current.clear();
    duplicates.forEach((group) => {
      if (!group.occurrences) return;
      group.occurrences.forEach((occ) => {
        const isDeleted = !occ.is_kept;
        // Skip kept sections when their toggle is off
        if (!isDeleted && !showKeptSections) return;
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
            segmentId: occ.id,  // DB primary key (not segment_index)
          },
        });
        regionsMapRef.current.set(region.id, region);
        // Track metadata in our own Map — don't rely on region.data
        regionMetaRef.current.set(region.id, { segmentId: occ.id, groupId: group.group_id, isDeleted });
        if (isDeleted) deletedRegionIdsRef.current.add(region.id);
      });
    });
  }, [wsRegions, duplicates, isReady, showKeptSections]);

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
    if (!pdfEditMarkers || pdfEditMarkers.length === 0 || !showPdfMarkers) return;
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
  }, [wsRegions, isReady, pdfEditMarkers, showPdfMarkers]);

  /* ─── Skip deleted during playback ─────────────────────────────── */
  // Use timeupdate (fires every ~50ms during play) rather than region-in
  // which can miss fast-moving cursors or fire inconsistently.
  useEffect(() => {
    if (!wavesurfer || !isReady) return;
    const handleTimeUpdate = (t) => {
      if (!skipDeleted) return;
      const dur = wavesurfer.getDuration();
      if (!dur) return;
      for (const [, region] of regionsMapRef.current) {
        if (deletedRegionIdsRef.current.has(region.id) && t >= region.start && t < region.end) {
          isSeekingRef.current = true;
          wavesurfer.seekTo(region.end / dur);
          // Release throttle after the seek has had time to propagate
          setTimeout(() => { isSeekingRef.current = false; }, 300);
          break;
        }
      }
    };
    wavesurfer.on('timeupdate', handleTimeUpdate);
    return () => { try { wavesurfer.un('timeupdate', handleTimeUpdate); } catch(e){} };
  }, [wavesurfer, isReady, skipDeleted]);

  /* ─── Locked scrollbar: single scrollbar controls waveform + text ─ */
  // Keep refs in sync with state so RAF closures always read current values
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);

  useEffect(() => {
    if (!isReady) return;

    // WaveSurfer v7 uses Shadow DOM — its scroll container lives inside a shadow root
    // and is invisible to querySelectorAll. Use shadowRoot + part attribute to find it.
    const findScrollEl = () => {
      if (!waveformRef.current) return null;
      // WaveSurfer appends a shadow host div to our container
      const host = waveformRef.current.firstElementChild;
      if (host?.shadowRoot) {
        return (
          host.shadowRoot.querySelector('[part="scroll"]') ||
          host.shadowRoot.querySelector('.scroll') ||
          null
        );
      }
      // Fallback for non-shadow builds
      return (
        Array.from(waveformRef.current.querySelectorAll('div')).find(el => {
          const ov = window.getComputedStyle(el).overflowX;
          return ov === 'auto' || ov === 'scroll';
        }) || waveformRef.current.firstElementChild || null
      );
    };

    // Give WaveSurfer time to render its shadow DOM, then locate the scroll container
    const initTimer = setTimeout(() => {
      wsScrollRef.current = findScrollEl();
    }, 200);

    // When user drags the TEXT STRIP scrollbar:
    //  - push position to WaveSurfer immediately
    //  - mark as user-scrolling so RAF loop keeps pushing (prevents WaveSurfer snap-back)
    const onTextScroll = () => {
      if (!overlayScrollRef.current || !wsScrollRef.current) return;
      wsScrollRef.current.scrollLeft = overlayScrollRef.current.scrollLeft;
      isUserScrollingRef.current = true;
      clearTimeout(userScrollTimerRef.current);
      userScrollTimerRef.current = setTimeout(() => {
        isUserScrollingRef.current = false;
      }, 500);
    };

    let rafId;
    let textScrollAttached = false;

    const syncLoop = () => {
      if (!wsScrollRef.current) wsScrollRef.current = findScrollEl();

      // Lazily attach the text-strip scroll listener once it's in the DOM
      if (!textScrollAttached && overlayScrollRef.current) {
        overlayScrollRef.current.addEventListener('scroll', onTextScroll, { passive: true });
        textScrollAttached = true;
      }

      if (wsScrollRef.current && overlayScrollRef.current) {
        if (isUserScrollingRef.current) {
          // User dragged the TEXT STRIP scrollbar → keep pushing to WaveSurfer every frame
          wsScrollRef.current.scrollLeft = overlayScrollRef.current.scrollLeft;
        } else if (isPlayingRef.current && wavesurferRef.current) {
          // PLAYING: calculate text position from getCurrentTime() directly.
          // This reads from the Web Audio API clock (sub-ms precision, 60fps ready)
          // instead of WaveSurfer's scrollLeft which only updates every ~90ms.
          const t        = wavesurferRef.current.getCurrentTime();
          const pxPerSec = 10 * zoomRef.current;
          const half     = overlayScrollRef.current.clientWidth / 2;
          const target   = Math.max(0, t * pxPerSec - half);
          const current  = overlayScrollRef.current.scrollLeft;
          const diff     = target - current;
          overlayScrollRef.current.scrollLeft =
            Math.abs(diff) > 0.5 ? current + diff * 0.3 : target;
        } else {
          // PAUSED / idle: mirror WaveSurfer's scroll position instantly
          // (covers user scrolling the waveform while paused)
          overlayScrollRef.current.scrollLeft = wsScrollRef.current.scrollLeft;
        }
      }

      rafId = requestAnimationFrame(syncLoop);
    };
    rafId = requestAnimationFrame(syncLoop);

    return () => {
      clearTimeout(initTimer);
      clearTimeout(userScrollTimerRef.current);
      cancelAnimationFrame(rafId);
      if (overlayScrollRef.current) {
        overlayScrollRef.current.removeEventListener('scroll', onTextScroll);
      }
    };
  }, [isReady]);

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
    const deletedCount = deletedRegionIdsRef.current.size;
    if (!wavesurfer || !isReady || deletedCount === 0) {
      alert('No deleted regions found — run duplicate detection in Tab 3 first.');
      return;
    }
    setIsAligningToSilence(true);
    setAlignResult(null);
    try {
      const buf = wavesurfer.getDecodedData();
      if (!buf) throw new Error('Audio buffer not available. Try clicking the waveform first to ensure it is fully loaded.');
      let adjusted = 0, skipped = 0;
      regionsMapRef.current.forEach((region) => {
        // Use our own Set rather than region.data to identify deleted regions
        if (!deletedRegionIdsRef.current.has(region.id)) return;
        const s = region.start;
        const e = region.end;
        if (isInSilence(buf, s) && isInSilence(buf, e)) { skipped++; return; }
        const ns = isInSilence(buf, s) ? s : findSilenceCenter(buf, s);
        const ne = isInSilence(buf, e) ? e : findSilenceCenter(buf, e);
        if (ns < ne && ne - ns >= 0.1) { region.setOptions({ start: ns, end: ne }); adjusted++; }
        else { skipped++; }
      });
      setAlignResult({ adjusted, skipped, total: deletedCount });
    } catch (err) {
      alert(`Align to silence failed: ${err.message}`);
    } finally {
      setIsAligningToSilence(false);
    }
  };

  /* ─── Add a new manually-marked deleted section ─────────────────── */
  const handleAddDeletedSection = async () => {
    if (!wavesurfer || !isReady || !wsRegions) return;
    const t   = wavesurfer.getCurrentTime();
    const dur = wavesurfer.getDuration();
    const end = Math.min(t + 2.0, dur);
    if (end - t < 0.1) {
      alert('Not enough space at current position — seek further back and try again.');
      return;
    }

    // Add the region visually immediately so the user sees instant feedback
    const region = wsRegions.addRegion({
      start: t,
      end,
      color: 'rgba(239,68,68,0.35)',
      drag:   true,
      resize: true,
    });
    regionsMapRef.current.set(region.id, region);
    deletedRegionIdsRef.current.add(region.id);
    regionMetaRef.current.set(region.id, { segmentId: null, groupId: 'manual', isDeleted: true });

    // Persist to backend
    try {
      const url = `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/segments/`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_time: t, end_time: end, text: '[Manually deleted]' }),
      });
      if (res.ok) {
        const data = await res.json();
        // Store the new DB id so Save Timings can PATCH it later
        regionMetaRef.current.set(region.id, {
          segmentId: data.segment.id,
          groupId:   data.segment.duplicate_group_id,
          isDeleted: true,
        });
      } else {
        // Roll back the visual region on server failure
        try { region.remove(); } catch (_) {}
        regionsMapRef.current.delete(region.id);
        deletedRegionIdsRef.current.delete(region.id);
        regionMetaRef.current.delete(region.id);
        alert('Failed to save new deleted section to server.');
      }
    } catch (err) {
      try { region.remove(); } catch (_) {}
      regionsMapRef.current.delete(region.id);
      deletedRegionIdsRef.current.delete(region.id);
      regionMetaRef.current.delete(region.id);
      alert('Network error saving new deleted section.');
    }
  };

  /* ─── Save region timings to backend ────────────────────────────── */
  const handleSaveRegions = async () => {
    if (regionMetaRef.current.size === 0) {
      alert('No regions to save. Load a file and run duplicate detection first.');
      return;
    }
    setIsSaving(true);
    setSaveResult(null);
    let saved = 0, failed = 0;
    const promises = [];
    regionsMapRef.current.forEach((region, regionId) => {
      const meta = regionMetaRef.current.get(regionId);
      if (!meta?.segmentId) return;
      // Read the current region boundaries directly from the WaveSurfer Region
      // object — these are updated in-place when the user drags or when
      // handleAlignToSilence calls region.setOptions().
      const startTime = region.start;
      const endTime   = region.end;
      if (typeof startTime !== 'number' || typeof endTime !== 'number') return;
      const url = `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${meta.segmentId}/`;
      promises.push(
        fetch(url, {
          method: 'PATCH',
          headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ start_time: startTime, end_time: endTime }),
        })
          .then(r => { if (r.ok) saved++; else failed++; })
          .catch(() => failed++)
      );
    });
    await Promise.all(promises);
    setSaveResult({ saved, failed });
    setIsSaving(false);
    // Re-fetch from the server to confirm the save persisted and to ensure the
    // component's state matches the database (critical when the tab remounts).
    if (failed === 0 && saved > 0) {
      await fetchDuplicates();
    }
  };

  /* ─── Skip playhead to the next deleted region ───────────────────── */
  const handleSkipToNextDeleted = () => {
    if (!wavesurfer || !isReady) return;
    const t = wavesurfer.getCurrentTime();
    let nextRegion = null;
    regionsMapRef.current.forEach((region) => {
      if (
        deletedRegionIdsRef.current.has(region.id) &&
        region.start > t + 0.1 &&
        (!nextRegion || region.start < nextRegion.start)
      ) {
        nextRegion = region;
      }
    });
    if (nextRegion) {
      const dur = wavesurfer.getDuration();
      if (dur > 0) {
        wavesurfer.seekTo(nextRegion.start / dur);
        setCurrentTime(nextRegion.start);
      }
    } else {
      alert('No more deleted sections after current position.');
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
            <label style={S.checkLabel}>
              <input type="checkbox" checked={showKeptSections} onChange={(e) => setShowKeptSections(e.target.checked)} style={{ accentColor: '#22c55e' }} />
              <span style={{ color: '#16a34a' }}>🟢 Kept</span>
            </label>
            {pdfEditMarkers?.length > 0 && (
              <label style={S.checkLabel}>
                <input type="checkbox" checked={showPdfMarkers} onChange={(e) => setShowPdfMarkers(e.target.checked)} style={{ accentColor: '#9333ea' }} />
                <span style={{ color: '#7e22ce' }}>🟣 PDF</span>
              </label>
            )}
            <div style={S.zoomRow}>
              🔍
              <input type="range" min="0.5" max="15" step="0.5" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} style={S.slider} />
              <span style={S.zoomLabel}>{zoom}x</span>
            </div>
            {/* Add Deleted Section */}
            <button
              onClick={handleAddDeletedSection}
              disabled={!isReady}
              title="Mark the next 2 seconds from the current playhead position as a deleted section"
              style={{
                padding: '0.45rem 0.9rem',
                background: !isReady ? '#9ca3af' : '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 700,
                cursor: !isReady ? 'not-allowed' : 'pointer',
                opacity: !isReady ? 0.7 : 1,
                fontSize: '0.82rem',
                whiteSpace: 'nowrap',
              }}
            >
              ➕ Add Deleted
            </button>
            {/* Align to Silence toggle */}
            <button
              onClick={() => setShowAlignPanel(v => !v)}
              disabled={!isReady}
              title="Snap deleted region boundaries to nearest silence"
              style={{
                padding: '0.45rem 0.9rem',
                background: !isReady ? '#9ca3af' : (showAlignPanel ? '#0369a1' : '#0ea5e9'),
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontWeight: 700,
                cursor: !isReady ? 'not-allowed' : 'pointer',
                opacity: !isReady ? 0.7 : 1,
                fontSize: '0.82rem',
                whiteSpace: 'nowrap',
              }}
            >
              🎯 Align to Silence
            </button>
          </div>
        </div>

        {/* Align-to-Silence panel — shown when toggled on */}
        {showAlignPanel && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1.25rem',
            alignItems: 'flex-end',
            background: '#f0f9ff',
            padding: '1rem 1.25rem',
            borderBottom: '1px solid #bae6fd',
          }}>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem' }}>
                Threshold: {silenceThreshold} dB
              </label>
              <input type="range" min="-60" max="-20" value={silenceThreshold}
                onChange={(e) => setSilenceThreshold(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem' }}>Lower = stricter</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem' }}>
                Search Range: {silenceSearchRange}s
              </label>
              <input type="range" min="0.1" max="2.0" step="0.1" value={silenceSearchRange}
                onChange={(e) => setSilenceSearchRange(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem' }}>Range from boundary to search</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem' }}>
                Min Silence: {silenceMinDuration}s
              </label>
              <input type="range" min="0.01" max="0.5" step="0.01" value={silenceMinDuration}
                onChange={(e) => setSilenceMinDuration(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem' }}>Min gap to qualify</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem' }}>
              <button
                onClick={handleAlignToSilence}
                disabled={isAligningToSilence || !isReady}
                style={{
                  padding: '0.6rem 1.25rem',
                  background: (isAligningToSilence || !isReady) ? '#9ca3af' : '#0ea5e9',
                  color: 'white', border: 'none', borderRadius: '6px',
                  fontWeight: 'bold', cursor: (isAligningToSilence || !isReady) ? 'not-allowed' : 'pointer',
                  opacity: (isAligningToSilence || !isReady) ? 0.7 : 1,
                  whiteSpace: 'nowrap', fontSize: '0.9rem',
                }}
              >
                {isAligningToSilence ? '⏳ Aligning…' : '🎯 Run Alignment'}
              </button>
              {alignResult && (
                <span style={{ fontSize: '0.78rem', color: '#0369a1', fontWeight: 600 }}>
                  ✅ {alignResult.adjusted} adjusted · {alignResult.skipped} at boundary · {alignResult.total} total
                </span>
              )}
            </div>
          </div>
        )}

        {/* Waveform with loading spinner */}
        <div style={S.waveOuter}>
          {isWaveformLoading && (
            <div style={S.loadOverlay}>
              <div style={S.spinner} />
              <p style={{ margin: 0, color: '#64748b', fontSize: '0.9em' }}>Loading waveform…</p>
            </div>
          )}
          <div ref={timelineRef} style={{ borderBottom: '1px solid #e2e8f0' }} />
          <div ref={waveformRef} className="wavesurfer-container" style={{ width: '100%' }} />

          {/* ── Transcript overlay: time-aligned text beneath the waveform ── */}
          {segments.length > 0 && isReady && (
            <div
              ref={overlayScrollRef}
              style={{
                overflowX: 'scroll',
                overflowY: 'hidden',
                width: '100%',
                height: `${Math.max(30, 18 + zoom * 2)}px`,
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
                }}
              >
                {/* Playhead line extending down from the waveform cursor */}
                {duration > 0 && (
                  <div style={{
                    position: 'absolute',
                    left: `${currentTime * 10 * zoom}px`,
                    top: 0,
                    bottom: 0,
                    width: '2px',
                    background: '#ef4444',
                    pointerEvents: 'none',
                    zIndex: 10,
                    opacity: 0.9,
                  }} />
                )}
                {segments.map((seg, idx) => {
                  const pxPerSec = 10 * zoom;
                  const left     = seg.start * pxPerSec;
                  const segWidth = Math.max(1, (seg.end - seg.start) * pxPerSec);
                  const fontSize = Math.max(8, Math.min(13, 6 + zoom * 0.7));
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
          {pdfEditMarkers?.length > 0 && (
            <span style={S.legendItem}><span style={{ ...S.swatch, background: 'rgba(147,51,234,0.5)' }} /> PDF Marker</span>
          )}
          {isReady && totalRegions === 0 && (
            <span style={{ color: '#f59e0b', fontSize: '0.82em', marginLeft: 'auto' }}>
              ⚠️ No regions found — run duplicate detection in Tab 3 first.
            </span>
          )}
        </div>
      </div>

      {/* ── Editing Tools Card ───────────────────────────────────────── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <h3 style={S.cardTitle}>🛠 Editing Tools</h3>
          <span style={S.cardMeta}>Drag region edges on the waveform above to fine-tune boundaries</span>
        </div>

        <div style={S.toolsGrid}>

          {/* Add Deleted Section */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>Edit Operations</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <button
                onClick={handleAddDeletedSection}
                disabled={!isReady}
                title="Add a new 2-second deleted region starting at the current playhead position"
                style={{
                  padding: '0.6rem 1rem',
                  background: !isReady ? '#9ca3af' : '#ef4444',
                  color: 'white', border: 'none', borderRadius: '6px',
                  fontWeight: 700, cursor: !isReady ? 'not-allowed' : 'pointer',
                  opacity: !isReady ? 0.7 : 1, fontSize: '0.875rem', whiteSpace: 'nowrap',
                }}
              >
                ➕ Add Deleted Section
              </button>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                Adds a 2s red region at playhead. Drag edges to resize.
              </span>
            </div>
          </div>

          {/* Navigation */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>Navigation</div>
            <div style={S.btnRow}>
              <button
                onClick={handleSkipToNextDeleted}
                disabled={!isReady}
                title="Jump playhead to the start of the next deleted region"
                style={{
                  padding: '0.6rem 1rem',
                  background: !isReady ? '#9ca3af' : '#8b5cf6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 600,
                  cursor: !isReady ? 'not-allowed' : 'pointer',
                  opacity: !isReady ? 0.7 : 1,
                  fontSize: '0.875rem',
                  whiteSpace: 'nowrap',
                }}
              >
                ⏭ Next Deleted
              </button>
            </div>
          </div>

          {/* Save */}
          <div style={S.toolGroup}>
            <div style={S.toolGroupLabel}>Save</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                onClick={handleSaveRegions}
                disabled={isSaving || !isReady}
                title="Save all dragged region timings to the database"
                style={{
                  padding: '0.6rem 1.25rem',
                  background: (isSaving || !isReady) ? '#9ca3af' : '#16a34a',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 600,
                  cursor: (isSaving || !isReady) ? 'not-allowed' : 'pointer',
                  opacity: (isSaving || !isReady) ? 0.7 : 1,
                  fontSize: '0.875rem',
                  whiteSpace: 'nowrap',
                }}
              >
                {isSaving ? '⏳ Saving…' : '💾 Save Timings'}
              </button>
              {saveResult && (
                <span style={{ fontSize: '0.875rem', color: saveResult.failed > 0 ? '#dc2626' : '#16a34a', fontWeight: 600 }}>
                  {saveResult.failed === 0
                    ? `✅ ${saveResult.saved} saved`
                    : `✅ ${saveResult.saved} saved · ❌ ${saveResult.failed} failed`}
                </span>
              )}
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
