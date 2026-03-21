import React, { useEffect, useState, useCallback } from 'react';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import { API_BASE_URL } from '../../config/api';
import clientSideTranscription from '../../services/clientSideTranscription';
import clientAudioStorage from '../../services/clientAudioStorage';
import { uploadWithTranscription } from '../../services/uploadWithTranscription';
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

  // Process file client-side
  const processFileClientSide = async (file) => {
    setUploading(true);
    setUploadProgress(0);
    setProcessingStep('loading');

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

      // Reading audio file
      setProcessingStep('reading');
      setUploadProgress(30);

      // Transcribe audio - show time estimate based on file duration
      setProcessingStep('transcribing');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);
      
      // Calculate estimated time (rough estimate: 1 minute of audio = ~30 seconds processing)
      const audioDurationMinutes = file.size / (1024 * 1024 * 10); // Very rough estimate
      const estimatedMinutes = Math.ceil(audioDurationMinutes * 0.5);
      
      console.log(`[Tab1Files] Starting transcription - estimated time: ~${estimatedMinutes} minutes`);
      
      const result = await clientSideTranscription.transcribe(
        file,
        {},
        (progress) => {
          // Update progress percentage
          setUploadProgress(30 + Math.round((progress.percent || 0) * 0.4));
          
          // Update time estimate on first progress update
          if (progress.estimatedTimeMin && progress.estimatedTimeMax && !processingTimeEstimate) {
            setProcessingTimeEstimate({
              min: progress.estimatedTimeMin,
              max: progress.estimatedTimeMax,
              audioDuration: progress.audioDuration
            });
          }
          
          // Update elapsed time
          if (progress.elapsed !== undefined) {
            setProcessingElapsed(progress.elapsed);
          }
        }
      );

      setProcessingStep('finalizing');
      setUploadProgress(70);

      // *** NEW: Upload audio file + transcription to server ***
      // This enables server-side assembly after client-side transcription
      setProcessingStep('uploading');
      console.log('[Tab1Files] Uploading audio + transcription to server...');
      
      let serverAudioFileId = null;
      let uploadSuccess = false;
      
      try {
        const uploadResult = await uploadWithTranscription(
          file,
          result,  // transcriptionResult with all_segments
          projectId,
          token,
          {
            title: file.name.replace(/\.[^/.]+$/, ''),  // Remove extension
            orderIndex: audioFiles?.length || 0,
            onProgress: (percent) => {
              // Upload progress: 70% to 90%
              setUploadProgress(70 + Math.round(percent * 0.2));
            }
          }
        );
        
        serverAudioFileId = uploadResult.audio_file_id;
        uploadSuccess = true;
        console.log('[Tab1Files] Upload successful! Server audio_file_id:', serverAudioFileId);
        
      } catch (uploadError) {
        console.error('[Tab1Files] Upload failed:', uploadError);
        // Don't fail the whole process - we can still use client-side data
        uploadSuccess = false;
      }

      setUploadProgress(90);

      // For client-side processing, store locally and display in UI
      console.log('[Tab1Files] Storing transcription locally');
      
      // Create a unique ID for this file
      const fileId = `local-${Date.now()}`;
      
      // Store the actual File object in IndexedDB for persistence
      await clientAudioStorage.storeFile(fileId, projectId, file, {
        transcription: {
          text: result.text,
          all_segments: result.all_segments || [],
          word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
          client_processed: true
        },
        duration_seconds: result.all_segments && result.all_segments.length > 0 
          ? result.all_segments[result.all_segments.length - 1].end 
          : 0,
        server_audio_file_id: serverAudioFileId  // *** NEW: Link to server file ***
      });
      
      console.log(`[Tab1Files] Stored audio file in IndexedDB: ${fileId}`);
      
      // Create a local file object to display in the list
      const localFile = {
        id: fileId,
        filename: file.name,
        title: file.name.replace(/\.[^/.]+$/, ''),
        status: 'transcribed',
        file_size_bytes: file.size,
        duration_seconds: result.all_segments && result.all_segments.length > 0 
          ? result.all_segments[result.all_segments.length - 1].end 
          : 0,
        transcription: {
          text: result.text,
          all_segments: result.all_segments || [],
          word_count: result.text.split(/\s+/).filter(w => w.length > 0).length,
          client_processed: true
        },
        client_only: !uploadSuccess,  // Only client if upload failed
        has_local_audio: true,
        server_audio_file_id: serverAudioFileId,  // *** NEW: Server file ID ***
        server_upload_complete: uploadSuccess  // *** NEW: Upload status ***
      };

      // Store metadata in localStorage for quick access
      const storageKey = `client_transcriptions_${projectId}`;
      const existing = JSON.parse(localStorage.getItem(storageKey) || '[]');
      existing.push({
        id: localFile.id,
        filename: localFile.filename,
        title: localFile.title,
        transcription: localFile.transcription,
        timestamp: Date.now(),
        has_local_audio: true,
        server_audio_file_id: serverAudioFileId,  // *** NEW ***
        server_upload_complete: uploadSuccess  // *** NEW ***
      });
      localStorage.setItem(storageKey, JSON.stringify(existing));

      // Save transcription metadata to server for cross-device persistence
      // This is separate from the audio file upload above
      const serverSave = await saveTranscriptionToServer(
        fileId,
        file.name,
        localFile.transcription,
        localFile.duration_seconds,
        file.size
      );

      // Update local file with server sync status
      if (serverSave.success) {
        localFile.server_synced = true;
        localFile.server_id = serverSave.data?.id;
        console.log('[Tab1Files] Transcription metadata synced to server');
      } else {
        localFile.server_synced = false;
        console.log('[Tab1Files] Transcription saved locally only (server unavailable)');
      }

      setProcessingStep('complete');
      setUploadProgress(100);
      
      // Add to audioFiles state for immediate display
      const currentFiles = audioFiles || [];
      const updatedFiles = [...currentFiles, localFile];
      // Trigger refresh to include local file
      await refreshAudioFiles(token);
      
      // Enhanced success alert with detailed information
      const duration = formatDuration(localFile.duration_seconds);
      const segments = result.all_segments?.length || 0;
      const words = localFile.transcription.word_count;
      
      // *** NEW: Different messaging based on upload status ***
      let uploadStatusMsg;
      let additionalInfo;
      
      if (uploadSuccess) {
        uploadStatusMsg = `✅ Upload Complete: Audio + transcription uploaded to server`;
        additionalInfo = `🔧 Server-Side Features Available:\n` +
                        `   • Server-side assembly (removes duplicates server-side)\n` +
                        `   • Cross-device access\n` +
                        `   • Persistent storage\n\n` +
                        `Your audio was transcribed on your device (no server load),\n` +
                        `then uploaded with transcription data for server-side assembly.`;
      } else {
        uploadStatusMsg = `⚠️ Upload Failed: Local-only processing`;
        additionalInfo = `📱 Your transcription is saved locally but:\n` +
                        `   • Server-side assembly NOT available\n` +
                        `   • Limited to this device only\n` +
                        `   • Will try to upload again later\n\n` +
                        `To enable server-side features, check your connection\n` +
                        `and try re-processing this file.`;
      }
      
      const syncStatus = localFile.server_synced 
        ? `☁️ Metadata Synced: Transcription available on all devices`
        : `📱 Local Metadata: Server unavailable for sync`;
      
      alert(
        `✅ Transcription Complete!\n\n` +
        `📄 File: ${file.name}\n` +
        `⏱️ Duration: ${duration}\n` +
        `💬 Words: ${words.toLocaleString()}\n` +
        `📝 Segments: ${segments}\n\n` +
        `${uploadStatusMsg}\n` +
        `${syncStatus}\n\n` +
        `${additionalInfo}`
      );

      setUploading(false);
      setUploadProgress(0);
      setModelLoading(false);
      setModelProgress(null);
      setProcessingStep('');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);
    } catch (error) {
      console.error('Client-side processing error:', error);
      alert(`Client-side processing failed: ${error.message}\n\nPlease try server-side processing instead.`);
      setUploading(false);
      setUploadProgress(0);
      setModelLoading(false);
      setModelProgress(null);
      setProcessingStep('');
      setProcessingTimeEstimate(null);
      setProcessingElapsed(0);
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
        const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/`, {
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
      {/* Client-Side Processing Info Banner */}
      <div className="client-side-info-banner">
        <p>
          🖥️ <strong>Processing on Your Device</strong><br />
          All transcription happens in your browser for faster, private processing.
          Your audio files never leave your device. Results are saved locally in your browser.
        </p>
      </div>

      <div style={{
        background: '#ffffff',
        border: '1px solid #dbeafe',
        borderRadius: '12px',
        padding: '1rem',
        marginBottom: '1.25rem',
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)'
      }}>
        <h3 style={{ margin: 0, marginBottom: '0.5rem', color: '#1e293b' }}>Step 2: Duplicate Detection Mode</h3>
        <p style={{ margin: 0, marginBottom: '0.75rem', color: '#475569', fontSize: '0.9rem' }}>
          Choose the mode now. The Duplicates tab will use this selection when you click start.
        </p>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setDuplicateDetectionMode('algorithm')}
            style={{
              padding: '0.6rem 0.9rem',
              borderRadius: '8px',
              border: duplicateDetectionMode === 'algorithm' ? '2px solid #2563eb' : '1px solid #cbd5e1',
              background: duplicateDetectionMode === 'algorithm' ? '#eff6ff' : '#ffffff',
              color: '#1e293b',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Algorithm (faster)
          </button>

          <button
            type="button"
            onClick={() => setDuplicateDetectionMode('ai')}
            style={{
              padding: '0.6rem 0.9rem',
              borderRadius: '8px',
              border: duplicateDetectionMode === 'ai' ? '2px solid #0891b2' : '1px solid #cbd5e1',
              background: duplicateDetectionMode === 'ai' ? '#ecfeff' : '#ffffff',
              color: '#1e293b',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            AI (higher quality)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('duplicates')}
            style={{
              marginLeft: 'auto',
              padding: '0.6rem 0.9rem',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              background: '#f8fafc',
              color: '#1e293b',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Open Duplicates Tab
          </button>
        </div>
      </div>

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
                  >
                    <td className="file-cell">
                      <div className="file-info-inline">
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
    </div>
  );
};

export default Tab1Files;
