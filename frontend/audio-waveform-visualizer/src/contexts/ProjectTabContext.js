import React, { createContext, useContext, useState, useCallback } from 'react';

const ProjectTabContext = createContext();

/**
 * Context for managing state across all project tabs
 * Tracks selected audio file, project details, and tab-specific data
 */
export const ProjectTabProvider = ({ children, projectId }) => {
  const [activeTab, setActiveTab] = useState('files');
  const [selectedAudioFile, setSelectedAudioFile] = useState(null);
  const [audioFiles, setAudioFiles] = useState([]);
  const [projectData, setProjectData] = useState(null);
  
  // Tab-specific state
  const [transcriptionData, setTranscriptionData] = useState(null);
  const [duplicatesData, setDuplicatesData] = useState(null);
  const [pdfComparisonData, setPdfComparisonData] = useState(null);
  
  // Deletion workflow state
  const [pendingDeletions, setPendingDeletions] = useState(null); // Confirmed deletions waiting to be processed
  const [processingDeletion, setProcessingDeletion] = useState(null); // Currently processing deletion task
  
  // Loading and error states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load project data including PDF
  const refreshProjectData = useCallback(async (token) => {
    if (!projectId || !token) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/`, {
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setProjectData(data.project || data);
        return data.project || data;
      }
    } catch (err) {
      console.error('Error loading project data:', err);
      setError(err.message);
    }
  }, [projectId]);

  // Refresh audio files list (used by multiple tabs)
  const refreshAudioFiles = useCallback(async (token) => {
    if (!projectId || !token) return;
    
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8000/api/projects/${projectId}/files/`, {
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setAudioFiles(data.audio_files || []);
        return data.audio_files;
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Select audio file and load its data
  const selectAudioFile = useCallback((audioFile) => {
    setSelectedAudioFile(audioFile);
    // Clear tab-specific data when switching files
    setTranscriptionData(null);
    setDuplicatesData(null);
    setPdfComparisonData(null);
    setPendingDeletions(null);
  }, []);

  // Clear selected file
  const clearSelection = useCallback(() => {
    setSelectedAudioFile(null);
    setTranscriptionData(null);
    setDuplicatesData(null);
    setPdfComparisonData(null);
    setPendingDeletions(null);
    setProcessingDeletion(null);
  }, []);

  // Update audio file in the list after status change
  const updateAudioFile = useCallback((updatedFile) => {
    setAudioFiles(prev => 
      prev.map(file => file.id === updatedFile.id ? updatedFile : file)
    );
    
    // Update selected file if it's the one that changed
    if (selectedAudioFile?.id === updatedFile.id) {
      setSelectedAudioFile(updatedFile);
    }
  }, [selectedAudioFile]);

  // Remove audio file from list (after deletion)
  const removeAudioFile = useCallback((fileId) => {
    setAudioFiles(prev => prev.filter(file => file.id !== fileId));
    
    // Clear selection if deleted file was selected
    if (selectedAudioFile?.id === fileId) {
      clearSelection();
    }
  }, [selectedAudioFile, clearSelection]);

  const value = {
    // Navigation
    activeTab,
    setActiveTab,
    
    // Project
    projectId,
    projectData,
    setProjectData,
    refreshProjectData,
    
    // Audio Files
    audioFiles,
    setAudioFiles,
    refreshAudioFiles,
    updateAudioFile,
    removeAudioFile,
    
    // Selected File
    selectedAudioFile,
    selectAudioFile,
    clearSelection,
    
    // Tab-specific data
    transcriptionData,
    setTranscriptionData,
    duplicatesData,
    setDuplicatesData,
    pdfComparisonData,
    setPdfComparisonData,
    
    // Deletion workflow
    pendingDeletions,
    setPendingDeletions,
    processingDeletion,
    setProcessingDeletion,
    
    // UI State
    loading,
    setLoading,
    error,
    setError
  };

  return (
    <ProjectTabContext.Provider value={value}>
      {children}
    </ProjectTabContext.Provider>
  );
};

export const useProjectTab = () => {
  const context = useContext(ProjectTabContext);
  if (!context) {
    throw new Error('useProjectTab must be used within ProjectTabProvider');
  }
  return context;
};

export default ProjectTabContext;
