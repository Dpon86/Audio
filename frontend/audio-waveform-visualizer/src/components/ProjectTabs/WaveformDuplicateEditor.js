import React, { useRef, useState, useEffect } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import './WaveformDuplicateEditor.css';

/**
 * Interactive waveform editor for duplicate segment visualization and editing
 * 
 * Features:
 * - Full audio waveform visualization with zoom controls
 * - Color-coded regions (red = delete, green = keep)
 * - Draggable region boundaries for precise editing
 * - Two-way sync with duplicate groups list
 * - Real-time playback with visual cursor
 * 
 * @param {Object} props
 * @param {string} props.audioFile - URL of audio file to visualize
 * @param {Array} props.duplicateGroups - Array of duplicate groups with segments
 * @param {string|null} props.selectedGroupId - Currently selected group ID for highlighting
 * @param {Function} props.onRegionUpdate - Callback when region boundary is dragged: (groupId, segmentId, newStartTime, newEndTime)
 * @param {Function} props.onGroupSelect - Callback when region is clicked: (groupId)
 * @param {Function} props.onRefresh - Callback to refresh duplicate groups from backend
 */
const WaveformDuplicateEditor = ({ 
  audioFile, 
  duplicateGroups, 
  selectedGroupId, 
  onRegionUpdate, 
  onGroupSelect,
  onRefresh
}) => {
  // WaveSurfer instances
  const [wavesurfer, setWavesurfer] = useState(null);
  const [regionsPlugin, setRegionsPlugin] = useState(null);
  
  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  
  // Zoom state (pixels per second)
  const [zoomLevel, setZoomLevel] = useState(10);
  
  // Loading state
  const [isLoading, setIsLoading] = useState(true);
  
  // Silence detection state
  const [silenceThreshold, setSilenceThreshold] = useState(-40); // dB
  const [silenceSearchRange, setSilenceSearchRange] = useState(0.6); // seconds
  const [silenceMinDuration, setSilenceMinDuration] = useState(0.08); // seconds
  const [isAligningToSilence, setIsAligningToSilence] = useState(false);
  
  // Ref for waveform container
  const waveformRef = useRef(null);
  
  // Track regions we create to avoid iterating over WaveSurfer's internal regions
  const createdRegionsRef = useRef(new Map());
  
  // Flag to prevent triggering updates when we're programmatically updating regions
  const isProgrammaticUpdateRef = useRef(false);

  // Debug: Log component mount and props
  useEffect(() => {
    console.log('🎵 WaveformDuplicateEditor mounted');
    console.log('Props:', {
      audioFile,
      duplicateGroupsCount: duplicateGroups?.length,
      selectedGroupId
    });
  }, []);

  // Initialize WaveSurfer with Regions plugin
  useEffect(() => {
    if (!waveformRef.current || !audioFile) {
      return;
    }

    let ws = null;
    let regions = null;
    let mounted = true;

    const initWavesurfer = async () => {
      try {
        setIsLoading(true);

        // Create regions plugin instance
        regions = RegionsPlugin.create();

        // Create WaveSurfer instance
        ws = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: '#4a90e2',
          progressColor: '#2563eb',
          cursorColor: '#1e40af',
          barWidth: 2,
          barRadius: 3,
          cursorWidth: 2,
          height: 200,
          barGap: 2,
          responsive: true,
          normalize: true,
          plugins: [regions],
        });

        // Set up event listeners BEFORE loading
        // Event: Audio is ready to play
        ws.on('ready', () => {
          if (mounted) {
            setDuration(ws.getDuration());
            setIsLoading(false);
            console.log('Waveform loaded successfully, duration:', ws.getDuration());
          }
        });

        // Event: Playback started
        ws.on('play', () => {
          if (mounted) setIsPlaying(true);
        });

        // Event: Playback paused
        ws.on('pause', () => {
          if (mounted) setIsPlaying(false);
        });

        // Event: Playback finished
        ws.on('finish', () => {
          if (mounted) setIsPlaying(false);
        });

        // Event: Playback position updated
        ws.on('audioprocess', (time) => {
          if (mounted) setCurrentTime(time);
        });

        // Event: User seeks to new position
        ws.on('seek', () => {
          if (mounted) setCurrentTime(ws.getCurrentTime());
        });
        
        // Handle load errors
        ws.on('error', (error) => {
          console.error('WaveSurfer error:', error);
          if (mounted) {
            setIsLoading(false);
          }
        });

        // Load audio file (after event listeners are set up)
        const audioUrl = `http://localhost:8000${audioFile}`;
        console.log('Loading audio from:', audioUrl);
        
        try {
          await ws.load(audioUrl);
        } catch (error) {
          // Only log if not an abort error (expected during cleanup)
          if (error.name !== 'AbortError') {
            console.error('Failed to load audio:', error);
          }
          if (mounted) setIsLoading(false);
          return;
        }

        // Store instances in state
        if (mounted) {
          setWavesurfer(ws);
          setRegionsPlugin(regions);
        }
      } catch (error) {
        // Handle any initialization errors
        if (error.name !== 'AbortError') {
          console.error('Error initializing WaveSurfer:', error);
        }
        if (mounted) setIsLoading(false);
      }
    };

    // Initialize the waveform
    initWavesurfer().catch((error) => {
      // Catch any unhandled errors from initialization
      if (error.name !== 'AbortError') {
        console.error('WaveSurfer initialization error:', error);
      }
      if (mounted) setIsLoading(false);
    });

    // Cleanup on unmount
    return () => {
      mounted = false;
      if (ws) {
        try {
          ws.pause();
          ws.destroy();
        } catch (error) {
          // Suppress cleanup errors (expected in React Strict Mode)
          console.debug('WaveSurfer cleanup:', error.message);
        }
      }
    };
  }, [audioFile]);

  // Apply zoom level to waveform
  useEffect(() => {
    if (wavesurfer) {
      wavesurfer.zoom(zoomLevel);
    }
  }, [zoomLevel, wavesurfer]);

  // Create/update color-coded regions from duplicate groups
  useEffect(() => {
    if (!regionsPlugin || !duplicateGroups || duplicateGroups.length === 0) {
      return;
    }

    console.log('Syncing regions with', duplicateGroups.length, 'duplicate groups');

    // Build a map of what should exist
    const expectedRegions = new Map();
    let deleteCount = 0;
    let keepCount = 0;
    
    duplicateGroups.forEach((group, groupIndex) => {
      const segments = group.segments || [];

      segments.forEach((segment, segIndex) => {
        // Validate required fields
        if (!group.group_id || !segment.id || segment.start_time == null || segment.end_time == null) {
          return;
        }

        const isDelete = segment.is_duplicate === true;
        const isKeep = segment.is_kept === true;
        
        if (isDelete) deleteCount++;
        if (isKeep) keepCount++;

       // Determine color based on deletion status
        const baseColor = isDelete 
          ? 'rgba(239, 68, 68, 0.15)'  // Red for DELETE
          : 'rgba(34, 197, 94, 0.15)';  // Green for KEEP

        const regionId = `${group.group_id}-${segment.id}`;
        
        expectedRegions.set(regionId, {
          id: regionId,
          groupId: group.group_id,
          segmentId: segment.id,
          groupIndex,
          start: segment.start_time,
          end: segment.end_time,
          color: baseColor,
          isDelete,
          isKeep,
          occurrenceNumber: segment.occurrence_number || (segIndex + 1),
          content: `Group ${duplicateGroups.length - groupIndex} - ${isDelete ? 'DELETE' : 'KEEP'}`
        });
      });
    });

    // Update existing regions or create new ones
    let created = 0;
    let updated = 0;
    
    expectedRegions.forEach((regionData, regionId) => {
      const existingRegion = createdRegionsRef.current.get(regionId);
      
      if (existingRegion) {
        // Update existing region if times changed
        const timesChanged = 
          Math.abs(existingRegion.start - regionData.start) > 0.001 ||
          Math.abs(existingRegion.end - regionData.end) > 0.001;
          
        if (timesChanged) {
          console.log(`Updating region ${regionId}: ${existingRegion.start.toFixed(2)}-${existingRegion.end.toFixed(2)} → ${regionData.start.toFixed(2)}-${regionData.end.toFixed(2)}`);
          
          // Set flag to prevent region-update-end event from firing
          isProgrammaticUpdateRef.current = true;
          
          try {
            existingRegion.setOptions({
              start: regionData.start,
              end: regionData.end
            });
            updated++;
          } finally {
            // Reset flag immediately after update
            // Use a microtask to ensure this runs after any synchronous event handlers
            Promise.resolve().then(() => {
              isProgrammaticUpdateRef.current = false;
            });
          }
        }
      } else {
        // Create new region
        const region = regionsPlugin.addRegion({
          id: regionId,
          start: regionData.start,
          end: regionData.end,
          color: regionData.color,
          drag: true,
          resize: true,
          content: regionData.content
        });
        
        // Manually attach custom data (WaveSurfer.js 7.x workaround)
        region.data = {
          groupId: regionData.groupId,
          segmentId: regionData.segmentId,
          isDelete: regionData.isDelete,
          isKeep: regionData.isKeep,
          occurrenceNumber: regionData.occurrenceNumber,
        };
        
        createdRegionsRef.current.set(regionId, region);
        created++;
      }
    });

    // Remove regions that shouldn't exist anymore
    const toRemove = [];
    createdRegionsRef.current.forEach((region, regionId) => {
      if (!expectedRegions.has(regionId)) {
        toRemove.push(regionId);
      }
    });
    
    toRemove.forEach(regionId => {
      const region = createdRegionsRef.current.get(regionId);
      if (region) {
        region.remove();
        createdRegionsRef.current.delete(regionId);
      }
    });

    if (created > 0 || updated > 0 || toRemove.length > 0) {
      console.log(`Regions: ${created} created, ${updated} updated, ${toRemove.length} removed (${createdRegionsRef.current.size} total: ${deleteCount} DELETE, ${keepCount} KEEP)`);
    }
  }, [regionsPlugin, duplicateGroups]);

  // Handle region click - notify parent to select group
  useEffect(() => {
    if (!regionsPlugin) return;

    const handleRegionClick = (region) => {
      // Safety check: ensure region.data exists
      if (!region.data) {
        console.warn('Region clicked but missing data:', region);
        return;
      }
      
      const { groupId } = region.data;
      console.log('Region clicked:', groupId);
      if (onGroupSelect) {
        onGroupSelect(groupId);
      }
    };

    regionsPlugin.on('region-clicked', handleRegionClick);

    return () => {
      regionsPlugin.un('region-clicked', handleRegionClick);
    };
  }, [regionsPlugin, onGroupSelect]);

  // Handle region boundary updates (drag/resize)
  useEffect(() => {
    if (!regionsPlugin || !duration) return;

    const handleRegionUpdate = (region) => {
      console.log(`🖱️ region-update-end event fired (programmatic=${isProgrammaticUpdateRef.current})`);
      console.log(`   Region details:`, {
        id: region.id,
        start: region.start?.toFixed(2),
        end: region.end?.toFixed(2),
        hasData: !!region.data,
        data: region.data
      });
      
      // Ignore programmatic updates (from sync useEffect)
      if (isProgrammaticUpdateRef.current) {
        console.log('   ⏭️ Ignoring programmatic update');
        return;
      }
      
      // Safety check: ensure region.data exists
      if (!region.data) {
        console.warn('   ❌ Region updated but missing data:', region);
        return;
      }
      
      const { groupId, segmentId } = region.data;
      const newStartTime = region.start;
      const newEndTime = region.end;

      // Validate minimum duration (0.1 seconds)
      if (newEndTime - newStartTime < 0.1) {
        console.warn('   ❌ Region too short (minimum 0.1s), reverting');
        return;
      }

      // Validate boundaries (no negative times, no exceeding duration)
      if (newStartTime < 0 || newEndTime > duration) {
        console.warn('   ❌ Region out of bounds, reverting');
        return;
      }

      console.log(`   ✅ Manual drag detected: ${groupId} - ${segmentId} -> ${newStartTime.toFixed(2)}s - ${newEndTime.toFixed(2)}s`);
      console.log(`   📤 Calling onRegionUpdate callback...`);

      // Notify parent component (this is async, don't await it here)
      if (onRegionUpdate) {
        try {
          onRegionUpdate(groupId, segmentId, newStartTime, newEndTime);
        } catch (error) {
          console.error('   ❌ Error in onRegionUpdate callback:', error);
        }
      } else {
        console.warn('   ⚠️ onRegionUpdate callback is missing!');
      }
    };
    
    // Log ALL events to see what's actually firing
    const logAllEvents = (eventName) => (region) => {
      console.log(`🎯 RegionsPlugin event: ${eventName}`, region?.id || region);
    };
    
    // Listen to various possible event names
    const possibleEvents = [
      'region-clicked',
      'region-updated',
      'region-update-end',
      'region-in',
      'region-out',
      'region-created',
      'region-removed'
    ];
    
    possibleEvents.forEach(eventName => {
      regionsPlugin.on(eventName, logAllEvents(eventName));
    });

    regionsPlugin.on('region-update-end', handleRegionUpdate);
    regionsPlugin.on('region-updated', handleRegionUpdate);

    return () => {
      regionsPlugin.un('region-update-end', handleRegionUpdate);
      regionsPlugin.un('region-updated', handleRegionUpdate);
      possibleEvents.forEach(eventName => {
        regionsPlugin.un(eventName, logAllEvents(eventName));
      });
    };
  }, [regionsPlugin, duration, onRegionUpdate]);

  // Highlight selected region and scroll to it
  useEffect(() => {
    if (!regionsPlugin || !selectedGroupId || createdRegionsRef.current.size === 0) return;

    // Find the earliest region in the selected group (to seek to)
    let earliestSelectedRegion = null;

    // Only iterate through regions we created
    createdRegionsRef.current.forEach((region, regionId) => {
      // Safety check: ensure region and region.data exists
      if (!region || !region.data) {
        return; // Silently skip without spamming console
      }

      const isSelected = region.data.groupId === selectedGroupId;

      // Update region color based on selection
      const baseColor = region.data.isDelete
        ? (isSelected ? 'rgba(239, 68, 68, 0.5)' : 'rgba(239, 68, 68, 0.15)')
        : (isSelected ? 'rgba(34, 197, 94, 0.5)' : 'rgba(34, 197, 94, 0.15)');

      try {
        region.setOptions({ color: baseColor });

        // Track the earliest region in the selected group
        if (isSelected) {
          if (!earliestSelectedRegion || region.start < earliestSelectedRegion.start) {
            earliestSelectedRegion = region;
          }
        }
      } catch (error) {
        // Region might have been destroyed, ignore
      }
    });

    // After updating all region colors, seek to the earliest region in the selected group
    if (earliestSelectedRegion && wavesurfer && duration) {
      const seekPosition = earliestSelectedRegion.start / duration;
      wavesurfer.seekTo(seekPosition);
      setCurrentTime(earliestSelectedRegion.start);
      console.log(`Seeked to group ${selectedGroupId}: ${earliestSelectedRegion.start.toFixed(2)}s`);
    }
  }, [selectedGroupId, regionsPlugin, wavesurfer, duration]);

  // Playback controls
  const handlePlayPause = () => {
    if (wavesurfer) {
      wavesurfer.playPause();
    }
  };

  const handleStop = () => {
    if (wavesurfer) {
      wavesurfer.stop();
      setIsPlaying(false);
      setCurrentTime(0);
    }
  };

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 5, 100));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 5, 1));
  };

  /**
   * Calculate RMS (Root Mean Square) amplitude for a section of audio
   * Returns value in dB
   */
  const calculateRMS = (audioBuffer, startSample, endSample) => {
    const channelData = audioBuffer.getChannelData(0); // Use first channel
    let sum = 0;
    let count = 0;
    
    for (let i = startSample; i < endSample && i < channelData.length; i++) {
      sum += channelData[i] * channelData[i];
      count++;
    }
    
    if (count === 0) return -100; // Very quiet
    
    const rms = Math.sqrt(sum / count);
    const dB = 20 * Math.log10(rms);
    return dB;
  };

  /**
   * Check if a specific time position is already in a silent section
   * Returns true if the position is silent, false otherwise
   */
  const isInSilence = (audioBuffer, time) => {
    const sampleRate = audioBuffer.sampleRate;
    const checkDuration = 0.05; // Check 50ms window around the point
    const checkSamples = Math.floor(checkDuration * sampleRate);
    const centerSample = Math.floor(time * sampleRate);
    
    const startSample = Math.max(0, centerSample - checkSamples / 2);
    const endSample = Math.min(audioBuffer.length, centerSample + checkSamples / 2);
    
    const rms = calculateRMS(audioBuffer, startSample, endSample);
    return rms < silenceThreshold;
  };

  /**
   * Find the center of a silent section near a target time
   * Searches within ±searchRange seconds of targetTime
   * Returns the time at the center of the silent section, or targetTime if no silence found
   */
  const findSilenceCenter = (audioBuffer, targetTime, searchRange, minSilenceDurationSec) => {
    const sampleRate = audioBuffer.sampleRate;
    const targetSample = Math.floor(targetTime * sampleRate);
    const searchSamples = Math.floor(searchRange * sampleRate);
    const minSilenceSamples = Math.floor(minSilenceDurationSec * sampleRate);
    
    const startSearch = Math.max(0, targetSample - searchSamples);
    const endSearch = Math.min(audioBuffer.length, targetSample + searchSamples);
    
    // Scan for silent sections
    const windowSize = Math.floor(0.02 * sampleRate); // 20ms windows
    let silentSections = [];
    let currentSilentStart = null;
    
    for (let i = startSearch; i < endSearch; i += windowSize) {
      const rms = calculateRMS(audioBuffer, i, i + windowSize);
      const isSilent = rms < silenceThreshold;
      
      if (isSilent && currentSilentStart === null) {
        // Start of silent section
        currentSilentStart = i;
      } else if (!isSilent && currentSilentStart !== null) {
        // End of silent section
        const silentLength = i - currentSilentStart;
        if (silentLength >= minSilenceSamples) {
          silentSections.push({
            start: currentSilentStart / sampleRate,
            end: i / sampleRate,
            center: (currentSilentStart + i) / 2 / sampleRate
          });
        }
        currentSilentStart = null;
      }
    }
    
    // If still in silence at end of search
    if (currentSilentStart !== null) {
      const silentLength = endSearch - currentSilentStart;
      if (silentLength >= minSilenceSamples) {
        silentSections.push({
          start: currentSilentStart / sampleRate,
          end: endSearch / sampleRate,
          center: (currentSilentStart + endSearch) / 2 / sampleRate
        });
      }
    }
    
    // Find closest silent section to target
    if (silentSections.length === 0) {
      console.log(`No silence found near ${targetTime.toFixed(2)}s`);
      return targetTime;
    }
    
    // Return center of closest silent section
    const closest = silentSections.reduce((prev, curr) => {
      const prevDist = Math.abs(prev.center - targetTime);
      const currDist = Math.abs(curr.center - targetTime);
      return currDist < prevDist ? curr : prev;
    });
    
    console.log(`Found silence at ${closest.center.toFixed(2)}s (was ${targetTime.toFixed(2)}s)`);
    return closest.center;
  };

  /**
   * Align all DELETE regions to silent sections
   */
  const handleAlignToSilence = async () => {
    if (!wavesurfer || !regionsPlugin || createdRegionsRef.current.size === 0) {
      console.warn('Cannot align: WaveSurfer not ready');
      return;
    }
    
    setIsAligningToSilence(true);
    
    try {
      const audioBuffer = wavesurfer.getDecodedData();
      if (!audioBuffer) {
        throw new Error('Audio buffer not available');
      }
      
      console.log(`🔇 Starting silence alignment with threshold: ${silenceThreshold}dB`);
      console.log(`🔎 Silence search range: ${silenceSearchRange}s, min silence: ${(silenceMinDuration * 1000).toFixed(0)}ms`);
      console.log(`📊 Processing DELETE regions (KEEP regions will be skipped)`);
      
      const updates = [];
      let skippedCount = 0;
      let processedCount = 0;
      let keepRegions = 0;
      
      // Process ALL DELETE regions (not just selected ones)
      createdRegionsRef.current.forEach((region, regionId) => {
        if (!region || !region.data) {
          return; // Skip if no data attached
        }
        
        // Skip KEEP regions (process only DELETE regions)
        if (!region.data.isDelete) {
          keepRegions++;
          return;
        }
        
        processedCount++;
        const originalStart = region.start;
        const originalEnd = region.end;
        
        // Check if boundaries are already in silence
        const startAlreadySilent = isInSilence(audioBuffer, originalStart);
        const endAlreadySilent = isInSilence(audioBuffer, originalEnd);
        
        if (startAlreadySilent && endAlreadySilent) {
          // Both boundaries already in silence, no need to adjust
          console.log(`✓ Region ${regionId} already in silence: ${originalStart.toFixed(2)}-${originalEnd.toFixed(2)}s`);
          skippedCount++;
          return;
        }
        
        // Find silent sections for boundaries that need adjustment
        const newStart = startAlreadySilent 
          ? originalStart 
          : findSilenceCenter(audioBuffer, originalStart, silenceSearchRange, silenceMinDuration);
        const newEnd = endAlreadySilent 
          ? originalEnd 
          : findSilenceCenter(audioBuffer, originalEnd, silenceSearchRange, silenceMinDuration);
        
        // Check if anything actually changed
        const startChanged = Math.abs(newStart - originalStart) > 0.01; // 10ms threshold
        const endChanged = Math.abs(newEnd - originalEnd) > 0.01;
        
        if (!startChanged && !endChanged) {
          console.log(`✓ Region ${regionId} needs no adjustment: ${originalStart.toFixed(2)}-${originalEnd.toFixed(2)}s`);
          skippedCount++;
          return;
        }
        
        // Ensure new boundaries are valid
        if (newStart < newEnd && newEnd - newStart >= 0.1) {
          // Update region visually
          region.setOptions({
            start: newStart,
            end: newEnd
          });
          
          // Track for backend update
          updates.push({
            groupId: region.data.groupId,
            segmentId: region.data.segmentId,
            oldStart: originalStart,
            oldEnd: originalEnd,
            newStart: newStart,
            newEnd: newEnd
          });
          
          const changeDescription = [];
          if (startChanged) changeDescription.push(`start: ${originalStart.toFixed(2)}→${newStart.toFixed(2)}s`);
          if (endChanged) changeDescription.push(`end: ${originalEnd.toFixed(2)}→${newEnd.toFixed(2)}s`);
          console.log(`✏️ Adjusted region ${regionId}: ${changeDescription.join(', ')}`);
        }
      });
      
      console.log(`📊 Results: ${processedCount} DELETE regions processed, ${updates.length} adjusted, ${skippedCount} already aligned, ${keepRegions} KEEP regions skipped`);
      
      // Update backend for each adjusted region
      for (const update of updates) {
        if (onRegionUpdate) {
          await onRegionUpdate(
            update.groupId,
            update.segmentId,
            update.newStart,
            update.newEnd
          );
        }
      }
      
      // Show detailed results
      const message = updates.length > 0
        ? `✅ Alignment Complete!\n\n` +
          `• ${processedCount} DELETE regions processed\n` +
          `• ${updates.length} regions adjusted to silence\n` +
          `• ${skippedCount} regions already aligned (no change needed)`
        : `✅ All ${processedCount} DELETE regions are already aligned to silence!\n\nNo adjustments needed.`;
      
      alert(message);
      
    } catch (error) {
      console.error('Error aligning to silence:', error);
      alert(`Error aligning to silence: ${error.message}`);
    } finally {
      setIsAligningToSilence(false);
    }
  };

  // Format time as MM:SS
  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="waveform-editor-container">
      {/* Header */}
      <div className="waveform-editor-header">
        <h4 className="waveform-editor-title">🎵 Interactive Waveform Editor</h4>
        
        {/* Zoom Controls */}
        <div className="waveform-zoom-controls">
          <button 
            onClick={handleZoomOut} 
            disabled={zoomLevel <= 1}
            className="zoom-btn"
            title="Zoom out"
          >
            🔍-
          </button>
          <input
            type="range"
            min="1"
            max="100"
            value={zoomLevel}
            onChange={(e) => setZoomLevel(Number(e.target.value))}
            className="zoom-slider"
            title="Adjust zoom level"
          />
          <span className="zoom-level">{zoomLevel}x</span>
          <button 
            onClick={handleZoomIn} 
            disabled={zoomLevel >= 100}
            className="zoom-btn"
            title="Zoom in"
          >
            🔍+
          </button>
        </div>
      </div>

      {/* Waveform Container */}
      <div className="waveform-wrapper">
        {isLoading && (
          <div className="waveform-loading">
            <div className="loading-spinner"></div>
            <p>Loading waveform...</p>
          </div>
        )}
        <div ref={waveformRef} className="waveform-container"></div>
      </div>

      {/* Playback Controls & Time Display */}
      <div className="waveform-playback-controls">
        <button 
          onClick={handlePlayPause} 
          className="waveform-control-btn play-btn"
          disabled={!wavesurfer || isLoading}
        >
          {isPlaying ? '⏸️ Pause' : '▶️ Play'}
        </button>
        <button 
          onClick={handleStop} 
          className="waveform-control-btn stop-btn"
          disabled={!wavesurfer || isLoading}
        >
          ⏹️ Stop
        </button>
        
        <button 
          onClick={() => {
            if (onRefresh) {
              console.log('🔄 Refreshing duplicate groups from backend...');
              onRefresh();
            }
          }}
          className="waveform-control-btn refresh-btn"
          disabled={!onRefresh}
          title="Reload list from database (use after manually adjusting regions)"
        >
          🔄 Refresh List
        </button>
        
        <button 
          onClick={handleAlignToSilence}
          className="waveform-control-btn align-btn"
          disabled={!wavesurfer || isLoading || isAligningToSilence}
          title={`Align all DELETE regions to silence (threshold: ${silenceThreshold}dB)`}
        >
          {isAligningToSilence ? '⏳ Aligning...' : '🎯 Align to Silence'}
        </button>
        
        <div className="silence-threshold-compact">
          <label title="Silence detection threshold">
            {silenceThreshold}dB
          </label>
          <input
            type="range"
            min="-60"
            max="-20"
            value={silenceThreshold}
            onChange={(e) => setSilenceThreshold(Number(e.target.value))}
            className="threshold-slider-compact"
            title="Adjust silence detection sensitivity"
          />
        </div>

        <div className="silence-threshold-compact">
          <label title="Search range around boundaries">
            {silenceSearchRange.toFixed(2)}s
          </label>
          <input
            type="range"
            min="0.2"
            max="2.0"
            step="0.05"
            value={silenceSearchRange}
            onChange={(e) => setSilenceSearchRange(Number(e.target.value))}
            className="threshold-slider-compact"
            title="Adjust silence search range"
          />
        </div>

        <div className="silence-threshold-compact">
          <label title="Minimum silence duration">
            {(silenceMinDuration * 1000).toFixed(0)}ms
          </label>
          <input
            type="range"
            min="0.04"
            max="0.3"
            step="0.01"
            value={silenceMinDuration}
            onChange={(e) => setSilenceMinDuration(Number(e.target.value))}
            className="threshold-slider-compact"
            title="Adjust minimum silence duration"
          />
        </div>

        <div className="waveform-time-display">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
      </div>

      {/* Legend */}
      <div className="waveform-legend">
        <div className="legend-item">
          <div className="legend-color delete"></div>
          <span>Delete (first occurrences)</span>
        </div>
        <div className="legend-item">
          <div className="legend-color keep"></div>
          <span>Keep (last occurrence)</span>
        </div>
        <div className="legend-help">
          💡 Tip: Click a region to select it, drag edges to adjust boundaries
        </div>
      </div>
    </div>
  );
};

export default WaveformDuplicateEditor;
