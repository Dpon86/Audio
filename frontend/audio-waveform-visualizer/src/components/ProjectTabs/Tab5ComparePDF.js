import React, { useState, useEffect, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import PDFRegionSelector from '../PDFRegionSelector';
import PreciseComparisonDisplay from '../PreciseComparisonDisplay';

/**
 * Tab 5: PDF Comparison
 * Compare transcription to PDF document
 * - AI Mode: Automatic semantic comparison using GPT-4
 * - Precise Mode: Word-by-word comparison with 3-word lookahead
 * - Manual PDF region selection for precise comparisons
 * - Find where audio starts in PDF
 * - Identify missing content (in PDF but not in audio)
 * - Identify extra content (in audio but not in PDF)
 * - Allow marking sections as ignored (narrator info, chapter titles, etc.)
 * - Show side-by-side comparison with timestamps
 */
const Tab5ComparePDF = () => {
  const { selectedAudioFile, audioFiles, selectAudioFile, projectId } = useProjectTab();
  const { token } = useAuth();
  
  // Comparison mode
  const [comparisonMode, setComparisonMode] = useState('ai'); // 'ai' or 'precise'
  
  // State
  const [comparisonResults, setComparisonResults] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  
  // PDF Region Selection (for precise mode) - separate start and end
  const [showRegionSelector, setShowRegionSelector] = useState(false);
  const [regionSelectorMode, setRegionSelectorMode] = useState('start'); // 'start' or 'end'
  const [regionSelectorType, setRegionSelectorType] = useState('pdf'); // 'pdf' or 'transcript'
  const [pdfStartChar, setPdfStartChar] = useState(null);
  const [pdfEndChar, setPdfEndChar] = useState(null);
  const [pdfStartText, setPdfStartText] = useState('');
  const [pdfEndText, setPdfEndText] = useState('');
  
  // Transcript Region Selection (for precise mode)
  const [transcriptStartChar, setTranscriptStartChar] = useState(null);
  const [transcriptEndChar, setTranscriptEndChar] = useState(null);
  
  // Transcript text for comparison preview
  const [transcriptText, setTranscriptText] = useState('');
  const [transcriptStartText, setTranscriptStartText] = useState('');
  const [transcriptEndText, setTranscriptEndText] = useState('');
  
  // Side-by-side view
  const [showSideBySide, setShowSideBySide] = useState(false);
  const [sideBySideData, setSideBySideData] = useState(null);
  
  // Ignored sections
  const [ignoredSections, setIgnoredSections] = useState([]);
  const [selectedText, setSelectedText] = useState('');
  const [showIgnoreDialog, setShowIgnoreDialog] = useState(false);
  
  // Load comparison results when file is selected
  const loadComparisonResults = useCallback(async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/pdf-result/`,
        {
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.has_results) {
          setComparisonResults(data);
        }
      }
    } catch (err) {
      console.error('Failed to load comparison results:', err);
    }
  }, [selectedAudioFile, projectId, token]);
  
  const loadIgnoredSections = useCallback(async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/ignored-sections/`,
        {
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setIgnoredSections(data.ignored_sections || []);
      }
    } catch (err) {
      console.error('Failed to load ignored sections:', err);
    }
  }, [selectedAudioFile, projectId, token]);
  
  // Load data when file is selected
  useEffect(() => {
    if (selectedAudioFile) {
      loadComparisonResults();
      loadIgnoredSections();
    }
  }, [selectedAudioFile, loadComparisonResults, loadIgnoredSections]);
  
  // Wrap checkComparisonStatus in useCallback
  const checkComparisonStatus = useCallback(async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/pdf-status/`,
        {
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.completed) {
          setIsComparing(false);
          setProgress(100);
          
          // Load results
          await loadComparisonResults();
        } else {
          setProgress(data.progress || 0);
        }
        
        if (data.error) {
          setError(data.error);
          setIsComparing(false);
        }
      }
    } catch (err) {
      console.error('Failed to check status:', err);
    }
  }, [selectedAudioFile, projectId, token, loadComparisonResults]);
  
  // Poll for comparison progress
  useEffect(() => {
    if (isComparing && selectedAudioFile) {
      const interval = setInterval(() => {
        checkComparisonStatus();
      }, 2000); // Poll every 2 seconds
      
      return () => clearInterval(interval);
    }
  }, [isComparing, selectedAudioFile, checkComparisonStatus]);
  
  const startComparison = async () => {
    if (!selectedAudioFile) {
      alert('Please select an audio file first');
      return;
    }
    
    setIsComparing(true);
    setProgress(0);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/compare-pdf/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log('Comparison started:', data);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to start comparison');
        setIsComparing(false);
      }
    } catch (err) {
      setError('Network error: ' + err.message);
      setIsComparing(false);
    }
  };
  
  /**
   * Start precise word-by-word comparison
   * Requiresboth start and end positions to be selected
   */
  const startPreciseComparison = () => {
    if (!selectedAudioFile) {
      alert('Please select an audio file first');
      return;
    }
    
    // Check if both positions are selected
    if (pdfStartChar === null || pdfEndChar === null) {
      alert('Please select both start and end positions for the PDF region first');
      return;
    }
    
    // Execute comparison with selected region
    executePreciseComparison();
  };
  
  /**
   * Handle position selection (PDF or Transcript, start or end)
   */
  const handlePositionSelected = (position, text) => {
    console.log(`${regionSelectorType} ${regionSelectorMode} position selected:`, position);
    
    if (regionSelectorType === 'pdf') {
      if (regionSelectorMode === 'start') {
        setPdfStartChar(position);
        setPdfStartText(text);
      } else {
        setPdfEndChar(position);
        setPdfEndText(text);
      }
    } else if (regionSelectorType === 'transcript') {
      if (regionSelectorMode === 'start') {
        setTranscriptStartChar(position);
        // Update preview to show text from selected position
        const PREVIEW_LENGTH = 400;
        const preview = transcriptText.substring(position, Math.min(position + PREVIEW_LENGTH, transcriptText.length));
        setTranscriptStartText(preview + (position + PREVIEW_LENGTH < transcriptText.length ? '...' : ''));
      } else {
        setTranscriptEndChar(position);
        // Update preview to show text ending at selected position
        const PREVIEW_LENGTH = 400;
        const start = Math.max(0, position - PREVIEW_LENGTH);
        const preview = transcriptText.substring(start, position);
        setTranscriptEndText((start > 0 ? '...' : '') + preview);
      }
    }
    
    setShowRegionSelector(false);
  };
  
  /**
   * Execute precise comparison with selected PDF region
   */
  const executePreciseComparison = async () => {
    if (pdfStartChar === null || pdfEndChar === null) {
      alert('Please select both start and end positions');
      return;
    }
    
    if (pdfStartChar >= pdfEndChar) {
      alert('Start position must be before end position');
      return;
    }
    
    setIsComparing(true);
    setProgress(0);
    setError(null);
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/precise-compare/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            algorithm: 'precise',
            pdf_start_char: pdfStartChar,
            pdf_end_char: pdfEndChar,
            transcript_start_char: transcriptStartChar,
            transcript_end_char: transcriptEndChar
          })
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log('Precise comparison started:', data);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to start precise comparison');
        setIsComparing(false);
      }
    } catch (err) {
      setError('Network error: ' + err.message);
      setIsComparing(false);
    }
  };
  
  /**
   * Change comparison mode and reset PDF region selection
   */
  const handleModeChange = (newMode) => {
    setComparisonMode(newMode);
    setPdfStartChar(null);
    setPdfEndChar(null);
    setPdfStartText('');
    setPdfEndText('');
    setComparisonResults(null);
  };
  
  /**
   * Load transcript text and generate preview snippets
   * Prioritize: retranscribed (most accurate) > adjusted (quick preview) > original
   */
  useEffect(() => {
    if (selectedAudioFile) {
      // Select the best available transcript based on source
      let fullText = '';
      
      if (selectedAudioFile.transcript_source === 'retranscribed' && selectedAudioFile.transcript_text) {
        fullText = selectedAudioFile.transcript_text;  // Most accurate - re-transcribed processed audio
      } else if (selectedAudioFile.transcript_source === 'adjusted' && selectedAudioFile.transcript_adjusted) {
        fullText = selectedAudioFile.transcript_adjusted;  // Quick preview - segments concatenated
      } else if (selectedAudioFile.transcript_text) {
        fullText = selectedAudioFile.transcript_text;  // Original transcript (fallback)
      }
      
      if (fullText) {
        // Reset transcript positions when file changes
        setTranscriptStartChar(null);
        setTranscriptEndChar(null);
        setTranscriptText(fullText);
        
        // Generate start preview (first 400 chars)
        const PREVIEW_LENGTH = 400;
        const startPreview = fullText.substring(0, Math.min(PREVIEW_LENGTH, fullText.length));
        setTranscriptStartText(startPreview + (fullText.length > PREVIEW_LENGTH ? '...' : ''));
        
        // Generate end preview (last 400 chars)
        const endStart = Math.max(0, fullText.length - PREVIEW_LENGTH);
        const endPreview = fullText.substring(endStart);
        setTranscriptEndText((endStart > 0 ? '...' : '') + endPreview);
      } else {
        setTranscriptText('');
        setTranscriptStartText('');
        setTranscriptEndText('');
      }
    } else {
      setTranscriptText('');
      setTranscriptStartText('');
      setTranscriptEndText('');
    }
  }, [selectedAudioFile]);
  
  const loadSideBySide = async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/side-by-side/`,
        {
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setSideBySideData(data);
        setShowSideBySide(true);
      } else {
        alert('Failed to load side-by-side comparison');
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    }
  };
  
  const addIgnoredSection = async () => {
    if (!selectedText.trim()) {
      alert('Please select some text first');
      return;
    }
    
    const newSection = {
      text: selectedText,
      reason: 'user_marked',
      timestamp: new Date().toISOString()
    };
    
    const updatedIgnored = [...ignoredSections, newSection];
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/ignored-sections/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            ignored_sections: updatedIgnored,
            recompare: true // Automatically recompare after adding ignored section
          })
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setIgnoredSections(updatedIgnored);
        setShowIgnoreDialog(false);
        setSelectedText('');
        
        if (data.task_id) {
          // Comparison restarted
          setIsComparing(true);
          setProgress(0);
        }
      } else {
        const errorData = await response.json();
        alert('Failed to save ignored section: ' + (errorData.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    }
  };
  
  const removeIgnoredSection = async (index) => {
    const updatedIgnored = ignoredSections.filter((_, i) => i !== index);
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/ignored-sections/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            ignored_sections: updatedIgnored,
            recompare: true
          })
        }
      );
      
      if (response.ok) {
        setIgnoredSections(updatedIgnored);
        setIsComparing(true);
      }
    } catch (err) {
      alert('Failed to remove ignored section: ' + err.message);
    }
  };
  
  const resetComparison = async () => {
    if (!window.confirm('Reset PDF comparison? This will clear all results and ignored sections.')) {
      return;
    }
    
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/reset-comparison/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`
          },
          credentials: 'include'
        }
      );
      
      if (response.ok) {
        setComparisonResults(null);
        setIgnoredSections([]);
        setSideBySideData(null);
        setShowSideBySide(false);
        setError(null);
      }
    } catch (err) {
      alert('Failed to reset comparison: ' + err.message);
    }
  };
  
  const getQualityColor = (quality) => {
    switch (quality) {
      case 'excellent': return '#10b981';
      case 'good': return '#3b82f6';
      case 'fair': return '#f59e0b';
      case 'poor': return '#ef4444';
      default: return '#6b7280';
    }
  };
  
  // Format time in seconds to MM:SS
  const formatTime = (seconds) => {
    if (seconds === undefined || seconds === null) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  // Handle marking content for deletion
  const handleMarkForDeletion = async (item) => {
    if (item.start_time === undefined || item.end_time === undefined) {
      alert('No timestamp information available for this item');
      return;
    }
    
    const confirmMsg = `Mark content for deletion?\n\nTime Range: ${formatTime(item.start_time)} - ${formatTime(item.end_time)}\nType: ${item.possible_type}\nText: ${item.text.substring(0, 100)}${item.text.length > 100 ? '...' : ''}`;
    
    if (!window.confirm(confirmMsg)) {
      return;
    }
    
    try {
      // Use the timestamps to mark segments for deletion
      // This will integrate with the existing deletion workflow
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/mark-for-deletion/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify({
            start_time: item.start_time,
            end_time: item.end_time,
            text: item.text,
            reason: 'pdf_comparison_extra_content',
            type: item.possible_type,
            timestamps: item.timestamps || []
          })
        }
      );
      
      if (response.ok) {
        alert('Content marked for deletion successfully! You can review it in the Results tab.');
      } else {
        const errorData = await response.json();
        alert('Failed to mark for deletion: ' + (errorData.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    }
  };
  
  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <h2>📄 Compare Transcription to PDF</h2>
      <p style={{ color: '#666', marginBottom: '2rem' }}>
        Find where the audio starts in the PDF, identify missing or extra content, and mark sections to ignore.
      </p>
      
      {/* File Selection */}
      <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '600' }}>
          Select Audio File:
        </label>
        <select 
          value={selectedAudioFile?.id || ''}
          onChange={(e) => {
            const file = audioFiles.find(f => f.id === parseInt(e.target.value));
            selectAudioFile(file);
            setShowSideBySide(false);
          }}
          style={{ 
            width: '100%', 
            padding: '0.75rem', 
            borderRadius: '6px', 
            border: '2px solid #e0e0e0',
            fontSize: '1rem'
          }}
        >
          <option value="">-- Select a file --</option>
          {audioFiles.filter(f => f.status === 'transcribed' || f.status === 'processed').map(file => (
            <option key={file.id} value={file.id}>
              {file.filename} ({file.status})
            </option>
          ))}
        </select>
      </div>
      
      {selectedAudioFile && (
        <>
          {/* Comparison Mode Selection */}
          <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <h3 style={{ marginBottom: '1rem', color: '#1e293b' }}>Comparison Algorithm</h3>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button
                onClick={() => handleModeChange('ai')}
                style={{
                  flex: 1,
                  padding: '1rem',
                  background: comparisonMode === 'ai' 
                    ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' 
                    : '#f1f5f9',
                  color: comparisonMode === 'ai' ? 'white' : '#475569',
                  border: comparisonMode === 'ai' ? 'none' : '2px solid #cbd5e1',
                  borderRadius: '8px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
              >
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>🤖</div>
                <div style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>AI Mode</div>
                <div style={{ fontSize: '0.85rem', opacity: 0.9 }}>
                  Semantic understanding with GPT-4
                </div>
              </button>
              
              <button
                onClick={() => handleModeChange('precise')}
                style={{
                  flex: 1,
                  padding: '1rem',
                  background: comparisonMode === 'precise' 
                    ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' 
                    : '#f1f5f9',
                  color: comparisonMode === 'precise' ? 'white' : '#475569',
                  border: comparisonMode === 'precise' ? 'none' : '2px solid #cbd5e1',
                  borderRadius: '8px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.3s'
                }}
              >
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>🎯</div>
                <div style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>Precise Mode</div>
                <div style={{ fontSize: '0.85rem', opacity: 0.9 }}>
                  Word-by-word with 3-word lookahead
                </div>
              </button>
            </div>
            
            {/* PDF and Transcript Comparison Preview (Precise Mode) */}
            {comparisonMode === 'precise' && (
              <div style={{ marginTop: '2rem' }}>
                <h4 style={{ marginBottom: '1rem', color: '#1e293b' }}>
                  Region Selection & Preview
                </h4>
                
                {/* Start Position Comparison */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: '1fr 1fr', 
                  gap: '1rem', 
                  marginBottom: '1rem' 
                }}>
                  {/* PDF Start */}
                  <div style={{ 
                    padding: '1rem', 
                    background: pdfStartChar !== null ? '#f0fdf4' : '#f9fafb',
                    border: pdfStartChar !== null ? '2px solid #10b981' : '2px dashed #d1d5db',
                    borderRadius: '6px'
                  }}>
                    <div style={{ 
                      fontWeight: '600', 
                      color: pdfStartChar !== null ? '#065f46' : '#6b7280', 
                      marginBottom: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span>📄 PDF Start</span>
                      {pdfStartChar !== null && (
                        <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                          Char {pdfStartChar}
                        </span>
                      )}
                    </div>
                    {pdfStartChar !== null ? (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#047857', 
                        lineHeight: '1.5',
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {pdfStartText}
                      </div>
                    ) : (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#9ca3af', 
                        fontStyle: 'italic' 
                      }}>
                        Not selected
                      </div>
                    )}
                    <button
                      onClick={() => {
                        setRegionSelectorMode('start');
                        setShowRegionSelector(true);
                      }}
                      style={{
                        marginTop: '0.75rem',
                        width: '100%',
                        padding: '0.5rem 1rem',
                        background: pdfStartChar !== null ? 'white' : '#10b981',
                        color: pdfStartChar !== null ? '#059669' : 'white',
                        border: pdfStartChar !== null ? '2px solid #10b981' : 'none',
                        borderRadius: '6px',
                        fontWeight: '500',
                        cursor: 'pointer',
                        fontSize: '0.875rem'
                      }}
                    >
                      {pdfStartChar !== null ? '📝 Change Start' : '📄 Select Start'}
                    </button>
                  </div>
                  
                  {/* Transcript Start */}
                  <div style={{ 
                    padding: '1rem', 
                    background: transcriptStartChar !== null ? '#eff6ff' : '#f9fafb',
                    border: transcriptStartChar !== null ? '2px solid #3b82f6' : '2px dashed #d1d5db',
                    borderRadius: '6px'
                  }}>
                    <div style={{ 
                      fontWeight: '600', 
                      color: transcriptStartChar !== null ? '#1e40af' : '#6b7280', 
                      marginBottom: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span>🎤 Transcript Start</span>
                      {transcriptStartChar !== null && (
                        <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                          Char {transcriptStartChar}
                        </span>
                      )}
                    </div>
                    {transcriptStartChar !== null ? (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#1d4ed8', 
                        lineHeight: '1.5',
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {transcriptStartText}
                      </div>
                    ) : (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#9ca3af', 
                        fontStyle: 'italic' 
                      }}>
                        {transcriptText ? 'Not selected (using beginning)' : 'No transcript available'}
                      </div>
                    )}
                    {transcriptText && (
                      <button
                        onClick={() => {
                          setRegionSelectorType('transcript');
                          setRegionSelectorMode('start');
                          setShowRegionSelector(true);
                        }}
                        style={{
                          marginTop: '0.75rem',
                          width: '100%',
                          padding: '0.5rem 1rem',
                          background: transcriptStartChar !== null ? 'white' : '#3b82f6',
                          color: transcriptStartChar !== null ? '#2563eb' : 'white',
                          border: transcriptStartChar !== null ? '2px solid #3b82f6' : 'none',
                          borderRadius: '6px',
                          fontWeight: '500',
                          cursor: 'pointer',
                          fontSize: '0.875rem'
                        }}
                      >
                        {transcriptStartChar !== null ? '📝 Change Start' : '🎤 Select Start'}
                      </button>
                    )}
                  </div>
                </div>
                
                {/* End Position Comparison */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: '1fr 1fr', 
                  gap: '1rem' 
                }}>
                  {/* PDF End */}
                  <div style={{ 
                    padding: '1rem', 
                    background: pdfEndChar !== null ? '#f0fdf4' : '#f9fafb',
                    border: pdfEndChar !== null ? '2px solid #10b981' : '2px dashed #d1d5db',
                    borderRadius: '6px'
                  }}>
                    <div style={{ 
                      fontWeight: '600', 
                      color: pdfEndChar !== null ? '#065f46' : '#6b7280', 
                      marginBottom: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span>📄 PDF End</span>
                      {pdfEndChar !== null && (
                        <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                          Char {pdfEndChar}
                        </span>
                      )}
                    </div>
                    {pdfEndChar !== null ? (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#047857', 
                        lineHeight: '1.5',
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {pdfEndText}
                      </div>
                    ) : (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#9ca3af', 
                        fontStyle: 'italic' 
                      }}>
                        Not selected
                      </div>
                    )}
                    <button
                      onClick={() => {
                        setRegionSelectorMode('end');
                        setShowRegionSelector(true);
                      }}
                      style={{
                        marginTop: '0.75rem',
                        width: '100%',
                        padding: '0.5rem 1rem',
                        background: pdfEndChar !== null ? 'white' : '#10b981',
                        color: pdfEndChar !== null ? '#059669' : 'white',
                        border: pdfEndChar !== null ? '2px solid #10b981' : 'none',
                        borderRadius: '6px',
                        fontWeight: '500',
                        cursor: 'pointer',
                        fontSize: '0.875rem'
                      }}
                    >
                      {pdfEndChar !== null ? '📝 Change End' : '📄 Select End'}
                    </button>
                  </div>
                  
                  {/* Transcript End */}
                  <div style={{ 
                    padding: '1rem', 
                    background: transcriptEndChar !== null ? '#eff6ff' : '#f9fafb',
                    border: transcriptEndChar !== null ? '2px solid #3b82f6' : '2px dashed #d1d5db',
                    borderRadius: '6px'
                  }}>
                    <div style={{ 
                      fontWeight: '600', 
                      color: transcriptEndChar !== null ? '#1e40af' : '#6b7280', 
                      marginBottom: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span>🎤 Transcript End</span>
                      {transcriptEndChar !== null && (
                        <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>
                          Char {transcriptEndChar}
                        </span>
                      )}
                    </div>
                    {transcriptEndChar !== null ? (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#1d4ed8', 
                        lineHeight: '1.5',
                        fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap'
                      }}>
                        {transcriptEndText}
                      </div>
                    ) : (
                      <div style={{ 
                        fontSize: '0.875rem', 
                        color: '#9ca3af', 
                        fontStyle: 'italic' 
                      }}>
                        {transcriptText ? 'Not selected (using end)' : 'No transcript available'}
                      </div>
                    )}
                    {transcriptText && (
                      <button
                        onClick={() => {
                          setRegionSelectorType('transcript');
                          setRegionSelectorMode('end');
                          setShowRegionSelector(true);
                        }}
                        style={{
                          marginTop: '0.75rem',
                          width: '100%',
                          padding: '0.5rem 1rem',
                          background: transcriptEndChar !== null ? 'white' : '#3b82f6',
                          color: transcriptEndChar !== null ? '##2563eb' : 'white',
                          border: transcriptEndChar !== null ? '2px solid #3b82f6' : 'none',
                          borderRadius: '6px',
                          fontWeight: '500',
                          cursor: 'pointer',
                          fontSize: '0.875rem'
                        }}
                      >
                        {transcriptEndChar !== null ? '📝 Change End' : '🎤 Select End'}
                      </button>
                    )}
                  </div>
                </div>
                
                {/* Selection Summary */}
                {pdfStartChar !== null && pdfEndChar !== null && (
                  <div style={{ 
                    marginTop: '1rem', 
                    padding: '0.75rem', 
                    background: '#fef3c7', 
                    borderRadius: '6px',
                    fontSize: '0.875rem',
                    color: '#92400e',
                    textAlign: 'center'
                  }}>
                    ✓ PDF region selected: {pdfEndChar - pdfStartChar} characters ({pdfStartChar} to {pdfEndChar})
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Action Buttons */}
          <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <button
                onClick={comparisonMode === 'ai' ? startComparison : startPreciseComparison}
                disabled={isComparing || (comparisonMode === 'precise' && (pdfStartChar === null || pdfEndChar === null))}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: isComparing ? '#9ca3af' : (
                    comparisonMode === 'precise' && (pdfStartChar === null || pdfEndChar === null)
                      ? '#d1d5db'
                      : (comparisonMode === 'ai' ? '#0891b2' : '#10b981')
                  ),
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: '600',
                  cursor: isComparing || (comparisonMode === 'precise' && (pdfStartChar === null || pdfEndChar === null))
                    ? 'not-allowed' 
                    : 'pointer',
                  fontSize: '1rem'
                }}
              >
                {isComparing 
                  ? '🔄 Comparing...' 
                  : comparisonMode === 'ai' 
                    ? '▶️ Start AI Comparison' 
                    : (pdfStartChar !== null && pdfEndChar !== null)
                      ? '▶️ Start Precise Comparison'
                      : '⚠️ Select Start & End Positions First'
                }
              </button>
              
              {comparisonResults && (
                <>
                  <button
                    onClick={loadSideBySide}
                    style={{
                      padding: '0.75rem 1.5rem',
                      background: '#6366f1',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    📊 View Side-by-Side
                  </button>
                  
                  <button
                    onClick={() => setShowIgnoreDialog(!showIgnoreDialog)}
                    style={{
                      padding: '0.75rem 1.5rem',
                      background: '#f59e0b',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    🚫 Manage Ignored Sections ({ignoredSections.length})
                  </button>
                </>
              )}
              
              {comparisonResults && (
                <button
                  onClick={resetComparison}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  🔄 Reset
                </button>
              )}
            </div>
            
            {/* Progress Bar */}
            {isComparing && (
              <div style={{ marginTop: '1.5rem' }}>
                <div style={{ 
                  background: '#e5e7eb', 
                  borderRadius: '8px', 
                  overflow: 'hidden',
                  height: '24px'
                }}>
                  <div style={{
                    background: '#0891b2',
                    height: '100%',
                    width: `${progress}%`,
                    transition: 'width 0.3s',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontWeight: '600',
                    fontSize: '0.875rem'
                  }}>
                    {progress}%
                  </div>
                </div>
              </div>
            )}
            
            {error && (
              <div style={{ 
                marginTop: '1rem', 
                padding: '1rem', 
                background: '#fee2e2', 
                borderRadius: '6px',
                color: '#dc2626'
              }}>
                ❌ {error}
              </div>
            )}
          </div>
          
          {/* Comparison Results */}
          {comparisonResults && comparisonResults.matched_regions && (
            // Precise comparison results - use specialized display
            <PreciseComparisonDisplay 
              results={comparisonResults}
              onPlayAudio={(time) => {
                // TODO: Implement audio playback at specific timestamp
                console.log('Play audio at:', time);
                alert(`Audio playback at ${time}s not yet implemented. This will seek to the timestamp in the audio player.`);
              }}
            />
          )}
          
          {comparisonResults && comparisonResults.statistics && !comparisonResults.matched_regions && (
            // AI comparison results - use original display
            <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
              <h3 style={{ marginTop: 0 }}>📊 AI Comparison Statistics</h3>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
                <div style={{ padding: '1rem', background: '#f3f4f6', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Match Quality</div>
                  <div style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '600', 
                    color: getQualityColor(comparisonResults.statistics.match_quality)
                  }}>
                    {comparisonResults.statistics.match_quality?.toUpperCase() || 'N/A'}
                  </div>
                </div>
                
                <div style={{ padding: '1rem', background: '#f3f4f6', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Coverage</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#0891b2' }}>
                    {comparisonResults.statistics.coverage_percentage?.toFixed(1) || 0}%
                  </div>
                </div>
                
                <div style={{ padding: '1rem', background: '#f3f4f6', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Accuracy</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#6366f1' }}>
                    {comparisonResults.statistics.accuracy_percentage?.toFixed(1) || 0}%
                  </div>
                </div>
                
                <div style={{ padding: '1rem', background: '#f3f4f6', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Match Confidence</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#10b981' }}>
                    {(comparisonResults.match_result?.confidence * 100)?.toFixed(1) || 0}%
                  </div>
                </div>
              </div>
              
              {/* Word Counts */}
              <div style={{ marginTop: '2rem' }}>
                <h4>Word Counts</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
                  <div style={{ padding: '1rem', background: '#f9fafb', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Transcript Words</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>
                      {comparisonResults.statistics.transcript_word_count?.toLocaleString() || 0}
                    </div>
                  </div>
                  
                  <div style={{ padding: '1rem', background: '#f9fafb', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>PDF Words</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>
                      {comparisonResults.statistics.pdf_word_count?.toLocaleString() || 0}
                    </div>
                  </div>
                  
                  <div style={{ padding: '1rem', background: '#fef3c7', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.875rem', color: '#92400e' }}>Missing Words</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#d97706' }}>
                      {comparisonResults.statistics.missing_word_count?.toLocaleString() || 0}
                    </div>
                  </div>
                  
                  <div style={{ padding: '1rem', background: '#dbeafe', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.875rem', color: '#1e3a8a' }}>Extra Words</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#2563eb' }}>
                      {comparisonResults.statistics.extra_word_count?.toLocaleString() || 0}
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Matched PDF Section */}
              {comparisonResults.match_result && comparisonResults.match_result.matched_section && (
                <div style={{ marginTop: '2rem' }}>
                  <h4>📄 Matched PDF Section</h4>
                  <div style={{ 
                    padding: '1rem', 
                    background: '#f0fdf4', 
                    borderRadius: '6px', 
                    border: '1px solid #86efac',
                    marginTop: '1rem'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.875rem', color: '#166534' }}>
                      <div>
                        <strong>Start Position:</strong> {comparisonResults.match_result.start_char} | 
                        <strong> End Position:</strong> {comparisonResults.match_result.end_char} | 
                        <strong> Confidence:</strong> {(comparisonResults.match_result.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div style={{ 
                      maxHeight: '200px', 
                      overflowY: 'auto', 
                      padding: '1rem', 
                      background: 'white', 
                      borderRadius: '4px',
                      fontSize: '0.875rem',
                      lineHeight: '1.6'
                    }}>
                      {comparisonResults.match_result.matched_section}
                    </div>
                    {comparisonResults.match_result.start_preview && (
                      <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#166534' }}>
                        <strong>Preview Start:</strong> ...{comparisonResults.match_result.start_preview}...
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Missing Content */}
              {comparisonResults.missing_content && comparisonResults.missing_content.length > 0 && (
                <div style={{ marginTop: '2rem' }}>
                  <h4>❌ Missing Content (in PDF but not in Audio)</h4>
                  <div style={{ 
                    maxHeight: '300px', 
                    overflowY: 'auto', 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '6px',
                    padding: '1rem',
                    background: '#fef3c7'
                  }}>
                    {comparisonResults.missing_content.map((item, index) => (
                      <div key={index} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #fde68a' }}>
                        <div style={{ fontSize: '0.875rem', color: '#92400e', marginBottom: '0.25rem' }}>
                          {item.word_count} words
                        </div>
                        <div>{item.text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Extra Content */}
              {comparisonResults.extra_content && comparisonResults.extra_content.length > 0 && (
                <div style={{ marginTop: '2rem' }}>
                  <h4>➕ Extra Content (in Audio but not in PDF)</h4>
                  <div style={{ 
                    maxHeight: '300px', 
                    overflowY: 'auto', 
                    border: '1px solid #e5e7eb', 
                    borderRadius: '6px',
                    padding: '1rem',
                    background: '#dbeafe'
                  }}>
                    {comparisonResults.extra_content.map((item, index) => (
                      <div key={index} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #bfdbfe' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                          <div style={{ fontSize: '0.875rem', color: '#1e3a8a' }}>
                            {item.word_count} words · Type: <strong>{item.possible_type}</strong>
                            {item.start_time !== undefined && item.end_time !== undefined && (
                              <span style={{ marginLeft: '1rem', color: '#0891b2', fontWeight: '600' }}>
                                🕒 {formatTime(item.start_time)} - {formatTime(item.end_time)}
                              </span>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            {item.start_time !== undefined && item.end_time !== undefined && (
                              <button
                                onClick={() => handleMarkForDeletion(item)}
                                style={{
                                  padding: '0.25rem 0.75rem',
                                  background: '#dc2626',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  fontSize: '0.75rem',
                                  cursor: 'pointer'
                                }}
                              >
                                Mark for Deletion
                              </button>
                            )}
                            {item.possible_type !== 'other' && (
                              <button
                                onClick={() => {
                                  setSelectedText(item.text);
                                  setShowIgnoreDialog(true);
                                }}
                                style={{
                                  padding: '0.25rem 0.75rem',
                                  background: '#f59e0b',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  fontSize: '0.75rem',
                                  cursor: 'pointer'
                                }}
                              >
                                Ignore This
                              </button>
                            )}
                          </div>
                        </div>
                        <div>{item.text}</div>
                        {item.timestamps && item.timestamps.length > 1 && (
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.5rem', fontStyle: 'italic' }}>
                            Found in {item.timestamps.length} segments
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Ignored Sections Dialog */}
          {showIgnoreDialog && (
            <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem', border: '2px solid #f59e0b' }}>
              <h3 style={{ marginTop: 0 }}>🚫 Manage Ignored Sections</h3>
              
              {/* Add New Ignored Section */}
              <div style={{ marginBottom: '2rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '600' }}>
                  Text to Ignore:
                </label>
                <textarea
                  value={selectedText}
                  onChange={(e) => setSelectedText(e.target.value)}
                  placeholder="Enter text to ignore (e.g., 'Narrated by John Doe')"
                  style={{
                    width: '100%',
                    minHeight: '100px',
                    padding: '0.75rem',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    fontSize: '1rem',
                    fontFamily: 'inherit'
                  }}
                />
                <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                  <button
                    onClick={addIgnoredSection}
                    disabled={!selectedText.trim()}
                    style={{
                      padding: '0.75rem 1.5rem',
                      background: selectedText.trim() ? '#f59e0b' : '#9ca3af',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontWeight: '600',
                      cursor: selectedText.trim() ? 'pointer' : 'not-allowed'
                    }}
                  >
                    ➕ Add Ignored Section
                  </button>
                  
                  <button
                    onClick={() => {
                      setShowIgnoreDialog(false);
                      setSelectedText('');
                    }}
                    style={{
                      padding: '0.75rem 1.5rem',
                      background: '#6b7280',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontWeight: '600',
                      cursor: 'pointer'
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>
              
              {/* Current Ignored Sections */}
              {ignoredSections.length > 0 && (
                <div>
                  <h4>Current Ignored Sections ({ignoredSections.length})</h4>
                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {ignoredSections.map((section, index) => (
                      <div key={index} style={{ 
                        padding: '1rem', 
                        marginBottom: '0.5rem', 
                        background: '#fef3c7', 
                        borderRadius: '6px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start'
                      }}>
                        <div style={{ flex: 1 }}>{section.text}</div>
                        <button
                          onClick={() => removeIgnoredSection(index)}
                          style={{
                            padding: '0.25rem 0.75rem',
                            background: '#ef4444',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            fontSize: '0.875rem',
                            cursor: 'pointer',
                            marginLeft: '1rem'
                          }}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Side-by-Side View */}
          {showSideBySide && sideBySideData && (
            <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>📊 Side-by-Side Comparison</h3>
                <button
                  onClick={() => setShowSideBySide(false)}
                  style={{
                    padding: '0.5rem 1rem',
                    background: '#6b7280',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer'
                  }}
                >
                  Close
                </button>
              </div>
              
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: '1fr 1fr', 
                gap: '1rem',
                maxHeight: '600px',
                overflowY: 'auto',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                padding: '1rem'
              }}>
                {/* Transcription Column */}
                <div>
                  <h4 style={{ 
                    position: 'sticky', 
                    top: 0, 
                    background: '#f3f4f6', 
                    margin: '-1rem -1rem 1rem -1rem',
                    padding: '1rem',
                    borderRadius: '6px 6px 0 0'
                  }}>
                    Audio Transcription
                  </h4>
                  {sideBySideData.segments.map((segment, index) => {
                    if (segment.type === 'pdf_only') return null;
                    
                    return (
                      <div 
                        key={index} 
                        style={{ 
                          padding: '0.75rem',
                          marginBottom: '0.5rem',
                          borderRadius: '4px',
                          background: segment.type === 'match' ? '#d1fae5' : '#fed7aa',
                          border: segment.type === 'match' ? '1px solid #6ee7b7' : '1px solid #fdba74'
                        }}
                      >
                        {segment.transcription_text}
                      </div>
                    );
                  })}
                </div>
                
                {/* PDF Column */}
                <div>
                  <h4 style={{ 
                    position: 'sticky', 
                    top: 0, 
                    background: '#f3f4f6', 
                    margin: '-1rem -1rem 1rem -1rem',
                    padding: '1rem',
                    borderRadius: '6px 6px 0 0'
                  }}>
                    PDF Document
                  </h4>
                  {sideBySideData.segments.map((segment, index) => {
                    if (segment.type === 'extra') return null;
                    
                    return (
                      <div 
                        key={index} 
                        style={{ 
                          padding: '0.75rem',
                          marginBottom: '0.5rem',
                          borderRadius: '4px',
                          background: segment.type === 'match' ? '#d1fae5' : '#fecaca',
                          border: segment.type === 'match' ? '1px solid #6ee7b7' : '1px solid #fca5a5'
                        }}
                      >
                        {segment.pdf_text}
                      </div>
                    );
                  })}
                </div>
              </div>
              
              {/* Legend */}
              <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '20px', height: '20px', background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: '4px' }}></div>
                  <span>Matching content</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '20px', height: '20px', background: '#fed7aa', border: '1px solid #fdba74', borderRadius: '4px' }}></div>
                  <span>Extra in transcription</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '20px', height: '20px', background: '#fecaca', border: '1px solid #fca5a5', borderRadius: '4px' }}></div>
                  <span>Missing from transcription</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
      
      {/* PDF Region Selector Modal */}
      {showRegionSelector && (
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
          <div style={{
            maxWidth: '1200px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <PDFRegionSelector
              projectId={projectId}
              mode={regionSelectorMode}
              type={regionSelectorType}
              currentStart={regionSelectorType === 'pdf' ? pdfStartChar : transcriptStartChar}
              currentEnd={regionSelectorType === 'pdf' ? pdfEndChar : transcriptEndChar}
              transcriptText={transcriptText}
              onPositionSelected={handlePositionSelected}
              onCancel={() => setShowRegionSelector(false)}
            />
          </div>
        </div>
      )}
      
      {/* Empty State */}
      {!selectedAudioFile && (
        <div style={{ 
          textAlign: 'center', 
          padding: '4rem', 
          background: '#f9fafb', 
          borderRadius: '8px',
          color: '#6b7280'
        }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📄</div>
          <p style={{ fontSize: '1.1rem' }}>Select an audio file to begin PDF comparison</p>
        </div>
      )}
    </div>
  );
};

export default Tab5ComparePDF;
