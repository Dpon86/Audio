import React, { useState, useEffect, useMemo, useRef } from 'react';
import { API_BASE_URL } from '../../config/api';
import { useProjectTab } from '../../contexts/ProjectTabContext';
import { useAuth } from '../../contexts/AuthContext';
import WaveSurfer from 'wavesurfer.js';
import WaveformDuplicateEditor from './WaveformDuplicateEditor';
import PDFRegionSelector from '../PDFRegionSelector';
import clientDuplicateDetection from '../../services/clientDuplicateDetection';
import clientAudioAssembly from '../../services/clientAudioAssembly';
import downloadHelper from '../../utils/downloadHelper';
import clientAudioStorage from '../../services/clientAudioStorage';
import './Tab3Duplicates.css';

/**
 * Tab 3: Duplicate Detection and Review
 * Detects duplicate segments within a single audio file and allows user review
 */
const Tab3Duplicates = () => {
  const { token } = useAuth();
  const { 
    projectId, 
    selectedAudioFile, 
    audioFiles, 
    selectAudioFile,
    activeTab,
    setActiveTab, 
    setPendingDeletions,
    duplicateDetectionMode,
    setDuplicateDetectionMode
  } = useProjectTab();
  
  const [detecting, setDetecting] = useState(false);
  const [detectionProgress, setDetectionProgress] = useState({ current: 0, total: 0, status: '' });
  const [detectionAlgorithm, setDetectionAlgorithm] = useState('windowed_retry_pdf');
  const [showAlgorithmSettings, setShowAlgorithmSettings] = useState(true);
  const [lastRunSummary, setLastRunSummary] = useState(null);

  useEffect(() => {
    if (duplicateDetectionMode === 'ai') {
      setShowAlgorithmSettings(false);
    }
  }, [duplicateDetectionMode]);

  // Algorithm settings (user-adjustable before start)
  const [tfidfSimilarityThreshold, setTfidfSimilarityThreshold] = useState(0.85);
  const [windowMaxLookahead, setWindowMaxLookahead] = useState(90);
  const [windowRatioThreshold, setWindowRatioThreshold] = useState(0.76);
  const [windowStrongMatchRatio, setWindowStrongMatchRatio] = useState(0.84);
  const [windowMinWordLength, setWindowMinWordLength] = useState(3);

  // Optional PDF-hint region + cleaning controls
  const [showPdfRegionSelector, setShowPdfRegionSelector] = useState(false);
  const [pdfSelectorMode, setPdfSelectorMode] = useState('start');
  const [pdfStartChar, setPdfStartChar] = useState(null);
  const [pdfEndChar, setPdfEndChar] = useState(null);
  const [pdfStartText, setPdfStartText] = useState('');
  const [pdfEndText, setPdfEndText] = useState('');
  const [isCleaningPDF, setIsCleaningPDF] = useState(false);
  const [pdfCleanupMessage, setPdfCleanupMessage] = useState(null);
  const [transcriptText, setTranscriptText] = useState('');

  const [duplicateGroups, setDuplicateGroups] = useState([]);
  const [selectedDeletions, setSelectedDeletions] = useState([]);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [processing, setProcessing] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [isProcessingDeletions, setIsProcessingDeletions] = useState(false);

  // Audio assembly state
  const [isAssemblingAudio, setIsAssemblingAudio] = useState(false);
  const [assemblyProgress, setAssemblyProgress] = useState({ current: 0, total: 0, status: '' });
  const [assembledAudioBlob, setAssembledAudioBlob] = useState(null);
  const [assemblyInfo, setAssemblyInfo] = useState(null);

  const algorithmOptions = [
    { value: 'windowed_retry', label: 'New Retry-Aware (No PDF)' },
    { value: 'windowed_retry_pdf', label: 'New Retry-Aware + PDF Hint' },
    { value: 'tfidf_cosine', label: 'Classic TF-IDF Cosine' },
  ];

  // Audio player state
  const [wavesurfer, setWavesurfer] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const waveformRef = useRef(null);

  // Server storage functions for cross-device persistence
  const saveDuplicateAnalysisToServer = async (filename, duplicateGroups, algorithm, selectedDeletions = null, assemblyInfo = null) => {
    try {
      const duplicateCount = duplicateGroups.reduce((sum, group) => 
        sum + group.segments.filter(s => s.is_duplicate).length, 0
      );
      
      const totalSegments = duplicateGroups.reduce((sum, group) => 
        sum + group.segments.length, 0
      );

      const payload = {
        filename: filename,
        duplicate_groups: duplicateGroups,
        algorithm: algorithm,
        total_segments: totalSegments,
        duplicate_count: duplicateCount,
        duplicate_groups_count: duplicateGroups.length
      };

      if (selectedDeletions !== null) {
        payload.selected_deletions = selectedDeletions;
      }

      if (assemblyInfo !== null) {
        payload.assembly_info = assemblyInfo;
      }

      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/duplicate-analyses/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[Tab3Duplicates] Duplicate analysis saved to server:', data);
        return { success: true, data: data.analysis };
      } else {
        console.error('[Tab3Duplicates] Failed to save analysis to server:', response.status);
        return { success: false, error: 'Server error' };
      }
    } catch (error) {
      console.error('[Tab3Duplicates] Error saving analysis to server:', error);
      return { success: false, error: error.message };
    }
  };

  const loadDuplicateAnalysisFromServer = async (filename) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/duplicate-analyses/?filename=${encodeURIComponent(filename)}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Token ${token}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.analyses && data.analyses.length > 0) {
          console.log('[Tab3Duplicates] Loaded analysis from server');
          return data.analyses[0]; // Return most recent
        }
        return null;
      } else {
        console.error('[Tab3Duplicates] Failed to load analysis from server:', response.status);
        return null;
      }
    } catch (error) {
      console.error('[Tab3Duplicates] Error loading analysis from server:', error);
      return null;
    }
  };

  // Load duplicate groups when file is selected
  useEffect(() => {
    if (selectedAudioFile) {
      const loadDuplicates = async () => {
        // Try loading from server first (source of truth)
        const serverAnalysis = await loadDuplicateAnalysisFromServer(selectedAudioFile.filename);
        
        if (serverAnalysis) {
          console.log(`[Tab3Duplicates] Loaded duplicates from server for ${selectedAudioFile.filename}`);
          setDuplicateGroups(serverAnalysis.duplicate_groups || []);
          
          if (serverAnalysis.selected_deletions) {
            setSelectedDeletions(serverAnalysis.selected_deletions);
          }
          
          if (serverAnalysis.assembly_info) {
            setAssemblyInfo(serverAnalysis.assembly_info);
          }
          
          // Expand first 3 groups
          if (serverAnalysis.duplicate_groups && serverAnalysis.duplicate_groups.length > 0) {
            const firstThree = new Set();
            serverAnalysis.duplicate_groups.slice(0, 3).forEach(g => firstThree.add(g.group_id));
            setExpandedGroups(firstThree);
          }
          
          // Update localStorage to match server (keep in sync)
          const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
          localStorage.setItem(storageKey, JSON.stringify({
            duplicateGroups: serverAnalysis.duplicate_groups,
            detectionAlgorithm: serverAnalysis.algorithm,
            timestamp: Date.now(),
            fileId: selectedAudioFile.id,
            filename: selectedAudioFile.filename,
            server_synced: true
          }));
          
          if (serverAnalysis.selected_deletions) {
            localStorage.setItem(`${storageKey}_selectedDeletions`, JSON.stringify(serverAnalysis.selected_deletions));
          }
          
          return;
        }
        
        // Fallback to localStorage if server unavailable
        const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
        const storedData = localStorage.getItem(storageKey);
        
        if (storedData) {
          try {
            const data = JSON.parse(storedData);
            console.log(`[Tab3Duplicates] Loaded duplicates from localStorage for ${selectedAudioFile.filename}`);
            setDuplicateGroups(data.duplicateGroups || []);
            
            // Load saved selections
            const savedSelections = localStorage.getItem(`${storageKey}_selectedDeletions`);
            if (savedSelections) {
              setSelectedDeletions(JSON.parse(savedSelections));
            }
            
            // Load assembly info if it exists
            const assemblyInfoKey = `${storageKey}_assembly`;
            const savedAssembly = localStorage.getItem(assemblyInfoKey);
            if (savedAssembly) {
              try {
                const assemblyData = JSON.parse(savedAssembly);
                setAssemblyInfo(assemblyData.info);
                console.log(`[Tab3Duplicates] Loaded assembly info from localStorage`);
              } catch (error) {
                console.error('[Tab3Duplicates] Error loading assembly info:', error);
              }
            }
            
            // Expand first 3 groups
            if (data.duplicateGroups && data.duplicateGroups.length > 0) {
              const firstThree = new Set();
              data.duplicateGroups.slice(0, 3).forEach(g => firstThree.add(g.group_id));
              setExpandedGroups(firstThree);
            }
          } catch (error) {
            console.error('[Tab3Duplicates] Error loading from localStorage:', error);
            if (!selectedAudioFile.client_only) {
              loadDuplicateGroups();
            }
          }
        } else {
          // No saved data, load from server if not client-only
          if (!selectedAudioFile.client_only) {
            loadDuplicateGroups();
          }
        }
      };
      
      loadDuplicates();
      loadTranscriptText();
    }
  }, [selectedAudioFile]);

  const loadTranscriptText = async () => {
    if (!selectedAudioFile) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/transcription/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include'
        }
      );

      if (response.ok) {
        const data = await response.json();
        const fullText = data?.transcription?.full_text || '';
        setTranscriptText(fullText);
      } else {
        setTranscriptText('');
      }
    } catch (error) {
      console.error('Failed to load transcript text:', error);
      setTranscriptText('');
    }
  };

  const loadDuplicateGroups = async () => {
    if (!selectedAudioFile) return;
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/duplicates/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log('Received duplicate groups:', data.duplicate_groups);
        
        if (data.duplicate_groups && data.duplicate_groups.length > 0) {
          setDuplicateGroups(data.duplicate_groups);
          
          // Store in localStorage for persistence
          const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
          const detectionInfo = {
            duplicateGroups: data.duplicate_groups,
            timestamp: Date.now(),
            fileId: selectedAudioFile.id,
            filename: selectedAudioFile.filename,
            algorithm: data.algorithm || 'unknown',
            detectionDate: new Date().toLocaleString()
          };
          localStorage.setItem(storageKey, JSON.stringify(detectionInfo));
          console.log(`[Tab3Duplicates] Saved server duplicates to localStorage: ${storageKey}`);
          console.log(`[Tab3Duplicates] Algorithm used: ${detectionInfo.algorithm}`);
          
          // Update last run summary with algorithm from server response
          setLastRunSummary({
            algorithm: data.algorithm || 'unknown',
            timestamp: Date.now(),
            groupCount: data.duplicate_groups.length
          });
          
          // Auto-select all for deletion except last occurrence
          // Backend marks is_duplicate=true for segments that should be deleted
          const toDelete = [];
          data.duplicate_groups.forEach(group => {
            const segments = group.segments || group.occurrences || [];
            if (segments && Array.isArray(segments)) {
              segments.forEach((seg) => {
                console.log(`Segment ${seg.id}: is_duplicate=${seg.is_duplicate}, is_kept=${seg.is_kept}, is_last_occurrence=${seg.is_last_occurrence}`);
                
                // Backend sets is_duplicate=true for segments to DELETE
                // is_duplicate=false for LAST occurrence (to keep)
                if (seg.is_duplicate === true) {
                  toDelete.push(seg.id);
                }
              });
            }
          });
          
          console.log(`Auto-selected ${toDelete.length} segments for deletion:`, toDelete);
          setSelectedDeletions(toDelete);
          
          // Expand first 3 groups
          const firstThree = data.duplicate_groups.slice(0, 3).map(g => g.group_id);
          setExpandedGroups(new Set(firstThree));
        } else {
          setDuplicateGroups([]);
          setSelectedDeletions([]);
        }
      }
    } catch (error) {
      console.error('Error loading duplicate groups:', error);
    }
  };

  // Initialize WaveSurfer when file is selected
  useEffect(() => {
    // Check if we have either a server audio file or a client-side local file
    const hasServerAudio = selectedAudioFile && (selectedAudioFile.file || selectedAudioFile.audio_file);
    const hasLocalAudio = selectedAudioFile && selectedAudioFile.local_file;
    
    if (!selectedAudioFile || (!hasServerAudio && !hasLocalAudio) || !waveformRef.current) {
      return;
    }

    // Clean up existing instance
    if (wavesurfer) {
      try {
        wavesurfer.destroy();
      } catch (error) {
        console.error('Error destroying previous wavesurfer:', error);
      }
    }

    let ws = null;
    let mounted = true;
    let blobUrl = null;

    try {
      ws = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4a90e2',
        progressColor: '#2563eb',
        cursorColor: '#1e40af',
        barWidth: 2,
        barRadius: 3,
        cursorWidth: 1,
        height: 120,
        barGap: 2,
        responsive: true,
        normalize: true,
      });

      // Load audio from appropriate source
      let audioUrl;
      if (hasLocalAudio) {
        // Client-side file - create blob URL
        console.log('[Tab3Duplicates] Loading waveform from local file');
        blobUrl = URL.createObjectURL(selectedAudioFile.local_file);
        audioUrl = blobUrl;
      } else {
        // Server file - use server URL
        console.log('[Tab3Duplicates] Loading waveform from server');
        audioUrl = `${API_BASE_URL}${selectedAudioFile.file || selectedAudioFile.audio_file}`;
      }
      
      ws.load(audioUrl);
      
      ws.on('ready', () => {
        if (mounted) {
          setDuration(ws.getDuration());
        }
      });

      ws.on('play', () => {
        if (mounted) setIsPlaying(true);
      });
      
      ws.on('pause', () => {
        if (mounted) setIsPlaying(false);
      });
      
      ws.on('finish', () => {
        if (mounted) setIsPlaying(false);
      });
      
      ws.on('audioprocess', (time) => {
        if (mounted) setCurrentTime(time);
      });

      ws.on('seek', () => {
        if (mounted) setCurrentTime(ws.getCurrentTime());
      });

      if (mounted) {
        setWavesurfer(ws);
      }

      return () => {
        mounted = false;
        // Clean up blob URL if created
        if (blobUrl) {
          URL.revokeObjectURL(blobUrl);
        }
        if (ws) {
          try {
            ws.destroy();
          } catch (error) {
            console.debug('WaveSurfer cleanup error (expected):', error);
          }
        }
      };
    } catch (error) {
      console.error('Error initializing waveform:', error);
    }
  }, [selectedAudioFile]);

  // Audio player controls
  const handlePlayPause = () => {
    if (wavesurfer) {
      wavesurfer.playPause();
    }
  };

  const handleStop = () => {
    if (wavesurfer) {
      wavesurfer.stop();
      setIsPlaying(false);
      setCurrentTime(0);
    }
  };

  const seekToTime = (timeInSeconds) => {
    if (wavesurfer && duration > 0) {
      wavesurfer.seekTo(timeInSeconds / duration);
      if (!isPlaying) {
        wavesurfer.play();
      }
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle group selection from waveform
  const handleGroupSelect = (groupId) => {
    console.log('Group selected:', groupId);
    setSelectedGroupId(groupId);
    
    // Optionally expand the group in the list
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      newSet.add(groupId);
      return newSet;
    });
  };

  // Handle region boundary updates from waveform
  const handleRegionUpdate = async (groupId, segmentId, newStartTime, newEndTime) => {
    console.log(`\n---- MANUAL DRAG UPDATE ----`);
    console.log(`📝 Region: group=${groupId}, segment=${segmentId}`);
    console.log(`📝 New times: ${newStartTime.toFixed(2)}s - ${newEndTime.toFixed(2)}s`);
    
    // CRITICAL: Check if this is a client-only file FIRST to avoid 404 errors
    const isClientOnly = selectedAudioFile?.client_only || 
                         selectedAudioFile?.client_processed || 
                         (selectedAudioFile?.id && selectedAudioFile.id.toString().startsWith('local-'));
    
    console.log(`📋 File type: ${isClientOnly ? 'CLIENT-ONLY' : 'SERVER'}`);
    
    try {
      // Update local state immediately
      setDuplicateGroups(prevGroups =>
        prevGroups.map(group => {
          if (group.group_id !== groupId) return group;

          return {
            ...group,
            segments: group.segments.map(seg =>
              seg.id === segmentId
                ? { ...seg, start_time: newStartTime, end_time: newEndTime }
                : seg
            )
          };
        })
      );

      if (isClientOnly) {
        // For client-only files, update localStorage
        console.log(`📱 Client-only file detected, updating localStorage`);
        
        // Update the duplicate groups in localStorage
        const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
        const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
        
        if (stored.duplicateGroups) {
          stored.duplicateGroups = stored.duplicateGroups.map(group => {
            if (group.group_id !== groupId) return group;
            
            return {
              ...group,
              segments: group.segments.map(seg =>
                seg.id === segmentId
                  ? { ...seg, start_time: newStartTime, end_time: newEndTime }
                  : seg
              )
            };
          });
          
          localStorage.setItem(storageKey, JSON.stringify(stored));
          console.log(`✅ localStorage updated successfully`);
        }
        
        // Also update the transcription segments in localStorage if they exist
        const transcriptionKey = `client_transcriptions_${projectId}`;
        const transcriptions = JSON.parse(localStorage.getItem(transcriptionKey) || '[]');
        const updatedTranscriptions = transcriptions.map(file => {
          if (file.id !== selectedAudioFile.id && file.filename !== selectedAudioFile.filename) {
            return file;
          }
          
          if (file.transcription && file.transcription.all_segments) {
            return {
              ...file,
              transcription: {
                ...file.transcription,
                all_segments: file.transcription.all_segments.map(seg =>
                  seg.id === segmentId
                    ? { ...seg, start_time: newStartTime, end_time: newEndTime }
                    : seg
                )
              }
            };
          }
          return file;
        });
        
        localStorage.setItem(transcriptionKey, JSON.stringify(updatedTranscriptions));
        console.log(`✅ Transcription segments updated in localStorage`);
        console.log(`---- UPDATE COMPLETE (CLIENT-ONLY) ----\n`);
        
      } else {
        // For server files, save to backend
        console.log(`📤 Sending PATCH to: /api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${segmentId}/`);
        console.log(`📤 Payload:`, { start_time: newStartTime, end_time: newEndTime });
        
        const response = await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/segments/${segmentId}/`,
          {
            method: 'PATCH',
            headers: {
              'Authorization': `Token ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              start_time: newStartTime,
              end_time: newEndTime
            })
          }
        );

        console.log(`📥 Response status: ${response.status} ${response.statusText}`);
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error(`❌ PATCH failed:`, errorText);
          throw new Error(`Failed to update segment times: ${response.status}`);
        }
        
        const responseData = await response.json();
        console.log(`✅ Backend updated successfully:`, responseData);
        console.log(`---- UPDATE COMPLETE (SERVER) ----\n`);
      }

    } catch (error) {
      console.error('\n❌❌❌ ERROR UPDATING SEGMENT:', error);
      console.error('Error details:', error.message);
      console.log(`---- UPDATE FAILED ----\n`);
      
      // Only show alert for server files - client files are handled locally
      if (!isClientOnly) {
        alert(`Failed to update segment: ${error.message}`);
      } else {
        console.warn('⚠️ Client-only file update failed but changes are saved locally');
      }
    }
  };

  const handleClearResults = () => {
    if (window.confirm('Clear all duplicate detection results? You will need to re-run detection.')) {
      // Clear UI state
      setDuplicateGroups([]);
      setSelectedDeletions([]);
      setExpandedGroups(new Set());
      setLastRunSummary(null);
      
      // Clear localStorage
      if (selectedAudioFile && projectId) {
        const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
        localStorage.removeItem(storageKey);
        localStorage.removeItem(`${storageKey}_assembly`);
        localStorage.removeItem(`${storageKey}_selectedDeletions`);
        console.log(`[Tab3Duplicates] Cleared all stored data for ${storageKey}`);
      }
    }
  };

  const isPdfHintAlgorithm = detectionAlgorithm === 'windowed_retry_pdf';

  const handlePdfPositionSelected = (position, text) => {
    if (pdfSelectorMode === 'start') {
      setPdfStartChar(position);
      setPdfStartText(text);
    } else {
      setPdfEndChar(position);
      setPdfEndText(text);
    }
    setShowPdfRegionSelector(false);
  };

  const handleCleanPdfForDuplicateHint = async () => {
    if (!projectId) return;

    setIsCleaningPDF(true);
    setPdfCleanupMessage(null);

    try {
      const requestBody = {};
      if (pdfStartChar !== null) requestBody.pdf_start_char = pdfStartChar;
      if (pdfEndChar !== null) requestBody.pdf_end_char = pdfEndChar;

      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/clean-pdf-text/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
          body: JSON.stringify(requestBody)
        }
      );

      if (response.ok) {
        const data = await response.json();
        setPdfCleanupMessage({
          type: 'success',
          text: `PDF cleaned for duplicate hinting (${(data.statistics?.new_quality?.quality_score || 0).toFixed(2)} quality score)`
        });
      } else {
        const errorData = await response.json();
        setPdfCleanupMessage({
          type: 'error',
          text: `Failed to clean PDF: ${errorData.error || 'Unknown error'}`
        });
      }
    } catch (error) {
      setPdfCleanupMessage({
        type: 'error',
        text: `Network error: ${error.message}`
      });
    } finally {
      setIsCleaningPDF(false);
    }
  };

  const handleDetectDuplicates = async (algorithmOverride = null) => {
    if (!selectedAudioFile) return;
    
    // Clear old results before starting new detection
    setDuplicateGroups([]);
    setSelectedDeletions([]);
    setExpandedGroups(new Set());
    setDetecting(true);
    setDetectionProgress({ current: 0, total: 0, status: 'Initializing...' });

    // Check if this is a client-only file (processed locally)
    const isClientOnly = selectedAudioFile.client_only || selectedAudioFile.client_processed;

    if (isClientOnly) {
      console.log('[Tab3Duplicates] Using client-side duplicate detection for local file');
      
      try {
        // Get transcription from localStorage or file object
        let segments = [];
        
        if (selectedAudioFile.transcription && selectedAudioFile.transcription.all_segments) {
          segments = selectedAudioFile.transcription.all_segments;
        } else {
          // Try loading from localStorage
          const storageKey = `client_transcriptions_${projectId}`;
          const localFiles = JSON.parse(localStorage.getItem(storageKey) || '[]');
          const matchingFile = localFiles.find(f => f.id === selectedAudioFile.id || f.filename === selectedAudioFile.filename);
          
          if (matchingFile && matchingFile.transcription && matchingFile.transcription.all_segments) {
            segments = matchingFile.transcription.all_segments;
          }
        }

        if (segments.length === 0) {
          throw new Error('No transcription segments found for this file');
        }

        console.log(`[Tab3Duplicates] Analyzing ${segments.length} segments client-side`);

        // Run client-side duplicate detection
        const results = await clientDuplicateDetection.detectDuplicates(
          segments,
          {
            minLength: 10,
            minWords: windowMinWordLength || 3,
            similarityThreshold: tfidfSimilarityThreshold || 0.85
          },
          (current, total, status) => {
            setDetectionProgress({ current, total, status });
          }
        );

        console.log('[Tab3Duplicates] Client-side detection complete:', results);

        // Set results
        setDuplicateGroups(results.duplicate_groups);

        // Store duplicates in localStorage for persistence
        const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
        localStorage.setItem(storageKey, JSON.stringify({
          duplicateGroups: results.duplicate_groups,
          processedSegments: results.processed_segments, // Save segments with assigned IDs
          detectionAlgorithm,
          timestamp: Date.now(),
          fileId: selectedAudioFile.id,
          filename: selectedAudioFile.filename
        }));
        console.log(`[Tab3Duplicates] Saved duplicates to localStorage: ${storageKey}`);

        // Auto-select duplicates for deletion (all but last occurrence)
        const toDelete = [];
        results.duplicate_groups.forEach(group => {
          group.segments.forEach(seg => {
            if (seg.is_duplicate === true) {
              toDelete.push(seg.id);
            }
          });
        });
        
        setSelectedDeletions(toDelete);

        // Also save selected deletions
        localStorage.setItem(`${storageKey}_selectedDeletions`, JSON.stringify(toDelete));

        // Save to server for cross-device persistence
        const serverSave = await saveDuplicateAnalysisToServer(
          selectedAudioFile.filename,
          results.duplicate_groups,
          detectionAlgorithm,
          toDelete  // Save selected deletions after they're created
        );

        if (serverSave.success) {
          console.log('[Tab3Duplicates] Duplicate analysis synced to server');
        } else {
          console.log('[Tab3Duplicates] Analysis saved locally only (server unavailable)');
        }

        // Expand first 3 groups
        const firstThree = results.duplicate_groups.slice(0, 3).map(g => g.group_id);
        setExpandedGroups(new Set(firstThree));

        setLastRunSummary({
          algorithm: 'client-side',
          usePdfHint: false,
          settings: results.settings,
          statistics: clientDuplicateDetection.getStatistics()
        });

        const stats = clientDuplicateDetection.getStatistics();
        alert(
          `✅ Client-Side Duplicate Detection Complete!\n\n` +
          `📊 Analyzed: ${stats.analyzed_segments} segments\n` +
          `📝 Found: ${stats.duplicate_groups} duplicate groups\n` +
          `🗑️ Duplicates: ${stats.duplicate_segments} segments\n` +
          `⏱️ Time in duplicates: ${stats.duplicate_time_formatted}\n\n` +
          `🖥️ All processing done in your browser.`
        );

        setDetecting(false);
        setDetectionProgress({ current: 0, total: 0, status: '' });

      } catch (error) {
        console.error('[Tab3Duplicates] Client-side detection error:', error);
        alert(`Client-side detection failed: ${error.message}`);
        setDetecting(false);
        setDetectionProgress({ current: 0, total: 0, status: '' });
      }
      
      return;
    }

    // Server-side detection (existing code)
    const selectedAlgorithm = algorithmOverride || detectionAlgorithm;
    const usePdfHint = selectedAlgorithm === 'windowed_retry_pdf';
    
    console.log(`[Tab3Duplicates] Starting detection with algorithm: ${selectedAlgorithm}`);
    console.log(`[Tab3Duplicates] Settings:`, {
      tfidfSimilarityThreshold,
      windowMaxLookahead,
      windowRatioThreshold,
      windowStrongMatchRatio,
      windowMinWordLength,
      usePdfHint
    });

    const requestBody = {
      algorithm: selectedAlgorithm,
      use_pdf_hint: usePdfHint,
      tfidf_similarity_threshold: tfidfSimilarityThreshold,
      window_max_lookahead: windowMaxLookahead,
      window_ratio_threshold: windowRatioThreshold,
      window_strong_match_ratio: windowStrongMatchRatio,
      window_min_word_length: windowMinWordLength,
    };

    if (usePdfHint) {
      if (pdfStartChar !== null) requestBody.pdf_start_char = pdfStartChar;
      if (pdfEndChar !== null) requestBody.pdf_end_char = pdfEndChar;
    }
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/detect-duplicates/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        console.log(`[Tab3Duplicates] Server response:`, data);
        console.log(`[Tab3Duplicates] Server confirmed algorithm: ${data.algorithm}`);
        setLastRunSummary({
          algorithm: data.algorithm || selectedAlgorithm,
          usePdfHint,
          settings: data.settings || requestBody,
        });
        alert(`${data.message || 'Duplicate detection started'}\nAlgorithm: ${data.algorithm || selectedAlgorithm}`);
        
        // Poll for completion
        const pollInterval = setInterval(async () => {
          await loadDuplicateGroups();
          
          // Check if detection is complete
          const statusResponse = await fetch(
            `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/status/`,
            {
              headers: {
                'Authorization': `Token ${token}`,
                'Content-Type': 'application/json'
              }
            }
          );
          
          if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            if (statusData.status === 'failed') {
              clearInterval(pollInterval);
              setDetecting(false);
              const serverError = statusData.error || 'Duplicate detection failed on server.';
              alert(`Duplicate detection failed: ${serverError}`);
              return;
            }

            if (statusData.status !== 'processing') {
              clearInterval(pollInterval);
              setDetecting(false);
              await loadDuplicateGroups();
            }
          }
        }, 3000);
        
        // Stop polling after 5 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setDetecting(false);
        }, 300000);
        
      } else {
        let errorMessage = 'Failed to start duplicate detection';
        try {
          const error = await response.json();
          errorMessage = error.error || error.message || errorMessage;
        } catch (e) {
          // Response is not JSON, might be HTML error page
          errorMessage = `Server error (${response.status}): ${response.statusText}`;
        }
        alert(errorMessage);
        setDetecting(false);
      }
    } catch (error) {
      console.error('Error detecting duplicates:', error);
      alert(`Error: ${error.message}`);
      setDetecting(false);
    }
  };

  const normalizeAIDuplicateGroups = (aiGroups = []) => {
    return aiGroups.map((group, groupIndex) => {
      const occurrences = Array.isArray(group.occurrences) ? group.occurrences : [];
      const segments = occurrences.map((occurrence, occurrenceIndex) => {
        const defaultIsDuplicate = occurrenceIndex < (occurrences.length - 1);
        const action = occurrence.action || '';

        return {
          id: occurrence.occurrence_id || `${group.group_id || groupIndex + 1}-${occurrenceIndex + 1}`,
          start_time: occurrence.start_time || 0,
          end_time: occurrence.end_time || 0,
          text: occurrence.text || group.duplicate_text || '',
          segment_ids: occurrence.segment_ids || [],
          confidence_score: occurrence.confidence_score ?? group.confidence_score ?? 0.8,
          is_duplicate: action ? action === 'delete' : defaultIsDuplicate,
          is_kept: action ? action === 'keep' : !defaultIsDuplicate
        };
      });

      return {
        group_id: group.group_id || groupIndex + 1,
        duplicate_text: group.duplicate_text || '',
        confidence_score: group.confidence_score ?? 0.8,
        segments
      };
    });
  };

  const pollAIDetectionStatus = async (taskId) => {
    for (let i = 0; i < 120; i += 1) {
      const response = await fetch(
        `${API_BASE_URL}/api/ai-detection/status/${taskId}/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to check AI task status (${response.status})`);
      }

      const statusData = await response.json();
      const progress = Number(statusData.progress || 0);
      setDetectionProgress({
        current: progress,
        total: 100,
        status: statusData.message || 'AI detection in progress...'
      });

      if (statusData.state === 'SUCCESS') {
        return statusData;
      }

      if (statusData.state === 'FAILURE') {
        throw new Error(statusData.error || 'AI duplicate detection failed');
      }

      await new Promise((resolve) => setTimeout(resolve, 2500));
    }

    throw new Error('AI detection timed out. Please try again.');
  };

  const handleAIDetectDuplicates = async () => {
    if (!selectedAudioFile) {
      return;
    }

    if (selectedAudioFile.client_only || selectedAudioFile.client_processed) {
      alert('AI mode requires a server-side transcribed file. Please use Algorithm mode for local-only files.');
      return;
    }

    const numericAudioFileId = Number(selectedAudioFile.id);
    if (Number.isNaN(numericAudioFileId)) {
      alert('Invalid audio file ID for AI detection. Please pick a server file.');
      return;
    }

    setDuplicateGroups([]);
    setSelectedDeletions([]);
    setExpandedGroups(new Set());
    setDetecting(true);
    setDetectionProgress({ current: 5, total: 100, status: 'Starting AI duplicate detection...' });

    try {
      const startResponse = await fetch(`${API_BASE_URL}/api/ai-detection/detect/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          audio_file_id: numericAudioFileId,
          min_words: windowMinWordLength || 3,
          similarity_threshold: tfidfSimilarityThreshold || 0.85,
          keep_occurrence: 'last',
          enable_paragraph_expansion: false
        })
      });

      if (!startResponse.ok) {
        let message = `Failed to start AI detection (${startResponse.status})`;
        try {
          const errorPayload = await startResponse.json();
          message = errorPayload.error || errorPayload.message || message;
        } catch (e) {
          // Keep fallback message when error response is not JSON.
        }
        throw new Error(message);
      }

      const startPayload = await startResponse.json();
      const statusPayload = await pollAIDetectionStatus(startPayload.task_id);
      const detectionResult = statusPayload.detection_result;

      if (!detectionResult || !Array.isArray(detectionResult.duplicate_groups)) {
        throw new Error('AI detection completed but no duplicate groups were returned.');
      }

      const normalizedGroups = normalizeAIDuplicateGroups(detectionResult.duplicate_groups);
      setDuplicateGroups(normalizedGroups);

      const toDelete = [];
      normalizedGroups.forEach((group) => {
        (group.segments || []).forEach((segment) => {
          if (segment.is_duplicate) {
            toDelete.push(segment.id);
          }
        });
      });
      setSelectedDeletions(toDelete);

      const firstThree = normalizedGroups.slice(0, 3).map((g) => g.group_id);
      setExpandedGroups(new Set(firstThree));

      setLastRunSummary({
        algorithm: 'ai-duplicate-detection',
        groupCount: normalizedGroups.length
      });

      setDetectionProgress({ current: 100, total: 100, status: 'AI detection complete.' });
      alert(`AI duplicate detection completed. Found ${normalizedGroups.length} duplicate groups.`);
    } catch (error) {
      console.error('[Tab3Duplicates] AI detection error:', error);
      alert(`AI duplicate detection failed: ${error.message}`);
    } finally {
      setDetecting(false);
    }
  };

  const handleStartDetection = async () => {
    if (duplicateDetectionMode === 'ai') {
      await handleAIDetectDuplicates();
      return;
    }

    await handleDetectDuplicates();
  };

  const handleConfirmDeletions = async () => {
    console.log('handleConfirmDeletions called, selectedDeletions:', selectedDeletions.length);
    
    if (selectedDeletions.length === 0) {
      alert('No segments selected for deletion');
      return;
    }
    
    // Show loading state immediately
    setIsProcessingDeletions(true);
    
    try {
      // Simulate processing delay for UI feedback (remove if unnecessary)
      await new Promise(resolve => setTimeout(resolve, 300));
      
      // Format confirmed deletions with full segment data
      const confirmedDeletions = [];
      duplicateGroups.forEach(group => {
        if (group.segments && Array.isArray(group.segments)) {
          group.segments.forEach(seg => {
            if (selectedDeletions.includes(seg.id)) {
              confirmedDeletions.push({
                segment_id: seg.id,
                audio_file_id: selectedAudioFile.id,
                start_time: seg.start_time,
                end_time: seg.end_time,
                text: seg.text
              });
            }
          });
        }
      });
      
      // Store pending deletions in context
      console.log('Setting pending deletions:', confirmedDeletions.length, 'segments');
      console.log('Current activeTab before setting:', activeTab);
      console.log('setActiveTab function:', setActiveTab);
      
      // First set pending deletions
      setPendingDeletions({
        audioFile: selectedAudioFile,
        confirmedDeletions: confirmedDeletions,
        segmentIds: selectedDeletions,
        deletionCount: selectedDeletions.length,
        duplicateGroups: duplicateGroups
      });
      
      // Processing complete - show completion modal
      setIsProcessingDeletions(false);
      setShowCompletionModal(true);
    } catch (error) {
      console.error('Error processing deletions:', error);
      setIsProcessingDeletions(false);
      alert('Error processing deletions. Please try again.');
    }
  };

  // Server-side assembly - sends deletion request to backend
  const handleServerAssembly = async () => {
    console.log('[Tab3Duplicates] handleServerAssembly called');
    console.log(`[Tab3Duplicates] Sending ${selectedDeletions.length} segment IDs to server`);
    
    const confirmed = window.confirm(
      `Server-Side Assembly\n\n` +
      `This will send your ${selectedDeletions.length} selected deletions to the server for processing.\n` +
      `The server will generate a clean audio file without the duplicates.\n\n` +
      `This may take a few minutes depending on file size.\n\n` +
      `Continue?`
    );

    if (!confirmed) return;

    try {
      setIsAssemblingAudio(true);
      setAssemblyProgress({ current: 0, total: 100, status: 'Sending to server...' });

      // Format deletions for server API
      const confirmed_deletions = selectedDeletions.map(id => ({ segment_id: id }));

      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/confirm-deletions/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify({ confirmed_deletions })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Server assembly failed');
      }

      const result = await response.json();
      console.log('[Tab3Duplicates] Server assembly started:', result);

      // Poll for task completion
      const taskId = result.task_id;
      let complete = false;
      let attempts = 0;
      const pollIntervalMs = 2500;
      const maxAttempts = 720; // 30 minutes

      while (!complete && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
        
        const statusResponse = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/status/`, {
          headers: {
            'Authorization': `Token ${token}`
          }
        });

        if (statusResponse.ok) {
          const status = await statusResponse.json();
          console.log(`[Tab3Duplicates] Task status:`, status);

          if (status.progress) {
            setAssemblyProgress({ 
              current: status.progress, 
              total: 100, 
              status: status.message || 'Processing...' 
            });
          }

          const isCompleted = status.status === 'completed' || status.status === 'success' || status.task_state === 'SUCCESS';
          const isFailed = status.status === 'failed' || status.task_state === 'FAILURE';

          if (isCompleted) {
            complete = true;
            setIsAssemblingAudio(false);
            // Refresh selected file so Results tab shows processed_audio
            try {
              const fileResponse = await fetch(
                `${API_BASE_URL}/api/projects/${projectId}/files/${selectedAudioFile.id}/`,
                { headers: { 'Authorization': `Token ${token}` } }
              );
              if (fileResponse.ok) {
                const updatedFile = await fileResponse.json();
                // API returns { success: true, audio_file: {...} } — unwrap the nested object
                const fileData = updatedFile.audio_file || updatedFile;
                selectAudioFile({ ...selectedAudioFile, ...fileData });
              }
            } catch (refreshErr) {
              console.warn('[Tab3Duplicates] Could not refresh file after assembly:', refreshErr);
            }
            alert('Server assembly complete! Switching to Results tab.');
            setActiveTab('results');
          } else if (isFailed) {
            throw new Error(status.error || 'Task failed');
          }
        }

        attempts++;
      }

      if (!complete) {
        setIsAssemblingAudio(false);
        alert('Assembly is still running on the server. It has not failed, but it is taking longer than expected. Please check the Results tab in a few minutes.');
        return;
      }

    } catch (error) {
      console.error('[Tab3Duplicates] Server assembly error:', error);
      alert(`Server assembly failed: ${error.message}`);
      setIsAssemblingAudio(false);
    }
  };

  const handleNavigateToResults = () => {
    console.log('handleNavigateToResults called');
    console.log('Current tab:', activeTab);
    setShowCompletionModal(false);
    console.log('Setting activeTab to: results');
    setActiveTab('results');
    console.log('setActiveTab called with results');
  };

  const handleReturnToUpload = () => {
    console.log('handleReturnToUpload called');
    console.log('Current tab:', activeTab);
    setShowCompletionModal(false);
    console.log('Setting activeTab to: files');
    setActiveTab('files');
    console.log('setActiveTab called with files');
  };

  const handleAssembleAudio = async () => {
    console.log('[Tab3Duplicates] handleAssembleAudio called');
    console.log(`[Tab3Duplicates] Selected deletions count: ${selectedDeletions.length}`);
    console.log(`[Tab3Duplicates] Sample deletion IDs:`, selectedDeletions.slice(0, 10));
    
    if (selectedDeletions.length === 0) {
      alert('No segments selected for removal. Please mark duplicates first.');
      return;
    }

    // Check if this is a client-only file OR prefer server-side assembly
    const isClientOnly = selectedAudioFile.client_only || selectedAudioFile.client_processed;
    const useServerAssembly = !isClientOnly || window.confirm(
      `Choose assembly method:\n\n` +
      `CLIENT-SIDE (in browser):\n` +
      `✓ Faster for small files\n` +
      `✗ May have ID matching issues\n\n` +
      `SERVER-SIDE (on server):\n` +
      `✓ More reliable\n` +
      `✓ Works with any file size\n` +
      `✗ Requires server processing\n\n` +
      `Click OK for SERVER-SIDE, Cancel for CLIENT-SIDE`
    );

    if (!isClientOnly && !useServerAssembly) {
      alert('This file was processed on the server and must use server-side assembly.');
      handleServerAssembly();
      return;
    }

    if (useServerAssembly) {
      handleServerAssembly();
      return;
    }

    // === CLIENT-SIDE ASSEMBLY (original code) ===
    
    // Get the original audio file
    let originalFile = selectedAudioFile.local_file;
    
    // If not in memory, try loading from IndexedDB
    if (!originalFile && selectedAudioFile.has_local_audio) {
      console.log('[Tab3Duplicates] Loading audio file from IndexedDB...');
      try {
        const stored = await clientAudioStorage.getFile(selectedAudioFile.id);
        if (stored && stored.file) {
          originalFile = stored.file;
          console.log('[Tab3Duplicates] Loaded audio file from IndexedDB:', stored.filename);
        }
      } catch (error) {
        console.error('[Tab3Duplicates] Failed to load from IndexedDB:', error);
      }
    }
    
    if (!originalFile) {
      alert('Original audio file not available in browser storage.\n\nPlease re-upload and transcribe the file to use client-side assembly.');
      return;
    }

    // Get all segments - USE THE PROCESSED SEGMENTS FROM DUPLICATE DETECTION
    // This ensures segments have the same IDs that were used in selectedDeletions
    let allSegments = [];
    
    // First, try to get processed segments from duplicate detection results (saved in localStorage)
    const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
    const duplicatesStorage = localStorage.getItem(storageKey);
    
    if (duplicatesStorage) {
      try {
        const parsed = JSON.parse(duplicatesStorage);
        if (parsed.processedSegments && parsed.processedSegments.length > 0) {
          allSegments = parsed.processedSegments;
          console.log(`[Tab3Duplicates] Using ${allSegments.length} processed segments from duplicate detection (with assigned IDs)`);
          console.log(`[Tab3Duplicates] Sample segment IDs:`, allSegments.slice(0, 5).map(s => s.id));
        } else if (parsed.duplicate_groups && parsed.duplicate_groups.length > 0) {
          // Fallback: Extract all segments from duplicate groups
          console.warn('[Tab3Duplicates] No processedSegments found, extracting from duplicate groups');
          const segmentMap = new Map();
          parsed.duplicate_groups.forEach(group => {
            const segments = group.segments || group.occurrences || [];
            segments.forEach(seg => {
              if (seg.id && !segmentMap.has(seg.id)) {
                segmentMap.set(seg.id, seg);
              }
            });
          });
          allSegments = Array.from(segmentMap.values()).sort((a, b) => a.start_time - b.start_time);
          console.log(`[Tab3Duplicates] Extracted ${allSegments.length} segments from duplicate groups`);
        }
      } catch (error) {
        console.error('[Tab3Duplicates] Error parsing duplicates storage:', error);
      }
    }
    
    // Fallback: load from transcription (but this may not have matching IDs!)
    if (allSegments.length === 0) {
      console.warn('[Tab3Duplicates] Warning: No processed segments found, falling back to raw transcription segments');
      console.warn('[Tab3Duplicates] This may cause ID mismatch issues with segment deletion');
      
      if (selectedAudioFile.transcription && selectedAudioFile.transcription.all_segments) {
        allSegments = selectedAudioFile.transcription.all_segments;
      } else {
        // Try loading from localStorage
        const transcriptionStorageKey = `client_transcriptions_${projectId}`;
        const localFiles = JSON.parse(localStorage.getItem(transcriptionStorageKey) || '[]');
        const matchingFile = localFiles.find(f => f.id === selectedAudioFile.id || f.filename === selectedAudioFile.filename);
        
        if (matchingFile && matchingFile.transcription && matchingFile.transcription.all_segments) {
          allSegments = matchingFile.transcription.all_segments;
        }
      }
    }

    if (allSegments.length === 0) {
      alert('No transcription segments found for this file.');
      return;
    }

    const confirmed = window.confirm(
      `Ready to assemble audio?\n\n` +
      `Total segments: ${allSegments.length}\n` +
      `Segments to remove: ${selectedDeletions.length}\n` +
      `Segments to keep: ${allSegments.length - selectedDeletions.length}\n\n` +
      `This will process the audio in your browser and may take a minute.\n\n` +
      `Continue?`
    );

    if (!confirmed) return;

    setIsAssemblingAudio(true);
    setAssemblyProgress({ current: 0, total: 0, status: 'Starting...' });

    try {
      console.log('[Tab3Duplicates] Calling clientAudioAssembly.assembleAudio');
      console.log(`[Tab3Duplicates] Total segments: ${allSegments.length}`);
      console.log(`[Tab3Duplicates] Sample segment IDs from allSegments:`, allSegments.slice(0, 10).map(s => s.id));
      console.log(`[Tab3Duplicates] Selected deletions: ${selectedDeletions.length}`, selectedDeletions.slice(0, 10));
      console.log(`[Tab3Duplicates] Segments to keep: ${allSegments.length - selectedDeletions.length}`);
      
      // CRITICAL: Verify IDs match
      const allSegmentIds = new Set(allSegments.map(s => s.id));
      const matchingIds = selectedDeletions.filter(id => allSegmentIds.has(id));
      const mismatchedIds = selectedDeletions.filter(id => !allSegmentIds.has(id));
      
      console.log(`[Tab3Duplicates] ⚠️ ID Match Check: ${matchingIds.length}/${selectedDeletions.length} IDs match`);
      if (mismatchedIds.length > 0) {
        console.error(`[Tab3Duplicates] ❌ ${mismatchedIds.length} segment IDs in selectedDeletions don't exist in allSegments!`);
        console.error(`[Tab3Duplicates] Mismatched IDs (first 10):`, mismatchedIds.slice(0, 10));
      }
      
      const result = await clientAudioAssembly.assembleAudio(
        originalFile,
        allSegments,
        selectedDeletions,
        (current, total, status) => {
          setAssemblyProgress({ current, total, status });
        }
      );

      console.log('[Tab3Duplicates] Assembly complete:', result);

      setAssembledAudioBlob(result.blob);
      setAssemblyInfo(result.info);

      // Save to localStorage (note: blob can't be stored, only the info)
      const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
      const assemblyData = {
        info: result.info,
        timestamp: Date.now(),
        removedCount: result.removedCount,
        keptCount: result.keptCount
      };
      
      // Save assembly info in BOTH locations for compatibility
      // 1. Separate key (for backward compatibility)
      const assemblyInfoKey = `${storageKey}_assembly`;
      localStorage.setItem(assemblyInfoKey, JSON.stringify(assemblyData));
      
      // 2. Update main duplicates storage to include assemblyInfo (for Results tab detection)
      const existingDuplicates = localStorage.getItem(storageKey);
      console.log(`[Tab3Duplicates] Existing duplicates storage:`, existingDuplicates ? 'EXISTS' : 'MISSING');
      
      if (existingDuplicates) {
        try {
          const duplicatesData = JSON.parse(existingDuplicates);
          duplicatesData.assemblyInfo = assemblyData.info;
          localStorage.setItem(storageKey, JSON.stringify(duplicatesData));
          console.log(`[Tab3Duplicates] ✅ Saved assembly info to duplicates storage for Results tab`);
          console.log(`[Tab3Duplicates] Assembly info:`, assemblyData.info);
        } catch (error) {
          console.error('[Tab3Duplicates] ❌ Error updating duplicates storage with assembly info:', error);
        }
      } else {
        // Storage doesn't exist - create it with assembly info
        console.log(`[Tab3Duplicates] Creating new duplicates storage with assembly info`);
        const newStorage = {
          duplicateGroups: duplicateGroups,
          detectionAlgorithm: detectionAlgorithm,
          timestamp: Date.now(),
          fileId: selectedAudioFile.id,
          filename: selectedAudioFile.filename,
          assemblyInfo: assemblyData.info
        };
        localStorage.setItem(storageKey, JSON.stringify(newStorage));
        console.log(`[Tab3Duplicates] ✅ Created duplicates storage with assembly info`);
      }
      
      console.log(`[Tab3Duplicates] Saved assembly info to localStorage`);

      // Update server with assembly info
      if (duplicateGroups && duplicateGroups.length > 0) {
        const serverSave = await saveDuplicateAnalysisToServer(
          selectedAudioFile.filename,
          duplicateGroups,
          detectionAlgorithm,
          selectedDeletions,
          assemblyData  // Include assembly info
        );

        if (serverSave.success) {
          console.log('[Tab3Duplicates] Assembly info synced to server');
        } else {
          console.log('[Tab3Duplicates] Assembly info saved locally only');
        }
      }

      const removedTime = clientAudioAssembly.formatDuration(result.info.removedDuration);
      const newDuration = clientAudioAssembly.formatDuration(result.info.assembledDuration);
      const fileSize = clientAudioAssembly.formatFileSize(result.blob.size);

      alert(
        `✅ Audio Assembly Complete!\n\n` +
        `🎵 New Duration: ${newDuration}\n` +
        `🗑️ Removed: ${removedTime} (${result.removedCount} segments)\n` +
        `✅ Kept: ${result.keptCount} segments\n` +
        `💾 File Size: ${fileSize}\n\n` +
        `🖥️ Processed entirely in your browser.\n` +
        `☁️ Assembly info synced to server for cross-device access.\n\n` +
        `Download button is now available above.\n\n` +
        `Note: The assembled audio will remain available until you leave this tab or refresh the page.`
      );

    } catch (error) {
      console.error('[Tab3Duplicates] Audio assembly error:', error);
      alert(`Audio assembly failed: ${error.message}\n\nPlease try again or contact support.`);
    } finally {
      setIsAssemblingAudio(false);
      setAssemblyProgress({ current: 0, total: 0, status: '' });
    }
  };

  const handleDownloadAssembledAudio = () => {
    if (!assembledAudioBlob) {
      alert('No assembled audio available. Please assemble audio first.');
      return;
    }

    const url = URL.createObjectURL(assembledAudioBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedAudioFile.filename.replace(/\.[^/.]+$/, '')}_assembled.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('[Tab3Duplicates] Assembled audio downloaded');
  };

  // Select all duplicates for deletion
  const handleSelectAllDuplicates = () => {
    const allDuplicates = [];
    duplicateGroups.forEach(group => {
      group.segments.forEach(seg => {
        if (seg.is_duplicate === true) {
          allDuplicates.push(seg.id);
        }
      });
    });
    setSelectedDeletions(allDuplicates);
    
    // Save to localStorage
    if (selectedAudioFile) {
      const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
      localStorage.setItem(`${storageKey}_selectedDeletions`, JSON.stringify(allDuplicates));
    }
  };

  // Deselect all duplicates
  const handleDeselectAll = () => {
    setSelectedDeletions([]);
    
    // Save to localStorage
    if (selectedAudioFile) {
      const storageKey = `duplicates_${selectedAudioFile.id}_${projectId}`;
      localStorage.setItem(`${storageKey}_selectedDeletions`, JSON.stringify([]));
    }
  };

  const handleDownloadTranscription = (format) => {
    if (!selectedAudioFile) {
      alert('No file selected');
      return;
    }

    // Get all segments
    let allSegments = [];
    if (selectedAudioFile.transcription && selectedAudioFile.transcription.all_segments) {
      allSegments = selectedAudioFile.transcription.all_segments;
    } else {
      // Try loading from localStorage for client-only files
      const storageKey = `client_transcriptions_${projectId}`;
      const localFiles = JSON.parse(localStorage.getItem(storageKey) || '[]');
      const matchingFile = localFiles.find(f => f.id === selectedAudioFile.id || f.filename === selectedAudioFile.filename);
      
      if (matchingFile && matchingFile.transcription && matchingFile.transcription.all_segments) {
        allSegments = matchingFile.transcription.all_segments;
      }
    }

    if (allSegments.length === 0) {
      alert('No transcription segments found for this file.');
      return;
    }

    try {
      const baseFilename = selectedAudioFile.filename || selectedAudioFile.title || 'transcription';
      downloadHelper.downloadTranscription(allSegments, baseFilename, format);
      console.log(`[Tab3Duplicates] Downloaded transcription as ${format}`);
    } catch (error) {
      console.error('[Tab3Duplicates] Download error:', error);
      alert(`Failed to download: ${error.message}`);
    }
  };

  const toggleGroup = (groupId) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  const toggleDeletion = (segmentId) => {
    setSelectedDeletions(prev =>
      prev.includes(segmentId)
        ? prev.filter(id => id !== segmentId)
        : [...prev, segmentId]
    );
  };

  const renderHighlightedDuplicateText = (text, groupSegments) => {
    if (!text || !groupSegments || groupSegments.length < 2) {
      return text;
    }

    const normalizedWordSets = groupSegments
      .map(seg => (seg.text || '').toLowerCase().match(/[a-z0-9']+/g) || [])
      .map(words => new Set(words.filter(word => word.length >= 3)));

    if (normalizedWordSets.length < 2) {
      return text;
    }

    const commonWords = [...normalizedWordSets[0]].filter(word =>
      normalizedWordSets.slice(1).every(wordSet => wordSet.has(word))
    );

    if (commonWords.length === 0) {
      return text;
    }

    const commonWordSet = new Set(commonWords);
    const tokens = text.match(/\w+|\s+|[^\w\s]+/g) || [text];

    return tokens.map((token, index) => {
      const normalized = token.toLowerCase().replace(/[^a-z0-9']/g, '');
      if (normalized && commonWordSet.has(normalized)) {
        return (
          <mark
            key={`token-${index}`}
            style={{ background: '#fde68a', color: '#7c2d12', padding: '0 2px', borderRadius: '2px' }}
          >
            {token}
          </mark>
        );
      }
      return <React.Fragment key={`token-${index}`}>{token}</React.Fragment>;
    });
  };

  // Get transcribed files for selection
  const transcribedFiles = useMemo(() => {
    return audioFiles.filter(f => f.status === 'transcribed' || f.status === 'processed');
  }, [audioFiles]);

  return (
    <div className="tab3-container">
      <div className="tab-header">
        <h2>🔍 Find & Remove Duplicates</h2>
        <p>Detect repeated content within a single audio file. The system will keep the last occurrence of each duplicate.</p>
      </div>

      {/* Selected File Display */}
      {selectedAudioFile ? (
        <div className="file-selection-card">
          <div style={{ marginBottom: '1rem' }}>
            <label className="input-label">Working with:</label>
            <div style={{ 
              padding: '0.75rem', 
              background: '#e0e7ff', 
              borderRadius: '6px',
              border: '2px solid #667eea',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{ fontSize: '1.5rem' }}>🎵</span>
              <span style={{ fontWeight: '600', color: '#1e293b' }}>{selectedAudioFile.filename}</span>
              <span style={{ marginLeft: 'auto', fontSize: '0.9rem', color: '#64748b' }}>({selectedAudioFile.status})</span>
            </div>
            <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#64748b' }}>
              💡 Tip: Select a different file in the "Upload & Transcribe" tab to work with it here.
            </div>
          </div>

          {/* Download Transcription Section */}
          {selectedAudioFile && (selectedAudioFile.transcription || selectedAudioFile.client_only) && (
            <div style={{
              padding: '1rem',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              background: 'white',
              marginBottom: '1rem'
            }}>
              <h4 style={{ margin: 0, marginBottom: '0.75rem', color: '#1e293b', fontSize: '0.95rem' }}>
                📥 Download Transcription
              </h4>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  onClick={() => handleDownloadTranscription('txt')}
                  className="download-format-button"
                >
                  TXT
                </button>
                <button
                  onClick={() => handleDownloadTranscription('txt-timestamps')}
                  className="download-format-button"
                >
                  TXT + Timestamps
                </button>
                <button
                  onClick={() => handleDownloadTranscription('json')}
                  className="download-format-button"
                >
                  JSON
                </button>
                <button
                  onClick={() => handleDownloadTranscription('srt')}
                  className="download-format-button"
                >
                  SRT (Subtitles)
                </button>
                <button
                  onClick={() => handleDownloadTranscription('vtt')}
                  className="download-format-button"
                >
                  VTT (WebVTT)
                </button>
              </div>
            </div>
          )}

          <div style={{
            padding: '1rem',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            background: '#f8fafc',
            marginBottom: '1rem'
          }}>
            <h4 style={{ margin: 0, marginBottom: '0.5rem', color: '#1e293b' }}>Before you start</h4>
            <p style={{ margin: 0, color: '#475569', fontSize: '0.9rem' }}>
              1) Choose mode (AI or Algorithm). 2) For Algorithm mode, adjust settings (optional). 3) Click Start.
              All modes keep the last occurrence and mark earlier repeats for deletion.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="button"
                onClick={() => setDuplicateDetectionMode('algorithm')}
                disabled={detecting}
                style={{
                  padding: '0.55rem 0.75rem',
                  borderRadius: '8px',
                  border: duplicateDetectionMode === 'algorithm' ? '2px solid #2563eb' : '1px solid #cbd5e1',
                  background: duplicateDetectionMode === 'algorithm' ? '#eff6ff' : '#ffffff',
                  fontWeight: '600',
                  color: '#334155',
                  cursor: detecting ? 'not-allowed' : 'pointer'
                }}
              >
                Algorithm
              </button>
              <button
                type="button"
                onClick={() => setDuplicateDetectionMode('ai')}
                disabled={detecting || selectedAudioFile?.client_only || selectedAudioFile?.client_processed}
                style={{
                  padding: '0.55rem 0.75rem',
                  borderRadius: '8px',
                  border: duplicateDetectionMode === 'ai' ? '2px solid #0891b2' : '1px solid #cbd5e1',
                  background: duplicateDetectionMode === 'ai' ? '#ecfeff' : '#ffffff',
                  fontWeight: '600',
                  color: '#334155',
                  cursor: (detecting || selectedAudioFile?.client_only || selectedAudioFile?.client_processed) ? 'not-allowed' : 'pointer'
                }}
                title={selectedAudioFile?.client_only || selectedAudioFile?.client_processed ? 'AI mode requires a server-side transcribed file' : 'Use AI duplicate detection'}
              >
                AI
              </button>
            </div>

            {duplicateDetectionMode === 'algorithm' && (
              <select
                value={detectionAlgorithm}
                onChange={(e) => setDetectionAlgorithm(e.target.value)}
                disabled={detecting}
                style={{
                  minWidth: '280px',
                  padding: '0.6rem 0.75rem',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontWeight: '600',
                  color: '#334155',
                  background: 'white'
                }}
              >
                {algorithmOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            )}

            {duplicateDetectionMode === 'ai' && (
              <div style={{
                padding: '0.45rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid #99f6e4',
                background: '#f0fdfa',
                color: '#0f766e',
                fontWeight: '600'
              }}>
                AI mode uses server-side Claude detection
              </div>
            )}

            {duplicateDetectionMode === 'algorithm' && (
              <button
                onClick={() => setShowAlgorithmSettings((prev) => !prev)}
                disabled={detecting}
                style={{
                  padding: '0.75rem 1rem',
                  background: '#ffffff',
                  color: '#334155',
                  border: '1px solid #cbd5e1',
                  borderRadius: '8px',
                  fontWeight: '600',
                  cursor: detecting ? 'not-allowed' : 'pointer'
                }}
              >
                {showAlgorithmSettings ? '⚙️ Hide Settings' : '⚙️ Show Settings'}
              </button>
            )}

            <button
              onClick={handleStartDetection}
              disabled={detecting}
              className="detect-button"
            >
              {detecting
                ? (duplicateDetectionMode === 'ai' ? '⏳ Running AI Detection...' : '⏳ Detecting Duplicates...')
                : (duplicateDetectionMode === 'ai' ? '🤖 Start AI Detection' : '▶️ Start Detection')}
            </button>
            
            {detecting && detectionProgress.status && (
              <div className="detection-progress">
                <p className="progress-status">{detectionProgress.status}</p>
                {detectionProgress.total > 0 && (
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ width: `${(detectionProgress.current / detectionProgress.total) * 100}%` }}
                    />
                  </div>
                )}
              </div>
            )}
            
            {duplicateGroups.length > 0 && (
              <button
                onClick={handleClearResults}
                className="clear-button"
              >
                🔄 Clear Results
              </button>
            )}
          </div>

          {duplicateDetectionMode === 'algorithm' && showAlgorithmSettings && (
            <div style={{
              padding: '1rem',
              border: '1px solid #cbd5e1',
              borderRadius: '8px',
              background: 'white',
              marginBottom: '0.5rem'
            }}>
              <h4 style={{ margin: 0, marginBottom: '0.75rem', color: '#1e293b' }}>Algorithm Settings</h4>

              {detectionAlgorithm === 'tfidf_cosine' && (
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <label style={{ fontWeight: '600', color: '#475569' }}>Similarity Threshold</label>
                  <input
                    type="number"
                    min="0.5"
                    max="0.99"
                    step="0.01"
                    value={tfidfSimilarityThreshold}
                    onChange={(e) => setTfidfSimilarityThreshold(parseFloat(e.target.value || 0.85))}
                    style={{ width: '100px', padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              )}

              {(detectionAlgorithm === 'windowed_retry' || detectionAlgorithm === 'windowed_retry_pdf') && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Max Lookahead Segments
                    <input
                      type="number"
                      min="10"
                      max="300"
                      step="5"
                      value={windowMaxLookahead}
                      onChange={(e) => setWindowMaxLookahead(parseInt(e.target.value || 90, 10))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Ratio Threshold
                    <input
                      type="number"
                      min="0.5"
                      max="0.99"
                      step="0.01"
                      value={windowRatioThreshold}
                      onChange={(e) => setWindowRatioThreshold(parseFloat(e.target.value || 0.76))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Strong Match Ratio
                    <input
                      type="number"
                      min="0.6"
                      max="0.99"
                      step="0.01"
                      value={windowStrongMatchRatio}
                      onChange={(e) => setWindowStrongMatchRatio(parseFloat(e.target.value || 0.84))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>

                  <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontWeight: '600', color: '#475569' }}>
                    Min Word Length
                    <input
                      type="number"
                      min="1"
                      max="10"
                      step="1"
                      value={windowMinWordLength}
                      onChange={(e) => setWindowMinWordLength(parseInt(e.target.value || 3, 10))}
                      style={{ padding: '0.45rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                    />
                  </label>
                </div>
              )}

              {isPdfHintAlgorithm && (
                <div style={{
                  marginTop: '0.9rem',
                  padding: '0.9rem',
                  border: '1px solid #bfdbfe',
                  borderRadius: '8px',
                  background: '#eff6ff'
                }}>
                  <h5 style={{ margin: 0, marginBottom: '0.5rem', color: '#1e3a8a' }}>PDF Hint Scope (Optional)</h5>
                  <p style={{ margin: 0, marginBottom: '0.6rem', fontSize: '0.875rem', color: '#1d4ed8' }}>
                    Use the same start/end style as Compare PDF. You can also clean just this PDF region before detection.
                  </p>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
                    <button
                      onClick={() => {
                        setPdfSelectorMode('start');
                        setShowPdfRegionSelector(true);
                      }}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: '1px solid #93c5fd', background: 'white', color: '#1d4ed8', fontWeight: '600' }}
                    >
                      {pdfStartChar !== null ? `📄 Start: ${pdfStartChar}` : '📄 Select PDF Start'}
                    </button>
                    <button
                      onClick={() => {
                        setPdfSelectorMode('end');
                        setShowPdfRegionSelector(true);
                      }}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: '1px solid #93c5fd', background: 'white', color: '#1d4ed8', fontWeight: '600' }}
                    >
                      {pdfEndChar !== null ? `📄 End: ${pdfEndChar}` : '📄 Select PDF End'}
                    </button>
                    <button
                      onClick={handleCleanPdfForDuplicateHint}
                      disabled={isCleaningPDF}
                      style={{ padding: '0.45rem 0.75rem', borderRadius: '6px', border: 'none', background: isCleaningPDF ? '#94a3b8' : '#10b981', color: 'white', fontWeight: '600' }}
                    >
                      {isCleaningPDF ? 'Cleaning...' : '🧹 Clean PDF (Hint Scope)'}
                    </button>
                  </div>

                  {(pdfStartText || pdfEndText) && (
                    <div style={{
                      marginBottom: '0.6rem',
                      padding: '0.6rem',
                      borderRadius: '6px',
                      background: '#ffffff',
                      border: '1px solid #dbeafe',
                      fontSize: '0.8rem',
                      color: '#334155'
                    }}>
                      {pdfStartText && <div><strong>Start preview:</strong> {pdfStartText}</div>}
                      {pdfEndText && <div style={{ marginTop: '0.35rem' }}><strong>End preview:</strong> {pdfEndText}</div>}
                    </div>
                  )}

                  {pdfCleanupMessage && (
                    <div style={{
                      padding: '0.6rem',
                      borderRadius: '6px',
                      background: pdfCleanupMessage.type === 'success' ? '#dcfce7' : '#fee2e2',
                      color: pdfCleanupMessage.type === 'success' ? '#166534' : '#991b1b',
                      fontWeight: '600',
                      fontSize: '0.85rem'
                    }}>
                      {pdfCleanupMessage.text}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {lastRunSummary && (
            <div style={{ 
              fontSize: '0.9rem', 
              color: '#1e40af',
              background: '#eff6ff',
              padding: '0.75rem',
              borderRadius: '6px',
              border: '1px solid #bfdbfe',
              marginBottom: '1rem'
            }}>
              <strong>🔍 Detection Used:</strong> {lastRunSummary.algorithm}
              {lastRunSummary.groupCount !== undefined && (
                <> • <strong>{lastRunSummary.groupCount}</strong> duplicate groups found</>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state">
          <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎵</div>
            <h3 style={{ marginBottom: '0.5rem' }}>No File Selected</h3>
            <p>Please select a transcribed audio file in the <strong>"Upload & Transcribe"</strong> tab to begin duplicate detection.</p>
          </div>
        </div>
      )}

      {/* PDF Region Selector Modal (for PDF hint algorithm) */}
      {showPdfRegionSelector && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '2rem',
          overflowY: 'auto'
        }}>
          <div style={{ maxWidth: '1200px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <PDFRegionSelector
              projectId={projectId}
              mode={pdfSelectorMode}
              type="pdf"
              currentStart={pdfStartChar}
              currentEnd={pdfEndChar}
              transcriptText={transcriptText}
              onPositionSelected={handlePdfPositionSelected}
              onCancel={() => setShowPdfRegionSelector(false)}
            />
          </div>
        </div>
      )}
      
      {/* Duplicate Groups */}
      {selectedAudioFile && duplicateGroups.length === 0 && !detecting && (
        <div className="empty-state">
          <p>Click "Detect Duplicates" to analyze this file for repeated content.</p>
        </div>
      )}

      {/* Interactive Waveform Editor - works with both server and client files */}
      {selectedAudioFile && (selectedAudioFile.file || selectedAudioFile.audio_file || selectedAudioFile.local_file) && duplicateGroups.length > 0 && (
        <WaveformDuplicateEditor
          audioFile={selectedAudioFile.file || selectedAudioFile.audio_file || selectedAudioFile.local_file}
          duplicateGroups={duplicateGroups}
          selectedGroupId={selectedGroupId}
          onRegionUpdate={handleRegionUpdate}
          onGroupSelect={handleGroupSelect}
          onRefresh={loadDuplicateGroups}
        />
      )}

      {/* Action Buttons - Moved to top for better UX */}
      {duplicateGroups.length > 0 && (
        <div className="review-actions-top">
          {selectedAudioFile && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                onClick={handleSelectAllDuplicates}
                disabled={processing || isAssemblingAudio}
                className="secondary-button"
                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              >
                ✓ Select All
              </button>

              <button
                onClick={handleDeselectAll}
                disabled={processing || isAssemblingAudio || selectedDeletions.length === 0}
                className="secondary-button"
                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              >
                ✗ Deselect All
              </button>

              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  onClick={handleAssembleAudio}
                  disabled={selectedDeletions.length === 0 || isAssemblingAudio || processing}
                  className="confirm-button assemble-button"
                  style={{ background: isAssemblingAudio ? '#f59e0b' : '#16a34a' }}
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

      {/* Results */}
      {duplicateGroups.length > 0 && (
        <div className="duplicate-results">
          <div className="results-header">
            <h3>Review Detected Duplicates</h3>
            <p className="selection-summary">
              <strong>Selected for deletion:</strong> {selectedDeletions.length} segments
            </p>
          </div>

          <div className="duplicate-groups-list">
            {duplicateGroups.map((group, groupIndex) => {
              const isExpanded = expandedGroups.has(group.group_id);
              const segments = group.segments || group.occurrences || [];
              const isSelected = selectedGroupId === group.group_id;
              
              return (
                <div 
                  key={group.group_id} 
                  className={`duplicate-group-card ${isSelected ? 'selected' : ''}`}
                  data-group-id={group.group_id}
                >
                  <div 
                    className="group-header" 
                    onClick={() => {
                      toggleGroup(group.group_id);
                      handleGroupSelect(group.group_id);
                      if (segments.length > 0 && segments[0].start_time != null) {
                        seekToTime(segments[0].start_time);
                      }
                    }}
                  >
                    <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
                    <span className="group-title">Group {groupIndex + 1}</span>
                    <span className="group-text-inline">"{group.duplicate_text?.substring(0, 60) || (segments[0]?.text?.substring(0, 60)) || 'No text'}{(group.duplicate_text?.length > 60 || segments[0]?.text?.length > 60) ? '...' : ''}"</span>
                    <span className="group-meta-inline">
                      📊 {group.occurrence_count || segments.length} · ⏱️ {(group.total_duration_seconds || segments.reduce((sum, s) => sum + (s.end_time - s.start_time), 0)).toFixed(1)}s
                    </span>
                  </div>

                  {isExpanded && segments.length > 0 && (
                    <div className="group-occurrences">
                      {segments.map((segment, index) => {
                        // Backend flags:
                        // - is_duplicate = true → DELETE (all except last)
                        // - is_duplicate = false → KEEP (last occurrence)
                        // - is_kept = true → explicitly marked to keep
                        const shouldDelete = segment.is_duplicate === true;
                        const shouldKeep = segment.is_kept === true || !shouldDelete;
                        
                        return (
                          <div
                            key={segment.id}
                            className={`occurrence-card ${shouldKeep ? 'last-occurrence' : ''}`}
                          >
                            <div className="occurrence-header">
                              <label className="checkbox-container">
                                <input
                                  type="checkbox"
                                  checked={selectedDeletions.includes(segment.id)}
                                  onChange={() => toggleDeletion(segment.id)}
                                  disabled={shouldKeep}
                                />
                                <span className="occurrence-title">
                                  Occurrence #{segment.occurrence_number || segment.segment_index || (index + 1)}
                                  {shouldKeep && ' (LAST - Keep)'}
                                </span>
                              </label>
                              <span className={`action-badge ${shouldKeep ? 'keep' : 'delete'}`}>
                                {shouldKeep ? 'KEEP' : 'DELETE'}
                              </span>
                            </div>

                            <div className="occurrence-details">
                              <p>
                                <strong>Time:</strong> 
                                <span 
                                  className="timestamp-link"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    seekToTime(segment.start_time);
                                  }}
                                  title="Click to jump to this timestamp in audio"
                                >
                                  🎯 {segment.start_time?.toFixed(1)}s - {segment.end_time?.toFixed(1)}s
                                </span>
                                ({(segment.end_time - segment.start_time)?.toFixed(1)}s)
                              </p>
                              <p className="occurrence-text">
                                <strong>Text:</strong> "{renderHighlightedDuplicateText(segment.text, segments)}"
                              </p>
                              <p style={{fontSize: '0.8rem', color: '#666', marginTop: '0.5rem'}}>
                                <strong>DEBUG:</strong> is_duplicate={String(segment.is_duplicate)}, is_kept={String(segment.is_kept)}, is_last_occurrence={String(segment.is_last_occurrence)}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
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
