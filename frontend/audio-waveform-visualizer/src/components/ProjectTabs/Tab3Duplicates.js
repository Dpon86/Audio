import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import WaveSurfer from 'wavesurfer.js';
import WaveformDuplicateEditor from './WaveformDuplicateEditor';
import PDFRegionSelector from '../PDFRegionSelector';
import './Tab3Duplicates.css';

/**
 * Tab 3: Duplicate Detection and Review
 * Detects duplicate segments within a single audio file and allows user review
 */
const Tab3Duplicates = () => {
  const { token } = useAuth();
  const { 
    projectId, 
    selectedAudioFile, 
    audioFiles, 
    selectAudioFile,
    activeTab,
    setActiveTab, 
    setPendingDeletions 
  } = useProjectTab();
  
  const [detecting, setDetecting] = useState(false);
  const [detectionAlgorithm, setDetectionAlgorithm] = useState('windowed_retry');
  const [showAlgorithmSettings, setShowAlgorithmSettings] = useState(true);
  const [lastRunSummary, setLastRunSummary] = useState(null);

  // Algorithm settings (user-adjustable before start)
  const [tfidfSimilarityThreshold, setTfidfSimilarityThreshold] = useState(0.85);
  const [windowMaxLookahead, setWindowMaxLookahead] = useState(90);
  const [windowRatioThreshold, setWindowRatioThreshold] = useState(0.76);
  const [windowStrongMatchRatio, setWindowStrongMatchRatio] = useState(0.84);
  const [windowMinWordLength, setWindowMinWordLength] = useState(3);

  // Optional PDF-hint region + cleaning controls
  const [showPdfRegionSelector, setShowPdfRegionSelector] = useState(false);
  const [pdfSelectorMode, setPdfSelectorMode] = useState('start');
  const [pdfStartChar, setPdfStartChar] = useState(null);
  const [pdfEndChar, setPdfEndChar] = useState(null);
  const [pdfStartText, setPdfStartText] = useState('');
  const [pdfEndText, setPdfEndText] = useState('');
  const [isCleaningPDF, setIsCleaningPDF] = useState(false);
  const [pdfCleanupMessage, setPdfCleanupMessage] = useState(null);
  const [transcriptText, setTranscriptText] = useState('');

  const [duplicateGroups, setDuplicateGroups] = useState([]);
  const [selectedDeletions, setSelectedDeletions] = useState([]);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [processing, setProcessing] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [isProcessingDeletions, setIsProcessingDeletions] = useState(false);

  const algorithmOptions = [
    { value: 'windowed_retry', label: 'New Retry-Aware (No PDF)' },
    { value: 'windowed_retry_pdf', label: 'New Retry-Aware + PDF Hint' },
    { value: 'tfidf_cosine', label: 'Classic TF-IDF Cosine' },
  ];

  // Audio player state
  const [wavesurfer, setWavesurfer] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const waveformRef = useRef(null);

  // Load duplicate groups when file is selected
  useEffect(() => {
    if (selectedAudioFile) {
      loadDuplicateGroups();
      loadTranscriptText();
    }
  }, [selectedAudioFile]);

  const loadTranscriptText = async () => {
    if (!selectedAudioFile) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include'
        }
      );

      if (response.ok) {
        const data = await response.json();
        const fullText = data?.transcription?.full_text || '';
        setTranscriptText(fullText);
      } else {
        setTranscriptText('');
      }
    } catch (error) {
      console.error('Failed to load transcript text:', error);
      setTranscriptText('');
    }
  };

  const loadDuplicateGroups = async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/duplicates/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log('Received duplicate groups:', data.duplicate_groups);
        
        if (data.duplicate_groups && data.duplicate_groups.length > 0) {
          setDuplicateGroups(data.duplicate_groups);
          
          // Auto-select all for deletion except last occurrence
          // Backend marks is_duplicate=true for segments that should be deleted
          const toDelete = [];
          data.duplicate_groups.forEach(group => {
            const segments = group.segments || group.occurrences || [];
            if (segments && Array.isArray(segments)) {
              segments.forEach((seg) => {
                console.log(`Segment ${seg.id}: is_duplicate=${seg.is_duplicate}, is_kept=${seg.is_kept}, is_last_occurrence=${seg.is_last_occurrence}`);
                
                // Backend sets is_duplicate=true for segments to DELETE
                // is_duplicate=false for LAST occurrence (to keep)
                if (seg.is_duplicate === true) {
                  toDelete.push(seg.id);
                }
              });
            }
          });
          
          console.log(`Auto-selected ${toDelete.length} segments for deletion:`, toDelete);
          setSelectedDeletions(toDelete);
          
          // Expand first 3 groups
          const firstThree = data.duplicate_groups.slice(0, 3).map(g => g.group_id);
          setExpandedGroups(new Set(firstThree));
        } else {
          setDuplicateGroups([]);
          setSelectedDeletions([]);
        }
      }
    } catch (error) {
      console.error('Error loading duplicate groups:', error);
    }
  };

  // Initialize WaveSurfer when file is selected
  useEffect(() => {
    if (!selectedAudioFile || !selectedAudioFile.audio_file || !waveformRef.current) {
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

      const audioUrl = `http://localhost:8000${selectedAudioFile.audio_file}`;
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
            console.debug('WaveSurfer cleanup error (expected):', error);
          }
        }
      };
    } catch (error) {
      console.error('Error initializing waveform:', error);
    }
  }, [selectedAudioFile]);

  // Audio player controls
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

  const seekToTime = (timeInSeconds) => {
    if (wavesurfer && duration > 0) {
      wavesurfer.seekTo(timeInSeconds / duration);
      if (!isPlaying) {
        wavesurfer.play();
      }
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle group selection from waveform
  const handleGroupSelect = (groupId) => {
    console.log('Group selected:', groupId);
    setSelectedGroupId(groupId);
    
    // Optionally expand the group in the list
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      newSet.add(groupId);
      return newSet;
    });
  };

  // Handle region boundary updates from waveform
  const handleRegionUpdate = async (groupId, segmentId, newStartTime, newEndTime) => {
    console.log(`\n---- MANUAL DRAG UPDATE ----`);
    console.log(`📝 Region: group=${groupId}, segment=${segmentId}`);
    console.log(`📝 New times: ${newStartTime.toFixed(2)}s - ${newEndTime.toFixed(2)}s`);
    
    try {
      // Save to backend FIRST (before optimistic update)
      console.log(`📤 Sending PATCH to: /api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${segmentId}/`);
      console.log(`📤 Payload:`, { start_time: newStartTime, end_time: newEndTime });
      
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${segmentId}/`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            start_time: newStartTime,
            end_time: newEndTime
          })
        }
      );

      console.log(`📥 Response status: ${response.status} ${response.statusText}`);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`❌ PATCH failed:`, errorText);
        throw new Error(`Failed to update segment times: ${response.status}`);
      }
      
      const responseData = await response.json();
      console.log(`✅ Backend updated successfully:`, responseData);

      // Now update local state to match backend
      setDuplicateGroups(prevGroups =>
        prevGroups.map(group => {
          if (group.group_id !== groupId) return group;

          return {
            ...group,
            segments: group.segments.map(seg =>
              seg.id === segmentId
                ? { ...seg, start_time: newStartTime, end_time: newEndTime }
                : seg
            )
          };
        })
      );
      
      console.log(`✅ Local state updated`);
      console.log(`---- UPDATE COMPLETE ----\n`);

    } catch (error) {
      console.error('\n❌❌❌ ERROR UPDATING SEGMENT:', error);
      console.error('Error details:', error.message);
      console.log(`---- UPDATE FAILED ----\n`);
      // Don't reload - just show the error
      alert(`Failed to update segment: ${error.message}`);
    }
  };

  const handleClearResults = () => {
    if (window.confirm('Clear all duplicate detection results? You will need to re-run detection.')) {
      setDuplicateGroups([]);
      setSelectedDeletions([]);
      setExpandedGroups(new Set());
    }
  };

  const isPdfHintAlgorithm = detectionAlgorithm === 'windowed_retry_pdf';

  const handlePdfPositionSelected = (position, text) => {
    if (pdfSelectorMode === 'start') {
      setPdfStartChar(position);
      setPdfStartText(text);
    } else {
      setPdfEndChar(position);
      setPdfEndText(text);
    }
    setShowPdfRegionSelector(false);
  };

  const handleCleanPdfForDuplicateHint = async () => {
    if (!projectId) return;

    setIsCleaningPDF(true);
    setPdfCleanupMessage(null);

    try {
      const requestBody = {};
      if (pdfStartChar !== null) requestBody.pdf_start_char = pdfStartChar;
      if (pdfEndChar !== null) requestBody.pdf_end_char = pdfEndChar;

      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/clean-pdf-text/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify(requestBody)
        }
      );

      if (response.ok) {
        const data = await response.json();
        setPdfCleanupMessage({
          type: 'success',
          text: `PDF cleaned for duplicate hinting (${(data.statistics?.new_quality?.quality_score || 0).toFixed(2)} quality score)`
        });
      } else {
        const errorData = await response.json();
        setPdfCleanupMessage({
          type: 'error',
          text: `Failed to clean PDF: ${errorData.error || 'Unknown error'}`
        });
      }
    } catch (error) {
      setPdfCleanupMessage({
        type: 'error',
        text: `Network error: ${error.message}`
      });
    } finally {
      setIsCleaningPDF(false);
    }
  };

  const handleDetectDuplicates = async (algorithmOverride = null) => {
    if (!selectedAudioFile) return;
    
    // Clear old results before starting new detection
    setDuplicateGroups([]);
    setSelectedDeletions([]);
    setExpandedGroups(new Set());
    setDetecting(true);

    const selectedAlgorithm = algorithmOverride || detectionAlgorithm;
    const usePdfHint = selectedAlgorithm === 'windowed_retry_pdf';

    const requestBody = {
      algorithm: selectedAlgorithm,
      use_pdf_hint: usePdfHint,
      tfidf_similarity_threshold: tfidfSimilarityThreshold,
      window_max_lookahead: windowMaxLookahead,
      window_ratio_threshold: windowRatioThreshold,
      window_strong_match_ratio: windowStrongMatchRatio,
      window_min_word_length: windowMinWordLength,
    };

    if (usePdfHint) {
      if (pdfStartChar !== null) requestBody.pdf_start_char = pdfStartChar;
      if (pdfEndChar !== null) requestBody.pdf_end_char = pdfEndChar;
    }
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/detect-duplicates/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setLastRunSummary({
          algorithm: data.algorithm || selectedAlgorithm,
          usePdfHint,
          settings: data.settings || requestBody,
        });
        alert(`${data.message || 'Duplicate detection started'}\nAlgorithm: ${selectedAlgorithm}`);
        
        // Poll for completion
        const pollInterval = setInterval(async () => {
          await loadDuplicateGroups();
          
          // Check if detection is complete
          const statusResponse = await fetch(
            `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/status/`,
            {
              headers: {
                'Authorization': `Token ${token}`,
                'Content-Type': 'application/json'
              }
            }
          );
          
          if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            if (statusData.status !== 'processing') {
              clearInterval(pollInterval);
              setDetecting(false);
              await loadDuplicateGroups();
            }
          }
        }, 3000);
        
        // Stop polling after 5 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setDetecting(false);
        }, 300000);
        
      } else {
        let errorMessage = 'Failed to start duplicate detection';
        try {
          const error = await response.json();
          errorMessage = error.error || error.message || errorMessage;
        } catch (e) {
          // Response is not JSON, might be HTML error page
          errorMessage = `Server error (${response.status}): ${response.statusText}`;
        }
        alert(errorMessage);
        setDetecting(false);
      }
    } catch (error) {
      console.error('Error detecting duplicates:', error);
      alert(`Error: ${error.message}`);
      setDetecting(false);
    }
  };

  const handleConfirmDeletions = async () => {
    console.log('handleConfirmDeletions called, selectedDeletions:', selectedDeletions.length);
    
    if (selectedDeletions.length === 0) {
      alert('No segments selected for deletion');
      return;
    }
    
    // Show loading state immediately
    setIsProcessingDeletions(true);
    
    try {
      // Simulate processing delay for UI feedback (remove if unnecessary)
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Format confirmed deletions with full segment data
      const confirmedDeletions = [];
      duplicateGroups.forEach(group => {
        if (group.segments && Array.isArray(group.segments)) {
          group.segments.forEach(seg => {
            if (selectedDeletions.includes(seg.id)) {
              confirmedDeletions.push({
                segment_id: seg.id,
                audio_file_id: selectedAudioFile.id,
                start_time: seg.start_time,
                end_time: seg.end_time,
                text: seg.text
              });
            }
          });
        }
      });
      
      // Store pending deletions in context
      console.log('Setting pending deletions:', confirmedDeletions.length, 'segments');
      console.log('Current activeTab before setting:', activeTab);
      console.log('setActiveTab function:', setActiveTab);
      
      // First set pending deletions
      setPendingDeletions({
        audioFile: selectedAudioFile,
        confirmedDeletions: confirmedDeletions,
        segmentIds: selectedDeletions,
        deletionCount: selectedDeletions.length,
        duplicateGroups: duplicateGroups
      });
      
      // Processing complete - show completion modal
      setIsProcessingDeletions(false);
      setShowCompletionModal(true);
    } catch (error) {
      console.error('Error processing deletions:', error);
      setIsProcessingDeletions(false);
      alert('Error processing deletions. Please try again.');
    }
  };

  const handleNavigateToResults = () => {
    console.log('handleNavigateToResults called');
    console.log('Current tab:', activeTab);
    setShowCompletionModal(false);
    console.log('Setting activeTab to: results');
    setActiveTab('results');
    console.log('setActiveTab called with results');
  };

  const handleReturnToUpload = () => {
    console.log('handleReturnToUpload called');
    console.log('Current tab:', activeTab);
    setShowCompletionModal(false);
    console.log('Setting activeTab to: files');
    setActiveTab('files');
    console.log('setActiveTab called with files');
  };

  const toggleGroup = (groupId) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  const toggleDeletion = (segmentId) => {
    setSelectedDeletions(prev =>
      prev.includes(segmentId)
        ? prev.filter(id => id !== segmentId)
        : [...prev, segmentId]
    );
  };

  const renderHighlightedDuplicateText = (text, groupSegments) => {
    if (!text || !groupSegments || groupSegments.length < 2) {
      return text;
    }

    const normalizedWordSets = groupSegments
      .map(seg => (seg.text || '').toLowerCase().match(/[a-z0-9']+/g) || [])
      .map(words => new Set(words.filter(word => word.length >= 3)));

    if (normalizedWordSets.length < 2) {
      return text;
    }

    const commonWords = [...normalizedWordSets[0]].filter(word =>
      normalizedWordSets.slice(1).every(wordSet => wordSet.has(word))
    );

    if (commonWords.length === 0) {
      return text;
    }

    const commonWordSet = new Set(commonWords);
    const tokens = text.match(/\w+|\s+|[^\w\s]+/g) || [text];

    return tokens.map((token, index) => {
      const normalized = token.toLowerCase().replace(/[^a-z0-9']/g, '');
      if (normalized && commonWordSet.has(normalized)) {
        return (
          <mark
            key={`token-${index}`}
            style={{ background: '#fde68a', color: '#7c2d12', padding: '0 2px', borderRadius: '2px' }}
          >
            {token}
          </mark>
        );
      }
      return <React.Fragment key={`token-${index}`}>{token}</React.Fragment>;
    });
  };

  // Get transcribed files for selection
  const transcribedFiles = useMemo(() => {
    return audioFiles.filter(f => f.status === 'transcribed' || f.status === 'processed');
  }, [audioFiles]);

  return (
    <div className="tab3-container">
      <div className="tab-header">
        <h2>🔍 Find & Remove Duplicates</h2>
        <p>Detect repeated content within a single audio file. The system will keep the last occurrence of each duplicate.</p>
      </div>

      {/* Selected File Display */}
      {selectedAudioFile ? (
        <div className="file-selection-card">
          <div style={{ marginBottom: '1rem' }}>
            <label className="input-label">Working with:</label>
            <div style={{ 
              padding: '0.75rem', 
              background: '#e0e7ff', 
              borderRadius: '6px',
              border: '2px solid #667eea',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{ fontSize: '1.5rem' }}>🎵</span>
              <span style={{ fontWeight: '600', color: '#1e293b' }}>{selectedAudioFile.filename}</span>
              <span style={{ marginLeft: 'auto', fontSize: '0.9rem', color: '#64748b' }}>({selectedAudioFile.status})</span>
            </div>
            <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#64748b' }}>
              💡 Tip: Select a different file in the "Upload & Transcribe" tab to work with it here.
            </div>
          </div>

          <div style={{
            padding: '1rem',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            background: '#f8fafc',
            marginBottom: '1rem'
          }}>
            <h4 style={{ margin: 0, marginBottom: '0.5rem', color: '#1e293b' }}>Before you start</h4>
            <p style={{ margin: 0, color: '#475569', fontSize: '0.9rem' }}>
              1) Choose algorithm. 2) Adjust settings (optional). 3) Click Start.
              All algorithms keep the last occurrence and mark earlier repeats for deletion.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <select
              value={detectionAlgorithm}
              onChange={(e) => setDetectionAlgorithm(e.target.value)}
              disabled={detecting}
              style={{
                minWidth: '280px',
                padding: '0.6rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontWeight: '600',
                color: '#334155',
                background: 'white'
              }}
            >
              {algorithmOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>

            <button
              onClick={() => setShowAlgorithmSettings((prev) => !prev)}
              disabled={detecting}
              style={{
                padding: '0.75rem 1rem',
                background: '#ffffff',
                color: '#334155',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                fontWeight: '600',
                cursor: detecting ? 'not-allowed' : 'pointer'
              }}
            >
              {showAlgorithmSettings ? '⚙️ Hide Settings' : '⚙️ Show Settings'}
            </button>

            <button
              onClick={() => handleDetectDuplicates()}
              disabled={detecting}
              className="detect-button"
            >
              {detecting ? '⏳ Detecting Duplicates...' : '▶️ Start Detection'}
            </button>
            
            {duplicateGroups.length > 0 && (
              <button
                onClick={handleClearResults}
                className="clear-button"
              >
                🔄 Clear Results
              </button>
            )}
          </div>

          {showAlgorithmSettings && (
            <div style={{
              padding: '1rem',
              border: '1px solid #cbd5e1',
              borderRadius: '8px',
              background: 'white',
              marginBottom: '0.5rem'
            }}>
              <h4 style={{ margin: 0, marginBottom: '0.75rem', color: '#1e293b' }}>Algorithm Settings</h4>

              {detectionAlgorithm === 'tfidf_cosine' && (
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <label style={{ fontWeight: '600', color: '#475569' }}>Similarity Threshold</label>
                  <input
                    type="number"
                    min="0.5"
                    max="0.99"
                    step="0.01"
                    value={tfidfSimilarityThreshold}
                    onChange={(e) => setTfidfSimilarityThreshold(parseFloat(e.target.value || 0.85))}
                    style={{ width: '100px', padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              )}

              {(detectionAlgorithm === 'windowed_retry' || detectionAlgorithm === 'windowed_retry_pdf') && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Max Lookahead Segments
                    <input
                      type="number"
                      min="10"
                      max="300"
                      step="5"
                      value={windowMaxLookahead}
                      onChange={(e) => setWindowMaxLookahead(parseInt(e.target.value || 90, 10))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Ratio Threshold
                    <input
                      type="number"
                      min="0.5"
                      max="0.99"
                      step="0.01"
                      value={windowRatioThreshold}
                      onChange={(e) => setWindowRatioThreshold(parseFloat(e.target.value || 0.76))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Strong Match Ratio
                    <input
                      type="number"
                      min="0.6"
                      max="0.99"
                      step="0.01"
                      value={windowStrongMatchRatio}
                      onChange={(e) => setWindowStrongMatchRatio(parseFloat(e.target.value || 0.84))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Min Word Length
                    <input
                      type="number"
                      min="1"
                      max="10"
                      step="1"
                      value={windowMinWordLength}
                      onChange={(e) => setWindowMinWordLength(parseInt(e.target.value || 3, 10))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>
                </div>
              )}

              {isPdfHintAlgorithm && (
                <div style={{
                  marginTop: '0.9rem',
                  padding: '0.9rem',
                  border: '1px solid #bfdbfe',
                  borderRadius: '8px',
                  background: '#eff6ff'
                }}>
                  <h5 style={{ margin: 0, marginBottom: '0.5rem', color: '#1e3a8a' }}>PDF Hint Scope (Optional)</h5>
                  <p style={{ margin: 0, marginBottom: '0.6rem', fontSize: '0.875rem', color: '#1d4ed8' }}>
                    Use the same start/end style as Compare PDF. You can also clean just this PDF region before detection.
                  </p>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
                    <button
                      onClick={() => {
                        setPdfSelectorMode('start');
                        setShowPdfRegionSelector(true);
                      }}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: '1px solid #93c5fd', background: 'white', color: '#1d4ed8', fontWeight: '600' }}
                    >
                      {pdfStartChar !== null ? `📄 Start: ${pdfStartChar}` : '📄 Select PDF Start'}
                    </button>
                    <button
                      onClick={() => {
                        setPdfSelectorMode('end');
                        setShowPdfRegionSelector(true);
                      }}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: '1px solid #93c5fd', background: 'white', color: '#1d4ed8', fontWeight: '600' }}
                    >
                      {pdfEndChar !== null ? `📄 End: ${pdfEndChar}` : '📄 Select PDF End'}
                    </button>
                    <button
                      onClick={handleCleanPdfForDuplicateHint}
                      disabled={isCleaningPDF}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: 'none', background: isCleaningPDF ? '#94a3b8' : '#10b981', color: 'white', fontWeight: '600' }}
                    >
                      {isCleaningPDF ? 'Cleaning...' : '🧹 Clean PDF (Hint Scope)'}
                    </button>
                  </div>

                  {(pdfStartText || pdfEndText) && (
                    <div style={{
                      marginBottom: '0.6rem',
                      padding: '0.6rem',
                      borderRadius: '6px',
                      background: '#ffffff',
                      border: '1px solid #dbeafe',
                      fontSize: '0.8rem',
                      color: '#334155'
                    }}>
                      {pdfStartText && <div><strong>Start preview:</strong> {pdfStartText}</div>}
                      {pdfEndText && <div style={{ marginTop: '0.35rem' }}><strong>End preview:</strong> {pdfEndText}</div>}
                    </div>
                  )}

                  {pdfCleanupMessage && (
                    <div style={{
                      padding: '0.6rem',
                      borderRadius: '6px',
                      background: pdfCleanupMessage.type === 'success' ? '#dcfce7' : '#fee2e2',
                      color: pdfCleanupMessage.type === 'success' ? '#166534' : '#991b1b',
                      fontWeight: '600',
                      fontSize: '0.85rem'
                    }}>
                      {pdfCleanupMessage.text}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {lastRunSummary && (
            <div style={{ fontSize: '0.85rem', color: '#475569' }}>
              Last run: <strong>{lastRunSummary.algorithm}</strong>
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state">
          <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎵</div>
            <h3 style={{ marginBottom: '0.5rem' }}>No File Selected</h3>
            <p>Please select a transcribed audio file in the <strong>"Upload & Transcribe"</strong> tab to begin duplicate detection.</p>
          </div>
        </div>
      )}

      {/* PDF Region Selector Modal (for PDF hint algorithm) */}
      {showPdfRegionSelector && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '2rem',
          overflowY: 'auto'
        }}>
          <div style={{ maxWidth: '1200px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <PDFRegionSelector
              projectId={projectId}
              mode={pdfSelectorMode}
              type="pdf"
              currentStart={pdfStartChar}
              currentEnd={pdfEndChar}
              transcriptText={transcriptText}
              onPositionSelected={handlePdfPositionSelected}
              onCancel={() => setShowPdfRegionSelector(false)}
            />
          </div>
        </div>
      )}
      
      {/* Duplicate Groups */}
      {selectedAudioFile && duplicateGroups.length === 0 && !detecting && (
        <div className="empty-state">
          <p>Click "Detect Duplicates" to analyze this file for repeated content.</p>
        </div>
      )}

      {/* Interactive Waveform Editor */}
      {selectedAudioFile && selectedAudioFile.file && duplicateGroups.length > 0 && (
        <WaveformDuplicateEditor
          audioFile={selectedAudioFile.file}
          duplicateGroups={duplicateGroups}
          selectedGroupId={selectedGroupId}
          onRegionUpdate={handleRegionUpdate}
          onGroupSelect={handleGroupSelect}
          onRefresh={loadDuplicateGroups}
        />
      )}
      
      {/* Debug: Show why waveform isn't rendering */}
      {duplicateGroups.length > 0 && !selectedAudioFile?.file && (
        <div style={{
          padding: '1rem',
          background: '#fef2f2',
          border: '1px solid #fca5a5',
          borderRadius: '6px',
          marginBottom: '1rem',
          color: '#991b1b'
        }}>
          ⚠️ Waveform not showing: No audio file path found. 
          Selected file: {selectedAudioFile?.filename || 'none'}
          {selectedAudioFile && (
            <div><small>Audio file path: {selectedAudioFile.file || 'MISSING'}</small></div>
          )}
        </div>
      )}

      {/* Results */}
      {duplicateGroups.length > 0 && (
        <div className="duplicate-results">
          <div className="results-header">
            <h3>Review Detected Duplicates</h3>
            <p className="selection-summary">
              <strong>Selected for deletion:</strong> {selectedDeletions.length} segments
            </p>
          </div>

          <div className="duplicate-groups-list">
            {[...duplicateGroups].reverse().map((group, reversedIndex) => {
              const groupIndex = duplicateGroups.length - 1 - reversedIndex; // Original index
              const isExpanded = expandedGroups.has(group.group_id);
              const segments = group.segments || group.occurrences || [];
              const isSelected = selectedGroupId === group.group_id;
              
              return (
                <div 
                  key={group.group_id} 
                  className={`duplicate-group-card ${isSelected ? 'selected' : ''}`}
                  data-group-id={group.group_id}
                >
                  <div 
                    className="group-header" 
                    onClick={() => {
                      toggleGroup(group.group_id);
                      handleGroupSelect(group.group_id);
                      if (segments.length > 0 && segments[0].start_time != null) {
                        seekToTime(segments[0].start_time);
                      }
                    }}
                  >
                    <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                    <div className="group-info">
                      <h4>Duplicate Group {duplicateGroups.length - groupIndex}</h4>
                      <p className="group-text">"{group.duplicate_text?.substring(0, 150) || (segments[0]?.text?.substring(0, 150)) || 'No text'}{(group.duplicate_text?.length > 150 || segments[0]?.text?.length > 150) ? '...' : ''}"</p>
                      <div className="group-meta">
                        <span>📊 {group.occurrence_count || segments.length} occurrences</span>
                        <span>⏱️ {(group.total_duration_seconds || segments.reduce((sum, s) => sum + (s.end_time - s.start_time), 0)).toFixed(1)}s total</span>
                      </div>
                    </div>
                  </div>

                  {isExpanded && segments.length > 0 && (
                    <div className="group-occurrences">
                      {segments.map((segment, index) => {
                        // Backend flags:
                        // - is_duplicate = true → DELETE (all except last)
                        // - is_duplicate = false → KEEP (last occurrence)
                        // - is_kept = true → explicitly marked to keep
                        const shouldDelete = segment.is_duplicate === true;
                        const shouldKeep = segment.is_kept === true || !shouldDelete;
                        
                        return (
                          <div
                            key={segment.id}
                            className={`occurrence-card ${shouldKeep ? 'last-occurrence' : ''}`}
                          >
                            <div className="occurrence-header">
                              <label className="checkbox-container">
                                <input
                                  type="checkbox"
                                  checked={selectedDeletions.includes(segment.id)}
                                  onChange={() => toggleDeletion(segment.id)}
                                  disabled={shouldKeep}
                                />
                                <span className="occurrence-title">
                                  Occurrence #{segment.occurrence_number || segment.segment_index || (index + 1)}
                                  {shouldKeep && ' (LAST - Keep)'}
                                </span>
                              </label>
                              <span className={`action-badge ${shouldKeep ? 'keep' : 'delete'}`}>
                                {shouldKeep ? 'KEEP' : 'DELETE'}
                              </span>
                            </div>

                            <div className="occurrence-details">
                              <p>
                                <strong>Time:</strong> 
                                <span 
                                  className="timestamp-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    seekToTime(segment.start_time);
                                  }}
                                  title="Click to jump to this timestamp in audio"
                                >
                                  🎯 {segment.start_time?.toFixed(1)}s - {segment.end_time?.toFixed(1)}s
                                </span>
                                ({(segment.end_time - segment.start_time)?.toFixed(1)}s)
                              </p>
                              <p className="occurrence-text">
                                <strong>Text:</strong> "{renderHighlightedDuplicateText(segment.text, segments)}"
                              </p>
                              <p style={{fontSize: '0.8rem', color: '#666', marginTop: '0.5rem'}}>
                                <strong>DEBUG:</strong> is_duplicate={String(segment.is_duplicate)}, is_kept={String(segment.is_kept)}, is_last_occurrence={String(segment.is_last_occurrence)}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="review-actions">
            <button
              onClick={() => {
                console.log('Button clicked!');
                handleConfirmDeletions();
              }}
              disabled={selectedDeletions.length === 0 || processing || isProcessingDeletions}
              className={`confirm-button ${isProcessingDeletions ? 'processing' : ''}`}
            >
              {isProcessingDeletions ? (
                <>
                  <span className="spinner"></span>
                  Processing {selectedDeletions.length} segments...
                </>
              ) : processing ? (
                '⏳ Processing...'
              ) : (
                `✅ Review Deletions (${selectedDeletions.length} segments)`
              )}
            </button>
          </div>
        </div>
      )}

      {/* Completion Modal */}
      {showCompletionModal && (
        <div className="modal-overlay" onClick={(e) => {
          if (e.target.className === 'modal-overlay') {
            setShowCompletionModal(false);
          }
        }}>
          <div className="modal-content">
            <div className="modal-header">
              <h3>✅ Complete</h3>
            </div>
            <div className="modal-body">
              <p>Your deletions have been prepared successfully.</p>
              <p>What would you like to do next?</p>
            </div>
            <div className="modal-actions">
              <button
                onClick={handleNavigateToResults}
                className="modal-button primary-button"
              >
                📊 Navigate to Results
              </button>
              <button
                onClick={handleReturnToUpload}
                className="modal-button secondary-button"
              >
                📁 Return to Upload
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Tab3Duplicates;
