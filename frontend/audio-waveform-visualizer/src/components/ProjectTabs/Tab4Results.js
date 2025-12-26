import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import WaveSurfer from 'wavesurfer.js';
import './Tab4Results.css';

/**
 * Tab 4: Deletion Review and Results
 * Review confirmed deletions, process them, and view results with audio playback
 */
const Tab4Results = () => {
  const { token } = useAuth();
  const { 
    projectId,
    selectedAudioFile, 
    audioFiles, 
    selectAudioFile, 
    pendingDeletions,
    setPendingDeletions,
    processingDeletion, 
    setProcessingDeletion,
    updateAudioFile 
  } = useProjectTab();
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [wavesurfer, setWavesurfer] = useState(null);
  const [processing, setProcessing] = useState(false);
  const waveformRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const autoProcessedRef = useRef(false);

  // Get processed files (status === 'processed')
  const processedFiles = audioFiles.filter(f => f.status === 'processed' && f.processed_audio);

  // Handle completion of processing task
  const handleProcessingComplete = useCallback(async (taskId, audioFileInfo) => {
    try {
      // Update the audio file with processed data
      const fileResponse = await fetch(
        `http://localhost:8000/api/projects/${audioFileInfo.project}/files/${audioFileInfo.id}/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      if (fileResponse.ok) {
        const responseData = await fileResponse.json();
        // Extract the audio_file from the response wrapper
        const updatedFile = responseData.audio_file || responseData;
        
        console.log('Updated file data:', updatedFile);
        console.log('Original duration:', updatedFile.duration_seconds);
        console.log('Processed duration:', updatedFile.processed_duration_seconds);
        
        updateAudioFile(updatedFile);
        selectAudioFile(updatedFile);
      }
      
      // Clear processing state
      setProcessingDeletion(null);
    } catch (error) {
      console.error('Error fetching updated file:', error);
    }
  }, [token, updateAudioFile, selectAudioFile, setProcessingDeletion]);

  // Process deletions (called when user confirms on this tab OR auto-triggered)
  const handleConfirmDeletion = useCallback(async () => {
    if (!pendingDeletions || !pendingDeletions.confirmedDeletions) {
      console.error('No pending deletions to process');
      return;
    }

    setProcessing(true);

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${pendingDeletions.audioFile.id}/confirm-deletions/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            confirmed_deletions: pendingDeletions.confirmedDeletions
          })
        }
      );

      if (response.ok) {
        const data = await response.json();

        // Set processing state with file info and task ID
        setProcessingDeletion({
          audioFile: pendingDeletions.audioFile,
          taskId: data.task_id,
          deletionCount: pendingDeletions.deletionCount,
          startTime: Date.now()
        });

        // Clear pending deletions since we've started processing
        setPendingDeletions(null);
      } else {
        const error = await response.json();
        alert(error.error || 'Failed to process deletions');
        setProcessing(false);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
      setProcessing(false);
    }
  }, [pendingDeletions, projectId, token, setProcessingDeletion, setPendingDeletions]);

  // Auto-process deletions when pendingDeletions are set (user clicked Review Deletions)
  // DISABLED: Let user manually trigger processing instead of auto-processing
  /*
  useEffect(() => {
    console.log('Tab4Results useEffect - pendingDeletions:', !!pendingDeletions, 'processingDeletion:', !!processingDeletion, 'autoProcessedRef:', autoProcessedRef.current);
    
    if (pendingDeletions && !processingDeletion && !autoProcessedRef.current) {
      console.log('Auto-triggering deletion processing...');
      autoProcessedRef.current = true;
      
      // Automatically start processing after a brief moment
      const timer = setTimeout(() => {
        console.log('Timeout fired, calling handleConfirmDeletion');
        handleConfirmDeletion();
      }, 500);
      
      return () => {
        console.log('Cleaning up auto-process timer');
        clearTimeout(timer);
      };
    }
    
    // Reset ref when no pending deletions
    if (!pendingDeletions && !processingDeletion) {
      autoProcessedRef.current = false;
    }
  }, [pendingDeletions, processingDeletion, handleConfirmDeletion]);
  */

  // Reset the deletion workflow
  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset? All pending deletions will be cleared.')) {
      setPendingDeletions(null);
      setProcessingDeletion(null);
      setProcessing(false);
      
      // Clear waveform
      if (wavesurfer) {
        wavesurfer.destroy();
        setWavesurfer(null);
      }
    }
  };

  // Poll for task completion when processing
  useEffect(() => {
    if (!processingDeletion || !processingDeletion.taskId || !token) {
      return;
    }

    let isActive = true;
    const abortController = new AbortController(); // Create once, persist for cleanup

    const pollTaskStatus = async () => {
      if (!isActive) return;
      
      try {
        const response = await fetch(
          `http://localhost:8000/tasks/${processingDeletion.taskId}/status/`,
          {
            headers: {
              'Authorization': `Token ${token}`,
              'Content-Type': 'application/json'
            },
            signal: abortController.signal
          }
        );

        if (!isActive) return;

        if (response.ok) {
          const data = await response.json();
          
          if (data.status === 'completed') {
            isActive = false; // Stop polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            await handleProcessingComplete(processingDeletion.taskId, processingDeletion.audioFile);
          } else if (data.status === 'failed') {
            isActive = false; // Stop polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            alert(`Processing failed: ${data.error || 'Unknown error'}`);
            setProcessingDeletion(null);
          }
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          // Request was aborted, this is expected on cleanup
          return;
        }
        if (isActive) {
          console.error('Error polling task status:', error);
        }
      }
    };

    // Start polling
    pollTaskStatus();
    pollingIntervalRef.current = setInterval(pollTaskStatus, 2000);

    // Cleanup on unmount
    return () => {
      isActive = false;
      abortController.abort();
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [processingDeletion?.taskId, token, handleProcessingComplete, setProcessingDeletion]);

  // Initialize WaveSurfer when file is selected
  useEffect(() => {
    if (!selectedAudioFile || !selectedAudioFile.processed_audio || !waveformRef.current) {
      return;
    }

    // Clean up existing instance
    if (wavesurfer) {
      try {
        wavesurfer.destroy();
      } catch (error) {
        console.error('Error destroying previous wavesurfer:', error);
      }
    }

    let ws = null;
    let mounted = true;

    try {
      ws = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4a90e2',
        progressColor: '#2563eb',
        cursorColor: '#1e40af',
        barWidth: 2,
        barRadius: 3,
        cursorWidth: 1,
        height: 120,
        barGap: 2,
        responsive: true,
        normalize: true,
      });

      const audioUrl = `http://localhost:8000${selectedAudioFile.processed_audio}`;
      ws.load(audioUrl);
      
      ws.on('ready', () => {
        if (mounted) {
          setDuration(ws.getDuration());
        }
      });

      ws.on('play', () => {
        if (mounted) setIsPlaying(true);
      });
      
      ws.on('pause', () => {
        if (mounted) setIsPlaying(false);
      });
      
      ws.on('finish', () => {
        if (mounted) setIsPlaying(false);
      });
      
      ws.on('audioprocess', (time) => {
        if (mounted) setCurrentTime(time);
      });

      ws.on('seek', () => {
        if (mounted) setCurrentTime(ws.getCurrentTime());
      });

      if (mounted) {
        setWavesurfer(ws);
      }

      return () => {
        mounted = false;
        if (ws) {
          try {
            ws.destroy();
          } catch (error) {
            // Silently ignore cleanup errors
            console.debug('WaveSurfer cleanup error (expected):', error);
          }
        }
      };
    } catch (error) {
      console.error('Error initializing waveform:', error);
    }
  }, [selectedAudioFile]);

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

  const handleDownload = async () => {
    if (!selectedAudioFile || !selectedAudioFile.processed_audio) return;
    
    try {
      const audioUrl = `http://localhost:8000${selectedAudioFile.processed_audio}`;
      const response = await fetch(audioUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedAudioFile.filename.replace(/\.[^/.]+$/, '')}_clean.wav`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      alert('Failed to download audio file');
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const calculateStats = () => {
    if (!selectedAudioFile) return null;
    
    // Get original duration - if not set, try to calculate from transcription or fallback
    let originalDuration = selectedAudioFile.duration_seconds;
    
    // If no duration_seconds, try to calculate from transcription
    if (!originalDuration && selectedAudioFile.transcription && selectedAudioFile.transcription.segments) {
      const segments = selectedAudioFile.transcription.segments;
      if (segments.length > 0) {
        const lastSegment = segments[segments.length - 1];
        originalDuration = lastSegment.end_time;
      }
    }
    
    // Fallback to 0 if still not found
    originalDuration = originalDuration || 0;
    
    const processedDuration = selectedAudioFile.processed_duration_seconds || duration || 0;
    const timeSaved = originalDuration - processedDuration;
    const percentageSaved = originalDuration > 0 ? (timeSaved / originalDuration * 100) : 0;
    
    console.log('Duration Debug:', {
      originalDuration,
      processedDuration,
      duration_seconds: selectedAudioFile.duration_seconds,
      processed_duration_seconds: selectedAudioFile.processed_duration_seconds,
      waveformDuration: duration
    });
    
    return {
      originalDuration,
      processedDuration,
      timeSaved,
      percentageSaved
    };
  };

  const stats = selectedAudioFile ? calculateStats() : null;

  return (
    <div className="tab4-container">
      <div className="tab-header">
        <h2>🗑️ Deletion Review & Results</h2>
        <p>Review confirmed deletions, process them, and listen to your clean audio files</p>
      </div>

      {/* Pending Deletions Review - Show button for manual processing */}
      {pendingDeletions && !processingDeletion && (
        <div className="pending-deletions-card">
          <h3>📋 Ready to Process Deletions</h3>
          <div className="deletion-summary">
            <p><strong>File:</strong> {pendingDeletions.audioFile.filename}</p>
            <p><strong>Segments to Delete:</strong> {pendingDeletions.deletionCount}</p>
            <p className="deletion-warning">
              ⚠️ This will permanently remove the selected duplicate segments from the audio.
            </p>
          </div>
          
          <div className="deletion-actions">
            <button
              onClick={handleConfirmDeletion}
              disabled={processing}
              className="confirm-deletion-button"
            >
              {processing ? '⏳ Processing...' : '✅ Start Processing Now'}
            </button>
            <button
              onClick={handleReset}
              disabled={processing}
              className="reset-button"
            >
              🔄 Cancel
            </button>
          </div>
          
          {/* Show segments to be deleted */}
          <div className="deletion-preview">
            <h4>Segments to be deleted (first 10):</h4>
            <div className="segments-list">
              {pendingDeletions.confirmedDeletions.slice(0, 10).map((seg, idx) => (
                <div key={idx} className="segment-preview">
                  <span className="segment-time">{seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s</span>
                  <span className="segment-text">{seg.text.substring(0, 100)}{seg.text.length > 100 ? '...' : ''}</span>
                </div>
              ))}
              {pendingDeletions.confirmedDeletions.length > 10 && (
                <p className="more-segments">... and {pendingDeletions.confirmedDeletions.length - 10} more segments</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Processing Loading State */}
      {processingDeletion && (
        <div className="processing-state">
          <div className="loading-card">
            <div className="loading-spinner"></div>
            <div className="loading-content">
              <h3>🔄 Processing Audio</h3>
              <p className="processing-filename">
                <strong>{processingDeletion.audioFile.filename}</strong>
              </p>
              <p className="processing-details">
                Removing {processingDeletion.deletionCount} duplicate segments...
              </p>
              <p className="processing-info">
                This may take a few moments. The clean audio will appear below when ready.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* File Selection - only show when not reviewing or processing */}
      {!pendingDeletions && !processingDeletion && processedFiles.length > 0 && (
        <div className="file-selection-card">
          <label className="input-label">Select Processed File:</label>
          <select
            value={selectedAudioFile?.id || ''}
            onChange={(e) => {
              const file = audioFiles.find(f => f.id === parseInt(e.target.value));
              selectAudioFile(file);
            }}
            className="file-select"
          >
            <option value="">-- Select a processed file --</option>
            {processedFiles.map(file => (
              <option key={file.id} value={file.id}>
                {file.filename}
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedAudioFile && selectedAudioFile.processed_audio && !pendingDeletions && !processingDeletion && (
        <div className="results-content">
          {/* Statistics Cards */}
          {stats && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">⏱️</div>
                <div className="stat-info">
                  <div className="stat-label">Original Duration</div>
                  <div className="stat-value">{formatTime(stats.originalDuration)}</div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">✂️</div>
                <div className="stat-info">
                  <div className="stat-label">Clean Duration</div>
                  <div className="stat-value">{formatTime(stats.processedDuration)}</div>
                </div>
              </div>

              <div className="stat-card success">
                <div className="stat-icon">💾</div>
                <div className="stat-info">
                  <div className="stat-label">Time Saved</div>
                  <div className="stat-value">{formatTime(stats.timeSaved)}</div>
                  <div className="stat-subtitle">{stats.percentageSaved.toFixed(1)}% reduction</div>
                </div>
              </div>
            </div>
          )}

          {/* Audio Player */}
          <div className="audio-player-card">
            <h3>🎵 Clean Audio Playback</h3>
            
            <div className="waveform-container" ref={waveformRef}></div>
            
            <div className="player-controls">
              <div className="time-display">
                <span className="current-time">{formatTime(currentTime)}</span>
                <span className="time-separator"> / </span>
                <span className="duration-time">{formatTime(duration)}</span>
              </div>
              
              <div className="control-buttons">
                <button
                  onClick={handlePlayPause}
                  className="control-btn play-pause"
                  disabled={!wavesurfer}
                >
                  {isPlaying ? '⏸️ Pause' : '▶️ Play'}
                </button>
                
                <button
                  onClick={handleStop}
                  className="control-btn stop"
                  disabled={!wavesurfer}
                >
                  ⏹️ Stop
                </button>
              </div>
            </div>
          </div>

          {/* Download Section */}
          <div className="download-section">
            <button
              onClick={handleDownload}
              className="download-button"
            >
              ⬇️ Download Clean Audio
            </button>
            <button
              onClick={handleReset}
              className="reset-button secondary"
            >
              🔄 Process Another File
            </button>
            <p className="download-info">
              Download the processed audio file with all duplicates removed
            </p>
          </div>
        </div>
      )}

      {!pendingDeletions && !processingDeletion && processedFiles.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📭</div>
          <h3>No Processed Files Yet</h3>
          <p>Process audio files in the Duplicates tab to see results here.</p>
        </div>
      )}

      {processedFiles.length > 0 && !selectedAudioFile && (
        <div className="empty-state">
          <p>Select a processed file to view results and download clean audio.</p>
        </div>
      )}
    </div>
  );
};

export default Tab4Results;
