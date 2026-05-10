import re

with open('frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Grab everything before "Step 3: Review Duplicates"
blocks = text.split('{/* Step 3: Review Duplicates */}')
header = blocks[0]

# 2. Grab the good inner loop from the Results block
results_match = re.search(r'\{/\* Results \*/\}.*?<div className="duplicate-groups-list">(.*?)</div>\s*</div>\s*\)\}\s*\{/\* Completion Modal \*/\}', text, re.DOTALL)
good_inner = results_match.group(1).strip()

# 3. Assemble
new_text = header + """{/* Step 3: Review Duplicates */}
      {duplicateGroups.length > 0 && (
        <div className="review-step-card" style={{
          background: '#ffffff',
          borderRadius: '12px',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          border: '1px solid #e2e8f0',
          padding: '1.5rem',
          marginBottom: '2rem'
        }}>
          <div className="step-card-header" style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem', cursor: 'pointer' }} onClick={() => setIsReviewExpanded(!isReviewExpanded)}>
            <span className="step-badge step-badge-3" style={{
              background: '#0ea5e9',
              color: 'white',
              padding: '0.25rem 0.75rem',
              borderRadius: '9999px',
              fontSize: '0.875rem',
              fontWeight: '600',
              marginRight: '0.75rem'
            }}>Step 3</span>
            <h4 className="step-card-title" style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>
              📋 Review Detected Duplicates
            </h4>
            
            <p className="selection-summary" style={{ margin: '0 0 0 auto', color: '#475569', fontSize: '0.9rem', fontWeight: '500' }}>
              Selected: <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{selectedDeletions.length}</span>
            </p>
          </div>
          
          <p className="step-card-description" style={{ color: '#475569', marginBottom: '1.5rem' }}>
            Verify the automatically detected duplicates and make manual adjustments if needed.
          </p>

          {!isReviewExpanded ? (
            <button
              onClick={() => setIsReviewExpanded(true)}
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#f8fafc',
                border: '1px dashed #cbd5e1',
                borderRadius: '8px',
                color: '#3b82f6',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
              onMouseOver={(e) => e.currentTarget.style.background = '#f1f5f9'}
              onMouseOut={(e) => e.currentTarget.style.background = '#f8fafc'}
            >
              <span>👁️ Review each duplicate (Expand List)</span>
            </button>
          ) : (
            <div className="duplicate-results" style={{ marginTop: '1rem' }}>
              <div className="duplicate-groups-list">
""" + "\n                " + good_inner + "\n" + """              </div>

              <button
                onClick={() => setIsReviewExpanded(false)}
                style={{
                  marginTop: '1rem',
                  padding: '0.5rem',
                  background: 'transparent',
                  border: 'none',
                  color: '#64748b',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  margin: '1rem auto 0 auto'
                }}
              >
                ▲ Collapse Review List
              </button>
            </div>
          )}
        </div>
      )}

      {/* Action Buttons - Step 4: Assemble Step */}
      {duplicateGroups.length > 0 && (
        <div className="assemble-step-card" style={{
          background: '#ffffff',
          borderRadius: '12px',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          border: '1px solid #e2e8f0',
          padding: '1.5rem',
          marginBottom: '2rem'
        }}>
          <div className="step-card-header" style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="step-badge step-badge-4" style={{
              background: '#2563eb',
              color: 'white',
              padding: '0.25rem 0.75rem',
              borderRadius: '9999px',
              fontSize: '0.875rem',
              fontWeight: '600',
              marginRight: '0.75rem'
            }}>Step 4</span>
            <h4 className="step-card-title" style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>🖥️ Assemble Audio</h4>
          </div>
          <p className="step-card-description" style={{ color: '#475569', marginBottom: '1.5rem' }}>
            Select the duplicate segments to remove, then assemble the clean audio file.
          </p>
          {selectedAudioFile && (
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', background: '#f8fafc', padding: '1rem', borderRadius: '8px', border: '1px solid #f1f5f9' }}>
              <div style={{ display: 'flex', gap: '0.5rem', borderRight: '1px solid #cbd5e1', paddingRight: '1rem' }}>
                <button
                  onClick={handleSelectAllDuplicates}
                  disabled={processing || isAssemblingAudio}
                  className="secondary-button"
                  style={{
                    padding: '0.6rem 1.25rem',
                    fontSize: '0.9rem',
                    fontWeight: '600',
                    color: '#0f172a',
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    cursor: (processing || isAssemblingAudio) ? 'not-allowed' : 'pointer',
                    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    transition: 'all 0.2s'
                  }}
                  onMouseOver={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseOut={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#ffffff')}
                >
                  <span style={{ color: '#10b981' }}>✓</span> Select All
                </button>

                <button
                  onClick={handleDeselectAll}
                  disabled={processing || isAssemblingAudio || selectedDeletions.length === 0}
                  className="secondary-button"
                  style={{
                    padding: '0.6rem 1.25rem',
                    fontSize: '0.9rem',
                    fontWeight: '600',
                    color: '#0f172a',
                    background: '#ffffff',
                    border: '1px solid #cbd5e1',
                    borderRadius: '6px',
                    cursor: (processing || isAssemblingAudio || selectedDeletions.length === 0) ? 'not-allowed' : 'pointer',
                    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    opacity: (processing || isAssemblingAudio || selectedDeletions.length === 0) ? 0.6 : 1,
                    transition: 'all 0.2s'
                  }}
                  onMouseOver={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#f1f5f9')}
                  onMouseOut={(e) => !e.currentTarget.disabled && (e.currentTarget.style.background = '#ffffff')}
                >
                  <span style={{ color: '#ef4444' }}>✗</span> Deselect All
                </button>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  onClick={handleAssembleAudio}
                  disabled={selectedDeletions.length === 0 || isAssemblingAudio || processing}
                  className="confirm-button assemble-button"
                  style={{ 
                    padding: '0.75rem 1.5rem',
                    fontSize: '1rem',
                    fontWeight: '600',
                    color: 'white',
                    background: isAssemblingAudio ? '#f59e0b' : (selectedDeletions.length === 0 ? '#94a3b8' : '#22c55e'),
                    border: 'none',
                    borderRadius: '8px',
                    cursor: (selectedDeletions.length === 0 || isAssemblingAudio || processing) ? 'not-allowed' : 'pointer',
                    boxShadow: '0 4px 6px -1px rgba(34, 197, 94, 0.4), 0 2px 4px -1px rgba(34, 197, 94, 0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    transition: 'all 0.2s'
                  }}
                  onMouseOver={(e) => !e.currentTarget.disabled && isAssemblingAudio === false && (e.currentTarget.style.background = '#16a34a')}
                  onMouseOut={(e) => !e.currentTarget.disabled && isAssemblingAudio === false && (e.currentTarget.style.background = '#22c55e')}
                >
                  {isAssemblingAudio ? (
                    <>
                      <span className="spinner"></span>
                      Assembling Audio...
                    </>
                  ) : ((selectedAudioFile?.client_only || selectedAudioFile?.client_processed)
                    ? `🎵 Assemble Audio (Remove ${selectedDeletions.length} segments)`
                    : `🖥️ Assemble on Server (Remove ${selectedDeletions.length} segments)`)}
                </button>
              </div>
            </div>
          )}

          {selectedDeletions.length > 0 && assembledAudioBlob && assemblyInfo && (
            <div className="assembled-audio-info-inline">
              <span className="success-icon">✅</span>
              <span className="info-text">Audio Ready: {clientAudioAssembly.formatDuration(assemblyInfo.assembledDuration)}</span>
              <button
                onClick={handleDownloadAssembledAudio}
                className="download-button-inline"
              >
                📥 Download Audio
              </button>
            </div>
          )}
        </div>
      )}

      {/* Assembly Progress */}
      {isAssemblingAudio && assemblyProgress.status && (
        <div className="assembly-progress-inline">
          <p className="progress-status">{assemblyProgress.status}</p>
          {assemblyProgress.total > 0 && (
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${(assemblyProgress.current / assemblyProgress.total) * 100}%` }}
              />
            </div>
          )}
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
"""

with open('frontend/audio-waveform-visualizer/src/components/ProjectTabs/Tab3Duplicates.js', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Done splicing Tab3Duplicates.js!")
