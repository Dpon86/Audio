import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import { getApiUrl, API_BASE_URL, resolveMediaUrl } from '../../config/api';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js';
import clientAudioAssembly from '../../services/clientAudioAssembly';
import clientAudioStorage from '../../services/clientAudioStorage';
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
    setActiveTab,
    transcriptionData,
    setTranscriptionData,
    pdfEditMarkers,
    sharedDuplicateGroups,
    sharedSelectedDeletions,
    setSharedSelectedDeletions,
  } = useProjectTab();

  /* ─── Assembly state ─────────────────────────────────────────────── */
  const [isAssemblingAudio, setIsAssemblingAudio] = useState(false);
  const [assemblyProgress, setAssemblyProgress] = useState({ current: 0, total: 0, status: '' });
  const [assembledAudioBlob, setAssembledAudioBlob] = useState(null);
  const [assemblyInfo, setAssemblyInfo] = useState(null);

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

  /* ─── Waveform height (user-resizable) ──────────────────────────── */
  const [waveformHeight, setWaveformHeight] = useState(120);
  const waveformHeightRef = useRef(120);
  // Keep ref in sync with state so drag closure always reads latest height
  waveformHeightRef.current = waveformHeight;

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
      height:        waveformHeight,
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

  /* ─── Sync WaveSurfer canvas height when user resizes ─────────── */
  useEffect(() => {
    if (!wavesurfer || !isReady) return;
    wavesurfer.setOptions({ height: waveformHeight });
  }, [waveformHeight, wavesurfer, isReady]);

  /* ─── Resize drag handler ──────────────────────────────────────── */
  const handleResizeMouseDown = useCallback((e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = waveformHeightRef.current;
    const onMove = (ev) => {
      const newH = Math.max(60, Math.min(500, startH + ev.clientY - startY));
      waveformHeightRef.current = newH;
      setWaveformHeight(newH);
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, []);

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
      // Track which segments were adjusted and their new boundaries
      const adjustedBoundaries = new Map(); // segmentId → { start, end }
      regionsMapRef.current.forEach((region) => {
        // Use our own Set rather than region.data to identify deleted regions
        if (!deletedRegionIdsRef.current.has(region.id)) return;
        const s = region.start;
        const e = region.end;
        if (isInSilence(buf, s) && isInSilence(buf, e)) { skipped++; return; }
        const ns = isInSilence(buf, s) ? s : findSilenceCenter(buf, s);
        const ne = isInSilence(buf, e) ? e : findSilenceCenter(buf, e);
        if (ns < ne && ne - ns >= 0.1) {
          region.setOptions({ start: ns, end: ne });
          adjusted++;
          // Store the new boundaries keyed by segment ID
          const meta = regionMetaRef.current.get(region.id);
          if (meta?.segmentId) {
            adjustedBoundaries.set(meta.segmentId, { start: ns, end: ne });
          }
        }
        else { skipped++; }
      });
      // Update the duplicates state with the new boundaries so they persist through re-renders
      if (adjustedBoundaries.size > 0) {
        setDuplicates(prevDuplicates => 
          prevDuplicates.map(group => ({
            ...group,
            occurrences: (group.occurrences || []).map(occ => {
              const adjusted = adjustedBoundaries.get(occ.id);
              if (adjusted) {
                return { ...occ, start_time: adjusted.start, end_time: adjusted.end };
              }
              return occ;
            })
          }))
        );
      }
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
  const segments = rawSegments
    .map(seg => ({
      ...seg,
      start: typeof seg.start     === 'number' ? seg.start     : (typeof seg.start_time === 'number' ? seg.start_time : 0),
      end:   typeof seg.end       === 'number' ? seg.end       : (typeof seg.end_time   === 'number' ? seg.end_time   : 0),
    }))
    .filter(seg => seg.end > seg.start)        // drop zero-width / invalid segments
    .sort((a, b) => a.start - b.start);        // guarantee time order
  const activeSegIdx = segments.findIndex((seg) => currentTime >= seg.start && currentTime < seg.end);
  const totalRegions   = duplicates.reduce((n, g) => n + (g.occurrences?.length || 0), 0);
  const deletedRegions = duplicates.reduce((n, g) => n + (g.occurrences?.filter(o => !o.is_kept).length || 0), 0);
  const keptRegions    = totalRegions - deletedRegions;

  /* ─── Assembly handlers ─────────────────────────────────────────── */
  const handleAssembleAudio = async () => {
    if (sharedSelectedDeletions.length === 0) {
      alert('No segments selected for removal. Go to the "Find Duplicates" tab first to detect and select duplicate segments.');
      return;
    }

    const isClientOnly = selectedAudioFile?.client_only || selectedAudioFile?.client_processed;

    if (!isClientOnly) {
      // Server-side assembly
      const confirmed = window.confirm(
        `Server-Side Assembly\n\n` +
        `This will send your ${sharedSelectedDeletions.length} selected deletions to the server for processing.\n` +
        `Continue?`
      );
      if (!confirmed) return;

      try {
        setIsAssemblingAudio(true);
        setAssemblyProgress({ current: 0, total: 100, status: 'Sending to server...' });
        const confirmed_deletions = sharedSelectedDeletions.map(id => ({ segment_id: id }));
        const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/confirm-deletions/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${token}` },
          body: JSON.stringify({ confirmed_deletions })
        });
        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.error || 'Server assembly failed');
        }
        const result = await response.json();
        const taskId = result.task_id;
        let complete = false;
        let attempts = 0;
        while (!complete && attempts < 720) {
          await new Promise(r => setTimeout(r, 2500));
          const statusRes = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/status/`, { headers: { 'Authorization': `Token ${token}` } });
          if (statusRes.ok) {
            const status = await statusRes.json();
            if (status.progress) setAssemblyProgress({ current: status.progress, total: 100, status: status.message || 'Processing...' });
            if (status.status === 'completed' || status.status === 'success' || status.task_state === 'SUCCESS') {
              complete = true;
              setIsAssemblingAudio(false);
              alert('Server assembly complete! Switching to Results tab.');
              setActiveTab('results');
            } else if (status.status === 'failed' || status.task_state === 'FAILURE') {
              throw new Error(status.error || 'Task failed');
            }
          }
          attempts++;
        }
        if (!complete) {
          setIsAssemblingAudio(false);
          alert('Assembly is still running on the server. Check the Results tab in a few minutes.');
        }
      } catch (error) {
        setIsAssemblingAudio(false);
        alert(`Assembly failed: ${error.message}`);
      }
      return;
    }

    // Client-side assembly
    let originalFile = selectedAudioFile.local_file;
    if (!originalFile && selectedAudioFile.has_local_audio) {
      try {
        const stored = await clientAudioStorage.getFile(selectedAudioFile.id);
        if (stored?.file) originalFile = stored.file;
      } catch (e) {
        console.error('[TabEdit] Failed to load from IndexedDB:', e);
      }
    }
    if (!originalFile) {
      alert('Original audio file not found in browser storage. Please re-upload and transcribe the file.');
      return;
    }

    // Get all segments
    let allSegments = [];
    const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
    const duplicatesStorage = localStorage.getItem(storageKey);
    if (duplicatesStorage) {
      try {
        const parsed = JSON.parse(duplicatesStorage);
        if (parsed.processedSegments?.length > 0) allSegments = parsed.processedSegments;
        else if (parsed.duplicate_groups?.length > 0) {
          const segMap = new Map();
          parsed.duplicate_groups.forEach(g => (g.segments || []).forEach(s => { if (s.id && !segMap.has(s.id)) segMap.set(s.id, s); }));
          allSegments = Array.from(segMap.values()).sort((a, b) => a.start_time - b.start_time);
        }
      } catch (e) { console.error('[TabEdit] Error parsing duplicates storage:', e); }
    }
    if (allSegments.length === 0 && selectedAudioFile.transcription?.all_segments) {
      allSegments = selectedAudioFile.transcription.all_segments;
    }
    if (allSegments.length === 0) {
      alert('No transcription segments found. Please run duplicate detection first.');
      return;
    }

    const confirmed = window.confirm(
      `Assemble audio?\n\nSegments to remove: ${sharedSelectedDeletions.length}\nSegments to keep: ${allSegments.length - sharedSelectedDeletions.length}\n\nThis will process the audio in your browser.\n\nContinue?`
    );
    if (!confirmed) return;

    setIsAssemblingAudio(true);
    setAssemblyProgress({ current: 0, total: 0, status: 'Starting...' });
    try {
      const result = await clientAudioAssembly.assembleAudio(
        originalFile, allSegments, sharedSelectedDeletions,
        (current, total, status) => setAssemblyProgress({ current, total, status })
      );
      setAssembledAudioBlob(result.blob);
      setAssemblyInfo(result.info);
      alert(
        `✅ Assembly Complete!\n\n` +
        `Removed: ${clientAudioAssembly.formatDuration(result.info.removedDuration)}\n` +
        `New Duration: ${clientAudioAssembly.formatDuration(result.info.assembledDuration)}`
      );
    } catch (error) {
      alert(`Assembly failed: ${error.message}`);
    } finally {
      setIsAssemblingAudio(false);
      setAssemblyProgress({ current: 0, total: 0, status: '' });
    }
  };

  const handleDownloadAssembledAudio = () => {
    if (!assembledAudioBlob) { alert('No assembled audio available. Please assemble first.'); return; }
    const url = URL.createObjectURL(assembledAudioBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedAudioFile.filename.replace(/\.[^/.]+$/, '')}_assembled.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

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

      {/* ── Step 1: Align to Silence ────────────────────────────────── */}
      <div style={{ ...S.card, padding: 0, overflow: 'hidden' }}>
        <button
          onClick={() => setShowAlignPanel(v => !v)}
          style={{
            width: '100%', display: 'flex', alignItems: 'flex-start', gap: '12px',
            padding: '16px 20px', background: 'none', border: 'none',
            cursor: 'pointer', textAlign: 'left',
          }}
        >
          <span style={S.stepBadge}>Step 1</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'Arial, sans-serif' }}>
              🎯 Align Regions to Silence
              <span style={{ fontWeight: 400, color: '#64748b', fontSize: '0.88rem' }}>(Optional)</span>
            </div>
            <div style={{ fontSize: '0.82rem', color: '#0369a1', marginTop: '5px', lineHeight: 1.5, fontFamily: 'Arial, sans-serif' }}>
              Snap the boundaries of all DELETE regions to the nearest silence point. This ensures cleaner cuts with no abrupt audio interruptions before assembling.
            </div>
          </div>
          <span style={{ flexShrink: 0, color: '#94a3b8', fontSize: '0.9rem', marginTop: '3px' }}>
            {showAlignPanel ? '▲' : '▼'}
          </span>
        </button>
        {showAlignPanel && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '1.25rem', alignItems: 'flex-end',
            background: '#f0f9ff', padding: '1rem 1.25rem 1.25rem',
            borderTop: '1px solid #bae6fd',
          }}>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem', fontFamily:'Arial,sans-serif' }}>
                Silence Threshold: {silenceThreshold} dB
              </label>
              <input type="range" min="-60" max="-20" value={silenceThreshold}
                onChange={(e) => setSilenceThreshold(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem', fontFamily:'Arial,sans-serif' }}>Lower = stricter silence requirement</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem', fontFamily:'Arial,sans-serif' }}>
                Search Range: {silenceSearchRange}s
              </label>
              <input type="range" min="0.1" max="2.0" step="0.1" value={silenceSearchRange}
                onChange={(e) => setSilenceSearchRange(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem', fontFamily:'Arial,sans-serif' }}>How far to look from current boundary</span>
            </div>
            <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:'160px' }}>
              <label style={{ fontSize:'0.8rem', fontWeight:600, color:'#334155', marginBottom:'0.3rem', fontFamily:'Arial,sans-serif' }}>
                Min Silence Duration: {silenceMinDuration}s
              </label>
              <input type="range" min="0.01" max="0.5" step="0.01" value={silenceMinDuration}
                onChange={(e) => setSilenceMinDuration(Number(e.target.value))}
                style={{ width:'100%', accentColor:'#0ea5e9' }} />
              <span style={{ fontSize:'0.7rem', color:'#64748b', marginTop:'0.2rem', fontFamily:'Arial,sans-serif' }}>Required length of silent section</span>
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
                  whiteSpace: 'nowrap', fontSize: '0.9rem', fontFamily: 'Arial,sans-serif',
                }}
              >
                {isAligningToSilence ? '⏳ Aligning…' : '🎯 Auto-Align to Silence'}
              </button>
              {alignResult && (
                <span style={{ fontSize: '0.78rem', color: '#0369a1', fontWeight: 600, fontFamily: 'Arial,sans-serif' }}>
                  ✅ {alignResult.adjusted} adjusted · {alignResult.skipped} at boundary · {alignResult.total} total
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Step 2: Waveform ─────────────────────────────────────────── */}
      <div style={S.card}>
        <div style={{ display:'flex', alignItems:'center', gap:'10px', marginBottom:'12px' }}>
          <span style={S.stepBadge}>Step 2</span>
          <span style={{ fontSize:'1rem', fontWeight:700, color:'#0f172a', fontFamily:'Arial,sans-serif' }}>🔊 Audio Waveform</span>
        </div>

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
          <div ref={waveformRef} className="wavesurfer-container" style={{ width: '100%' }} />

          {/* ── Transcript overlay: time-aligned text beneath the waveform ── */}
          {segments.length > 0 && isReady && (
            <div
              ref={overlayScrollRef}
              style={{
                overflowX: 'scroll',
                overflowY: 'hidden',
                width: '100%',
                height: `${Math.max(52, 32 + zoom * 3)}px`,
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
                  // Clamp visual width so this segment never overlaps the next one
                  const nextStart = segments[idx + 1]?.start ?? seg.end;
                  const visEnd    = Math.min(seg.end, nextStart);
                  const segWidth  = Math.max(1, (visEnd - seg.start) * pxPerSec);
                  const fontSize  = Math.max(8, Math.min(13, 6 + zoom * 0.7));
                  const isActive  = idx === activeSegIdx;
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
                        top:        '0',
                        overflow:   'hidden',
                        whiteSpace: 'nowrap',
                        textOverflow: 'ellipsis',
                        fontSize:   `${fontSize}px`,
                        fontFamily: 'Arial, sans-serif',
                        lineHeight: 1,
                        display:    'flex',
                        alignItems: 'center',
                        padding:    '0 3px',
                        background: isActive ? 'rgba(254,249,195,0.95)' : 'rgba(248,250,252,0.92)',
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

        {/* Resize handle */}
        <div
          onMouseDown={handleResizeMouseDown}
          title="Drag to resize the waveform"
          style={{
            height: '10px',
            cursor: 'ns-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginTop: '4px',
            userSelect: 'none',
          }}
        >
          <div style={{ width: '48px', height: '4px', background: '#cbd5e1', borderRadius: '2px' }} />
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

      {/* ── Editing Tools ────────────────────────────────────── */}
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

      {/* ── Step 3: Assemble Audio ───────────────────────────────────── */}
      <div style={S.card}>
        <div style={S.cardHead}>
          <span style={S.stepBadge}>Step 3</span>
          <h3 style={S.cardTitle}>🖥️ Assemble Audio</h3>
          <span style={S.cardMeta}>
            {sharedSelectedDeletions.length > 0
              ? `${sharedSelectedDeletions.length} segments selected for removal from Find Duplicates tab`
              : 'Go to "Find Duplicates" tab first to detect and select duplicate segments'}
          </span>
        </div>

        {sharedSelectedDeletions.length === 0 && (
          <div style={{ padding: '1rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', color: '#92400e', fontSize: '0.9rem' }}>
            ⚠️ No duplicate segments selected yet. First go to the <strong>Find Duplicates</strong> tab, run detection, and select which segments to remove. Then come back here to assemble.
          </div>
        )}

        {sharedSelectedDeletions.length > 0 && (
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '0.9rem', color: '#475569' }}>
              <strong style={{ color: '#1e293b' }}>{sharedSelectedDeletions.length}</strong> duplicate segments selected for removal
              {sharedDuplicateGroups.length > 0 && ` across ${sharedDuplicateGroups.length} groups`}
            </div>
            <button
              onClick={handleAssembleAudio}
              disabled={isAssemblingAudio}
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '1rem',
                fontWeight: '600',
                color: 'white',
                background: isAssemblingAudio ? '#f59e0b' : '#22c55e',
                border: 'none',
                borderRadius: '8px',
                cursor: isAssemblingAudio ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              {isAssemblingAudio
                ? <><span>⏳</span> Assembling Audio...</>
                : ((selectedAudioFile?.client_only || selectedAudioFile?.client_processed)
                  ? `🎵 Assemble Audio (Remove ${sharedSelectedDeletions.length} segments)`
                  : `🖥️ Assemble on Server (Remove ${sharedSelectedDeletions.length} segments)`)}
            </button>
          </div>
        )}

        {isAssemblingAudio && assemblyProgress.status && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#fefce8', border: '1px solid #fde68a', borderRadius: '8px' }}>
            <p style={{ margin: '0 0 0.5rem 0', fontWeight: '600', color: '#92400e' }}>{assemblyProgress.status}</p>
            {assemblyProgress.total > 0 && (
              <div style={{ background: '#e2e8f0', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                <div style={{ background: '#f59e0b', height: '100%', width: `${(assemblyProgress.current / assemblyProgress.total) * 100}%`, transition: 'width 0.3s' }} />
              </div>
            )}
          </div>
        )}

        {assembledAudioBlob && assemblyInfo && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <span style={{ color: '#166534', fontWeight: '600' }}>
              ✅ Audio Ready — {clientAudioAssembly.formatDuration(assemblyInfo.assembledDuration)}
            </span>
            <button
              onClick={handleDownloadAssembledAudio}
              style={{ padding: '0.5rem 1rem', background: '#16a34a', color: 'white', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer', fontSize: '0.9rem' }}
            >
              📥 Download Assembled Audio
            </button>
          </div>
        )}
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
  stepBadge:{ padding:'3px 10px', background:'#3b82f6', color:'#fff', borderRadius:'20px', fontSize:'0.78rem', fontWeight:700, flexShrink:0, fontFamily:'Arial,sans-serif' },
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
