import React, { useState, useEffect } from 'react';
import { useProjectTab } from '../contexts/ProjectTabContext';
import { useAuth } from '../contexts/AuthContext';
import './Tab4Review.css';

/**
 * Tab 4: Review - Project-Wide Comparison
 * Compare processed audio files against originals, PDF, and detected deletions
 */
const Tab4Review = () => {
  const { token } = useAuth();
  const { projectId } = useProjectTab();
  
  const [comparisonData, setComparisonData] = useState(null);
  const [selectedFileId, setSelectedFileId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch project-wide comparison data
  useEffect(() => {
    if (projectId) {
      fetchComparisonData();
    }
  }, [projectId]);

  const fetchComparisonData = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/comparison/`,
        {
          headers: {
            'Authorization': `Token ${token}`,
          },
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setComparisonData(data);
        setError(null);
      } else {
        setError('Failed to load comparison data');
      }
    } catch (err) {
      console.error('Error fetching comparison data:', err);
      setError('Failed to load comparison data');
    } finally {
      setLoading(false);
    }
  };

  const markAsReviewed = async (fileId) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/projects/${projectId}/files/${fileId}/mark-reviewed/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.ok) {
        // Refresh comparison data
        fetchComparisonData();
      }
    } catch (err) {
      console.error('Error marking file as reviewed:', err);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
      return `${mins}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const formatPercentage = (value) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="tab4-review">
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading comparison data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab4-review">
        <div className="error-message">
          {error}
        </div>
      </div>
    );
  }

  if (!comparisonData || !comparisonData.files || comparisonData.files.length === 0) {
    return (
      <div className="tab4-review">
        <div className="empty-state">
          <h3>No Processed Files Found</h3>
          <p>Process audio files in the Results tab first to see comparison data here.</p>
        </div>
      </div>
    );
  }

  const projectStats = comparisonData.project_stats || {};

  return (
    <div className="tab4-review">
      <div className="review-header">
        <h2>Project-Wide Comparison & Review</h2>
        <p className="review-description">
          Compare processed audio against originals, review detected deletions, and validate against PDF transcripts.
        </p>
      </div>

      {/* Project-Wide Statistics */}
      <div className="tab4-project-statistics">
        <h3>Project Summary</h3>
        <div className="tab4-stats-grid">
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Total Files</div>
            <div className="tab4-stat-value">{projectStats.total_files || 0}</div>
          </div>
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Processed Files</div>
            <div className="tab4-stat-value success">{projectStats.processed_files || 0}</div>
          </div>
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Total Time Saved</div>
            <div className="tab4-stat-value">{formatDuration(projectStats.total_time_saved)}</div>
          </div>
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Avg Compression</div>
            <div className="tab4-stat-value">{formatPercentage(projectStats.avg_compression_ratio || 0)}</div>
          </div>
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Total Deletions</div>
            <div className="tab4-stat-value">{projectStats.total_deletions || 0}</div>
          </div>
          <div className="tab4-stat-card">
            <div className="tab4-stat-label">Reviewed Files</div>
            <div className="tab4-stat-value">{projectStats.reviewed_files || 0}</div>
          </div>
        </div>
      </div>

      {/* File Comparison Table */}
      <div className="tab4-files-comparison">
        <h3>File-by-File Comparison</h3>
        <div className="tab4-comparison-table">
          <div className="tab4-table-header">
            <div className="tab4-col-filename">Filename</div>
            <div className="tab4-col-original">Original Duration</div>
            <div className="tab4-col-processed">Processed Duration</div>
            <div className="tab4-col-saved">Time Saved</div>
            <div className="tab4-col-deletions">Deletions</div>
            <div className="tab4-col-status">Status</div>
            <div className="tab4-col-actions">Actions</div>
          </div>
          
          {comparisonData.files.map((file) => (
            <div 
              key={file.id} 
              className={`tab4-table-row ${selectedFileId === file.id ? 'selected' : ''}`}
              onClick={() => setSelectedFileId(file.id)}
            >
              <div className="tab4-col-filename">
                <span className="tab4-file-icon">🎵</span>
                {file.filename}
              </div>
              <div className="tab4-col-original">
                {formatDuration(file.original_duration)}
              </div>
              <div className="tab4-col-processed">
                {formatDuration(file.processed_duration)}
              </div>
              <div className="tab4-col-saved success">
                {formatDuration(file.time_saved)}
                <span className="tab4-percentage">({formatPercentage(file.compression_ratio)})</span>
              </div>
              <div className="tab4-col-deletions">
                {file.deletion_count || 0}
              </div>
              <div className="tab4-col-status">
                {file.comparison_status === 'reviewed' ? (
                  <span className="tab4-badge reviewed">✓ Reviewed</span>
                ) : file.comparison_status === 'approved' ? (
                  <span className="tab4-badge approved">✓ Approved</span>
                ) : (
                  <span className="tab4-badge pending">Pending</span>
                )}
              </div>
              <div className="tab4-col-actions">
                {file.comparison_status !== 'reviewed' && file.comparison_status !== 'approved' && (
                  <button 
                    className="tab4-btn-review"
                    onClick={(e) => {
                      e.stopPropagation();
                      markAsReviewed(file.id);
                    }}
                  >
                    Mark Reviewed
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Selected File Details */}
      {selectedFileId && (
        <div className="tab4-file-details">
          <h3>File Details</h3>
          <p>Detailed comparison view coming soon...</p>
          <p>Selected File ID: {selectedFileId}</p>
          {/* TODO: Add dual audio player, deletion regions overlay, PDF comparison */}
        </div>
      )}
    </div>
  );
};

export default Tab4Review;
