import React, { useState, useEffect, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';

/**
 * Tab 5: PDF Comparison
 * Compare transcription to PDF document
 * - Find where audio starts in PDF
 * - Identify missing content (in PDF but not in audio)
 * - Identify extra content (in audio but not in PDF)
 * - Allow marking sections as ignored (narrator info, chapter titles, etc.)
 * - Show side-by-side comparison
 */
const Tab5ComparePDF = () => {
  const { selectedAudioFile, audioFiles, selectAudioFile, projectId } = useProjectTab();
  const { token } = useAuth();
  
  // State
  const [comparisonResults, setComparisonResults] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  
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
          {/* Action Buttons */}
          <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <button
                onClick={startComparison}
                disabled={isComparing}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: isComparing ? '#9ca3af' : '#0891b2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: '600',
                  cursor: isComparing ? 'not-allowed' : 'pointer',
                  fontSize: '1rem'
                }}
              >
                {isComparing ? '🔄 Comparing...' : '▶️ Start Comparison'}
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
          {comparisonResults && comparisonResults.statistics && (
            <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginBottom: '2rem' }}>
              <h3 style={{ marginTop: 0 }}>📊 Comparison Statistics</h3>
              
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
