import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { getApiUrl } from "../config/api";
import "../static/CSS/ProjectPage.css";

const ProjectPage = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newProjectTitle, setNewProjectTitle] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const isWelcome = searchParams.get('welcome') === 'true';

  const fetchProjects = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(getApiUrl("/api/projects/"), {
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        // Handle both array format and {projects: []} format
        const projectsArray = Array.isArray(data) ? data : (data.projects || []);
        setProjects(projectsArray);
        console.log('Projects loaded:', projectsArray);
      } else if (response.status === 401) {
        setError("Authentication required. Please log in again.");
        navigate('/login');
      } else {
        setError("Failed to fetch projects. Please try again.");
        console.error("Failed to fetch projects:", response.statusText);
      }
    } catch (error) {
      setError("Network error. Please check your connection.");
      console.error("Error fetching projects:", error);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const createProject = async (e) => {
    e.preventDefault();
    
    if (!newProjectTitle.trim()) {
      alert("Please enter a project title");
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(getApiUrl("/api/projects/"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify({
          title: newProjectTitle.trim()
        })
      });

      if (response.ok) {
        const data = await response.json();
        setNewProjectTitle("");
        setShowCreateForm(false);
        fetchProjects(); // Refresh list
        
        // Navigate to the new project
        navigate(`/project/${data.project.id}`);
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to create project");
      }
    } catch (error) {
      console.error("Error creating project:", error);
      alert("Failed to create project");
    }
  };

  const deleteProject = async (projectId, projectTitle, e) => {
    e.stopPropagation(); // Prevent card click from triggering
    
    if (!window.confirm(`Are you sure you want to delete "${projectTitle}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(getApiUrl(`/api/projects/${projectId}/`), {
        method: "DELETE",
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        // Remove project from state
        setProjects(prev => prev.filter(p => p.id !== projectId));
      } else {
        const errorData = await response.json();
        alert(errorData.error || "Failed to delete project");
      }
    } catch (error) {
      console.error("Error deleting project:", error);
      alert("Failed to delete project");
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#4CAF50';
      case 'processing': return '#FF9800';
      case 'failed': return '#F44336';
      default: return '#9E9E9E';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending': return 'Ready to upload files';
      case 'processing': return 'Processing...';
      case 'completed': return 'Completed';
      case 'failed': return 'Failed';
      default: return status;
    }
  };

  if (loading) {
    return (
      <div className="project-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading projects...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-page">
      <div className="project-header">
        <h1>Audio Duplicate Detection Projects</h1>
        <button
          className="create-project-btn"
          onClick={() => setShowCreateForm(true)}
        >
          Create New Project
        </button>
      </div>

      {isWelcome && (
        <div className="welcome-banner">
          <h2>🎉 Welcome to Audio Duplicate Detection!</h2>
          <p>
            Hello {user?.first_name || user?.username}! Your account has been created successfully. 
            You can now start creating projects to remove duplicate content from your audio recordings.
          </p>
        </div>
      )}

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {showCreateForm && (
        <div className="create-form-overlay">
          <div className="create-form">
            <h2>Create New Project</h2>
            <form onSubmit={createProject}>
              <input
                type="text"
                placeholder="Enter project title..."
                value={newProjectTitle}
                onChange={(e) => setNewProjectTitle(e.target.value)}
                autoFocus
              />
              <div className="form-buttons">
                <button type="submit">Create Project</button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    setNewProjectTitle("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="projects-grid">
        {projects.length === 0 ? (
          <div className="empty-state">
            <h3>No projects yet</h3>
            <p>Create your first project to get started with audio duplicate detection.</p>
            <button
              className="create-first-project-btn"
              onClick={() => setShowCreateForm(true)}
            >
              Create Your First Project
            </button>
          </div>
        ) : (
          projects.map(project => (
            <div
              key={project.id}
              className="project-card"
              onClick={() => navigate(`/project/${project.id}`)}
            >
              <div className="project-card-header">
                <h3>{project.title}</h3>
                <div className="header-actions">
                  <div
                    className="status-indicator"
                    style={{ backgroundColor: getStatusColor(project.status) }}
                  ></div>
                  <button
                    className="delete-project-btn"
                    onClick={(e) => deleteProject(project.id, project.title, e)}
                    title="Delete project"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              
              <div className="project-info">
                <p className="status-text">{getStatusText(project.status)}</p>
                
                <div className="file-indicators">
                  <div className={`file-indicator ${project.has_pdf ? 'uploaded' : 'missing'}`}>
                    📄 PDF {project.has_pdf ? '✓' : '✗'}
                  </div>
                  <div className={`file-indicator ${project.has_audio ? 'uploaded' : 'missing'}`}>
                    🎵 Audio {project.has_audio ? '✓' : '✗'}
                  </div>
                  {project.has_processed_audio && (
                    <div className="file-indicator completed">
                      ✨ Processed ✓
                    </div>
                  )}
                </div>
                
                <div className="project-dates">
                  <small>Created: {new Date(project.created_at).toLocaleDateString()}</small>
                  <small>Updated: {new Date(project.updated_at).toLocaleDateString()}</small>
                </div>
              </div>
              
              <div className="project-actions">
                <button className="open-project-btn">
                  Open Project →
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ProjectPage;