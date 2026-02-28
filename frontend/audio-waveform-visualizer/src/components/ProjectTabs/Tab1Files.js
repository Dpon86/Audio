import React, { useEffect, useState, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import clientSideTranscription from '../../services/clientSideTranscription';
import './Tab1Files.css';

/**
 * Tab 1: Upload & Transcribe
 * Upload audio files and transcribe them inline with status monitoring
 */
const Tab1Files = () => {
  const { token } = useAuth();
  const {
    projectId,
    audioFiles,
    refreshAudioFiles,
    removeAudioFile,
    projectData,
    setProjectData,
    refreshProjectData,
    selectedAudioFile,
    selectAudioFile
  } = useProjectTab();

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [transcribingFiles, setTranscribingFiles] = useState({}); // Track which files are transcribing
  const [taskIds, setTaskIds] = useState({}); // Track Celery task IDs
  const [uploadingPdf, setUploadingPdf] = useState(false);
  
  // Client-side processing state
  const [useClientSide, setUseClientSide] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelProgress, setModelProgress] = useState(null);
  const [clientSideSupported, setClientSideSupported] = useState(false);

  // Load project data including PDF info on mount
  useEffect(() => {
    if (token) {
      refreshProjectData(token);
    }
    // Check if client-side processing is supported
    setClientSideSupported(clientSideTranscription.constructor.isSupported());
  }, [refreshProjectData, token]);

  // Load files on mount and set up polling
  useEffect(() => {
    refreshAudioFiles(token);
    
    // Poll for updates every 5 seconds if any files are transcribing
    const interval = setInterval(() => {
      if (Object.keys(transcribingFiles).length > 0) {
        refreshAudioFiles(token);
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [refreshAudioFiles, token, transcribingFiles]);

  // Check for completed transcriptions or failures
  useEffect(() => {
    audioFiles.forEach(file => {
      if (transcribingFiles[file.id]) {
        const hasTranscription = !!(file.transcription && file.transcription.text);
        const hasFailureWithoutTranscription = (file.status === 'failed' || file.error_message) && !hasTranscription;

        // Check if transcription completed successfully
        if (hasTranscription) {
          // Transcription completed!
          setTranscribingFiles(prev => {
            const updated = { ...prev };
            delete updated[file.id];
            return updated;
          });
          setTaskIds(prev => {
            const updated = { ...prev };
            delete updated[file.id];
            return updated;
          });
        }
        // Check if transcription failed (status is 'failed' or error_message exists)
        else if (hasFailureWithoutTranscription) {
          // Transcription failed - reset so user can try again
          setTranscribingFiles(prev => {
            const updated = { ...prev };
            delete updated[file.id];
            return updated;
          });
          setTaskIds(prev => {
            const updated = { ...prev };
            delete updated[file.id];
            return updated;
          });
        }
      }
    });
  }, [audioFiles, transcribingFiles]);

  // Process file client-side
  const processFileClientSide = async (file) => {
    setUploading(true);
    setUploadProgress(0);

    try {
      // Initialize model if not loaded
      if (!clientSideTranscription.modelLoaded) {
        setModelLoading(true);
        await clientSideTranscription.initialize('tiny', (progress) => {
          setModelProgress(progress);
          setUploadProgress(Math.min(progress.percent || 0, 30));
        });
        setModelLoading(false);
      }

      // Transcribe audio
      const result = await clientSideTranscription.transcribe(
        file,
        {},
        (progress) => {
          setUploadProgress(30 + Math.round((progress.percent || 0) * 0.4));
        }
      );

      setUploadProgress(70);

      // Now upload the file with transcription data to the server
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', file.name.replace(/\.[^/.]+$/, ''));
      formData.append('transcription_data', JSON.stringify({
        text: result.text,
        segments: result.all_segments || [],
        client_processed: true
      }));

      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/files/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`
        },
        body: formData
      });

      if (response.ok) {
        setUploadProgress(100);
        await refreshAudioFiles(token);
      } else {
        let errorMessage = `Failed to upload ${file.name}`;
        try {
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            const error = await response.json();
            errorMessage = error.error || error.message || errorMessage;
          } else {
            errorMessage = `Server error (${response.status}): ${response.statusText}`;
          }
        } catch (parseError) {
          console.error('Error parsing response:', parseError);
          errorMessage = `Server error (${response.status}): ${response.statusText}`;
        }
        alert(errorMessage);
      }

      setUploading(false);
      setUploadProgress(0);
      setModelLoading(false);
      setModelProgress(null);
    } catch (error) {
      console.error('Client-side processing error:', error);
      alert(`Client-side processing failed: ${error.message}\n\nPlease try server-side processing instead.`);
      setUploading(false);
      setUploadProgress(0);
      setModelLoading(false);
      setModelProgress(null);
      setUseClientSide(false); // Fallback to server-side
    }
  };

  // Handle file upload
  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    // If client-side processing is enabled and only one file, use client-side
    if (useClientSide && files.length === 1) {
      await processFileClientSide(files[0]);
      return;
    } else if (useClientSide && files.length > 1) {
      alert('Client-side processing currently supports one file at a time. Processing first file only.');
      await processFileClientSide(files[0]);
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('file', file);  // Backend expects 'file' not 'audio_file'
      formData.append('title', file.name.replace(/\.[^/.]+$/, ''));  // Remove extension for title

      try {
        const response = await fetch(`http://localhost:8000/api/projects/${projectId}/files/`, {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`
          },
          body: formData
        });

        if (response.ok) {
          await response.json();
          setUploadProgress(Math.round(((i + 1) / files.length) * 100));
          
          // Refresh list after each upload
          await refreshAudioFiles(token);
        } else {
          // Try to parse error as JSON, but handle HTML responses
          let errorMessage = `Failed to upload ${file.name}`;
          try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
              const error = await response.json();
              errorMessage = error.error || error.message || errorMessage;
            } else {
              // HTML or other non-JSON response
              const text = await response.text();
              console.error('Server returned non-JSON error:', text);
              errorMessage = `Server error (${response.status}): ${response.statusText}`;
            }
          } catch (parseError) {
            console.error('Error parsing response:', parseError);
            errorMessage = `Server error (${response.status}): ${response.statusText}`;
          }
          alert(errorMessage);
        }
      } catch (error) {
        console.error('Upload error:', error);
        alert(`Error uploading ${file.name}: ${error.message}`);
      }
    }

    setUploading(false);
    setUploadProgress(0);
  };

  // Handle file deletion
  const handleDelete = async (fileId) => {
    if (!window.confirm('Are you sure you want to delete this audio file?')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/files/${fileId}/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        removeAudioFile(fileId);
      } else {
        const error = await response.json();
        alert(`Failed to delete file: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      alert(`Error deleting file: ${error.message}`);
    }
  };

  // Drag and drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  // Handle transcription
  const handleTranscribe = async (fileId) => {
    try {
      setTranscribingFiles(prev => ({ ...prev, [fileId]: true }));
      
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/files/${fileId}/transcribe/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.task_id) {
          setTaskIds(prev => ({ ...prev, [fileId]: data.task_id }));
        }
        // Refresh to get latest status
        await refreshAudioFiles(token);
      } else {
        const error = await response.json();
        alert(`Failed to start transcription: ${error.error || 'Unknown error'}`);
        setTranscribingFiles(prev => {
          const updated = { ...prev };
          delete updated[fileId];
          return updated;
        });
      }
    } catch (error) {
      alert(`Error starting transcription: ${error.message}`);
      setTranscribingFiles(prev => {
        const updated = { ...prev };
        delete updated[fileId];
        return updated;
      });
    }
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  // Format duration
  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return 'N/A';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle PDF upload
  const handlePdfUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingPdf(true);
    const formData = new FormData();
    formData.append('pdf_file', file);

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Token ${token}`
        },
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        console.log('PDF upload response:', data);
        console.log('PDF file path:', data.pdf_file);
        setProjectData(data);
        alert('PDF uploaded successfully!');
      } else {
        const errorData = await response.json();
        console.error('PDF upload failed:', errorData);
        alert('Failed to upload PDF');
      }
    } catch (error) {
      console.error('Error uploading PDF:', error);
      alert('Error uploading PDF');
    } finally {
      setUploadingPdf(false);
      // Clear the file input so user can upload the same file again
      event.target.value = null;
    }
  };

  // Handle PDF delete
  const handlePdfDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this PDF? This will remove it from the project.')) {
      return;
    }

    setUploadingPdf(true);

    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          pdf_file: null
        })
      });

      if (response.ok) {
        const data = await response.json();
        setProjectData(data);
        alert('PDF deleted successfully!');
      } else {
        alert('Failed to delete PDF');
      }
    } catch (error) {
      console.error('Error deleting PDF:', error);
      alert('Error deleting PDF');
    } finally {
      setUploadingPdf(false);
    }
  };

  // Extract filename from PDF path
  const getPdfFilename = (pdfPath) => {
    if (!pdfPath) return 'PDF';
    const parts = pdfPath.split('/');
    const filename = parts[parts.length - 1];
    // Remove any hash/UUID if present and get just the readable name
    return filename.length > 30 ? filename.substring(0, 27) + '...' : filename;
  };

  // Get status badge for table
  const getStatusBadgeInfo = (status) => {
    const statusMap = {
      'uploaded': { class: 'status-uploaded', text: 'Uploaded', icon: '📤' },
      'transcribing': { class: 'status-processing', text: 'Transcribing', icon: '⏳' },
      'transcribed': { class: 'status-transcribed', text: 'Transcribed', icon: '✅' },
      'processing': { class: 'status-processing', text: 'Processing', icon: '⚙️' },
      'processed': { class: 'status-processed', text: 'Processed', icon: '✨' },
      'failed': { class: 'status-failed', text: 'Failed', icon: '❌' }
    };
    return statusMap[status] || { class: 'status-unknown', text: status, icon: '❓' };
  };

  // Get status badge class and text
  const getStatusBadge = (status) => {
    const statusMap = {
      'uploaded': { class: 'status-uploaded', text: 'Uploaded' },
      'processing': { class: 'status-processing', text: 'Processing...' },
      'transcribed': { class: 'status-transcribed', text: 'Transcribed' },
      'processed': { class: 'status-processed', text: 'Processed' },
      'failed': { class: 'status-failed', text: 'Failed' }
    };
    return statusMap[status] || { class: 'status-unknown', text: status };
  };

  return (
    <div className="tab1-container">
      <div className="tab-description-banner">
        <p>📝 <strong>Upload files, press transcribe, and don't refresh or leave the page.</strong> Transcription can take a while - watch the status update automatically.</p>
      </div>

      {/* Processing Mode Toggle */}
      {clientSideSupported && (
        <div className="processing-mode-selector">
          <div className="processing-mode-toggle">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={useClientSide}
                onChange={(e) => setUseClientSide(e.target.checked)}
                disabled={uploading}
              />
              <span className="toggle-text">
                {useClientSide ? '🖥️ Process on My Device' : '☁️ Process on Server'}
              </span>
            </label>
          </div>
          <div className="processing-mode-info">
            {useClientSide ? (
              <p>
                ✓ <strong>Faster processing</strong> (uses your computer's CPU/GPU)<br />
                ✓ <strong>No upload time</strong> - files stay on your device<br />
                ⓘ First use downloads AI model (~39MB, cached for future use)
              </p>
            ) : (
              <p>
                ☁️ Processing happens on our server<br />
                ⓘ Best for older devices or slow internet
              </p>
            )}
          </div>
        </div>
      )}

      {/* Model Loading Progress */}
      {modelLoading && modelProgress && (
        <div className="model-loading-banner">
          <p><strong>📥 Downloading AI Model...</strong></p>
          <p>{modelProgress.message}</p>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${modelProgress.percent || 0}%` }} />
          </div>
          <p style={{ fontSize: '0.9em', color: '#666' }}>
            This happens once. The model will be cached for future use.
          </p>
        </div>
      )}

      {/* Upload Area */}
      <div 
        className={`upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="upload-icon">📁</div>
        <h3>Upload Audio Files</h3>
        <p>Drag & drop files here, or click to browse</p>
        <p className="upload-hint">Supported formats: MP3, WAV, M4A, FLAC, OGG (max 500MB each)</p>
        
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".mp3,.wav,.m4a,.flac,.ogg"
          onChange={(e) => handleFileUpload(e.target.files)}
          style={{ display: 'none' }}
        />
        <label htmlFor="file-upload" className="upload-button">
          Select Files
        </label>

        {uploading && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
            <span>{uploadProgress}% uploaded</span>
          </div>
        )}
      </div>

      {/* Files Table */}
      <div className="files-table-container">
        <div className="files-header">
          <h3>Audio Files ({audioFiles.length})</h3>
          <button className="refresh-button" onClick={() => refreshAudioFiles(token)}>
            🔄 Refresh
          </button>
        </div>

        {audioFiles.length === 0 ? (
          <div className="empty-state">
            <p>No audio files yet. Upload your first file above!</p>
          </div>
        ) : (
          <table className="files-table">
            <thead>
              <tr>
                <th>Audio File</th>
                <th>Duration</th>
                <th>Status</th>
                <th>PDF</th>
                <th>Transcription</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {audioFiles.map((file) => {
                const isTranscribing = transcribingFiles[file.id];
                const hasTranscription = file.transcription && file.transcription.text;
                const hasFailureWithoutTranscription = (file.status === 'failed' || file.error_message) && !hasTranscription;
                
                const statusInfo = getStatusBadgeInfo(file.status);
                
                return (
                  <tr 
                    key={file.id}
                    className={selectedAudioFile?.id === file.id ? 'selected' : ''}
                    onClick={() => selectAudioFile(file)}
                    title="Click to select this file for use in other tabs"
                  >
                    <td className="file-cell">
                      <div className="file-info-inline">
                        <span className="file-icon">🎵</span>
                        <div className="file-details">
                          <div className="file-name" title={file.filename}>{file.filename}</div>
                          <div className="file-meta">
                            <span>💾 {formatFileSize(file.file_size_bytes)}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="duration-cell">
                      <span className="duration-value">{formatDuration(file.duration_seconds || file.original_duration)}</span>
                    </td>
                    <td className="status-cell">
                      <span className={`status-badge ${statusInfo.class}`}>
                        <span className="status-icon">{statusInfo.icon}</span>
                        {statusInfo.text}
                      </span>
                    </td>
                    <td className="pdf-cell">
                      {projectData?.pdf_file ? (
                        <div className="pdf-actions">
                          <a 
                            href={`http://localhost:8000${projectData.pdf_file}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="pdf-link"
                            title={`Download ${getPdfFilename(projectData.pdf_file)}`}
                          >
                            <span className="pdf-icon">📄</span>
                            <span className="pdf-name">{getPdfFilename(projectData.pdf_file)}</span>
                          </a>
                          <button
                            className="pdf-delete-button"
                            onClick={handlePdfDelete}
                            disabled={uploadingPdf}
                            title="Delete PDF"
                          >
                            {uploadingPdf ? '⏳' : '🗑️'}
                          </button>
                        </div>
                      ) : (
                        <div className="pdf-upload-inline">
                          <input
                            type="file"
                            id="pdf-upload-input"
                            accept=".pdf"
                            onChange={handlePdfUpload}
                            style={{ display: 'none' }}
                          />
                          <label 
                            htmlFor="pdf-upload-input"
                            className="pdf-upload-button"
                            title="Upload PDF"
                          >
                            {uploadingPdf ? '⏳ Uploading...' : '📄+ Upload PDF'}
                          </label>
                        </div>
                      )}
                    </td>
                    <td className="transcription-cell">
                      {isTranscribing ? (
                        <div className="transcribing-status">
                          <div className="spinner"></div>
                          <span>Transcribing... Please wait</span>
                        </div>
                      ) : hasFailureWithoutTranscription ? (
                        <div className="transcription-error">
                          <span className="error-icon">⚠️</span>
                          <div className="error-details">
                            <span className="error-text">Transcription failed</span>
                            <button 
                              className="retry-button"
                              onClick={() => handleTranscribe(file.id)}
                            >
                              🔄 Retry
                            </button>
                          </div>
                        </div>
                      ) : hasTranscription ? (
                        <div className="transcription-preview">
                          {file.transcription.text.substring(0, 150)}
                          {file.transcription.text.length > 150 && '...'}
                        </div>
                      ) : (
                        <button 
                          className="transcribe-button"
                          onClick={() => handleTranscribe(file.id)}
                          disabled={isTranscribing}
                        >
                          🎙️ Transcribe
                        </button>
                      )}
                    </td>
                    <td className="actions-cell">
                      <button 
                        className="delete-button"
                        onClick={() => handleDelete(file.id)}
                        title="Delete file"
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default Tab1Files;
