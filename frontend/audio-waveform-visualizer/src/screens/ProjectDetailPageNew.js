import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { ProjectTabProvider } from "../contexts/ProjectTabContext";
import ProjectTabs from "../components/ProjectTabs/ProjectTabs";
import Tab1Files from "../components/ProjectTabs/Tab1Files";
import Tab3Duplicates from "../components/ProjectTabs/Tab3Duplicates";
import Tab4Results from "../components/ProjectTabs/Tab4Results";
import Tab4Review from "../components/Tab4Review";
import Tab5ComparePDF from "../components/ProjectTabs/Tab5ComparePDF";
import "./ProjectDetailPageNew.css";

/**
 * New Tab-Based Project Detail Page
 * Replaces the old single-page workflow with 5 independent tabs
 */
const ProjectDetailPageNew = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  
  const [projectData, setProjectData] = useState(null);
  const [activeTab, setActiveTab] = useState('files');
  const [loading, setLoading] = useState(true);

  // Load project details
  useEffect(() => {
    const fetchProject = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/projects/${projectId}/`, {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          setProjectData(data);
        } else if (response.status === 404) {
          alert('Project not found');
          navigate('/projects');
        }
      } catch (error) {
        console.error('Error loading project:', error);
      } finally {
        setLoading(false);
      }
    };

    if (token && projectId) {
      fetchProject();
    }
  }, [projectId, token, navigate]);

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading project...</p>
      </div>
    );
  }

  if (!projectData) {
    return (
      <div className="error-container">
        <p>Failed to load project</p>
        <button onClick={() => navigate('/projects')}>Back to Projects</button>
      </div>
    );
  }

  return (
    <ProjectTabProvider projectId={projectId}>
      <div className="project-detail-page-new">
        {/* Header */}
        <div className="project-header">
          <button className="back-button" onClick={() => navigate('/projects')}>
            ← Back to Projects
          </button>
          <div className="project-title-section">
            <h1>{projectData.name}</h1>
            {projectData.description && (
              <p className="project-description">{projectData.description}</p>
            )}
          </div>
          <div className="project-info">
            <span className="info-badge">
              📁 Project ID: {projectId}
            </span>
            {projectData.pdf_file && (
              <span className="info-badge success">
                ✅ PDF Uploaded
              </span>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <ProjectTabs 
          activeTab={activeTab} 
          onTabChange={setActiveTab}
        />

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'files' && <Tab1Files />}
          {activeTab === 'duplicates' && <Tab3Duplicates />}
          {activeTab === 'results' && <Tab4Results />}
          {activeTab === 'review' && <Tab4Review />}
          {activeTab === 'compare' && <Tab5ComparePDF />}
        </div>
      </div>
    </ProjectTabProvider>
  );
};

export default ProjectDetailPageNew;
