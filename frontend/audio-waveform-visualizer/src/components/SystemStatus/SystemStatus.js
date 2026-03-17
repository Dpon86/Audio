import React, { useState, useEffect } from 'react';
import { getApiUrl } from '../../config/api';
import './SystemStatus.css';

const SystemStatus = ({ showDetailed = false }) => {
  const [versionInfo, setVersionInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchVersionInfo();
    
    // Refresh every 60 seconds
    const interval = setInterval(fetchVersionInfo, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchVersionInfo = async () => {
    try {
      const response = await fetch(getApiUrl('/api/system-version/'));
      if (response.ok) {
        const data = await response.json();
        setVersionInfo(data);
        setError(null);
      } else {
        throw new Error('Failed to fetch version info');
      }
    } catch (err) {
      console.error('Error fetching version info:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="system-status compact">
        <div className="status-loading">Loading system status...</div>
      </div>
    );
  }

  if (error || !versionInfo) {
    return (
      <div className="system-status compact">
        <div className="status-error">⚠️ System status unavailable</div>
      </div>
    );
  }

  const getStatusIcon = (status) => {
    if (status === 'online' || status === 'deployed' || status === 'all_systems_operational') {
      return '🟢';
    }
    return '🔴';
  };

  const getStatusColor = (status) => {
    if (status === 'online' || status === 'deployed' || status === 'all_systems_operational') {
      return 'status-online';
    }
    return 'status-offline';
  };

  if (!showDetailed) {
    // Compact view for login page
    const allOnline = versionInfo.overall_status === 'all_systems_operational';
    
    return (
      <div className={`system-status compact ${allOnline ? 'all-ok' : 'degraded'}`}>
        <div className="status-header">
          <span className="status-icon">{getStatusIcon(versionInfo.overall_status)}</span>
          <span className="status-text">
            {allOnline ? 'All Systems Operational' : 'Some Services Degraded'}
          </span>
        </div>
        <div className="status-details-compact">
          <span className="status-item">
            Backend: <span className={getStatusColor(versionInfo.backend.status)}>
              {versionInfo.backend.git_commit}
            </span>
          </span>
          <span className="status-item">
            Frontend: <span className={getStatusColor(versionInfo.frontend.status)}>
              {versionInfo.frontend.build_file !== 'unknown' 
                ? versionInfo.frontend.build_file.replace('main.', '').replace('.js', '')
                : 'unknown'}
            </span>
          </span>
          <span className="status-item">
            Celery: <span className={getStatusColor(versionInfo.services.celery)}>
              {versionInfo.services.celery}
            </span>
          </span>
        </div>
      </div>
    );
  }

  // Detailed view
  return (
    <div className="system-status detailed">
      <h3>System Status</h3>
      
      <div className="status-section">
        <h4>Overall Status</h4>
        <div className={`status-badge ${getStatusColor(versionInfo.overall_status)}`}>
          {getStatusIcon(versionInfo.overall_status)} {versionInfo.overall_status.replace(/_/g, ' ')}
        </div>
      </div>

      <div className="status-section">
        <h4>Backend</h4>
        <div className="status-row">
          <span>Status:</span>
          <span className={getStatusColor(versionInfo.backend.status)}>
            {getStatusIcon(versionInfo.backend.status)} {versionInfo.backend.status}
          </span>
        </div>
        <div className="status-row">
          <span>Git Commit:</span>
          <code>{versionInfo.backend.git_commit}</code>
        </div>
        <div className="status-row">
          <span>Branch:</span>
          <code>{versionInfo.backend.git_branch}</code>
        </div>
        <div className="status-row">
          <span>Last Updated:</span>
          <span>{versionInfo.backend.last_updated}</span>
        </div>
      </div>

      <div className="status-section">
        <h4>Frontend</h4>
        <div className="status-row">
          <span>Status:</span>
          <span className={getStatusColor(versionInfo.frontend.status)}>
            {getStatusIcon(versionInfo.frontend.status)} {versionInfo.frontend.status}
          </span>
        </div>
        <div className="status-row">
          <span>Build File:</span>
          <code>{versionInfo.frontend.build_file}</code>
        </div>
      </div>

      <div className="status-section">
        <h4>Services</h4>
        <div className="status-row">
          <span>Celery Workers:</span>
          <span className={getStatusColor(versionInfo.services.celery)}>
            {getStatusIcon(versionInfo.services.celery)} {versionInfo.services.celery}
            {versionInfo.services.celery_workers && ` (${versionInfo.services.celery_workers} workers)`}
          </span>
        </div>
        <div className="status-row">
          <span>Redis:</span>
          <span className={getStatusColor(versionInfo.services.redis)}>
            {getStatusIcon(versionInfo.services.redis)} {versionInfo.services.redis}
          </span>
        </div>
        <div className="status-row">
          <span>Docker:</span>
          <span className={getStatusColor(versionInfo.services.docker)}>
            {getStatusIcon(versionInfo.services.docker)} {versionInfo.services.docker}
          </span>
        </div>
      </div>

      <div className="status-footer">
        <small>Environment: {versionInfo.environment}</small>
      </div>
    </div>
  );
};

export default SystemStatus;
