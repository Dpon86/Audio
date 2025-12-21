import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import DebugPanel from "../components/DebugPanel";
import WaveSurfer from "wavesurfer.js";
import "../static/CSS/ProjectDetailPage.css";
import "../static/CSS/PDFRefinement.css";

// Helper function for authenticated API calls
const fetchWithAuth = (url, options = {}, token) => {
  const headers = {
    'Authorization': `Token ${token}`,
    ...options.headers
  };
  
  // Don't set Content-Type for FormData (let browser set it with boundary)
  if (!options.body || !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  
  // Ensure full URL to backend server
  const fullUrl = url.startsWith('http') ? url : `http://localhost:8000${url}`;
  
  return fetch(fullUrl, {
    ...options,
    headers
  });
};

// Audio Files List Component
const AudioFilesList = ({ projectId, onUpdate, token }) => {
  const [audioFiles, setAudioFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAudioFiles = useCallback(async () => {
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/audio-files/`, {}, token);
      if (response.ok) {
        const data = await response.json();
        setAudioFiles(data.audio_files);
      }
    } catch (error) {
    } finally {
      setLoading(false);
    }
  }, [projectId, token]);

  useEffect(() => {
    fetchAudioFiles();
  }, [fetchAudioFiles]);

  const transcribeAudioFile = async (audioFileId) => {
    const url = `/api/projects/${projectId}/audio-files/${audioFileId}/transcribe/`;
    
    // Debug logging
    if (window.debugLog) {
      window.debugLog('api-call', `POST ${url}`, { 
        projectId, 
        audioFileId,
        hasToken: !!token
      });
    }
    
    try {
      const response = await fetchWithAuth(url, {
        method: "POST"
      }, token);
      
      // Log response
      if (window.debugLog) {
        window.debugLog('api-response', `Response: ${response.status}`, {
          status: response.status,
          statusText: response.statusText,
          url: response.url,
          ok: response.ok
        });
      }
      
      if (response.ok) {
        const responseData = await response.json();
        if (window.debugLog) {
          window.debugLog('info', 'Transcription started successfully', responseData);
        }
        fetchAudioFiles(); // Refresh the list
        onUpdate(); // Update parent component
      } else {
        let errorData;
        try {
          errorData = await response.json();
        } catch (jsonError) {
          errorData = { error: `HTTP ${response.status}: ${response.statusText}` };
        }
        
        if (window.debugLog) {
          window.debugLog('error', `Transcription failed: ${response.status}`, errorData);
        }
        
        alert(errorData.error || `Failed to start transcription (${response.status})`);
      }
    } catch (error) {
      if (window.debugLog) {
        window.debugLog('error', 'Network/Connection Error', {
          message: error.message,
          stack: error.stack
        });
      }
      
      alert(`Failed to start transcription: ${error.message}`);
    }
  };

  const restartTranscription = async (audioFileId) => {
    const url = `/api/projects/${projectId}/audio-files/${audioFileId}/restart/`;
    
    if (window.debugLog) {
      window.debugLog('api-call', `POST ${url}`, { projectId, audioFileId });
    }
    
    try {
      const response = await fetchWithAuth(url, {
        method: "POST"
      }, token);
      
      if (window.debugLog) {
        window.debugLog('api-response', `Restart Response: ${response.status}`, {
          status: response.status,
          ok: response.ok
        });
      }
      
      if (response.ok) {
        const responseData = await response.json();
        if (window.debugLog) {
          window.debugLog('info', 'Transcription restarted successfully', responseData);
        }
        fetchAudioFiles(); // Refresh the list
        onUpdate(); // Update parent component
      } else {
        const errorData = await response.json();
        if (window.debugLog) {
          window.debugLog('error', `Restart failed: ${response.status}`, errorData);
        }
        alert(errorData.error || "Failed to restart transcription");
      }
    } catch (error) {
      if (window.debugLog) {
        window.debugLog('error', 'Restart Network Error', { message: error.message });
      }
      alert("Failed to restart transcription");
    }
  };

  const processAudioFile = async (audioFileId) => {
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/audio-files/${audioFileId}/process/`, {
        method: "POST"
      }, token);
      if (response.ok) {
        fetchAudioFiles(); // Refresh the list
        onUpdate(); // Update parent component
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to start processing");
      }
    } catch (error) {
      alert("Failed to start processing");
    }
  };

  const deleteAudioFile = async (audioFileId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/audio-files/${audioFileId}/`, {
        method: 'DELETE'
      }, token);

      if (response.ok) {
        // Refresh the audio files list
        fetchAudioFiles();
        onUpdate(); // Update parent component
        alert("Audio file deleted successfully");
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to delete audio file");
      }
    } catch (error) {
      alert("Failed to delete audio file");
    }
  };

  if (loading) return <div className="audio-files-loading">Loading audio files...</div>;


  return (
    <div className="audio-files-list">
      {audioFiles.map((audioFile) => (
        <div key={audioFile.id} className="audio-file-item">
          <div className="audio-file-info">
            <div className="audio-file-name">{audioFile.filename}</div>
            <div className={`audio-file-status ${audioFile.status}`}>
              {audioFile.status}
            </div>
          </div>
          <div className="audio-file-actions">
            {(audioFile.status === 'pending' || audioFile.status === 'uploaded') && (
              <button
                className="transcribe-audio-btn"
                onClick={() => transcribeAudioFile(audioFile.id)}
              >
                1. Transcribe
              </button>
            )}
            {audioFile.status === 'transcribing' && (
              <div className="transcribing-actions">
                <span className="status-text">Transcribing...</span>
                <button
                  className="restart-btn"
                  onClick={() => restartTranscription(audioFile.id)}
                  title="Restart transcription"
                >
                  ↻ Restart
                </button>
              </div>
            )}
            {audioFile.status === 'transcribed' && (
              <button
                className="process-audio-btn"
                onClick={() => processAudioFile(audioFile.id)}
              >
                2. Detect Duplicates
              </button>
            )}
            {audioFile.status === 'processing' && (
              <span className="status-text">Processing...</span>
            )}
            {audioFile.status === 'completed' && audioFile.processed_audio_url && (
              <a 
                href={audioFile.processed_audio_url}
                download
                className="download-btn"
              >
                Download
              </a>
            )}
            
            {/* Delete button - appears for all statuses except processing */}
            {audioFile.status !== 'processing' && (
              <button
                className="delete-audio-btn"
                onClick={() => deleteAudioFile(audioFile.id, audioFile.filename)}
                title="Delete this audio file"
              >
                🗑️ Delete
              </button>
            )}
            {audioFile.status === 'failed' && (
              <div className="failed-actions">
                <span className="status-text error">Failed</span>
                <button
                  className="retry-btn"
                  onClick={() => transcribeAudioFile(audioFile.id)}
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

const ProjectDetailPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { token, user, isAuthenticated } = useAuth();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadingPDF, setUploadingPDF] = useState(false);
  const [uploadingAudio, setUploadingAudio] = useState(false);
  const [infrastructureStatus, setInfrastructureStatus] = useState(null);
  const [debugPanelVisible, setDebugPanelVisible] = useState(false);
  const [transcript, setTranscript] = useState(null);
  const [transcriptVisible, setTranscriptVisible] = useState(false);
  
  // Suppress AbortError in console - Enhanced version
  useEffect(() => {
    const handleUnhandledRejection = (event) => {
      if (event.reason?.name === 'AbortError' || 
          event.reason?.message?.includes('aborted') ||
          event.reason?.message?.includes('abort') ||
          event.message?.includes('aborted')) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        return false;
      }
    };
    
    const handleError = (event) => {
      if (event.message?.includes('AbortError') || 
          event.message?.includes('aborted') ||
          event.error?.name === 'AbortError') {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        return false;
      }
    };
    
    // Suppress console error for AbortError
    const originalConsoleError = console.error;
    console.error = (...args) => {
      const message = args.join(' ');
      if (message.includes('AbortError') || 
          message.includes('aborted') || 
          message.includes('BodyStreamBuffer was aborted')) {
        return; // Silently ignore
      }
      originalConsoleError.apply(console, args);
    };
    
    window.addEventListener('unhandledrejection', handleUnhandledRejection, true);
    window.addEventListener('error', handleError, true);
    
    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection, true);
      window.removeEventListener('error', handleError, true);
      console.error = originalConsoleError;
    };
  }, []);
  
  // New state for step-by-step workflow
  const [duplicateResults, setDuplicateResults] = useState(null);
  const [duplicateReview, setDuplicateReview] = useState(null);
  const [pdfMatchResults, setPdfMatchResults] = useState(null);
  const [currentTaskName, setCurrentTaskName] = useState(null);
  const [showPdfRefinement, setShowPdfRefinement] = useState(false);
  
  // Step 4: Verification state
  const [verificationResults, setVerificationResults] = useState(null);
  const [isVerifying, setIsVerifying] = useState(false);
  
  // Step 5: PDF Validation state
  const [isValidatingPDF, setIsValidatingPDF] = useState(false);
  const [validationProgress, setValidationProgress] = useState(0);
  const [validationResults, setValidationResults] = useState(null);
  const [validationError, setValidationError] = useState(null);
  const [validationTaskId, setValidationTaskId] = useState(null);
  
  // Step 6 & 7: Iterative Cleaning state
  const [creatingIteration, setCreatingIteration] = useState(false);
  const [iterationProject, setIterationProject] = useState(null);
  
  // Retry state - keep history of attempts
  const [retryAttempts, setRetryAttempts] = useState([]);
  const [showRetrySection, setShowRetrySection] = useState(false);
  
  // Waveform state
  const [wavesurfer, setWavesurfer] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const waveformRef = useRef(null);
  const [currentPass, setCurrentPass] = useState(1);
  const [processingPasses, setProcessingPasses] = useState([]);
  const [isRetrying, setIsRetrying] = useState(false);
  
  const pdfInputRef = useRef();
  const audioInputRef = useRef();
  const progressIntervalRef = useRef();
  const abortControllerRef = useRef(null);

  const fetchProjectDetails = useCallback(async () => {
    if (!token) {
      return;
    }
    
    // Cancel previous request if still pending
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    
    try {
      const response = await fetchWithAuth(
        `/api/projects/${projectId}/`, 
        { signal: abortControllerRef.current.signal }, 
        token
      );
      
      if (response.ok) {
        const data = await response.json();
        setProject(data.project);
        
        // Load duplicate results if they exist
        if (data.project.duplicates_detected) {
          setDuplicateResults(data.project.duplicates_detected);
        }
        
        // If project is processing, start polling for progress
        if (data.project.status === 'processing') {
          startProgressPolling();
        }
      } else if (response.status === 404) {
        alert("Project not found");
        navigate("/projects");
      }
    } catch (error) {
      // Ignore abort errors
      if (error.name !== 'AbortError') {
        alert("Error loading project details");
      }
    } finally {
      setLoading(false);
    }
  }, [projectId, token, navigate]);

  const fetchInfrastructureStatus = useCallback(async () => {
    if (!token) {
      return;
    }
    const url = 'http://localhost:8000/api/infrastructure/status/';
    
    if (window.debugLog) {
      window.debugLog('api-call', `GET ${url}`, { method: 'GET' });
    }
    
    try {
      const response = await fetchWithAuth(url, {}, token);
      
      if (window.debugLog) {
        window.debugLog('api-response', `Infrastructure Status: ${response.status}`, {
          status: response.status,
          ok: response.ok
        });
      }
      
      if (response.ok) {
        const data = await response.json();
        setInfrastructureStatus(data);
        
        if (window.debugLog) {
          window.debugLog('info', 'Infrastructure status updated', data);
        }
      } else {
        if (window.debugLog) {
          window.debugLog('error', `Infrastructure status failed: ${response.status}`, {
            status: response.status,
            statusText: response.statusText
          });
        }
      }
    } catch (error) {
      if (window.debugLog) {
        window.debugLog('error', 'Infrastructure status network error', {
          message: error.message
        });
      }
    }
  }, [token]);

  const fetchTranscript = useCallback(async () => {
    if (!token) {
      return;
    }
    
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/transcript/`, {}, token);
      
      if (response.ok) {
        const data = await response.json();
        setTranscript(data);
        
        if (window.debugLog) {
          window.debugLog('info', 'Transcript fetched successfully', {
            totalSegments: data.total_segments,
            audioFilesCount: data.audio_files_count
          });
        }
      } else {
        if (window.debugLog) {
          window.debugLog('error', `Transcript fetch failed: ${response.status}`, {
            status: response.status,
            statusText: response.statusText
          });
        }
      }
    } catch (error) {
      if (window.debugLog) {
        window.debugLog('error', 'Transcript fetch network error', {
          message: error.message
        });
      }
    }
  }, [token, projectId]);

  // Main useEffect hook for component initialization
  useEffect(() => {
    // Delay initial fetch to prevent double-calls during React strict mode
    const timeoutId = setTimeout(() => {
      fetchProjectDetails();
      fetchInfrastructureStatus();
    }, 100);
    
    // Poll infrastructure status every 30 seconds
    const infraInterval = setInterval(fetchInfrastructureStatus, 30000);
    
    return () => {
      clearTimeout(timeoutId);
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      clearInterval(infraInterval);
      // Cancel any pending fetch requests
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [projectId, fetchProjectDetails, fetchInfrastructureStatus]);

  const uploadPDF = async (file) => {
    setUploadingPDF(true);
    
    const formData = new FormData();
    formData.append('pdf_file', file);
    
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/upload-pdf/`, {
        method: "POST",
        body: formData
      }, token);
      
      if (response.ok) {
        fetchProjectDetails(); // Refresh project data
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to upload PDF");
      }
    } catch (error) {
      alert("Failed to upload PDF");
    } finally {
      setUploadingPDF(false);
    }
  };

  const uploadAudio = async (file) => {
    setUploadingAudio(true);
    
    const formData = new FormData();
    formData.append('audio_file', file);
    
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/upload-audio/`, {
        method: "POST",
        body: formData
      }, token);
      
      if (response.ok) {
        fetchProjectDetails(); // Refresh project data
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to upload audio");
      }
    } catch (error) {
      alert("Failed to upload audio");
    } finally {
      setUploadingAudio(false);
    }
  };

  const startTranscription = async () => {
    if (!project.has_pdf || !project.audio_files_count || project.audio_files_count === 0) {
      alert("Please upload both PDF and audio files before transcription");
      return;
    }

    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/transcribe/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        setProcessing(true);
        setProgress(0);
        startProgressPolling();
        fetchProjectDetails(); // Refresh to get updated status
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to start transcription");
      }
    } catch (error) {
      alert("Failed to start transcription");
    }
  };

  // Task Status Polling Function for Async Operations
  const pollTaskStatus = async (taskId, taskName, onSuccess) => {
    setCurrentTaskName(taskName);
    const pollInterval = 2000; // Poll every 2 seconds
    const maxPolls = 300; // Maximum 10 minutes (300 * 2 seconds)
    let pollCount = 0;
    
    const poll = async () => {
      try {
        
        const response = await fetchWithAuth(`/api/tasks/${taskId}/status/`, {}, token);
        
        if (response.ok) {
          const statusData = await response.json();
          
          if (statusData.status === 'completed') {
            setCurrentTaskName(null);
            setProcessing(false);
            if (onSuccess && statusData.result) {
              await onSuccess(statusData.result);
            }
            return; // Stop polling
          } else if (statusData.status === 'failed') {
            setCurrentTaskName(null);
            setProcessing(false);
            alert(`${taskName} failed: ${statusData.error || 'Unknown error'}`);
            return; // Stop polling
          } else if (statusData.status === 'in_progress' || statusData.status === 'pending') {
            
            // Update progress if we have a progress indicator
            if (statusData.progress && typeof statusData.progress === 'number') {
              setProgress(statusData.progress);
            }
            
            // Continue polling
            pollCount++;
            if (pollCount < maxPolls) {
              setTimeout(poll, pollInterval);
            } else {
              setCurrentTaskName(null);
              setProcessing(false);
              alert(`${taskName} is taking longer than expected. Please check back later.`);
            }
          }
        } else {
          // Retry a few times on server errors
          pollCount++;
          if (pollCount < 5) {
            setTimeout(poll, pollInterval * 2); // Wait longer on errors
          } else {
            setCurrentTaskName(null);
            setProcessing(false);
            alert(`Unable to check ${taskName} status. Please refresh and try again.`);
          }
        }
      } catch (error) {
        pollCount++;
        if (pollCount < 5) {
          setTimeout(poll, pollInterval * 2); // Wait longer on errors
        } else {
          setCurrentTaskName(null);
          setProcessing(false);
          alert(`Unable to check ${taskName} status. Please refresh and try again.`);
        }
      }
    };
    
    // Start polling immediately
    poll();
  };

  // New Step-by-Step Processing Functions
  
  const startPDFMatching = async () => {
    
    if (project.status !== 'transcribed') {
      alert(`All audio files must be transcribed first. Current status: ${project.status}`);
      return;
    }

    if (!project.has_pdf) {
      alert("A PDF file must be uploaded first before matching can begin.");
      return;
    }

    try {
      setProcessing(true);
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/match-pdf/`, {
        method: "POST"
      }, token);
      
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.task_id) {
          // Start polling for task completion
          await pollTaskStatus(data.task_id, 'PDF Matching', (result) => {
            // On successful completion
            if (result && result.match_result) {
              setPdfMatchResults(result.match_result);
            }
            fetchProjectDetails(); // Refresh to get updated status
          });
        } else {
          // Fallback to old synchronous response
          setPdfMatchResults(data.match_result);
          await fetchProjectDetails(); // Refresh to get updated status
        }
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to match PDF section");
      }
    } catch (error) {
      alert("Failed to match PDF section");
    } finally {
      setProcessing(false);
    }
  };

  const startDuplicateDetection = async () => {
    if (!project.pdf_match_completed) {
      alert("PDF matching must be completed first");
      return;
    }

    try {
      setProcessing(true);
      setProgress(0);
      const response = await fetchWithAuth(`/api/projects/${projectId}/detect-duplicates/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.task_id) {
          // Start polling for task completion
          await pollTaskStatus(data.task_id, 'Duplicate Detection', async (result) => {
            // On successful completion
            
            // First, refresh project details to get the saved duplicate results
            await fetchProjectDetails();
            
            // Then try to get the duplicate results from the task result or from project
            if (result && result.duplicate_results) {
              setDuplicateResults(result.duplicate_results);
              
              const count = result.duplicate_results.duplicates_found || 0;
              const groups = result.duplicate_results.duplicate_groups || 0;
              
              if (count > 0) {
                alert(`✅ Found ${count} duplicate segments in ${groups} groups!\n\nYou can now review them below.`);
              } else {
                alert(`ℹ️ No duplicates found in the audio transcription.`);
              }
            } else {
              // Fallback: fetch from project endpoint
              try {
                const projectResponse = await fetchWithAuth(`/api/projects/${projectId}/`, {}, token);
                if (projectResponse.ok) {
                  const projectData = await projectResponse.json();
                  if (projectData.project.duplicates_detected) {
                    setDuplicateResults(projectData.project.duplicates_detected);
                    const count = projectData.project.duplicates_detected.summary?.duplicates_count || 0;
                    alert(`✅ Found ${count} duplicate segments!`);
                  }
                }
              } catch (err) {
              }
            }
          });
        } else {
          // Fallback to old synchronous response
          setDuplicateResults(data.duplicate_results);
          alert(`Found ${data.duplicates_found} duplicate segments in ${data.duplicate_results.summary.unique_duplicate_groups} groups`);
          await fetchProjectDetails(); // Refresh to get updated status
        }
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to detect duplicates");
        setProcessing(false);
      }
    } catch (error) {
      alert("Failed to detect duplicates");
      setProcessing(false);
    }
  };

  const loadDuplicateReview = async () => {
    if (!project.duplicates_detection_completed) {
      alert("Duplicate detection must be completed first");
      return;
    }

    try {
      setProcessing(true);
      const response = await fetchWithAuth(`/api/projects/${projectId}/duplicates/`, {}, token);
      
      if (response.ok) {
        const data = await response.json();
        setDuplicateReview(data);
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`Failed to load duplicate review: ${errorData.error || errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      alert(`Failed to load duplicate review: ${error.message || 'Network error'}`);
    } finally {
      setProcessing(false);
    }
  };

  const savePdfBoundaries = async (startChar, endChar) => {
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/refine-pdf-boundaries/`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          start_char: startChar,
          end_char: endChar
        })
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        
        // Refresh project data to get updated boundaries
        await fetchProjectDetails();
        
        // Hide refinement UI and show comparison
        setShowPdfRefinement(false);
        
        alert(`✅ PDF boundaries saved successfully!\n\nSection length: ${data.section_length} characters\nConfidence: ${(data.confidence * 100).toFixed(1)}%`);
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to save PDF boundaries");
      }
    } catch (error) {
      alert("Failed to save PDF boundaries");
    }
  };

  const resetPDFMatching = async () => {
    if (!window.confirm("This will reset PDF matching and force re-extraction of PDF text. Continue?")) {
      return;
    }

    try {
      setProcessing(true);
      const response = await fetchWithAuth(`/api/projects/${projectId}/`, {
        method: "PATCH",
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          reset_pdf_text: true
        })
      }, token);
      
      if (response.ok) {
        setPdfMatchResults(null);
        setShowPdfRefinement(false);
        fetchProjectDetails(); // Refresh to get updated status
        alert("PDF matching has been reset. You can now try matching again.");
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to reset PDF matching");
      }
    } catch (error) {
      alert("Failed to reset PDF matching");
    } finally {
      setProcessing(false);
    }
  };

  const confirmDeletions = async (confirmedDeletions) => {
    try {
      setProcessing(true);
      setProgress(0);
      
      // Check infrastructure status first
      const infraResponse = await fetchWithAuth('/api/infrastructure/status/', {}, token);
      if (infraResponse.ok) {
        const infraData = await infraResponse.json();
        
        // If infrastructure is not running, start it
        if (!infraData.redis_running || !infraData.celery_running) {
          const confirmStart = window.confirm(
            "⚠️ Infrastructure not ready:\n\n" +
            `Redis: ${infraData.redis_running ? '✅ Running' : '❌ Stopped'}\n` +
            `Celery: ${infraData.celery_running ? '✅ Running' : '❌ Stopped'}\n\n` +
            "Would you like to start the infrastructure now?"
          );
          
          if (!confirmStart) {
            setProcessing(false);
            return;
          }
          
          // Start infrastructure
          const startResponse = await fetchWithAuth('/api/infrastructure/start/', {
            method: 'POST'
          }, token);
          
          if (!startResponse.ok) {
            alert("❌ Failed to start infrastructure. Please check Docker and try again.");
            setProcessing(false);
            return;
          }
          
          // Wait a moment for services to start
          alert("✅ Infrastructure starting... Please wait a moment.");
          await new Promise(resolve => setTimeout(resolve, 3000));
        }
      }
      
      // Proceed with deletion processing
      const response = await fetchWithAuth(`/api/projects/${projectId}/confirm-deletions/`, {
        method: "POST",
        body: JSON.stringify({
          confirmed_deletions: confirmedDeletions
        })
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        alert(`Processing ${data.confirmed_count} confirmed deletions...\n\nThis will:\n1. Remove duplicate segments\n2. Generate clean audio\n3. Automatically validate against PDF`);
        
        // Monitor progress and auto-validate on completion
        startProgressPolling(async () => {
          // On completion, automatically trigger PDF validation
          await fetchProjectDetails();
          
          // Give UI a moment to update
          setTimeout(async () => {
            try {
              // Auto-trigger PDF validation
              await validateAgainstPDF();
            } catch (error) {
              console.error('Auto-validation failed:', error);
            }
          }, 1000);
        });
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to process deletions");
        setProcessing(false);
      }
    } catch (error) {
      // Ignore abort errors
      if (error.name !== 'AbortError') {
        alert("Failed to confirm deletions");
      }
      setProcessing(false);
    }
  };

  const verifyCleanup = async () => {
    try {
      setIsVerifying(true);
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/verify-cleanup/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        setVerificationResults(data);
        alert("Verification complete! Check results below.");
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Verification failed");
      }
    } catch (error) {
      alert("Failed to verify cleanup");
    } finally {
      setIsVerifying(false);
    }
  };

  const validateAgainstPDF = async () => {
    try {
      setIsValidatingPDF(true);
      setValidationProgress(0);
      setValidationError(null);
      setValidationResults(null);
      
      // Start validation task
      const response = await fetchWithAuth(`/api/projects/${projectId}/validate-against-pdf/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        setValidationTaskId(data.task_id);
        
        // Poll progress
        const progressInterval = setInterval(async () => {
          try {
            const progressResponse = await fetchWithAuth(
              `/api/projects/${projectId}/validation-progress/${data.task_id}/`,
              {}, 
              token
            );
            
            if (progressResponse.ok) {
              const progressData = await progressResponse.json();
              setValidationProgress(progressData.progress || 0);
              
              if (progressData.completed) {
                clearInterval(progressInterval);
                setValidationResults(progressData.results);
                setIsValidatingPDF(false);
                
                // Check match percentage and alert accordingly
                const matchPercentage = progressData.results.match_percentage;
                if (matchPercentage < 90) {
                  alert(
                    `⚠️ PDF Validation Complete\n\n` +
                    `Match: ${matchPercentage}%\n\n` +
                    `Only ${matchPercentage}% of PDF words were found in the clean transcript.\n\n` +
                    `This is below the 90% threshold. You can:\n` +
                    `• Try different deletion selections\n` +
                    `• Create an iteration project for another pass\n` +
                    `• Accept the current result if it's good enough`
                  );
                } else {
                  alert(
                    `✅ PDF Validation Complete!\n\n` +
                    `Match: ${matchPercentage}%\n\n` +
                    `Great! ${matchPercentage}% of PDF words were found in the clean transcript.`
                  );
                }
              } else if (progressData.status === 'FAILURE') {
                clearInterval(progressInterval);
                setValidationError(progressData.error || "Validation failed");
                setIsValidatingPDF(false);
                alert("Validation failed: " + (progressData.error || "Unknown error"));
              }
            }
          } catch (error) {
          }
        }, 1000); // Poll every second
        
        // Timeout after 5 minutes
        setTimeout(() => {
          clearInterval(progressInterval);
          if (isValidatingPDF) {
            setValidationError("Validation timeout");
            setIsValidatingPDF(false);
          }
        }, 300000);
        
      } else {
        const errorData = await response.json();
        setValidationError(errorData.error || "Failed to start validation");
        setIsValidatingPDF(false);
        alert(errorData.error || "Failed to start validation");
      }
    } catch (error) {
      setValidationError("Failed to start validation");
      setIsValidatingPDF(false);
      alert("Failed to start PDF validation");
    }
  };

  // Helper function to format duration (seconds to MM:SS)
  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return '0:00';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  // Step 6: Create iteration project (completely fresh start with clean audio)
  const createIterationProject = async () => {
    if (!project.final_processed_audio) {
      alert("Clean audio must be generated first");
      return;
    }

    try {
      setCreatingIteration(true);
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/create-iteration/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        
        alert(`✅ Created new iteration project!\n\nIteration #${data.iteration_number}\n\nYou will now be redirected to the new project to continue the workflow from Step 1.`);
        
        // Navigate to the new child project
        navigate(`/projects/${data.child_project_id}`);
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to create iteration project");
      }
    } catch (error) {
      alert("Failed to create iteration project");
    } finally {
      setCreatingIteration(false);
    }
  };

  // Download processed audio file
  const downloadProcessedAudio = async () => {
    if (!project.final_processed_audio) {
      alert("No processed audio file available");
      return;
    }
    
    try {
      const audioUrl = `http://localhost:8000${project.final_processed_audio}`;
      const response = await fetch(audioUrl);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${project.title}_clean.wav`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      alert("Failed to download audio file");
    }
  };

  // Initialize WaveSurfer when processed audio is available
  useEffect(() => {
    if (project && project.final_processed_audio && waveformRef.current && !wavesurfer) {
      try {
        const ws = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: '#4a90e2',
          progressColor: '#2563eb',
          cursorColor: '#1e40af',
          barWidth: 2,
          barRadius: 3,
          cursorWidth: 1,
          height: 100,
          barGap: 2,
          responsive: true,
          normalize: true,
        });

        // Load audio file
        const audioUrl = `http://localhost:8000${project.final_processed_audio}`;
        ws.load(audioUrl);
        
        ws.on('ready', () => {
          // Waveform is ready
        });

        ws.on('play', () => {
          setIsPlaying(true);
        });

        ws.on('pause', () => {
          setIsPlaying(false);
        });

        ws.on('finish', () => {
          setIsPlaying(false);
        });

        ws.on('audioprocess', (time) => {
          setCurrentTime(time);
        });

        ws.on('seek', () => {
          setCurrentTime(ws.getCurrentTime());
        });
        
        ws.on('error', (error) => {
          // Silently handle waveform errors
          if (error.name !== 'AbortError') {
            // Only log non-abort errors if needed for debugging
          }
        });

        setWavesurfer(ws);

        return () => {
          if (ws) {
            ws.destroy();
          }
        };
      } catch (error) {
        // Silently handle initialization errors
        if (error.name !== 'AbortError') {
          // Only log non-abort errors
        }
      }
    }
  }, [project, waveformRef, wavesurfer]);

  // Waveform control functions
  const togglePlayPause = () => {
    if (wavesurfer) {
      wavesurfer.playPause();
    }
  };

  const stopAudio = () => {
    if (wavesurfer) {
      wavesurfer.stop();
      setIsPlaying(false);
      setCurrentTime(0);
    }
  };

  const retryProcessing = async () => {
    try {
      setIsRetrying(true);
      setProcessing(true);
      
      // Save current pass data before starting new one
      const passData = {
        passNumber: currentPass,
        timestamp: new Date().toLocaleString(),
        status: project.status,
        error: project.error_message,
        hasFile: !!project.final_processed_audio,
        duplicateResults: duplicateResults,
        duplicateReview: duplicateReview,
        segmentsKept: project.segments?.filter(s => !s.is_duplicate).length || 0,
        duplicatesRemoved: project.segments?.filter(s => s.is_duplicate).length || 0,
        pdfMatchResults: pdfMatchResults
      };
      
      setProcessingPasses(prev => [...prev, passData]);
      setCurrentPass(prev => prev + 1);
      
      // Clear current results to show new detection
      setDuplicateResults(null);
      setDuplicateReview(null);
      
      // Start fresh duplicate detection
      await startDuplicateDetection();
      
      setIsRetrying(false);
      
    } catch (error) {
      alert("Failed to retry processing");
      setIsRetrying(false);
      setProcessing(false);
    }
  };

  const resetPDFMatch = async () => {
    try {
      // Reset the PDF match status on the backend
      const response = await fetchWithAuth(`/api/projects/${projectId}/`, {
        method: 'PATCH',
        body: JSON.stringify({
          pdf_match_completed: false,
          pdf_matched_section: null,
          pdf_match_confidence: null,
          pdf_chapter_title: null
        })
      }, token);
      
      if (response.ok) {
        setPdfMatchResults(null);
        fetchProjectDetails(); // Refresh project data
      }
    } catch (error) {
      alert("Failed to reset match. Please refresh the page.");
    }
  };

  const resetDuplicateDetection = async () => {
    if (!window.confirm("Reset and re-run duplicate detection?\n\nThis will clear current results and immediately start detecting duplicates again.")) {
      return;
    }
    
    try {
      setProcessing(true);
      setProgress(0);
      
      // Reset the duplicate detection status on the backend
      const response = await fetchWithAuth(`/api/projects/${projectId}/`, {
        method: 'PATCH',
        body: JSON.stringify({
          duplicates_detection_completed: false,
          duplicates_detected: null,
          duplicates_confirmed_for_deletion: [],
          status: 'pdf_matched'  // Reset to the state before duplicate detection
        })
      }, token);
      
      if (response.ok) {
        setDuplicateResults(null);
        setDuplicateReview(null);
        
        // Wait a moment for the backend to update
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Refresh project data
        await fetchProjectDetails();
        
        // Automatically start duplicate detection again
        await startDuplicateDetection();
      } else {
        setProcessing(false);
        alert("Failed to reset duplicate detection. Please try again.");
      }
    } catch (error) {
      setProcessing(false);
      alert("Failed to reset duplicate detection. Please refresh the page.");
    }
  };

  const startProgressPolling = (onComplete) => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }

    progressIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetchWithAuth(`/api/projects/${projectId}/status/`, {}, token);
        
        if (response.ok) {
          const data = await response.json();
          setProgress(data.progress);
          
          // Check for various completion states
          if (data.status === 'completed' || data.status === 'transcribed' || data.status === 'ready') {
            setProcessing(false);
            clearInterval(progressIntervalRef.current);
            await fetchProjectDetails(); // Refresh project data
            
            // Call completion callback if provided
            if (onComplete && typeof onComplete === 'function') {
              setTimeout(() => onComplete(), 500);
            }
          } else if (data.status === 'failed') {
            setProcessing(false);
            clearInterval(progressIntervalRef.current);
            alert(`Processing failed: ${data.error || 'Unknown error'}`);
            fetchProjectDetails(); // Refresh project data
          }
        }
      } catch (error) {
      }
    }, 2000); // Poll every 2 seconds
  };

  const deleteProject = async () => {
    if (!project) {
      alert("Project data not loaded. Please refresh the page.");
      return;
    }
    
    const confirmDelete = window.confirm(
      `⚠️ Are you sure you want to delete "${project.title}"?\n\n` +
      `This will permanently delete:\n` +
      `• The project and all settings\n` +
      `• All uploaded audio files (${project.audio_files_count || 0} files)\n` +
      `• All transcriptions and processing results\n` +
      `• The uploaded PDF file\n` +
      `• Any processed audio files\n\n` +
      `This action CANNOT be undone!`
    );
    
    if (!confirmDelete) {
      return;
    }
    
    // Second confirmation for extra safety
    const secondConfirm = window.confirm(
      `🚨 FINAL CONFIRMATION\n\n` +
      `You are about to permanently delete "${project.title}" and ALL its data.\n\n` +
      `Type "${project.title}" in the prompt to confirm deletion.`
    );
    
    if (!secondConfirm) {
      return;
    }
    
    const typedTitle = prompt(
      `Please type the project title exactly to confirm deletion:\n"${project.title}"`
    );
    
    if (typedTitle !== project.title) {
      alert("Project title does not match. Deletion cancelled.");
      return;
    }
    
    try {
      setProcessing(true);
      
      // Debug log
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/`, {
        method: "DELETE"
      }, token);
      
      
      if (response.ok) {
        const data = await response.json();
        alert(`✅ ${data.message}\n\nFiles cleaned up: ${data.files_deleted || 0}`);
        navigate("/projects"); // Redirect to project list
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`❌ Failed to delete project: ${errorData.error || errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      alert(`❌ Failed to delete project: ${error.message || 'Please try again.'}`);
    } finally {
      setProcessing(false);
    }
  };

  const handlePDFFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'application/pdf') {
      uploadPDF(file);
    } else {
      alert("Please select a valid PDF file");
    }
  };

  const handleAudioFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      const allowedTypes = ['audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/flac', 'audio/ogg'];
      if (allowedTypes.includes(file.type) || file.name.match(/\\.(wav|mp3|m4a|flac|ogg)$/i)) {
        uploadAudio(file);
      } else {
        alert("Please select a valid audio file (WAV, MP3, M4A, FLAC, OGG)");
      }
    }
  };

  const getProgressMessage = () => {
    if (progress < 10) return "Initializing...";
    if (progress < 30) return "Transcribing audio...";
    if (progress < 50) return "Processing PDF...";
    if (progress < 70) return "Analyzing duplicates...";
    if (progress < 90) return "Generating processed audio...";
    return "Finalizing...";
  };

  if (loading) {
    return (
      <div className="project-detail-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading project...</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="project-detail-page">
        <div className="error-container">
          <h2>Project not found</h2>
          <button onClick={() => navigate("/projects")}>Back to Projects</button>
        </div>
      </div>
    );
  }

  return (
    <div className="project-detail-page">
      <div className="project-header">
        <div className="header-left">
          <button className="back-btn" onClick={() => navigate("/projects")}>
            ← Back to Projects
          </button>
          <h1>{project.title}</h1>
        </div>
        <div className="header-right">
          <button 
            className="delete-btn danger-btn"
            onClick={deleteProject}
            disabled={processing}
            title="Delete project and all data"
          >
            🗑️ Delete Project
          </button>
        </div>
        <div className="header-badges">
          <div className={`status-badge ${project.status}`}>
            {project.status}
          </div>
          {infrastructureStatus && (
            <div className={`infra-badge ${infrastructureStatus.infrastructure_running ? 'running' : 'stopped'}`}>
              Docker: {infrastructureStatus.infrastructure_running ? 'Running' : 'Stopped'}
              {infrastructureStatus.active_tasks > 0 && (
                <span className="task-count"> ({infrastructureStatus.active_tasks} tasks)</span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="project-content">
        {/* File Upload Section */}
        <div className="upload-section">
          <h2>1. Upload Files</h2>
          
          <div className="file-uploads">
            {/* PDF Upload */}
            <div className="file-upload-card">
              <div className="file-icon">📄</div>
              <h3>PDF Document</h3>
              <p>Upload the book/document that was read</p>
              
              {project.has_pdf ? (
                <div className="file-uploaded">
                  <span className="success-icon">✓</span>
                  <span>PDF uploaded successfully</span>
                  {project.pdf_filename && (
                    <div className="pdf-filename">File: <strong>{project.pdf_filename}</strong></div>
                  )}
                </div>
              ) : (
                <div>
                  <input
                    type="file"
                    accept=".pdf"
                    ref={pdfInputRef}
                    style={{ display: 'none' }}
                    onChange={handlePDFFileSelect}
                  />
                  <button
                    className="upload-btn"
                    onClick={() => pdfInputRef.current?.click()}
                    disabled={uploadingPDF}
                  >
                    {uploadingPDF ? "Uploading..." : "Choose PDF File"}
                  </button>
                </div>
              )}
            </div>

            {/* Audio Upload */}
            <div className="file-upload-card">
              <div className="file-icon">🎵</div>
              <h3>Audio Recording</h3>
              <p>Upload the audio recording of reading</p>
              
              <div>
                <input
                  type="file"
                  accept=".wav,.mp3,.m4a,.flac,.ogg"
                  ref={audioInputRef}
                  style={{ display: 'none' }}
                  onChange={handleAudioFileSelect}
                />
                <button
                  className="upload-btn"
                  onClick={() => audioInputRef.current?.click()}
                  disabled={uploadingAudio}
                >
                  {uploadingAudio ? "Uploading..." : (project.audio_files_count > 0 ? "Add Audio File" : "Choose Audio File")}
                </button>
                {project.audio_files_count > 0 && (
                  <div className="file-uploaded">
                    <span className="success-icon">✓</span>
                    <span>{project.audio_files_count} audio file(s) uploaded</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Audio Files Management */}
          {project.audio_files_count > 0 && (
            <div className="audio-files-section">
              <h3>Audio Files</h3>
              <AudioFilesList projectId={projectId} onUpdate={fetchProjectDetails} token={token} />
              
              <div className="add-more-audio">
                <input
                  type="file"
                  accept=".wav,.mp3,.m4a,.flac,.ogg"
                  ref={audioInputRef}
                  style={{ display: 'none' }}
                  onChange={handleAudioFileSelect}
                />
                <button
                  className="upload-btn secondary"
                  onClick={() => audioInputRef.current?.click()}
                  disabled={uploadingAudio}
                >
                  {uploadingAudio ? "Uploading..." : "Add Another Audio File"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Processing Section - New 2-Phase Workflow */}
        <div className="processing-section">
          <h2>2. Process Audio (2-Step Workflow)</h2>
          
          {/* Step 1: Transcription Phase */}
          <div className="workflow-step">
            <h3>Step 1: Transcribe All Audio Files</h3>
            <p>Convert all audio recordings to text with precise word timestamps</p>
            
            {(project.status === 'setup' || project.status === 'ready') && project.has_pdf && project.audio_files_count > 0 && (
              <div className="ready-to-transcribe">
                <p>✅ All files uploaded. Ready to start transcription!</p>
                <p>📝 This will transcribe {project.audio_files_count} audio file(s) with word timestamps</p>
                <button 
                  className="transcribe-btn primary-btn"
                  onClick={startTranscription}
                  disabled={processing}
                >
                  🎤 Start Transcription ({project.audio_files_count} files)
                </button>
              </div>
            )}
            
            {project.status === 'transcribing' && (
              <div className="transcribing-status">
                <p>🎤 Transcribing audio files... This may take several minutes.</p>
                <div className="progress-bar">
                  <div className="progress-fill" style={{width: `${progress}%`}}></div>
                </div>
                <p>Progress: {progress}%</p>
                <div className="transcribe-actions">
                  <button 
                    className="action-btn btn-warning"
                    onClick={async () => {
                      if (window.confirm('Are you sure you want to restart transcription? This will stop the current process and start over.')) {
                        setProcessing(false);
                        setProgress(0);
                        // Wait a moment for the current task to settle
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        startTranscription();
                      }
                    }}
                  >
                    🔄 Restart Transcription
                  </button>
                </div>
              </div>
            )}
            
            {project.status === 'transcribed' && (
              <div className="transcription-complete">
                <p>✅ Transcription Complete!</p>
                <p>📊 {project.transcribed_files_count} of {project.audio_files_count} files transcribed with word timestamps</p>
                <button 
                  className="action-btn btn-info"
                  onClick={() => {
                    if (!transcript) {
                      fetchTranscript();
                    }
                    setTranscriptVisible(!transcriptVisible);
                  }}
                >
                  {transcriptVisible ? '📄 Hide Transcript' : '📄 View Transcript'}
                </button>
                
                {transcriptVisible && transcript && (
                  <div className="transcript-display">
                    <h4>📝 Full Transcript</h4>
                    <div className="transcript-stats">
                      <p><strong>Total Segments:</strong> {transcript.total_segments}</p>
                      <p><strong>Audio Files:</strong> {transcript.audio_files_count}</p>
                    </div>
                    <div className="transcript-content">
                      <pre>{transcript.full_transcript}</pre>
                    </div>
                  </div>
                )}
              </div>
            )}

            {(project.status === 'failed' || project.status === 'error') && (
              <div className="transcription-failed">
                <p className="error-message">❌ Transcription Failed</p>
                <p>An error occurred during transcription. You can try again or check the logs.</p>
                <button 
                  className="action-btn btn-warning"
                  onClick={() => {
                    if (window.confirm('Retry transcription? This will start the process over.')) {
                      startTranscription();
                    }
                  }}
                >
                  🔄 Retry Transcription
                </button>
              </div>
            )}
          </div>

          {/* Step 2: Interactive Duplicate Detection Workflow */}
          <div className="workflow-step">
            <h3>Step 2: Interactive Duplicate Detection</h3>
            <p>Match audio to PDF and identify duplicates with user confirmation</p>
            
            {/* Step 2a: PDF Section Matching */}
            <div className="sub-step">
              <h4>2a. Match Audio to PDF Section</h4>
              {project.status === 'transcribed' && !project.pdf_match_completed && (
                <div className="pdf-matching">
                  <p>🔍 First, we'll identify which section of your PDF corresponds to the audio</p>
                  {processing ? (
                    <div className="processing-status">
                      <div className="loading-spinner"></div>
                      <p>🔍 {currentTaskName || 'Analyzing PDF content and matching with audio transcript'}...</p>
                      {progress > 0 && (
                        <div className="progress-container">
                          <div className="progress-bar">
                            <div className="progress-fill" style={{width: `${progress}%`}}></div>
                          </div>
                          <span className="progress-text">{progress}%</span>
                        </div>
                      )}
                      <p><em>This may take a few moments...</em></p>
                    </div>
                  ) : (
                    <button 
                      className="match-pdf-btn primary-btn"
                      onClick={startPDFMatching}
                      disabled={processing}
                    >
                      📚 Match Audio to PDF Section
                    </button>
                  )}
                </div>
              )}
              
              {project.pdf_match_completed && (
                <div className="pdf-match-complete">
                  <p>✅ PDF Section Matched!</p>
                  <div className="match-results">
                    <p><strong>Chapter:</strong> {project.pdf_chapter_title}</p>
                    <p><strong>Confidence:</strong> {(project.pdf_match_confidence * 100).toFixed(1)}%</p>
                  </div>
                  
                  <div className="pdf-actions">
                    <button 
                      className="action-btn btn-reset"
                      onClick={resetPDFMatching}
                      title="Reset and re-extract PDF text"
                    >
                      🔄 Reset PDF Matching
                    </button>
                    
                    <button 
                      className="action-btn btn-info"
                      onClick={() => {
                        if (!transcript) {
                          fetchTranscript();
                        }
                        setTranscriptVisible(!transcriptVisible);
                      }}
                    >
                      {transcriptVisible ? '📄 Hide Transcript' : '📄 View Transcript'}
                    </button>
                  </div>
                  
                  {transcriptVisible && transcript && (
                    <div className="transcript-display" style={{marginTop: '15px'}}>
                      <h4>📝 Full Transcript</h4>
                      <div className="transcript-stats">
                        <p><strong>Total Segments:</strong> {transcript.total_segments}</p>
                        <p><strong>Audio Files:</strong> {transcript.audio_files_count}</p>
                      </div>
                      <div className="transcript-content">
                        <pre>{transcript.full_transcript}</pre>
                      </div>
                    </div>
                  )}
                  
                  <div className="debug-info" style={{backgroundColor: '#f0f0f0', padding: '10px', margin: '10px 0'}}>
                    <h5>Debug Info:</h5>
                    <p>pdf_match_completed: {project.pdf_match_completed ? 'true' : 'false'}</p>
                    <p>combined_transcript: {project.combined_transcript ? 'exists' : 'missing'}</p>
                    <p>pdf_matched_section: {project.pdf_matched_section ? 'exists' : 'missing'}</p>
                    <p>pdfMatchResults: {pdfMatchResults ? 'exists' : 'null'}</p>
                  </div>
                  
                  {/* PDF Boundary Refinement UI */}
                  {showPdfRefinement && project && project.pdf_match_completed ? (
                    <PDFBoundaryRefinement 
                      project={project}
                      projectId={projectId}
                      token={token}
                      onSave={savePdfBoundaries}
                      onCancel={() => setShowPdfRefinement(false)}
                    />
                  ) : null}
                  
                  {/* Side-by-side comparison */}
                  {!showPdfRefinement && project && project.pdf_match_completed ? (
                    <>
                      <PDFMatchComparison 
                        project={project}
                        matchResults={pdfMatchResults || {
                          matched_section: project.pdf_matched_section,
                          confidence: project.pdf_match_confidence,
                          chapter_title: project.pdf_chapter_title
                        }}
                        onConfirmMatch={async () => {
                          setPdfMatchResults(null); // Hide comparison after confirmation
                          setShowPdfRefinement(false);
                          // Automatically trigger duplicate detection
                          await startDuplicateDetection();
                        }}
                        onRejectMatch={() => {
                          // Reset match status and try again
                          resetPDFMatch();
                        }}
                      />
                      
                      {/* Button to refine boundaries */}
                      <div style={{marginTop: '20px', textAlign: 'center'}}>
                        <button 
                          className="refine-boundaries-btn"
                          onClick={() => setShowPdfRefinement(true)}
                        >
                          🎯 Refine Start/End Boundaries
                        </button>
                      </div>
                    </>
                  ) : project.pdf_match_completed ? (
                    <div className="loading-comparison">
                      <p>Loading comparison data...</p>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
            
            {/* Step 2b: Duplicate Detection */}
            <div className="sub-step">
              <h4>2b. Detect Duplicates</h4>
              {project.pdf_match_completed && !project.duplicates_detection_completed && (
                <div className="duplicate-detection">
                  <p>🔍 Compare transcribed audio against PDF to find repeated content</p>
                  {processing ? (
                    <div className="processing-status">
                      <div className="loading-spinner"></div>
                      <p>🔍 {currentTaskName || 'Analyzing audio transcript for duplicate content'}...</p>
                      {progress > 0 && (
                        <div className="progress-container">
                          <div className="progress-bar">
                            <div className="progress-fill" style={{width: `${progress}%`}}></div>
                          </div>
                          <span className="progress-text">{progress}%</span>
                        </div>
                      )}
                      <p><em>Comparing against PDF sections...</em></p>
                    </div>
                  ) : (
                    <button 
                      className="detect-duplicates-btn primary-btn"
                      onClick={startDuplicateDetection}
                      disabled={processing}
                    >
                      🔍 Detect Duplicates
                    </button>
                  )}
                </div>
              )}
              
              {project.duplicates_detection_completed && (
                <div className="duplicates-detected">
                  <p>✅ Duplicates Detected!</p>
                  <div className="duplicate-summary">
                    <p><strong>Duplicates Found:</strong> {duplicateResults?.summary?.total_duplicate_segments || 0}</p>
                    <p><strong>Groups:</strong> {duplicateResults?.summary?.unique_duplicate_groups || 0}</p>
                    <p><strong>To Delete:</strong> {duplicateResults?.summary?.segments_to_delete || 0}</p>
                    <p><strong>To Keep:</strong> {duplicateResults?.summary?.segments_to_keep || 0}</p>
                  </div>
                  
                  <div className="action-buttons">
                    <button 
                      className="action-btn btn-info"
                      onClick={() => {
                        if (!transcript) {
                          fetchTranscript();
                        }
                        setTranscriptVisible(!transcriptVisible);
                      }}
                    >
                      {transcriptVisible ? '📄 Hide Transcript' : '📄 View Transcript'}
                    </button>
                    
                    <button 
                      className="action-btn btn-reset"
                      onClick={resetDuplicateDetection}
                      title="Reset duplicate detection and run again"
                    >
                      🔄 Reset & Re-detect
                    </button>
                  </div>
                  
                  {transcriptVisible && transcript && (
                    <div className="transcript-display" style={{marginTop: '15px'}}>
                      <h4>📝 Full Transcript</h4>
                      <div className="transcript-stats">
                        <p><strong>Total Segments:</strong> {transcript.total_segments}</p>
                        <p><strong>Audio Files:</strong> {transcript.audio_files_count}</p>
                      </div>
                      <div className="transcript-content">
                        <pre>{transcript.full_transcript}</pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {/* Step 2c: Interactive Review */}
            <div className="sub-step">
              <h4>2c. Review & Confirm Deletions</h4>
              {project.duplicates_detection_completed && (
                <div className="duplicate-review">
                  <p>👁️ Review detected duplicates and confirm which ones to delete</p>
                  <button 
                    className="review-duplicates-btn primary-btn"
                    onClick={loadDuplicateReview}
                    disabled={processing}
                  >
                    �️ Review Duplicates
                  </button>
                  
                  {duplicateReview && (
                    <DuplicateReviewComponent 
                      duplicates={duplicateReview}
                      transcript={transcript}
                      onConfirmDeletions={confirmDeletions}
                      onFetchTranscript={fetchTranscript}
                    />
                  )}
                </div>
              )}
            </div>
            
            {project.status === 'processing' && (
              <div className="processing-status">
                <p>🔍 Processing confirmed deletions and generating final audio...</p>
                <div className="progress-bar">
                  <div className="progress-fill" style={{width: `${progress}%`}}></div>
                </div>
                <p>Progress: {progress}%</p>
              </div>
            )}
            
            {project.status === 'failed' && project.duplicates_confirmed_for_deletion && (
              <div className="processing-failed">
                <h4>❌ Processing Failed</h4>
                <p className="error-message">{project.error_message || 'An error occurred during processing'}</p>
                <button 
                  className="retry-btn btn-warning"
                  onClick={() => confirmDeletions(project.duplicates_confirmed_for_deletion)}
                  disabled={processing}
                >
                  🔄 Retry Processing
                </button>
                <p className="help-text">If the error persists, contact support or restart the application.</p>
              </div>
            )}
          </div>

          {/* Results Section */}
          {project.status === 'completed' && project.processing_result && (
            <div className="results-section">
              <h3>✅ Processing Complete - Results</h3>
              <div className="results-grid">
                <div className="result-card">
                  <h4>🎯 Duplicates Found & Removed</h4>
                  <div className="result-stats">
                    <p><strong>Total Duplicates:</strong> {project.total_duplicates_found}</p>
                    <p><strong>Words Removed:</strong> {project.processing_result.words_removed}</p>
                    <p><strong>Sentences Removed:</strong> {project.processing_result.sentences_removed}</p>
                    <p><strong>Paragraphs Removed:</strong> {project.processing_result.paragraphs_removed}</p>
                  </div>
                </div>
                
                <div className="result-card">
                  <h4>⏱️ Time Savings</h4>
                  <div className="result-stats">
                    <p><strong>Original Duration:</strong> {Math.round(project.processing_result.original_total_duration / 60)} minutes</p>
                    <p><strong>Final Duration:</strong> {Math.round(project.processing_result.final_duration / 60)} minutes</p>
                    <p><strong>Time Saved:</strong> {Math.round(project.processing_result.time_saved / 60)} minutes</p>
                  </div>
                </div>
                
                <div className="result-card">
                  <h4>📖 Content Coverage</h4>
                  <div className="result-stats">
                    <p><strong>PDF Coverage:</strong> {project.processing_result.pdf_coverage_percentage?.toFixed(1)}%</p>
                    <p><strong>Missing Content:</strong> {project.processing_result.missing_content_count} sections</p>
                    <p><strong>Segments Processed:</strong> {project.processing_result.total_segments_processed}</p>
                  </div>
                </div>
              </div>
              
              {project.missing_content && (
                <div className="missing-content">
                  <h4>📝 Missing Content from PDF</h4>
                  <p>The following content from your PDF was not found in the audio recordings:</p>
                  <div className="missing-text">
                    {project.missing_content.split('\n').slice(0, 5).map((line, index) => (
                      <p key={index}>{line}</p>
                    ))}
                    {project.missing_content.split('\n').length > 5 && <p>... and more</p>}
                  </div>
                </div>
              )}
            </div>
          )}

          {(processing || project.status === 'processing' || isRetrying) && (
            <div className="processing-indicator">
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${Math.max(progress, 5)}%` }}
                ></div>
              </div>
              <p className="progress-text">
                {isRetrying ? `🔄 Pass #${currentPass} - ${getProgressMessage()}` : getProgressMessage()} ({Math.max(progress, 0)}%)
              </p>
              {isRetrying && (
                <p className="retry-info">Processing new duplicate detection while keeping previous results below...</p>
              )}
            </div>
          )}

          {project.status === 'failed' && (
            <div className="error-message">
              <p>❌ Processing failed: {project.error_message}</p>
              <button className="retry-btn" onClick={() => window.location.reload()}>
                Refresh Page to Retry
              </button>
            </div>
          )}
        </div>

        {/* Enhanced Results Section - Top Priority */}
        {project.status === 'completed' && (
          <div className="results-section">
            <h2>3. Results {processingPasses.length > 0 && `- Pass #${currentPass}`}</h2>
            
            {/* Primary Results Card - Download, Stats, Waveform */}
            <div className="primary-results-card">
              <h3>🎵 Processed Audio File</h3>
              
              {/* Download Section */}
              <div className="download-section">
                {project.final_processed_audio ? (
                  <>
                    <button 
                      className="primary-btn download-btn-large"
                      onClick={downloadProcessedAudio}
                    >
                      📥 Download Clean Audio
                    </button>
                    <p className="file-info">Audio with duplicates removed, keeping only the final version of repeated content</p>
                  </>
                ) : (
                  <div className="error-box">
                    <p>⚠️ Processed audio file not available. Processing may have failed.</p>
                    <button className="retry-btn" onClick={retryProcessing}>
                      🔄 Retry Processing
                    </button>
                  </div>
                )}
              </div>
              
              {/* Time Statistics */}
              <div className="time-stats-grid">
                <div className="time-stat-card original">
                  <div className="stat-icon">⏱️</div>
                  <div className="stat-content">
                    <h4>Original Duration</h4>
                    <div className="stat-value">{formatDuration(project.original_audio_duration)}</div>
                    <p className="stat-label">Total recorded time</p>
                  </div>
                </div>
                
                <div className="time-stat-card deleted">
                  <div className="stat-icon">✂️</div>
                  <div className="stat-content">
                    <h4>Time Deleted</h4>
                    <div className="stat-value">{formatDuration(project.duration_deleted)}</div>
                    <p className="stat-label">{project.total_duplicates_found} duplicate segments</p>
                  </div>
                </div>
                
                <div className="time-stat-card final">
                  <div className="stat-icon">✅</div>
                  <div className="stat-content">
                    <h4>Final Duration</h4>
                    <div className="stat-value">{formatDuration(project.final_audio_duration)}</div>
                    <p className="stat-label">Clean audio length</p>
                  </div>
                </div>
                
                <div className="time-stat-card savings">
                  <div className="stat-icon">📊</div>
                  <div className="stat-content">
                    <h4>Time Saved</h4>
                    <div className="stat-value">
                      {project.original_audio_duration > 0 
                        ? `${((project.duration_deleted / project.original_audio_duration) * 100).toFixed(1)}%`
                        : '0%'}
                    </div>
                    <p className="stat-label">Reduction in audio length</p>
                  </div>
                </div>
              </div>
              
              {/* Interactive Waveform */}
              {project.final_processed_audio && (
                <div className="waveform-section">
                  <h4>🎧 Preview & Listen</h4>
                  <p className="waveform-description">Click anywhere on the waveform to jump to that position</p>
                  
                  <div className="waveform-container">
                    <div id="waveform" ref={waveformRef}></div>
                    
                    <div className="waveform-controls">
                      <button 
                        className="control-btn"
                        onClick={togglePlayPause}
                      >
                        {isPlaying ? '⏸️ Pause' : '▶️ Play'}
                      </button>
                      
                      <div className="timeline-info">
                        <span className="current-time">{formatDuration(currentTime)}</span>
                        <span className="divider">/</span>
                        <span className="total-time">{formatDuration(project.final_audio_duration)}</span>
                      </div>
                      
                      <button 
                        className="control-btn"
                        onClick={stopAudio}
                      >
                        ⏹️ Stop
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Secondary Results - PDF Matching */}
            <div className="secondary-results-grid">
              <div className="result-card">
                <h3>📄 PDF Section Matched</h3>
                <div className="pdf-section">
                  {project.pdf_section_matched ? (
                    <p>{project.pdf_section_matched.substring(0, 300)}...</p>
                  ) : (
                    <p>No matching section found</p>
                  )}
                </div>
              </div>

              <div className="result-card">
                <h3>Processing Summary</h3>
                <div className="summary-stats">
                  <div className="stat">
                    <span className="stat-number">{project.segments?.filter(s => !s.is_duplicate).length || 0}</span>
                    <span className="stat-label">Segments Kept</span>
                  </div>
                  <div className="stat">
                    <span className="stat-number">{project.segments?.filter(s => s.is_duplicate).length || 0}</span>
                    <span className="stat-label">Duplicates Removed</span>
                  </div>
                </div>
              </div>

              <div className="result-card download-card">
                <h3>Download Processed Audio</h3>
                <p>Audio with duplicates removed, keeping only the final version of repeated content.</p>
                
                {/* Debug info */}
                <div style={{fontSize: '12px', color: '#666', marginBottom: '10px'}}>
                  Status: {project.status} | 
                  Has file: {project.final_processed_audio ? 'Yes' : 'No'} | 
                  Transcribed: {project.clean_audio_transcribed ? 'Yes' : 'No'}
                </div>
                
                {project.final_processed_audio ? (
                  <button 
                    className="download-btn"
                    onClick={downloadProcessedAudio}
                  >
                    📥 Download Clean Audio
                  </button>
                ) : (
                  <div>
                    <p className="error-text">⚠️ Processed audio file not available. Processing may have failed.</p>
                    {project.error_message && (
                      <p className="error-text">Error: {project.error_message}</p>
                    )}
                    <button 
                      className="retry-btn"
                      onClick={retryProcessing}
                    >
                      🔄 Retry Processing (Keep History)
                    </button>
                    <p style={{fontSize: '12px', color: '#666', marginTop: '10px'}}>
                      This will retry duplicate detection and confirmation while keeping the current results visible above.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Previous Passes Section - Show all historical passes */}
            {processingPasses.length > 0 && (
              <div className="previous-passes-section">
                <h2>📚 Previous Processing Passes</h2>
                <p className="section-description">Scroll down to see all attempts and compare results</p>
                
                {processingPasses.map((pass, index) => (
                  <div key={index} className="pass-card">
                    <div className="pass-header">
                      <h3>Pass #{pass.passNumber} - {pass.timestamp}</h3>
                      <span className={`pass-status ${pass.hasFile ? 'success' : 'failed'}`}>
                        {pass.hasFile ? '✅ Completed' : '❌ Failed'}
                      </span>
                    </div>
                    
                    <div className="pass-content">
                      {/* PDF Match Results */}
                      {pass.pdfMatchResults && (
                        <div className="pass-section">
                          <h4>PDF Section Matched</h4>
                          <div className="pdf-match-summary">
                            <p><strong>Chapter:</strong> {pass.pdfMatchResults.pdf_chapter_title || 'N/A'}</p>
                            <p><strong>Confidence:</strong> {(pass.pdfMatchResults.pdf_match_confidence * 100).toFixed(1)}%</p>
                          </div>
                        </div>
                      )}
                      
                      {/* Duplicate Detection Results */}
                      {pass.duplicateResults && (
                        <div className="pass-section">
                          <h4>Duplicate Detection</h4>
                          <div className="duplicate-stats">
                            <div className="stat-item">
                              <span className="stat-label">Total Duplicates:</span>
                              <span className="stat-value">{pass.duplicateResults.summary?.total_duplicate_segments || 0}</span>
                            </div>
                            <div className="stat-item">
                              <span className="stat-label">Groups:</span>
                              <span className="stat-value">{pass.duplicateResults.summary?.unique_duplicate_groups || 0}</span>
                            </div>
                            <div className="stat-item">
                              <span className="stat-label">To Delete:</span>
                              <span className="stat-value">{pass.duplicateResults.summary?.segments_to_delete || 0}</span>
                            </div>
                            <div className="stat-item">
                              <span className="stat-label">To Keep:</span>
                              <span className="stat-value">{pass.duplicateResults.summary?.segments_to_keep || 0}</span>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {/* Processing Results */}
                      <div className="pass-section">
                        <h4>Final Processing</h4>
                        <div className="processing-stats">
                          <div className="stat-box">
                            <div className="stat-number">{pass.segmentsKept}</div>
                            <div className="stat-label">Segments Kept</div>
                          </div>
                          <div className="stat-box">
                            <div className="stat-number">{pass.duplicatesRemoved}</div>
                            <div className="stat-label">Duplicates Removed</div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Error if any */}
                      {pass.error && (
                        <div className="pass-section error-section">
                          <h4>Error Details</h4>
                          <p className="error-text">{pass.error}</p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Retry History Section */}
            {retryAttempts.length > 0 && (
              <div className="retry-history-section">
                <h3>📋 Processing History</h3>
                <p>Previous attempts are shown below for comparison:</p>
                {retryAttempts.map((attempt, index) => (
                  <div key={index} className="history-card">
                    <div className="history-header">
                      <strong>Attempt #{index + 1}</strong>
                      <span>{attempt.timestamp}</span>
                    </div>
                    <div className="history-details">
                      <p><strong>Status:</strong> {attempt.status}</p>
                      <p><strong>File Generated:</strong> {attempt.hasFile ? '✅ Yes' : '❌ No'}</p>
                      <p><strong>Segments Kept:</strong> {attempt.segmentsKept}</p>
                      <p><strong>Duplicates Removed:</strong> {attempt.duplicatesRemoved}</p>
                      {attempt.error && (
                        <p className="error-text"><strong>Error:</strong> {attempt.error}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Step 4: Verification Section */}
            {project.clean_audio_transcribed && (
              <div className="processing-step verification-step">
                <h3>Step 4: Verify Clean Audio</h3>
                <p className="step-description">
                  The clean audio has been automatically transcribed. Compare it against the original PDF section to verify all duplicates were successfully removed.
                </p>
                
                {!verificationResults ? (
                  <button
                    className="start-process-btn"
                    onClick={verifyCleanup}
                    disabled={isVerifying}
                  >
                    {isVerifying ? "Verifying..." : "🔍 Compare Clean Audio to PDF"}
                  </button>
                ) : (
                  <div className="verification-results">
                    <div className="verification-stats">
                      <div className="stat-card">
                        <h4>Similarity Score</h4>
                        <div className="big-stat">{(verificationResults.verification_results.similarity_to_pdf * 100).toFixed(1)}%</div>
                        <p>Match with PDF section</p>
                      </div>
                      <div className="stat-card">
                        <h4>Repeated Sentences</h4>
                        <div className="big-stat">{verificationResults.verification_results.repeated_sentences_found}</div>
                        <p>Still present in clean audio</p>
                      </div>
                      <div className="stat-card">
                        <h4>Common Words</h4>
                        <div className="big-stat">{verificationResults.verification_results.common_words_count}</div>
                        <p>Shared with PDF</p>
                      </div>
                    </div>
                    
                    {verificationResults.verification_results.repeated_sentences_found > 0 && (
                      <div className="warning-box">
                        <h4>⚠️ Remaining Duplicates Found</h4>
                        <p>The following sentences still appear multiple times in the clean audio:</p>
                        <ul>
                          {verificationResults.verification_results.repeated_sentences.map((sentence, idx) => (
                            <li key={idx}>{sentence}</li>
                          ))}
                        </ul>
                        <p><em>You may want to review and re-process these duplicates.</em></p>
                      </div>
                    )}
                    
                    <div className="comparison-panels">
                      <div className="comparison-panel">
                        <h4>Clean Audio Transcript</h4>
                        <div className="transcript-box">
                          {verificationResults.clean_transcript}
                        </div>
                        <p className="char-count">{verificationResults.verification_results.clean_transcript_length} characters</p>
                      </div>
                      
                      <div className="comparison-panel">
                        <h4>Original PDF Section</h4>
                        <div className="transcript-box">
                          {verificationResults.pdf_section}
                        </div>
                        <p className="char-count">{verificationResults.verification_results.pdf_section_length} characters</p>
                      </div>
                    </div>
                    
                    <button 
                      className="secondary-btn"
                      onClick={() => setVerificationResults(null)}
                    >
                      ↻ Re-verify
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Step 5: PDF Word-by-Word Validation Section */}
            {project.duplicates_confirmed_for_deletion && (
              <div className="processing-step pdf-validation-step">
                <h3>Step 5: Test Against PDF</h3>
                <p className="step-description">
                  Perform word-by-word comparison of clean transcript (with deletions removed) against the original PDF section.
                  <br/>
                  <strong>Green</strong> = Word found in both | <strong>Red</strong> = Word missing in transcript
                </p>
                
                {!validationResults && !isValidatingPDF ? (
                  <button
                    className="start-process-btn validation-btn"
                    onClick={validateAgainstPDF}
                    disabled={isValidatingPDF}
                  >
                    📊 Test Against PDF Section
                  </button>
                ) : null}
                
                {isValidatingPDF && (
                  <div className="progress-section">
                    <div className="progress-bar-container">
                      <div 
                        className="progress-bar" 
                        style={{width: `${validationProgress}%`}}
                      />
                    </div>
                    <p className="progress-text">
                      Matching words against PDF: {validationProgress}%
                    </p>
                  </div>
                )}
                
                {validationResults && (
                  <div className="validation-results-container">
                    <div className="validation-stats-grid">
                      <div className="stat-card">
                        <h4>Match Percentage</h4>
                        <div className="big-stat success-stat">
                          {validationResults.match_percentage}%
                        </div>
                        <p>{validationResults.matched_words} of {validationResults.total_pdf_words} PDF words found</p>
                      </div>
                      <div className="stat-card">
                        <h4>Missing from Transcript</h4>
                        <div className="big-stat error-stat">
                          {validationResults.unmatched_pdf_words}
                        </div>
                        <p>PDF words not found in clean transcript</p>
                      </div>
                      <div className="stat-card">
                        <h4>Extra in Transcript</h4>
                        <div className="big-stat warning-stat">
                          {validationResults.unmatched_transcript_words}
                        </div>
                        <p>Transcript words not in PDF section</p>
                      </div>
                    </div>
                    
                    <div className="validation-comparison-container">
                      <div className="validation-comparison-panel pdf-validation-panel">
                        <h4>📄 PDF Section ({validationResults.total_pdf_words} words)</h4>
                        <div 
                          className="validation-text-content"
                          dangerouslySetInnerHTML={{__html: validationResults.pdf_html}}
                        />
                        <div className="legend">
                          <span className="legend-item"><span className="matched-word">Green</span> = Found in transcript</span>
                          <span className="legend-item"><span className="unmatched-word">Red</span> = Missing from transcript</span>
                        </div>
                      </div>
                      
                      <div className="validation-comparison-panel transcript-validation-panel">
                        <h4>📝 Clean Transcript ({validationResults.total_transcript_words} words)</h4>
                        <div 
                          className="validation-text-content"
                          dangerouslySetInnerHTML={{__html: validationResults.transcript_html}}
                        />
                        <div className="legend">
                          <span className="legend-item"><span className="matched-word">Green</span> = Matches PDF</span>
                          <span className="legend-item"><span className="unmatched-word">Red</span> = Not in PDF section</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="validation-actions">
                      <button 
                        className="secondary-btn"
                        onClick={() => {
                          setValidationResults(null);
                          setValidationProgress(0);
                        }}
                      >
                        ↻ Re-validate
                      </button>
                      
                      {validationResults.match_percentage < 90 && (
                        <div className="warning-box" style={{marginTop: '15px'}}>
                          <h4>⚠️ Low Match Percentage</h4>
                          <p>
                            Only {validationResults.match_percentage}% of PDF words were found in the transcript.
                            This is below the 90% quality threshold.
                          </p>
                          <div style={{marginTop: '15px', display: 'flex', gap: '10px', flexWrap: 'wrap'}}>
                            <button 
                              className="primary-btn"
                              onClick={() => {
                                // Reset to allow re-running duplicate detection
                                if (window.confirm(
                                  'This will let you review and select different duplicates to delete.\n\n' +
                                  'The current deletion selection will be reset. Continue?'
                                )) {
                                  setValidationResults(null);
                                  setDuplicateReview(null);
                                  alert('You can now go back to Step 2c to review duplicates again and make different selections.');
                                  // Scroll to duplicate review section
                                  setTimeout(() => {
                                    const element = document.querySelector('.duplicate-review');
                                    if (element) {
                                      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    }
                                  }, 100);
                                }
                              }}
                            >
                              ↻ Try Different Deletions
                            </button>
                            <button 
                              className="secondary-btn"
                              onClick={() => {
                                if (window.confirm(
                                  'This will create a new iteration project using your clean audio.\n\n' +
                                  'You can then run the full workflow again to remove any remaining duplicates.\n\nContinue?'
                                )) {
                                  createIterationProject();
                                }
                              }}
                            >
                              🔄 Create Iteration Project
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {validationError && (
                  <div className="error-box">
                    <h4>❌ Validation Error</h4>
                    <p>{validationError}</p>
                    <button 
                      className="secondary-btn"
                      onClick={() => {
                        setValidationError(null);
                        setValidationProgress(0);
                      }}
                    >
                      ↻ Try Again
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Step 6: Create Iteration Project for Further Cleaning */}
            {project.final_processed_audio && (
              <div className="processing-step iterative-cleaning-step">
                <h3>Step 6: Iterative Cleaning (Optional)</h3>
                <p className="step-description">
                  Continue improving audio quality by starting a fresh workflow with your clean audio.
                  <br/>
                  This creates a <strong>new separate project</strong> using the clean audio as input, allowing you to detect and remove any remaining duplicates.
                  <br/>
                  📋 <strong>What happens:</strong> PDF + Clean Audio → New Project → Steps 1-5 again
                </p>
                
                <div className="iteration-info-box" style={{
                  background: '#f0f9ff',
                  border: '2px solid #3b82f6',
                  borderRadius: '8px',
                  padding: '15px',
                  marginBottom: '15px'
                }}>
                  <h4 style={{margin: '0 0 10px 0', color: '#1e40af'}}>🔄 How Iterative Cleaning Works</h4>
                  <ul style={{margin: 0, paddingLeft: '20px'}}>
                    <li><strong>Original Project (Current):</strong> Remains unchanged with all your work intact</li>
                    <li><strong>New Iteration Project:</strong> Fresh start with clean audio from this project</li>
                    <li><strong>Workflow:</strong> Upload PDF (copied) → Transcribe clean audio → Detect duplicates → Confirm deletions → Even cleaner audio</li>
                    <li><strong>Result:</strong> Can repeat indefinitely until no duplicates remain</li>
                  </ul>
                </div>
                
                {creatingIteration ? (
                  <div className="processing-status">
                    <div className="loading-spinner"></div>
                    <p>🔄 Creating new iteration project...</p>
                    <p><em>Copying PDF and clean audio to new project...</em></p>
                  </div>
                ) : (
                  <button 
                    className="primary-btn"
                    onClick={createIterationProject}
                    disabled={creatingIteration}
                    style={{fontSize: '16px', padding: '12px 24px'}}
                  >
                    🚀 Start New Iteration Project
                  </button>
                )}
              </div>
            )}

            {/* Detailed Segments View */}
            {project.segments && project.segments.length > 0 && (
              <div className="segments-section">
                <h3>Detailed Transcript Analysis</h3>
                <div className="segments-list">
                  {project.segments.map((segment, index) => (
                    <div 
                      key={segment.id}
                      className={`segment-item ${segment.is_duplicate ? 'duplicate' : 'kept'}`}
                    >
                      <div className="segment-header">
                        <span className="segment-time">
                          {segment.start_time.toFixed(2)}s - {segment.end_time.toFixed(2)}s
                        </span>
                        <span className={`segment-status ${segment.is_duplicate ? 'removed' : 'kept'}`}>
                          {segment.is_duplicate ? 'REMOVED (Duplicate)' : 'KEPT'}
                        </span>
                      </div>
                      <div className="segment-text">
                        {segment.text}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Debug Panel */}
      <DebugPanel 
        isVisible={debugPanelVisible} 
        onToggle={() => setDebugPanelVisible(!debugPanelVisible)} 
      />
    </div>
  );
};

// PDF Match Comparison Component for side-by-side review
const PDFMatchComparison = ({ project, matchResults, onConfirmMatch, onRejectMatch }) => {
  const [showFullTexts, setShowFullTexts] = useState(false);
  
  // Comprehensive null checks
  if (!project) {
    return <div className="loading-message">Loading project data...</div>;
  }
  
  // For now, let's use a fallback if combined_transcript is not available
  // We can get the transcript from the audio files if needed
  const audioTranscript = project.combined_transcript || 
                         (project.audio_files && project.audio_files[0]?.transcript_text) ||
                         "Audio transcript is being processed...";
  
  const pdfSection = project.pdf_matched_section || 
                    (matchResults?.matched_section) || 
                    "PDF section is being analyzed...";
  
  // Don't fail if we don't have perfect data - show what we can
  if (!audioTranscript && !pdfSection) {
    return (
      <div className="loading-transcript">
        <p>⏳ Preparing comparison data...</p>
        <p><em>This may take a moment while we analyze your files...</em></p>
      </div>
    );
  }

  // Highlight common words/phrases
  const highlightCommonPhrases = (text, referenceText, isReference = false) => {
    if (!text || !referenceText || typeof text !== 'string' || typeof referenceText !== 'string') {
      return text || '';
    }
    
    try {
      // Find common phrases (3+ words)
      const words = text.toLowerCase().split(/\s+/);
      const refWords = referenceText.toLowerCase().split(/\s+/);
      
      let highlightedText = text;
    
      // Look for common 3-word phrases
      for (let i = 0; i < words.length - 2; i++) {
        const phrase = words.slice(i, i + 3).join(' ');
        const originalPhrase = text.split(/\s+/).slice(i, i + 3).join(' ');
        
        if (refWords.join(' ').includes(phrase)) {
          const className = isReference ? 'highlight-reference' : 'highlight-match';
          highlightedText = highlightedText.replace(
            new RegExp(`\\b${originalPhrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi'),
            `<span class="${className}">${originalPhrase}</span>`
          );
        }
      }
      
      return highlightedText;
    } catch (error) {
      return text || '';
    }
  };

  const truncatedPdf = showFullTexts 
    ? pdfSection 
    : (pdfSection && pdfSection.substring ? pdfSection.substring(0, 500) + (pdfSection.length > 500 ? '...' : '') : pdfSection);
  const truncatedTranscript = showFullTexts 
    ? audioTranscript 
    : (audioTranscript && audioTranscript.substring ? audioTranscript.substring(0, 500) + (audioTranscript.length > 500 ? '...' : '') : audioTranscript);

  return (
    <div className="pdf-match-comparison">
      <div className="comparison-header">
        <h4>📋 Review PDF Section Match</h4>
        <p>Please confirm this is the correct section of your PDF that matches your audio:</p>
        <div className="match-confidence">
          <span className={`confidence-badge ${(matchResults?.confidence || project.pdf_match_confidence || 0) > 0.5 ? 'high' : 'low'}`}>
            {((matchResults?.confidence || project.pdf_match_confidence || 0) * 100).toFixed(1)}% Match Confidence
          </span>
        </div>
      </div>

      <div className="text-comparison">
        <div className="text-panel pdf-panel">
          <h5>📄 PDF Section: {project.pdf_chapter_title}</h5>
          <div 
            className="text-content pdf-content"
            dangerouslySetInnerHTML={{
              __html: highlightCommonPhrases(truncatedPdf, audioTranscript, true)
            }}
          />
        </div>
        
        <div className="text-panel transcript-panel">
          <h5>🎤 Audio Transcript</h5>
          <div 
            className="text-content transcript-content"
            dangerouslySetInnerHTML={{
              __html: highlightCommonPhrases(truncatedTranscript, pdfSection, false)
            }}
          />
        </div>
      </div>

      <div className="comparison-controls">
        <button 
          className="toggle-text-btn"
          onClick={() => setShowFullTexts(!showFullTexts)}
        >
          {showFullTexts ? 'Show Less' : 'Show Full Text'}
        </button>
        
        <div className="match-actions">
          <button 
            className="reject-match-btn"
            onClick={onRejectMatch}
          >
            ❌ This doesn't match - Try again
          </button>
          
          <button 
            className="confirm-match-btn"
            onClick={onConfirmMatch}
          >
            ✅ This looks correct - Proceed
          </button>
        </div>
      </div>

      <div className="comparison-legend">
        <p><span className="highlight-reference">■</span> Common phrases found in PDF</p>
        <p><span className="highlight-match">■</span> Common phrases found in Audio</p>
      </div>
    </div>
  );
};

// PDF Boundary Refinement Component - allows user to select exact start/end
const PDFBoundaryRefinement = ({ project, projectId, token, onSave, onCancel }) => {
  const [pdfText, setPdfText] = useState('');
  const [loading, setLoading] = useState(true);
  const [startChar, setStartChar] = useState(project.pdf_match_start_char || 0);
  const [endChar, setEndChar] = useState(project.pdf_match_end_char || 0);
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const [saving, setSaving] = useState(false);
  const textAreaRef = useRef(null);

  useEffect(() => {
    // Fetch PDF text when component mounts (only when needed)
    const fetchPdfText = async () => {
      try {
        setLoading(true);
        const response = await fetchWithAuth(`/api/projects/${projectId}/?include_pdf_text=true`, {}, token);
        if (response.ok) {
          const data = await response.json();
          if (data.project.pdf_text) {
            setPdfText(data.project.pdf_text);
          } else {
            alert('PDF text not available');
          }
        }
      } catch (error) {
        alert('Failed to load PDF text');
      } finally {
        setLoading(false);
      }
    };
    
    fetchPdfText();
    
    if (project.pdf_match_start_char !== null && project.pdf_match_end_char !== null) {
      setStartChar(project.pdf_match_start_char);
      setEndChar(project.pdf_match_end_char);
    }
  }, [projectId, token, project.pdf_match_start_char, project.pdf_match_end_char]);

  const handleTextSelect = () => {
    if (textAreaRef.current) {
      const start = textAreaRef.current.selectionStart;
      const end = textAreaRef.current.selectionEnd;
      
      if (start !== end) {
        setSelectionStart(start);
        setSelectionEnd(end);
      }
    }
  };

  const applySelection = () => {
    if (selectionStart !== null && selectionEnd !== null) {
      setStartChar(selectionStart);
      setEndChar(selectionEnd);
      setSelectionStart(null);
      setSelectionEnd(null);
    }
  };

  const handleSave = async () => {
    if (startChar >= endChar) {
      alert('End position must be after start position');
      return;
    }

    setSaving(true);
    try {
      await onSave(startChar, endChar);
    } finally {
      setSaving(false);
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="pdf-boundary-refinement">
        <div className="refinement-header">
          <h4>🎯 Loading PDF Text...</h4>
          <p>Please wait while we load the full PDF text for refinement.</p>
        </div>
      </div>
    );
  }

  // Get text segments
  const beforeText = pdfText.substring(Math.max(0, startChar - 500), startChar);
  const matchedText = pdfText.substring(startChar, endChar);
  const afterText = pdfText.substring(endChar, Math.min(pdfText.length, endChar + 500));

  return (
    <div className="pdf-boundary-refinement">
      <div className="refinement-header">
        <h4>🎯 Refine PDF Section Boundaries</h4>
        <p>The system found this section, but you can adjust the start and end points:</p>
      </div>

      <div className="boundary-info">
        <div className="boundary-stat">
          <span className="stat-label">Start Position:</span>
          <span className="stat-value">{startChar.toLocaleString()}</span>
        </div>
        <div className="boundary-stat">
          <span className="stat-label">End Position:</span>
          <span className="stat-value">{endChar.toLocaleString()}</span>
        </div>
        <div className="boundary-stat">
          <span className="stat-label">Section Length:</span>
          <span className="stat-value">{(endChar - startChar).toLocaleString()} characters</span>
        </div>
      </div>

      <div className="pdf-text-display">
        <h5>📄 PDF Text with Context</h5>
        <p className="instruction">
          <strong>To adjust boundaries:</strong> Click and drag to select text below, then click "Apply Selection"
        </p>
        
        <div className="text-segments">
          <div className="text-segment context-before">
            <div className="segment-label">Before (Context)</div>
            <div className="segment-text">{beforeText}</div>
          </div>
          
          <div className="text-segment matched-section">
            <div className="segment-label">
              ▼ START at char {startChar}
            </div>
            <textarea
              ref={textAreaRef}
              className="segment-text selectable"
              value={matchedText}
              onSelect={handleTextSelect}
              readOnly
              rows={15}
            />
            <div className="segment-label">
              ▲ END at char {endChar}
            </div>
            {selectionStart !== null && selectionEnd !== null && (
              <div className="selection-info">
                <p>Selected: {selectionEnd - selectionStart} characters</p>
                <button 
                  className="apply-selection-btn"
                  onClick={applySelection}
                >
                  ✓ Apply Selection as New Boundaries
                </button>
              </div>
            )}
          </div>
          
          <div className="text-segment context-after">
            <div className="segment-label">After (Context)</div>
            <div className="segment-text">{afterText}</div>
          </div>
        </div>
      </div>

      <div className="refinement-actions">
        <button 
          className="cancel-btn"
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </button>
        <button 
          className="save-boundaries-btn"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : '💾 Save Boundaries & Continue'}
        </button>
      </div>
    </div>
  );
};

// Mini Waveform Component for duplicate segments - Lazy loaded
const MiniWaveform = ({ audioUrl, startTime, endTime, segmentId }) => {
  const waveformRef = useRef(null);
  const wavesurferRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!shouldLoad || !audioUrl || !waveformRef.current) return;

    let wavesurfer = null;
    const abortController = new AbortController();
    
    try {
      // Ensure full URL
      const fullAudioUrl = audioUrl.startsWith('http') ? audioUrl : `http://localhost:8000${audioUrl}`;

      // Create WaveSurfer instance
      wavesurfer = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#b8c1ec',
        progressColor: '#6f42c1',
        height: 60,
        barWidth: 2,
        barGap: 1,
        responsive: true,
        normalize: true,
        backend: 'WebAudio',
      });

      wavesurferRef.current = wavesurfer;

      // Load audio with region
      wavesurfer.load(fullAudioUrl);

      wavesurfer.on('ready', () => {
        if (mountedRef.current && !abortController.signal.aborted) {
          setIsReady(true);
          setError(null);
        }
      });

      wavesurfer.on('error', (err) => {
        if (mountedRef.current && !abortController.signal.aborted) {
          setError('Failed to load audio');
          setIsReady(false);
        }
      });

      wavesurfer.on('play', () => {
        if (mountedRef.current) setIsPlaying(true);
      });
      
      wavesurfer.on('pause', () => {
        if (mountedRef.current) setIsPlaying(false);
      });
      
      wavesurfer.on('finish', () => {
        if (mountedRef.current) setIsPlaying(false);
      });

    } catch (err) {
      if (mountedRef.current && !abortController.signal.aborted) {
        setError('Failed to initialize waveform');
      }
    }

    return () => {
      abortController.abort();
      if (wavesurfer) {
        try {
          wavesurfer.destroy();
        } catch (err) {
          // Silently handle cleanup errors
        }
      }
    };
  }, [shouldLoad, audioUrl, startTime, endTime, segmentId]);

  const handlePlayPause = () => {
    if (!wavesurferRef.current || !isReady) return;
    
    const wavesurfer = wavesurferRef.current;
    
    if (isPlaying) {
      wavesurfer.pause();
    } else {
      // Seek to start time and play until end time
      wavesurfer.seekTo(startTime / wavesurfer.getDuration());
      wavesurfer.play();
      
      // Stop at end time
      const checkTime = () => {
        if (wavesurfer.getCurrentTime() >= endTime) {
          wavesurfer.pause();
          wavesurfer.un('audioprocess', checkTime);
        }
      };
      wavesurfer.on('audioprocess', checkTime);
    }
  };

  return (
    <div className="mini-waveform-container">
      {!shouldLoad ? (
        <button 
          className="load-waveform-btn"
          onClick={() => setShouldLoad(true)}
        >
          📊 Load Waveform
        </button>
      ) : error ? (
        <div className="mini-waveform-error">{error}</div>
      ) : (
        <div ref={waveformRef} className="mini-waveform" />
      )}
      {shouldLoad && (
        <button 
          className={`mini-play-btn ${isPlaying ? 'playing' : ''}`}
          onClick={handlePlayPause}
          disabled={!isReady || error}
          title={isPlaying ? 'Pause' : 'Play segment'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
      )}
    </div>
  );
};

// Duplicate Review Component for interactive duplicate confirmation
const DuplicateReviewComponent = ({ duplicates, transcript, onConfirmDeletions, onFetchTranscript }) => {
  const [selectedDeletions, setSelectedDeletions] = useState([]);
  const [showTranscript, setShowTranscript] = useState(true); // Always show by default
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [highlightedSegmentId, setHighlightedSegmentId] = useState(null); // Track clicked segment
  
  // Create a lookup map for fast duplicate checking (optimization)
  const duplicateLookup = React.useMemo(() => {
    const map = new Map();
    if (duplicates && duplicates.duplicates) {
      duplicates.duplicates.forEach(d => {
        if (d.id) {
          map.set(d.id, d);
        }
      });
    }
    return map;
  }, [duplicates]);
  
  useEffect(() => {
    // Pre-select all segments marked for deletion (is_duplicate: true)
    // Do NOT select the last occurrence (is_last_occurrence: true)
    if (duplicates && duplicates.duplicates) {
      const recommended = duplicates.duplicates
        .filter(d => d.is_duplicate === true && d.is_last_occurrence !== true)
        .map(d => d.id);  // Use 'id' not 'segment_id'
      setSelectedDeletions(recommended);
      
      // Expand first 3 groups by default
      const groupIds = Object.keys(duplicates.grouped_duplicates || {}).slice(0, 3);
      setExpandedGroups(new Set(groupIds));
    }
  }, [duplicates]);

  // Fetch transcript if not already loaded
  useEffect(() => {
    if (!transcript && onFetchTranscript) {
      onFetchTranscript();
    }
  }, [transcript, onFetchTranscript]);

  const toggleGroup = (groupId) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  const handleTranscriptClick = (segmentId, groupId) => {
    // Highlight the segment
    setHighlightedSegmentId(segmentId);
    
    // Expand the group if not already expanded
    if (!expandedGroups.has(groupId.toString())) {
      setExpandedGroups(prev => new Set([...prev, groupId.toString()]));
    }
    
    // Scroll to the occurrence in the list
    setTimeout(() => {
      const element = document.getElementById(`occurrence-${segmentId}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  };

  const toggleDeletion = (segmentId) => {
    setSelectedDeletions(prev => 
      prev.includes(segmentId) 
        ? prev.filter(id => id !== segmentId)
        : [...prev, segmentId]
    );
  };

  const confirmAllDeletions = () => {
    if (selectedDeletions.length === 0) {
      alert("No deletions selected");
      return;
    }
    
    const confirmed = duplicates.duplicates
      .filter(d => selectedDeletions.includes(d.id))  // Use 'id' not 'segment_id'
      .map(d => ({
        segment_id: d.id,  // Backend expects segment_id
        audio_file_id: d.audio_file_id,
        start_time: d.start_time,
        end_time: d.end_time,
        text: d.text
      }));
    
    onConfirmDeletions(confirmed);
  };

  if (!duplicates || !duplicates.grouped_duplicates) {
    return <div>Loading duplicate review...</div>;
  }

  return (
    <div className="duplicate-review-container">
      <div className="review-header">
        <h4>Review Detected Duplicates</h4>
        <p>Select which duplicate segments to delete. The system recommends keeping the <strong>last occurrence</strong> of each duplicate.</p>
        <div className="selection-summary">
          <p><strong>Selected for deletion:</strong> {selectedDeletions.length} segments</p>
        </div>
      </div>

      {/* Full Transcript with Highlighting - Always Visible */}
      {transcript && transcript.transcript_data && (
        <div className="transcript-with-highlights">
          <h5>📝 Full Transcript (Click to locate in list below)</h5>
          <div className="transcript-content-highlighted">
            {transcript.transcript_data.map((fileData, fileIndex) => (
              <React.Fragment key={`file-${fileData.audio_file_id}`}>
                {fileData.segments && fileData.segments.map((segment, segIndex) => {
                  // Use fast lookup map instead of .find() for O(1) performance
                  const duplicateInfo = duplicateLookup.get(segment.id);
                  
                  // Backend now includes ALL occurrences:
                  // - is_duplicate: true = DELETE (first occurrences) → RED
                  // - is_duplicate: false + is_last_occurrence: true = KEEP (last occurrence) → GREEN
                  const isDuplicate = duplicateInfo && duplicateInfo.is_duplicate === true;
                  const isKept = duplicateInfo && duplicateInfo.is_last_occurrence === true;
                  const isHighlighted = highlightedSegmentId === segment.id;
                  
                  return (
                    <span
                      key={`segment-${fileData.audio_file_id}-${segment.id || segIndex}`}
                      className={`transcript-segment ${isDuplicate ? 'segment-duplicate' : ''} ${isKept ? 'segment-kept' : ''} ${isHighlighted ? 'segment-highlighted' : ''}`}
                      onClick={() => duplicateInfo && handleTranscriptClick(segment.id, duplicateInfo.group_id)}
                      style={{ cursor: duplicateInfo ? 'pointer' : 'default' }}
                      title={duplicateInfo ? 
                        `${fileData.filename} - ${segment.start_time?.toFixed(1)}s-${segment.end_time?.toFixed(1)}s\nGroup ${duplicateInfo.group_id + 1} - Occurrence ${duplicateInfo.occurrence_number}/${duplicateInfo.total_occurrences}\n${duplicateInfo.reason}\n\nClick to locate in list` :
                        `${fileData.filename} - ${segment.start_time?.toFixed(1)}s-${segment.end_time?.toFixed(1)}s`
                      }
                    >
                      {segment.text}{' '}
                    </span>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
          <div className="transcript-legend">
            <span className="legend-item"><span className="legend-box segment-duplicate"></span> Duplicate (to be deleted - first occurrences)</span>
            <span className="legend-item"><span className="legend-box segment-kept"></span> Last occurrence (kept)</span>
            <span className="legend-item"><span className="legend-box"></span> Normal segment</span>
          </div>
        </div>
      )}
      
      {!transcript && (
        <div className="transcript-loading">
          <p>Loading transcript...</p>
        </div>
      )}

      <div className="duplicate-groups">
        {Object.entries(duplicates.grouped_duplicates).map(([groupId, group]) => {
          const isExpanded = expandedGroups.has(groupId);
          return (
            <div key={groupId} className="duplicate-group">
              <div className="group-header" onClick={() => toggleGroup(groupId)} style={{cursor: 'pointer'}}>
                <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                  <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                  <div style={{flex: 1}}>
                    <h5>Duplicate Group {parseInt(groupId) + 1}</h5>
                    <p><strong>Text:</strong> "{group.group_info?.sample_text || group.occurrences?.[0]?.text?.substring(0, 100) + '...' || 'No text available'}"</p>
                    <p><strong>Occurrences:</strong> {group.occurrences?.length}</p>
                  </div>
                </div>
              </div>
            
              {isExpanded && (
                <div className="group-occurrences">
              {group.occurrences?.map((occurrence, index) => (
                <div 
                  key={occurrence.id} 
                  id={`occurrence-${occurrence.id}`}
                  className={`occurrence ${occurrence.is_last_occurrence ? 'last-occurrence' : ''} ${highlightedSegmentId === occurrence.id ? 'occurrence-highlighted' : ''}`}
                >
                  <div className="occurrence-header">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedDeletions.includes(occurrence.id)}
                        onChange={() => toggleDeletion(occurrence.id)}
                        disabled={occurrence.is_last_occurrence} // Don't allow deleting the last occurrence
                      />
                      <span className="occurrence-title">
                        Occurrence #{occurrence.occurrence_number} 
                        {occurrence.is_last_occurrence && " (LAST - Recommended to keep)"}
                      </span>
                    </label>
                  </div>
                  
                  <div className="occurrence-details">
                    <p><strong>File:</strong> {occurrence.audio_file_name || occurrence.audio_file_title}</p>
                    <p><strong>Time:</strong> {occurrence.start_time?.toFixed(1)}s - {occurrence.end_time?.toFixed(1)}s ({(occurrence.end_time - occurrence.start_time).toFixed(1)}s duration)</p>
                    <p><strong>Text:</strong> "{occurrence.text}"</p>
                    <p><strong>Action:</strong> 
                      <span className={`action-badge ${occurrence.is_duplicate ? 'delete' : 'keep'}`}>
                        {occurrence.is_last_occurrence ? 'KEEP' : 'DELETE'}
                      </span>
                    </p>
                    
                    {/* Audio waveform visualization */}
                    {occurrence.audio_file_path && (
                      <div className="waveform-section">
                        <MiniWaveform 
                          audioUrl={occurrence.audio_file_path}
                          startTime={occurrence.start_time}
                          endTime={occurrence.end_time}
                          segmentId={occurrence.id}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
              )}
          </div>
          );
        })}
      </div>

      <div className="review-actions">
        <button 
          className="confirm-deletions-btn primary-btn"
          onClick={confirmAllDeletions}
          disabled={selectedDeletions.length === 0}
        >
          ✅ Confirm Deletions ({selectedDeletions.length} segments)
        </button>
      </div>
    </div>
  );
};

// Helper function to play audio segments
const playSegment = (audioFilePath, startTime, endTime) => {
  // Create audio element and play specific segment
  const audio = new Audio(audioFilePath);
  audio.currentTime = startTime;
  
  const stopPlayback = () => {
    audio.pause();
    audio.removeEventListener('timeupdate', checkTime);
  };
  
  const checkTime = () => {
    if (audio.currentTime >= endTime) {
      stopPlayback();
    }
  };
  
  audio.addEventListener('timeupdate', checkTime);
  audio.play().catch(error => {
    alert('Could not play audio segment');
  });
};

export default ProjectDetailPage;
