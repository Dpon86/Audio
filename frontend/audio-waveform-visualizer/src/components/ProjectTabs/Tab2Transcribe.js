import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../../config/api';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import clientSideTranscription from '../../services/clientSideTranscription';
import './Tab2Transcribe.css';

/**
 * Tab 2: Individual File Transcription
 * Transcribe one audio file at a time
 * Supports both client-side (default) and server-side processing
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
  const [progressMessage, setProgressMessage] = useState('');
  
  // Client-side processing state
  const [useClientSide, setUseClientSide] = useState(true); // Default to client-side
  const [modelLoading, setModelLoading] = useState(false);
  const [modelProgress, setModelProgress] = useState(null);
  const [clientSideSupported, setClientSideSupported] = useState(false);

  // Check if client-side processing is supported
  useEffect(() => {
    const supported = clientSideTranscription.constructor.isSupported();
    setClientSideSupported(supported);
    if (!supported) {
      setUseClientSide(false); // Fallback to server-side if not supported
    }
  }, []);

  // Fetch the actual audio file from server
  const fetchAudioFile = async (audioFileUrl) => {
    try {
      const response = await fetch(audioFileUrl, {
        headers: {
          'Authorization': `Token ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch audio file: ${response.statusText}`);
      }
      
      const blob = await response.blob();
      const filename = selectedAudioFile.filename || 'audio.wav';
      return new File([blob], filename, { type: blob.type });
    } catch (error) {
      console.error('Error fetching audio file:', error);
      throw error;
    }
  };

  // Client-side transcription
  const transcribeClientSide = async () => {
    if (!selectedAudioFile) return;

    setTranscribing(true);
    setProgress(0);
    setProgressMessage('Fetching audio file...');

    try {
      // Fetch the audio file from server
      const audioFileUrl = selectedAudioFile.file.startsWith('http') 
        ? selectedAudioFile.file 
        : `${API_BASE_URL}${selectedAudioFile.file}`;
      
      const audioFile = await fetchAudioFile(audioFileUrl);
      
      // Initialize model if not loaded
      if (!clientSideTranscription.modelLoaded) {
        setModelLoading(true);
        setProgressMessage('Loading AI model (one-time download, ~39MB)...');
        
        await clientSideTranscription.initialize('tiny', (modelProg) => {
          setModelProgress(modelProg);
          setProgress(Math.min(modelProg.percent || 0, 30));
          setProgressMessage(modelProg.message || 'Loading model...');
        });
        
        setModelLoading(false);
      }

      // Transcribe audio
      setProgressMessage('Transcribing audio...');
      const result = await clientSideTranscription.transcribe(
        audioFile,
        {},
        (transProg) => {
          const baseProgress = clientSideTranscription.modelLoaded ? 0 : 30;
          setProgress(baseProgress + Math.round((transProg.percent || 0) * 0.7));
          setProgressMessage(transProg.message || 'Transcribing...');
        }
      );

      // Save transcription data to state
      setTranscriptionData({
        text: result.text,
        all_segments: result.all_segments || [],
        word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
        client_processed: true
      });

      // Update file status
      updateAudioFile({ ...selectedAudioFile, status: 'transcribed' });
      
      setProgress(100);
      setProgressMessage('Complete!');
      setTranscribing(false);
      
    } catch (error) {
      console.error('Client-side transcription error:', error);
      alert(`Client-side processing failed: ${error.message}\n\nTry server-side processing instead.`);
      setTranscribing(false);
      setProgress(0);
      setProgressMessage('');
      setModelLoading(false);
      setModelProgress(null);
    }
  };

  // Server-side transcription
  const transcribeServerSide = async () => {
    if (!selectedAudioFile) return;

    setTranscribing(true);
    setProgress(0);
    setProgressMessage('Starting server transcription...');

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcribe/`,
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
        setProgressMessage('Processing on server...');
        // Start polling with task_id
        pollTranscriptionStatus(data.task_id);
      } else {
        const error = await response.json();
        alert(`Failed to start transcription: ${error.error || 'Unknown error'}`);
        setTranscribing(false);
        setProgressMessage('');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
      setTranscribing(false);
      setProgressMessage('');
    }
  };

  // Start transcription (dispatch to client or server)
  const startTranscription = async () => {
    if (useClientSide) {
      await transcribeClientSide();
    } else {
      await transcribeServerSide();
    }
  };

  // Poll transcription status
  const pollTranscriptionStatus = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/status/`,
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
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
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
          disabled={transcribing}
        >
          <option value="">-- Select a file --</option>
          {audioFiles.map(file => (
            <option key={file.id} value={file.id}>
              {file.filename} ({file.status})
            </option>
          ))}
        </select>
      </div>

      {/* Processing Mode Toggle - DISABLED (server has low memory) */}
      {false && selectedAudioFile && clientSideSupported && (
        <div className="processing-mode-selector">
          <div className="processing-mode-toggle">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={useClientSide}
                onChange={(e) => setUseClientSide(e.target.checked)}
                disabled={transcribing}
              />
              <span className="toggle-text">
                {useClientSide ? '🖥️ Process on My Device' : '☁️ Process on Server'}
              </span>
            </label>
          </div>
          <div className="processing-mode-info">
            {useClientSide ? (
              <p>
                ✓ <strong>Faster</strong> - Uses your device's CPU/GPU<br />
                ✓ <strong>Private</strong> - Audio processed locally<br />
                ⓘ First use downloads AI model (~39MB, cached for future)
              </p>
            ) : (
              <p>
                ☁️ Processing on server<br />
                ⓘ Best for older devices or slow internet
              </p>
            )}
          </div>
        </div>
      )}

      {selectedAudioFile && (
        <div className="transcription-controls">
          {!transcribing && (
            <button 
              className="start-button" 
              onClick={startTranscription}
              disabled={!selectedAudioFile}
            >
              🎙️ Start Transcription {useClientSide ? '(Client-Side)' : '(Server-Side)'}
            </button>
          )}

          {transcribing && (
            <div className="progress-container">
              {modelLoading && modelProgress && (
                <div className="model-loading">
                  <p><strong>Downloading AI Model...</strong></p>
                  <p style={{ fontSize: '0.9em', color: '#666' }}>
                    This happens once. The model will be cached for future use.
                  </p>
                </div>
              )}
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p>{progress}% - {progressMessage}</p>
            </div>
          )}

          {transcriptionData && !transcribing && (
            <div className="transcription-result">
              <h3>Transcription Complete {transcriptionData.client_processed && '(Client-Side)'}</h3>
              <div className="transcription-stats">
                <span>Word Count: {transcriptionData.word_count}</span>
                <span> | Segments: {transcriptionData.all_segments?.length || 0}</span>
              </div>
              <div className="transcription-text">
                <h4>Full Text:</h4>
                <pre>{transcriptionData.text}</pre>
                
                {transcriptionData.all_segments && transcriptionData.all_segments.length > 0 && (
                  <div>
                    <h4>Segments with Timestamps:</h4>
                    <div className="segments-list">
                      {transcriptionData.all_segments.map((segment, idx) => (
                        <div key={idx} className="segment-item">
                          <span className="segment-time">
                            [{Math.floor(segment.start / 60)}:{(segment.start % 60).toFixed(1).padStart(4, '0')} - 
                            {Math.floor(segment.end / 60)}:{(segment.end % 60).toFixed(1).padStart(4, '0')}]
                          </span>
                          <span className="segment-text">{segment.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
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
