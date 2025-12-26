import React, { useState, useEffect, useRef } from 'react';
import { useProjectTab } from '../contexts/ProjectTabContext';
import { useAuth } from '../contexts/AuthContext';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import './Tab3Review.css';

const Tab3Review = () => {
  const { token } = useAuth();
  const { projectId, selectedAudioFile } = useProjectTab();
  
  const [previewStatus, setPreviewStatus] = useState('none');
  const [previewMetadata, setPreviewMetadata] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedRegions, setSelectedRegions] = useState(new Set());
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(null);
  
  const waveformRef = useRef(null);
  const wavesurferRef = useRef(null);
  const regionsPluginRef = useRef(null);

  // Fetch preview status on mount and when audioFile changes
  useEffect(() => {
    if (selectedAudioFile?.id) {
      fetchPreviewStatus();
    }
  }, [selectedAudioFile?.id]);

  // Initialize WaveSurfer when preview is ready
  useEffect(() => {
    if (previewStatus === 'ready' && previewMetadata && waveformRef.current && !wavesurferRef.current) {
      initializeWaveSurfer();
    }
    
    return () => {
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
    };
  }, [previewStatus, previewMetadata]);

  const fetchPreviewStatus = async () => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/deletion-preview/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
          },
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setPreviewStatus(data.preview_status);
        setPreviewMetadata(data.preview_metadata);
        setError(null);
      }
    } catch (err) {
      console.error('Error fetching preview status:', err);
      setError('Failed to fetch preview status');
    }
  };

  const generatePreview = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/preview-deletions/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setPreviewStatus('generating');
        
        // Poll for status
        pollPreviewStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to generate preview');
        setIsGenerating(false);
      }
    } catch (err) {
      console.error('Error generating preview:', err);
      setError('Failed to generate preview');
      setIsGenerating(false);
    }
  };

  const pollPreviewStatus = () => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/deletion-preview/`,
          {
            headers: {
              'Authorization': `Token ${token}`,
            },
          }
        );

        if (response.ok) {
          const data = await response.json();
          setPreviewStatus(data.preview_status);
          setPreviewMetadata(data.preview_metadata);

          if (data.preview_status === 'ready' || data.preview_status === 'failed') {
            clearInterval(interval);
            setIsGenerating(false);
            
            if (data.preview_status === 'failed') {
              setError('Preview generation failed');
            }
          }
        }
      } catch (err) {
        console.error('Error polling preview status:', err);
        clearInterval(interval);
        setIsGenerating(false);
      }
    }, 2000);
  };

  const initializeWaveSurfer = () => {
    // Create regions plugin
    regionsPluginRef.current = RegionsPlugin.create();

    // Initialize WaveSurfer
    wavesurferRef.current = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: '#4a9eff',
      progressColor: '#1e7ed4',
      cursorColor: '#ff4444',
      barWidth: 2,
      barRadius: 3,
      cursorWidth: 2,
      height: 120,
      barGap: 2,
      plugins: [regionsPluginRef.current],
    });

    // Load audio
    const audioUrl = `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/preview-audio/?t=${Date.now()}`;
    wavesurferRef.current.load(audioUrl);

    // Add deletion regions
    wavesurferRef.current.on('ready', () => {
      setDuration(wavesurferRef.current.getDuration());
      
      if (previewMetadata?.deletion_regions) {
        previewMetadata.deletion_regions.forEach((region, index) => {
          regionsPluginRef.current.addRegion({
            id: `region-${index}`,
            start: region.preview_start,
            end: region.preview_end,
            color: 'rgba(255, 68, 68, 0.3)',
            drag: false,
            resize: false,
          });
        });
      }
    });

    // Update time display
    wavesurferRef.current.on('audioprocess', (time) => {
      setCurrentTime(time);
    });

    wavesurferRef.current.on('seeking', (time) => {
      setCurrentTime(time);
    });

    // Handle play/pause
    wavesurferRef.current.on('play', () => setIsPlaying(true));
    wavesurferRef.current.on('pause', () => setIsPlaying(false));
  };

  const togglePlayPause = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const skipToRegion = (index) => {
    if (wavesurferRef.current && previewMetadata?.deletion_regions[index]) {
      const region = previewMetadata.deletion_regions[index];
      wavesurferRef.current.seekTo(region.preview_start / duration);
    }
  };

  const toggleRegionSelection = (index) => {
    const newSelected = new Set(selectedRegions);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedRegions(newSelected);
  };

  const restoreSelected = async () => {
    if (selectedRegions.size === 0) return;

    try {
      const segmentIds = Array.from(selectedRegions).map(index => 
        previewMetadata.deletion_regions[index].segment_id
      );

      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/restore-segments/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            segment_ids: segmentIds,
            regenerate_preview: true,
          }),
        }
      );

      if (response.ok) {
        setSelectedRegions(new Set());
        setPreviewStatus('generating');
        setIsGenerating(true);
        
        // Destroy existing WaveSurfer
        if (wavesurferRef.current) {
          wavesurferRef.current.destroy();
          wavesurferRef.current = null;
        }
        
        // Poll for new preview
        pollPreviewStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to restore segments');
      }
    } catch (err) {
      console.error('Error restoring segments:', err);
      setError('Failed to restore segments');
    }
  };

  const cancelPreview = async () => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/cancel-preview/`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Token ${token}`,
          },
        }
      );

      if (response.ok) {
        setPreviewStatus('none');
        setPreviewMetadata(null);
        setSelectedRegions(new Set());
        
        if (wavesurferRef.current) {
          wavesurferRef.current.destroy();
          wavesurferRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error canceling preview:', err);
      setError('Failed to cancel preview');
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
      return `${mins}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  if (!selectedAudioFile) {
    return (
      <div className="tab3-review">
        <div className="empty-state">
          <p>No audio file selected</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tab3-review">
      <div className="review-header">
        <h2>Preview Deletions</h2>
        <p className="review-description">
          Review detected duplicate segments before finalizing. Listen to the cleaned audio with deleted regions highlighted.
        </p>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {previewStatus === 'none' && (
        <div className="preview-actions">
          <button
            className="btn-primary generate-preview-btn"
            onClick={generatePreview}
            disabled={isGenerating}
          >
            Generate Preview
          </button>
          <p className="help-text">
            This will create a temporary preview of your audio with all marked duplicates removed.
          </p>
        </div>
      )}

      {(previewStatus === 'generating' || isGenerating) && (
        <div className="generating-state">
          <div className="spinner"></div>
          <p>Generating preview audio...</p>
        </div>
      )}

      {previewStatus === 'ready' && previewMetadata && (
        <>
          <div className="statistics-cards">
            <div className="stat-card">
              <div className="stat-label">Original Duration</div>
              <div className="stat-value">{formatDuration(previewMetadata.original_duration)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Preview Duration</div>
              <div className="stat-value">{formatDuration(previewMetadata.preview_duration)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Time Saved</div>
              <div className="stat-value success">{formatDuration(previewMetadata.time_saved)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Deletions</div>
              <div className="stat-value">{previewMetadata.deletion_regions?.length || 0}</div>
            </div>
          </div>

          <div className="audio-player">
            <div className="waveform-container" ref={waveformRef}></div>
            
            <div className="player-controls">
              <button className="play-pause-btn" onClick={togglePlayPause}>
                {isPlaying ? '⏸' : '▶'}
              </button>
              <div className="time-display">
                <span className="current-time">{formatTime(currentTime)}</span>
                <span className="separator"> / </span>
                <span className="total-time">{formatTime(duration)}</span>
              </div>
            </div>
          </div>

          <div className="deletion-regions">
            <div className="regions-header">
              <h3>Deleted Segments ({previewMetadata.deletion_regions?.length || 0})</h3>
              {selectedRegions.size > 0 && (
                <button className="btn-restore" onClick={restoreSelected}>
                  Restore Selected ({selectedRegions.size})
                </button>
              )}
            </div>

            <div className="regions-list">
              {previewMetadata.deletion_regions?.map((region, index) => (
                <div
                  key={index}
                  className={`region-item ${selectedRegions.has(index) ? 'selected' : ''}`}
                  onClick={() => skipToRegion(index)}
                >
                  <div className="region-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedRegions.has(index)}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleRegionSelection(index);
                      }}
                    />
                  </div>
                  <div className="region-info">
                    <div className="region-time">
                      {formatTime(region.original_start)} - {formatTime(region.original_end)}
                    </div>
                    <div className="region-duration">
                      Duration: {formatDuration(region.original_end - region.original_start)}
                    </div>
                    {region.text && (
                      <div className="region-text">{region.text}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="preview-actions">
            <button className="btn-secondary" onClick={cancelPreview}>
              Cancel Preview
            </button>
          </div>
        </>
      )}

      {previewStatus === 'failed' && (
        <div className="error-state">
          <p>Preview generation failed. Please try again.</p>
          <button className="btn-primary" onClick={() => setPreviewStatus('none')}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
};

export default Tab3Review;
