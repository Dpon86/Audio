import React, { useEffect, useState, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import { API_BASE_URL } from '../../config/api';
import clientSideTranscription from '../../services/clientSideTranscription';
import clientAudioStorage from '../../services/clientAudioStorage';
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
    selectAudioFile,
    duplicateDetectionMode,
    setDuplicateDetectionMode,
    setActiveTab
  } = useProjectTab();

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [transcribingFiles, setTranscribingFiles] = useState({}); // Track which files are transcribing
  const [taskIds, setTaskIds] = useState({}); // Track Celery task IDs
  const [uploadingPdf, setUploadingPdf] = useState(false);
  
  // Client-side processing state
  const [useClientSide, setUseClientSide] = useState(true); // Default to client-side (server has low memory)
  const [modelLoading, setModelLoading] = useState(false);
  const [modelProgress, setModelProgress] = useState(null);
  const [clientSideSupported, setClientSideSupported] = useState(false);
  const [processingTimeEstimate, setProcessingTimeEstimate] = useState(null); // { min, max, audioDuration }
  const [processingElapsed, setProcessingElapsed] = useState(0); // Minutes elapsed
  
  // State for displaying merged files (server + local)
  const [displayFiles, setDisplayFiles] = useState([]);
  const [processingStep, setProcessingStep] = useState(''); // Track current processing step for progress display
  const [showUploadSection, setShowUploadSection] = useState(true); // Show/hide upload section

  // Check if any files have been transcribed
  const hasTranscribedFiles = displayFiles.some(file => 
    file.transcription && file.transcription.text
  );

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

  // Server storage functions for cross-device persistence
  const saveTranscriptionToServer = async (fileId, filename, transcriptionData, duration, fileSize) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/client-transcriptions/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify({
          filename: filename,
          file_size_bytes: fileSize,
          transcription_data: {
            segments: transcriptionData.all_segments || [],
            text: transcriptionData.text,
            language: 'en'
          },
          processing_method: 'client',
          model_used: 'Xenova/whisper-tiny',
          duration_seconds: duration,
          language: 'en',
          metadata: {
            saved_at: new Date().toISOString(),
            local_file_id: fileId
          }
        })
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[Tab1Files] Transcription saved to server:', data);
        return { success: true, data: data.transcription };
      } else {
        console.error('[Tab1Files] Failed to save transcription to server:', response.status);
        return { success: false, error: 'Server error' };
      }
    } catch (error) {
      console.error('[Tab1Files] Error saving transcription to server:', error);
      return { success: false, error: error.message };
    }
  };

  const loadServerTranscriptions = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/client-transcriptions/`, {
        method: 'GET',
        headers: {
          'Authorization': `Token ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[Tab1Files] Loaded transcriptions from server:', data.total_count);
        return data.transcriptions || [];
      } else {
        console.error('[Tab1Files] Failed to load transcriptions from server:', response.status);
        return [];
      }
    } catch (error) {
      console.error('[Tab1Files] Error loading transcriptions from server:', error);
      return [];
    }
  };

  // Load and merge client-processed files from localStorage with server files
  useEffect(() => {
    const loadLocalFiles = async () => {
      // First, load transcriptions from server
      const serverTranscriptions = await loadServerTranscriptions();
      
      // Build map of server transcriptions by filename for easy lookup
      const serverTranscriptionsMap = {};
      serverTranscriptions.forEach(st => {
        serverTranscriptionsMap[st.filename] = st;
      });
      
      const storageKey = `client_transcriptions_${projectId}`;
      const localFilesJson = localStorage.getItem(storageKey);
      
      if (localFilesJson) {
        try {
          const localFiles = JSON.parse(localFilesJson);
          
          // Load audio files from IndexedDB
          const localFilesWithAudio = await Promise.all(
            localFiles.map(async (lf) => {
              // Check if this file has a server transcription
              const serverTranscription = serverTranscriptionsMap[lf.filename];
              
              let audioFile = null;
              if (lf.has_local_audio) {
                try {
                  const stored = await clientAudioStorage.getFile(lf.id);
                  if (stored && stored.file) {
                    audioFile = stored.file;
                    console.log(`[Tab1Files] Loaded audio from IndexedDB for ${lf.filename}`);
                  }
                } catch (error) {
                  console.error(`[Tab1Files] Failed to load audio for ${lf.filename}:`, error);
                }
              }
              
              // Use server transcription if available (it's the source of truth)
              const transcription = serverTranscription 
                ? {
                    text: serverTranscription.full_text || '',
                    all_segments: serverTranscription.transcription_data?.segments || [],
                    word_count: serverTranscription.full_text?.split(/\s+/).filter(w => w.length > 0).length || 0,
                    client_processed: true
                  }
                : lf.transcription;
              
              return {
                id: lf.id,
                filename: lf.filename,
                title: lf.title,
                status: 'transcribed',
                file_size_bytes: serverTranscription?.file_size_bytes || lf.file_size_bytes || 0,
                duration_seconds: serverTranscription?.duration_seconds || lf.duration_seconds || 0,
                transcription: transcription,
                client_only: true,
                local_file: audioFile, // Add the audio File object from IndexedDB
                server_synced: !!serverTranscription,
                server_id: serverTranscription?.id,
                status_badge: serverTranscription ? '☁️ Synced' : '📱 Local'
              };
            })
          );
          
          // Also add any server transcriptions that don't have local files
          const localFileNames = localFiles.map(lf => lf.filename);
          const serverOnlyFiles = serverTranscriptions
            .filter(st => !localFileNames.includes(st.filename))
            .map(st => ({
              id: `server-${st.id}`,
              filename: st.filename,
              title: st.filename.replace(/\.[^/.]+$/, ''),
              status: 'transcribed',
              file_size_bytes: st.file_size_bytes || 0,
              duration_seconds: st.duration_seconds || 0,
              transcription: {
                text: st.full_text || '',
                all_segments: st.transcription_data?.segments || [],
                word_count: st.full_text?.split(/\s+/).filter(w => w.length > 0).length || 0,
                client_processed: true
              },
              client_only: true,
              local_file: null,
              server_synced: true,
              server_id: st.id,
              status_badge: '☁️🔄 Server' // Server only, no local audio
            }));
          
          // Merge with server files (avoid duplicates by filename)
          const serverFileNames = audioFiles.map(f => f.filename);
          const allLocalFiles = [...localFilesWithAudio, ...serverOnlyFiles];
          const uniqueLocalFiles = allLocalFiles.filter(
            lf => !serverFileNames.includes(lf.filename)
          );
          
          setDisplayFiles([...audioFiles, ...uniqueLocalFiles]);
          
          console.log('[Tab1Files] Loaded', uniqueLocalFiles.length, 'client files (server + local)');
          console.log('[Tab1Files] Server transcriptions:', serverOnlyFiles.length, 'Server synced:', localFilesWithAudio.filter(f => f.server_synced).length);
        } catch (error) {
          console.error('[Tab1Files] Error loading local files:', error);
          setDisplayFiles(audioFiles);
        }
      } else if (serverTranscriptions.length > 0) {
        // No local storage, but we have server transcriptions
        const serverFiles = serverTranscriptions.map(st => ({
          id: `server-${st.id}`,
          filename: st.filename,
          title: st.filename.replace(/\.[^/.]+$/, ''),
          status: 'transcribed',
          file_size_bytes: st.file_size_bytes || 0,
          duration_seconds: st.duration_seconds || 0,
          transcription: {
            text: st.full_text || '',
            all_segments: st.transcription_data?.segments || [],
            word_count: st.full_text?.split(/\s+/).filter(w => w.length > 0).length || 0,
            client_processed: true
          },
          client_only: true,
          local_file: null,
          server_synced: true,
          server_id: st.id,
          status_badge: '☁️🔄 Server'
        }));
        
        const serverFileNames = audioFiles.map(f => f.filename);
        const uniqueServerFiles = serverFiles.filter(
          sf => !serverFileNames.includes(sf.filename)
        );
        
        setDisplayFiles([...audioFiles, ...uniqueServerFiles]);
        console.log('[Tab1Files] Loaded', uniqueServerFiles.length, 'files from server');
      } else {
        setDisplayFiles(audioFiles);
      }
    };
    
    loadLocalFiles();
  }, [audioFiles, projectId]);

  // Transcribe a file client-side AFTER it has already been uploaded to the server.
  // Model download happens here — only when client-side transcription is actually needed.
  const transcribeFileClientSide = async (file, serverAudioFileId) => {
    setProcessingStep('loading');

    try {
      // Initialize/download model only now — not during upload
      if (!clientSideTranscription.modelLoaded) {
        setModelLoading(true);
        await clientSideTranscription.initialize('tiny', (progress) => {
          setModelProgress(progress);
          setUploadProgress(40 + Math.min(progress.percent || 0, 20));
        });
        setModelLoading(false);
      }

      // Transcribe audio
      setProcessingStep('transcribing');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);

      const audioDurationMinutes = file.size / (1024 * 1024 * 10);
      const estimatedMinutes = Math.ceil(audioDurationMinutes * 0.5);
      console.log(`[Tab1Files] Starting transcription - estimated time: ~${estimatedMinutes} minutes`);

      const result = await clientSideTranscription.transcribe(
        file,
        {},
        (progress) => {
          setUploadProgress(60 + Math.round((progress.percent || 0) * 0.3));
          if (progress.estimatedTimeMin && progress.estimatedTimeMax && !processingTimeEstimate) {
            setProcessingTimeEstimate({
              min: progress.estimatedTimeMin,
              max: progress.estimatedTimeMax,
              audioDuration: progress.audioDuration
            });
          }
          if (progress.elapsed !== undefined) {
            setProcessingElapsed(progress.elapsed);
          }
        }
      );

      setProcessingStep('finalizing');
      setUploadProgress(90);

      // Store audio in IndexedDB for local playback
      const fileId = `local-${Date.now()}`;
      const duration = result.all_segments && result.all_segments.length > 0
        ? result.all_segments[result.all_segments.length - 1].end
        : 0;

      await clientAudioStorage.storeFile(fileId, projectId, file, {
        transcription: {
          text: result.text,
          all_segments: result.all_segments || [],
          word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
          client_processed: true
        },
        duration_seconds: duration,
        server_audio_file_id: serverAudioFileId
      });

      // Store metadata in localStorage
      const storageKey = `client_transcriptions_${projectId}`;
      const existing = JSON.parse(localStorage.getItem(storageKey) || '[]');
      existing.push({
        id: fileId,
        filename: file.name,
        title: file.name.replace(/\.[^/.]+$/, ''),
        transcription: {
          text: result.text,
          all_segments: result.all_segments || [],
          word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
          client_processed: true
        },
        timestamp: Date.now(),
        has_local_audio: true,
        server_audio_file_id: serverAudioFileId,
        server_upload_complete: true
      });
      localStorage.setItem(storageKey, JSON.stringify(existing));

      // Save transcription metadata to server
      const serverSave = await saveTranscriptionToServer(
        fileId,
        file.name,
        { text: result.text, all_segments: result.all_segments || [] },
        duration,
        file.size
      );

      setProcessingStep('complete');
      setUploadProgress(100);
      await refreshAudioFiles(token);

      const wordCount = result.text.split(/\s+/).filter(w => w.length > 0).length;
      const syncStatus = serverSave.success
        ? `☁️ Metadata Synced: Transcription available on all devices`
        : `📱 Local Metadata: Server unavailable for sync`;

      alert(
        `✅ Transcription Complete!\n\n` +
        `📄 File: ${file.name}\n` +
        `⏱️ Duration: ${formatDuration(duration)}\n` +
        `💬 Words: ${wordCount.toLocaleString()}\n` +
        `📝 Segments: ${result.all_segments?.length || 0}\n\n` +
        `✅ Audio already uploaded to server\n` +
        `${syncStatus}`
      );

      setProcessingStep('');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);
      setModelProgress(null);

    } catch (error) {
      console.error('[Tab1Files] Client-side transcription failed:', error);
      setModelLoading(false);
      setModelProgress(null);
      setProcessingStep('');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);

      const isNetworkBlock = error.message.includes('unavailable on this network') ||
                             error.message.includes('Model loading failed') ||
                             error.message.includes('Load failed') ||
                             error.message.includes('Failed to fetch');

      if (isNetworkBlock) {
        alert(
          `⚠️ Could not load transcription model.\n\n` +
          `All download sources were unreachable on this network.\n\n` +
          `Note: Your file was already uploaded to the server successfully.\n` +
          `If you are on a restricted network, connect to the internet and try again.`
        );
      } else {
        alert(`Transcription failed: ${error.message}\n\nNote: Your file was already uploaded to the server.`);
      }
    }
  };

  // Handle file upload — always uploads to server first.
  // If client-side transcription is selected, model download + transcription happens AFTER upload.
  // If server-side (AI) is selected, server handles transcription — no model download needed.
  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);

    if (useClientSide && fileArray.length > 1) {
      alert('Client-side transcription supports one file at a time. Processing first file only.');
      fileArray.splice(1);
    }

    setUploading(true);
    setUploadProgress(0);

    for (let i = 0; i < fileArray.length; i++) {
      const file = fileArray[i];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', file.name.replace(/\.[^/.]+$/, ''));

      let serverFileId = null;

      try {
        setProcessingStep('uploading');
        const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/`, {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`
          },
          body: formData
        });

        if (response.ok) {
          const data = await response.json();
          serverFileId = data.id;
          // For client-side: upload counts as first 40%; transcription follows.
          // For server-side (AI): upload is the whole job, count to 100%.
          const uploadPercent = useClientSide
            ? Math.round(((i + 1) / fileArray.length) * 40)
            : Math.round(((i + 1) / fileArray.length) * 100);
          setUploadProgress(uploadPercent);
          await refreshAudioFiles(token);
        } else {
          let errorMessage = `Failed to upload ${file.name}`;
          try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
              const error = await response.json();
              errorMessage = error.error || error.message || errorMessage;
            } else {
              const text = await response.text();
              console.error('Server returned non-JSON error:', text);
              errorMessage = `Server error (${response.status}): ${response.statusText}`;
            }
          } catch (parseError) {
            console.error('Error parsing response:', parseError);
            errorMessage = `Server error (${response.status}): ${response.statusText}`;
          }
          alert(errorMessage);
          continue;
        }
      } catch (error) {
        console.error('Upload error:', error);
        alert(`Error uploading ${file.name}: ${error.message}`);
        continue;
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
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/${fileId}/`, {
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
    // Remove window.confirm since we show an overlay now
    try {
      setTranscribingFiles(prev => ({ ...prev, [fileId]: true }));
      
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/${fileId}/transcribe/`, {
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
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/`, {
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
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/`, {
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
      {/* Processing Mode Toggle - DISABLED (server has low memory) */}
      {false && clientSideSupported && (
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

      {/* Processing Software Loading Progress */}
      {modelLoading && modelProgress && (
        <div className="model-loading-banner">
          <p><strong>📥 Loading Processing Software...</strong></p>
          <p>{modelProgress.message}</p>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${modelProgress.percent || 0}%` }} />
          </div>
          <p style={{ fontSize: '0.9em', color: '#666' }}>
            This happens once. The software will be cached for future use.
          </p>
        </div>
      )}

      {/* Upload Row: green info banner (25%) + upload area (75%) */}
      {hasTranscribedFiles && !showUploadSection ? (
        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          marginBottom: '1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ color: '#64748b', fontSize: '0.9rem' }}>
            📁 Upload section hidden
          </span>
          <button
            onClick={() => setShowUploadSection(true)}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              background: 'white',
              color: '#1e293b',
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.85rem'
            }}
          >
            Show Upload
          </button>
        </div>
      ) : (
        <div style={{
          display: 'flex',
          gap: '1rem',
          alignItems: 'stretch',
          marginBottom: '1rem'
        }}>
          {/* Green info banner — 25% */}
          <div className="client-side-info-banner" style={{ flex: '0 0 25%', marginBottom: 0, display: 'flex', alignItems: 'center' }}>
            <p style={{ margin: 0 }}>
              🖥️ <strong>Processing on Your Device</strong><br />
              All transcription happens in your browser for faster, private processing.
              Your audio files never leave your device. Results are saved locally in your browser.
            </p>
          </div>

          {/* Upload section — 75% */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {hasTranscribedFiles && (
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowUploadSection(false)}
                  style={{
                    padding: '0.3rem 0.5rem',
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                    background: 'white',
                    color: '#64748b',
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  Hide Upload Section
                </button>
              </div>
            )}
            <div
              className={`upload-area upload-area-compact ${dragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', width: '100%' }}>
                <div style={{ fontSize: '2rem', flexShrink: 0 }}>📁</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: '1rem', color: 'white', marginBottom: '0.2rem' }}>Upload Audio Files</div>
                  <div style={{ fontSize: '0.85rem', opacity: 0.9, color: 'white' }}>Drag &amp; drop files here, or click to browse</div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.75, color: 'white', marginTop: '0.1rem' }}>MP3, WAV, M4A, FLAC, OGG · max 500MB each</div>
                </div>
                <label htmlFor="file-upload" className="upload-button" style={{ flexShrink: 0, margin: 0, padding: '0.6rem 1.5rem', fontSize: '0.9rem' }}>
                  Select Files
                </label>
              </div>
        
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".mp3,.wav,.m4a,.flac,.ogg"
          onChange={(e) => handleFileUpload(e.target.files)}
          style={{ display: 'none' }}
        />
        {uploading && (
          <div className="upload-progress-overlay">
            <div className="progress-modal">
              <div className="processing-animation">
                <div className="spinner"></div>
              </div>
              
              <h3 className="processing-title">Processing Your Audio</h3>
              
              {processingStep === 'transcribing' && (
                <>
                  <div className="browser-warning">
                    ⚠️ <strong>Your browser may report this page as unresponsive.</strong>
                    <br />
                    This is normal – the transcription is processing on your device.
                    <br />
                    <strong>Please wait and click "Wait" if prompted.</strong>
                    {processingTimeEstimate && processingTimeEstimate.audioDuration && (
                      <>
                        <br /><br />
                        <strong>📊 Audio Duration: {Math.floor(processingTimeEstimate.audioDuration / 60)}:{Math.floor(processingTimeEstimate.audioDuration % 60).toString().padStart(2, '0')}</strong>
                        <br />
                        <strong>⏱️ Estimated Processing Time: {processingTimeEstimate.min}-{processingTimeEstimate.max} minutes</strong>
                        <br />
                        <em style={{color: '#10b981'}}>✓ This is the only step that will take this long.</em>
                      </>
                    )}
                  </div>
                  
                  {processingTimeEstimate && (
                    <div className="time-estimate">
                      <div className="time-row">
                        <span className="time-label">⏱️ Audio Duration:</span>
                        <span className="time-value">{Math.ceil(processingTimeEstimate.audioDuration / 60)} minutes</span>
                      </div>
                      <div className="time-row">
                        <span className="time-label">⏳ Estimated Time:</span>
                        <span className="time-value">{processingTimeEstimate.min}-{processingTimeEstimate.max} minutes</span>
                      </div>
                      {processingElapsed > 0 && (
                        <div className="time-row elapsed">
                          <span className="time-label">⌛ Elapsed:</span>
                          <span className="time-value">{processingElapsed.toFixed(1)} minutes</span>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
              
              <div className="progress-steps">
                <div className={`step-item ${processingStep === 'loading' ? 'active' : ''}`}>
                  <span className="step-icon">{processingStep === 'loading' ? '⏳' : '✓'}</span>
                  <span className="step-text">Loading Processing Software</span>
                </div>
                <div className={`step-item ${processingStep === 'reading' ? 'active' : ''}`}>
                  <span className="step-icon">{processingStep === 'reading' ? '⏳' : processingStep === 'loading' ? '○' : '✓'}</span>
                  <span className="step-text">Reading Audio File</span>
                </div>
                <div className={`step-item ${processingStep === 'transcribing' ? 'active' : ''}`}>
                  <span className="step-icon">{processingStep === 'transcribing' ? '⏳' : ['loading', 'reading'].includes(processingStep) ? '○' : '✓'}</span>
                  <span className="step-text">
                    Transcribing Audio
                    {processingTimeEstimate && processingTimeEstimate.audioDuration && (
                      <span style={{ marginLeft: '0.5rem', color: '#6b7280' }}>
                        (Audio: {Math.floor(processingTimeEstimate.audioDuration / 60)}:{Math.floor(processingTimeEstimate.audioDuration % 60).toString().padStart(2, '0')} - 
                        Est. {processingTimeEstimate.min}-{processingTimeEstimate.max} min)
                      </span>
                    )}
                    {!processingTimeEstimate && processingStep === 'transcribing' && (
                      <span style={{ marginLeft: '0.5rem', color: '#6b7280' }}>(Processing...)</span>
                    )}
                  </span>
                </div>
                <div className={`step-item ${processingStep === 'finalizing' ? 'active' : ''}`}>
                  <span className="step-icon">{processingStep === 'finalizing' ? '⏳' : ['loading', 'reading', 'transcribing'].includes(processingStep) ? '○' : '✓'}</span>
                  <span className="step-text">Finalizing Results</span>
                </div>
                <div className={`step-item ${processingStep === 'uploading' ? 'active' : ''}`}>
                  <span className="step-icon">{processingStep === 'uploading' ? '⏳' : ['loading', 'reading', 'transcribing', 'finalizing'].includes(processingStep) ? '○' : '✓'}</span>
                  <span className="step-text">Uploading to Server</span>
                  {processingStep === 'uploading' && (
                    <span style={{ marginLeft: '0.5rem', color: '#6b7280' }}>(Enables server-side assembly)</span>
                  )}
                </div>
              </div>
              
              <div className="progress-bar-container">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
                <div className="progress-text">{uploadProgress}% complete</div>
              </div>
              
              <div className="processing-info">
                💡 Tip: Processing happens on your device for privacy and security.
              </div>
            </div>
          </div>
        )}
            </div>
          </div>
        </div>
      )}

      {/* Files Table */}
      <div className="files-table-container">
        <div className="files-header">
          <h3>Audio Files ({displayFiles.length})</h3>
          <button className="refresh-button" onClick={() => refreshAudioFiles(token)}>
            🔄 Refresh
          </button>
        </div>

        {displayFiles.length === 0 ? (
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
              {displayFiles.map((file) => {
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
                    style={{
                      background: selectedAudioFile?.id === file.id ? '#eff6ff' : 'white',
                      borderLeft: selectedAudioFile?.id === file.id ? '4px solid #3b82f6' : '4px solid transparent',
                      cursor: 'pointer'
                    }}
                  >
                    <td className="file-cell">
                      <div className="file-info-inline">
                        {selectedAudioFile?.id === file.id && (
                          <span style={{ marginRight: '0.5rem', fontSize: '1.2rem' }}>✓</span>
                        )}
                        <span className="file-icon">🎵</span>
                        <div className="file-details">
                          <div className="file-name" title={file.filename}>
                            {file.filename}
                            {file.status_badge && <span className="local-badge">{file.status_badge}</span>}
                          </div>
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
                            href={`${API_BASE_URL}${projectData.pdf_file}`}
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

      {/* Move to Duplicates Button - Show when files are transcribed */}
      {hasTranscribedFiles && selectedAudioFile && (
        <div style={{
          marginTop: '1.5rem',
          padding: '1.5rem',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '12px',
          textAlign: 'center',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
        }}>
          <h3 style={{ margin: 0, marginBottom: '0.5rem', color: 'white', fontSize: '1.1rem' }}>
            ✨ Ready for Next Step
          </h3>
          <p style={{ margin: 0, marginBottom: '1rem', color: 'rgba(255, 255, 255, 0.9)', fontSize: '0.9rem' }}>
            Your files are transcribed! Now detect and remove duplicate content.
          </p>
          <button
            onClick={() => setActiveTab('duplicates')}
            style={{
              padding: '0.75rem 1.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'white',
              color: '#667eea',
              fontWeight: 700,
              fontSize: '1rem',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
              transition: 'transform 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.transform = 'scale(1.05)'}
            onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
          >
            → Move to Detecting Duplicates
          </button>
        </div>
      )}

      {/* Transcription Progress Overlay */}
      {Object.keys(transcribingFiles).length > 0 && (
        <div className="upload-progress-overlay">
          <div className="progress-modal">
            <div className="processing-animation">
              <div className="spinner"></div>
            </div>
            
            <h3 className="processing-title">Transcribing Audio</h3>
            
            <div className="browser-warning">
              ⏳ <strong>Transcription in Progress</strong>
              <br />
              This may take several minutes depending on the file length.
              <br />
              <strong>Please do not close or refresh this page.</strong>
            </div>
            
            <div className="progress-steps">
              <div className="step-item active">
                <span className="step-icon">⏳</span>
                <span className="step-text">Sending file to AI for analysis...</span>
              </div>
              <div className="step-item active">
                <span className="step-icon">⏳</span>
                <span className="step-text">Generating transcription...</span>
              </div>
            </div>
            
            <div className="processing-info" style={{ marginTop: '1.5rem', textAlign: 'center', color: '#6b7280' }}>
              💡 Hang tight! We are processing your file in the background.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Tab1Files;
