import React from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';

/**
 * Tab 4: PDF Comparison (Stub - to be fully implemented)
 */
const Tab4ComparePDF = () => {
  const { selectedAudioFile, audioFiles, selectAudioFile } = useProjectTab();

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h2>📄 Compare Transcription to PDF</h2>
      
      <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', marginTop: '2rem' }}>
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '600' }}>
            Select Audio File:
          </label>
          <select 
            value={selectedAudioFile?.id || ''}
            onChange={(e) => {
              const file = audioFiles.find(f => f.id === parseInt(e.target.value));
              selectAudioFile(file);
            }}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '6px', border: '2px solid #e0e0e0' }}
          >
            <option value="">-- Select a file --</option>
            {audioFiles.filter(f => f.status === 'transcribed' || f.status === 'processed').map(file => (
              <option key={file.id} value={file.id}>
                {file.filename} ({file.status})
              </option>
            ))}
          </select>
        </div>

        {selectedAudioFile ? (
          <div style={{ textAlign: 'center', padding: '3rem', background: '#f5f5f5', borderRadius: '8px' }}>
            <p style={{ fontSize: '1.2rem', color: '#666', marginBottom: '1rem' }}>
              PDF comparison for <strong>{selectedAudioFile.filename}</strong>
            </p>
            <p style={{ color: '#999' }}>Full implementation coming soon...</p>
            <button style={{ 
              marginTop: '1.5rem', 
              padding: '0.75rem 2rem', 
              background: '#0891b2', 
              color: 'white', 
              border: 'none', 
              borderRadius: '6px', 
              fontWeight: '600',
              cursor: 'pointer'
            }}>
              Compare to PDF
            </button>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#999' }}>
            Select a transcribed file to compare against PDF
          </div>
        )}
      </div>
    </div>
  );
};

export default Tab4ComparePDF;
