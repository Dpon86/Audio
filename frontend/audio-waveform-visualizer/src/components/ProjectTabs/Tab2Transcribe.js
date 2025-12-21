import React, { useState, useEffect, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import './Tab2Transcribe.css';

/**
 * Tab 2: Individual File Transcription
 * Transcribe one audio file at a time
 */
const Tab2Transcribe = () => {
  const { token } = useAuth();
  const {
    projectId,
    selectedAudioFile,
    audioFiles,
    selectAudioFile,
    transcriptionData,
    setTranscriptionData,
    updateAudioFile
  } = useProjectTab();

  const [transcribing, setTranscribing] = useState(false);
  const [progress, setProgress] = useState(0);

  // Start transcription
  const startTranscription = async () => {
    if (!selectedAudioFile) return;

    setTranscribing(true);
    setProgress(0);

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/transcribe/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        // Start polling with task_id
        pollTranscriptionStatus(data.task_id);
      } else {
        const error = await response.json();
        alert(`Failed to start transcription: ${error.error || 'Unknown error'}`);
        setTranscribing(false);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
      setTranscribing(false);
    }
  };

  // Poll transcription status
  const pollTranscriptionStatus = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/status/`,
          {
            headers: {
              'Authorization': `Token ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );

        if (response.ok) {
          const data = await response.json();
          setProgress(data.progress || 0);

          if (data.completed) {
            clearInterval(interval);
            setTranscribing(false);
            
            if (data.success) {
              loadTranscription();
              // Update file status
              updateAudioFile({ ...selectedAudioFile, status: 'transcribed' });
            }
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000);
  };

  // Load transcription result
  const loadTranscription = useCallback(async () => {
    if (!selectedAudioFile) return;

    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setTranscriptionData(data);
      }
    } catch (error) {
      console.error('Error loading transcription:', error);
    }
  }, [selectedAudioFile, projectId, token, setTranscriptionData]);

  // Load existing transcription on mount or file change
  useEffect(() => {
    if (selectedAudioFile && selectedAudioFile.status === 'transcribed') {
      loadTranscription();
    }
  }, [selectedAudioFile, loadTranscription]);

  return (
    <div className="tab2-container">
      <h2>Transcribe Audio File</h2>
      
      {/* File Selector */}
      <div className="file-selector">
        <label>Select Audio File:</label>
        <select 
          value={selectedAudioFile?.id || ''}
          onChange={(e) => {
            const file = audioFiles.find(f => f.id === parseInt(e.target.value));
            selectAudioFile(file);
          }}
        >
          <option value="">-- Select a file --</option>
          {audioFiles.map(file => (
            <option key={file.id} value={file.id}>
              {file.filename} ({file.status})
            </option>
          ))}
        </select>
      </div>

      {selectedAudioFile && (
        <div className="transcription-controls">
          {!transcribing && selectedAudioFile.status === 'uploaded' && (
            <button className="start-button" onClick={startTranscription}>
              🎙️ Start Transcription
            </button>
          )}

          {transcribing && (
            <div className="progress-container">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p>{progress}% complete</p>
            </div>
          )}

          {transcriptionData && (
            <div className="transcription-result">
              <h3>Transcription Complete</h3>
              <div className="transcription-stats">
                <span>Word Count: {transcriptionData.word_count}</span>
              </div>
              <div className="transcription-text">
                <pre>{transcriptionData.full_text}</pre>
              </div>
            </div>
          )}
        </div>
      )}

      {!selectedAudioFile && (
        <div className="empty-state">
          <p>Select an audio file to begin transcription</p>
        </div>
      )}
    </div>
  );
};

export default Tab2Transcribe;
