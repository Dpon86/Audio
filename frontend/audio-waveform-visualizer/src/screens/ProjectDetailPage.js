import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import DebugPanel from "../components/DebugPanel";
import "../static/CSS/ProjectDetailPage.css";

// Helper function for authenticated API calls
const fetchWithAuth = (url, options = {}, token) => {
  console.log('fetchWithAuth called:', { url, token: token ? `${token.substring(0, 8)}...` : 'null' });
  
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
  
  console.log('Making request to:', fullUrl, 'with headers:', headers);
  
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
      console.error("Error fetching audio files:", error);
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
      
      console.error("Error transcribing audio file:", error);
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
      console.error("Error restarting transcription:", error);
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
      console.error("Error processing audio file:", error);
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
      console.error("Error deleting audio file:", error);
      alert("Failed to delete audio file");
    }
  };

  if (loading) return <div className="audio-files-loading">Loading audio files...</div>;

  console.log('AudioFilesList rendering with:', audioFiles.length, 'files:', audioFiles);

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
  
  console.log('ProjectDetailPage render:', { 
    projectId, 
    token: token ? `${token.substring(0, 8)}...` : 'null', 
    tokenFromStorage: localStorage.getItem('token') ? `${localStorage.getItem('token').substring(0, 8)}...` : 'null',
    user: user ? user.username : 'null',
    isAuthenticated 
  });
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadingPDF, setUploadingPDF] = useState(false);
  const [uploadingAudio, setUploadingAudio] = useState(false);
  const [infrastructureStatus, setInfrastructureStatus] = useState(null);
  const [debugPanelVisible, setDebugPanelVisible] = useState(false);
  const [transcript, setTranscript] = useState(null);
  const [transcriptVisible, setTranscriptVisible] = useState(false);
  
  // New state for step-by-step workflow
  const [duplicateResults, setDuplicateResults] = useState(null);
  const [duplicateReview, setDuplicateReview] = useState(null);
  const [pdfMatchResults, setPdfMatchResults] = useState(null);
  
  const pdfInputRef = useRef();
  const audioInputRef = useRef();
  const progressIntervalRef = useRef();

  const fetchProjectDetails = useCallback(async () => {
    console.log('fetchProjectDetails called with token:', token, 'projectId:', projectId);
    if (!token) {
      console.warn('No token available for API call');
      return;
    }
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/`, {}, token);
      
      if (response.ok) {
        const data = await response.json();
        console.log("Project details fetched:", data.project);
        console.log("PDF match completed:", data.project.pdf_match_completed);
        setProject(data.project);
        
        // If project is processing, start polling for progress
        if (data.project.status === 'processing') {
          startProgressPolling();
        }
      } else if (response.status === 404) {
        alert("Project not found");
        navigate("/projects");
      } else {
        console.error("Failed to fetch project:", response.statusText);
      }
    } catch (error) {
      console.error("Error fetching project:", error);
    } finally {
      setLoading(false);
    }
  }, [projectId, token, navigate]);

  const fetchInfrastructureStatus = useCallback(async () => {
    if (!token) {
      console.warn('No token available for infrastructure status API call');
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
      console.error("Error fetching infrastructure status:", error);
    }
  }, [token]);

  const fetchTranscript = useCallback(async () => {
    if (!token) {
      console.warn('No token available for transcript API call');
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
      console.error("Error fetching transcript:", error);
    }
  }, [token, projectId]);

  // Main useEffect hook for component initialization
  useEffect(() => {
    fetchProjectDetails();
    fetchInfrastructureStatus();
    
    // Poll infrastructure status every 30 seconds
    const infraInterval = setInterval(fetchInfrastructureStatus, 30000);
    
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      clearInterval(infraInterval);
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
      console.error("Error uploading PDF:", error);
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
      console.error("Error uploading audio:", error);
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
      console.error("Error starting transcription:", error);
      alert("Failed to start transcription");
    }
  };

  // New Step-by-Step Processing Functions
  
  const startPDFMatching = async () => {
    console.log("startPDFMatching called");
    console.log("Project data:", project);
    console.log("Project status:", project.status);
    console.log("Has PDF file (pdf_file):", !!project.pdf_file);
    console.log("Has PDF file (has_pdf):", !!project.has_pdf);
    
    if (project.status !== 'transcribed') {
      alert(`All audio files must be transcribed first. Current status: ${project.status}`);
      return;
    }

    if (!project.has_pdf) {
      alert("A PDF file must be uploaded first before matching can begin.");
      return;
    }

    console.log("Starting PDF matching for project:", projectId);
    try {
      setProcessing(true);
      console.log("Set processing to true, making API call...");
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/match-pdf/`, {
        method: "POST"
      }, token);
      
      console.log("PDF matching response status:", response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log("PDF matching successful, data:", data);
        console.log("Match result:", data.match_result);
        setPdfMatchResults(data.match_result);
        await fetchProjectDetails(); // Refresh to get updated status
        console.log("Project after refresh:", project);
      } else {
        const errorData = await response.json();
        console.error("PDF matching failed:", errorData);
        alert(errorData.error || "Failed to match PDF section");
      }
    } catch (error) {
      console.error("Error matching PDF:", error);
      alert("Failed to match PDF section");
    } finally {
      console.log("Setting processing to false");
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
      const response = await fetchWithAuth(`/api/projects/${projectId}/detect-duplicates/`, {
        method: "POST"
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        setDuplicateResults(data.duplicate_results);
        alert(`Found ${data.duplicates_found} duplicate segments in ${data.duplicate_results.summary.unique_duplicate_groups} groups`);
        fetchProjectDetails(); // Refresh to get updated status
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to detect duplicates");
      }
    } catch (error) {
      console.error("Error detecting duplicates:", error);
      alert("Failed to detect duplicates");
    } finally {
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
        const errorData = await response.json();
        alert(errorData.error || "Failed to load duplicate review");
      }
    } catch (error) {
      console.error("Error loading duplicate review:", error);
      alert("Failed to load duplicate review");
    } finally {
      setProcessing(false);
    }
  };

  const confirmDeletions = async (confirmedDeletions) => {
    try {
      setProcessing(true);
      setProgress(0);
      
      const response = await fetchWithAuth(`/api/projects/${projectId}/confirm-deletions/`, {
        method: "POST",
        body: JSON.stringify({
          confirmed_deletions: confirmedDeletions
        })
      }, token);
      
      if (response.ok) {
        const data = await response.json();
        alert(`Processing ${data.confirmed_count} confirmed deletions...`);
        startProgressPolling(); // Monitor progress
        fetchProjectDetails(); // Refresh to get updated status
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to process deletions");
        setProcessing(false);
      }
    } catch (error) {
      console.error("Error confirming deletions:", error);
      alert("Failed to confirm deletions");
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
      console.error("Error resetting PDF match:", error);
      alert("Failed to reset match. Please refresh the page.");
    }
  };

  const startProgressPolling = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }

    progressIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetchWithAuth(`/api/projects/${projectId}/status/`, {}, token);
        
        if (response.ok) {
          const data = await response.json();
          setProgress(data.progress);
          
          if (data.status === 'completed') {
            setProcessing(false);
            clearInterval(progressIntervalRef.current);
            fetchProjectDetails(); // Refresh project data
          } else if (data.status === 'failed') {
            setProcessing(false);
            clearInterval(progressIntervalRef.current);
            alert(`Processing failed: ${data.error || 'Unknown error'}`);
            fetchProjectDetails(); // Refresh project data
          }
        }
      } catch (error) {
        console.error("Error polling progress:", error);
      }
    }, 2000); // Poll every 2 seconds
  };

  const downloadProcessedAudio = async () => {
    try {
      const response = await fetchWithAuth(`/api/projects/${projectId}/download/`, {}, token);
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `processed_${project.title}.wav`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to download processed audio");
      }
    } catch (error) {
      console.error("Error downloading audio:", error);
      alert("Failed to download processed audio");
    }
  };

  const deleteProject = async () => {
    const confirmDelete = window.confirm(
      `⚠️ Are you sure you want to delete "${project.title}"?\n\n` +
      `This will permanently delete:\n` +
      `• The project and all settings\n` +
      `• All uploaded audio files (${project.audio_files_count} files)\n` +
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
      
      const response = await fetch(`/api/projects/${projectId}/`, {
        method: "DELETE",
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        alert(`✅ ${data.message}\n\nFiles cleaned up: ${data.files_deleted}`);
        navigate("/projects"); // Redirect to project list
      } else {
        const errorData = await response.json();
        alert(`❌ Failed to delete project: ${errorData.error}`);
      }
    } catch (error) {
      console.error("Error deleting project:", error);
      alert("❌ Failed to delete project. Please try again.");
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
              </div>
            )}
            
            {project.status === 'transcribed' && (
              <div className="transcription-complete">
                <p>✅ Transcription Complete!</p>
                <p>📊 {project.transcribed_files_count} of {project.audio_files_count} files transcribed with word timestamps</p>
                <button 
                  className="btn btn-secondary"
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
                      <p>🔍 Analyzing PDF content and matching with audio transcript...</p>
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
                  
                  <div className="debug-info" style={{backgroundColor: '#f0f0f0', padding: '10px', margin: '10px 0'}}>
                    <h5>Debug Info:</h5>
                    <p>pdf_match_completed: {project.pdf_match_completed ? 'true' : 'false'}</p>
                    <p>combined_transcript: {project.combined_transcript ? 'exists' : 'missing'}</p>
                    <p>pdf_matched_section: {project.pdf_matched_section ? 'exists' : 'missing'}</p>
                    <p>pdfMatchResults: {pdfMatchResults ? 'exists' : 'null'}</p>
                  </div>
                  
                  {/* Side-by-side comparison */}
                  {project && project.pdf_match_completed ? (
                    <PDFMatchComparison 
                      project={project}
                      matchResults={pdfMatchResults || {
                        matched_section: project.pdf_matched_section,
                        confidence: project.pdf_match_confidence,
                        chapter_title: project.pdf_chapter_title
                      }}
                      onConfirmMatch={() => {
                        alert("Match confirmed! You can now proceed to detect duplicates.");
                        setPdfMatchResults(null); // Hide comparison after confirmation
                      }}
                      onRejectMatch={() => {
                        // Reset match status and try again
                        resetPDFMatch();
                      }}
                    />
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
                      <p>🔍 Analyzing audio transcript for duplicate content...</p>
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
                      onConfirmDeletions={confirmDeletions}
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

          {(processing || project.status === 'processing') && (
            <div className="processing-indicator">
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${Math.max(progress, 5)}%` }}
                ></div>
              </div>
              <p className="progress-text">
                {getProgressMessage()} ({Math.max(progress, 0)}%)
              </p>
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

        {/* Results Section */}
        {project.status === 'completed' && (
          <div className="results-section">
            <h2>3. Results</h2>
            
            <div className="results-grid">
              <div className="result-card">
                <h3>PDF Section Matched</h3>
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
                <button 
                  className="download-btn"
                  onClick={downloadProcessedAudio}
                >
                  📥 Download Clean Audio
                </button>
              </div>
            </div>

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
    console.log("PDFMatchComparison: No project data");
    return <div className="loading-message">Loading project data...</div>;
  }
  
  console.log("PDFMatchComparison render:", { 
    hasMatchResults: !!matchResults, 
    hasCombinedTranscript: !!project.combined_transcript,
    hasPdfMatchedSection: !!project.pdf_matched_section,
    projectKeys: Object.keys(project || {}),
    project: project
  });
  
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
    console.log("No transcript or PDF section data");
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
      console.error("Error highlighting text:", error);
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

// Duplicate Review Component for interactive duplicate confirmation
const DuplicateReviewComponent = ({ duplicates, onConfirmDeletions }) => {
  const [selectedDeletions, setSelectedDeletions] = useState([]);
  
  useEffect(() => {
    // Pre-select all recommended deletions
    if (duplicates && duplicates.duplicates) {
      const recommended = duplicates.duplicates
        .filter(d => d.recommended_action === 'delete')
        .map(d => d.segment_id);
      setSelectedDeletions(recommended);
    }
  }, [duplicates]);

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
      .filter(d => selectedDeletions.includes(d.segment_id))
      .map(d => ({
        segment_id: d.segment_id,
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

      <div className="duplicate-groups">
        {Object.entries(duplicates.grouped_duplicates).map(([groupId, group]) => (
          <div key={groupId} className="duplicate-group">
            <div className="group-header">
              <h5>Duplicate Group {parseInt(groupId) + 1}</h5>
              <p><strong>Text:</strong> "{group.group_info.original_text?.substring(0, 100)}..."</p>
              <p><strong>Occurrences:</strong> {group.occurrences?.length}</p>
            </div>
            
            <div className="group-occurrences">
              {group.occurrences?.map((occurrence, index) => (
                <div key={occurrence.segment_id} className={`occurrence ${occurrence.is_last_occurrence ? 'last-occurrence' : ''}`}>
                  <div className="occurrence-header">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedDeletions.includes(occurrence.segment_id)}
                        onChange={() => toggleDeletion(occurrence.segment_id)}
                        disabled={occurrence.is_last_occurrence} // Don't allow deleting the last occurrence
                      />
                      <span className="occurrence-title">
                        Occurrence #{occurrence.occurrence_number} 
                        {occurrence.is_last_occurrence && " (LAST - Recommended to keep)"}
                      </span>
                    </label>
                  </div>
                  
                  <div className="occurrence-details">
                    <p><strong>File:</strong> {occurrence.audio_file_title}</p>
                    <p><strong>Time:</strong> {occurrence.start_time.toFixed(1)}s - {occurrence.end_time.toFixed(1)}s</p>
                    <p><strong>Action:</strong> 
                      <span className={`action-badge ${occurrence.recommended_action}`}>
                        {occurrence.recommended_action === 'keep' ? 'KEEP' : 'DELETE'}
                      </span>
                    </p>
                    
                    {/* Audio playback button */}
                    <div className="audio-controls">
                      <button 
                        className="play-segment-btn"
                        onClick={() => playSegment(occurrence.audio_file_path, occurrence.start_time, occurrence.end_time)}
                        title="Play this audio segment"
                      >
                        ▶️ Play Segment ({(occurrence.end_time - occurrence.start_time).toFixed(1)}s)
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
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
    console.error('Error playing audio:', error);
    alert('Could not play audio segment');
  });
};

export default ProjectDetailPage;