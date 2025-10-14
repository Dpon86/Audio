import React, { useState, useEffect } from 'react';
import './DebugPanel.css';

const DebugPanel = ({ isVisible, onToggle }) => {
  const [logs, setLogs] = useState([]);
  const [systemStatus, setSystemStatus] = useState({
    backend: 'unknown',
    infrastructure: 'unknown',
    lastCheck: null
  });

  // Add a new log entry
  const addLog = (type, message, data = null) => {
    const timestamp = new Date().toLocaleTimeString();
    const newLog = {
      id: Date.now(),
      timestamp,
      type, // 'info', 'error', 'api-call', 'api-response', 'system'
      message,
      data
    };
    setLogs(prev => [newLog, ...prev].slice(0, 50)); // Keep only last 50 logs
  };

  // Check system status
  const checkSystemStatus = async () => {
    const timestamp = new Date().toLocaleTimeString();
    
    // Check backend connectivity
    try {
      const token = localStorage.getItem('token');
      const backendResponse = await fetch('http://localhost:8000/api/projects/', {
        method: 'GET',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (backendResponse.ok) {
        setSystemStatus(prev => ({ ...prev, backend: 'online', lastCheck: timestamp }));
        addLog('system', 'Backend: Online', { status: backendResponse.status });
      } else {
        setSystemStatus(prev => ({ ...prev, backend: 'error', lastCheck: timestamp }));
        addLog('error', `Backend: Error ${backendResponse.status}`, { status: backendResponse.status });
      }
    } catch (error) {
      setSystemStatus(prev => ({ ...prev, backend: 'offline', lastCheck: timestamp }));
      addLog('error', 'Backend: Offline', { error: error.message });
    }

    // Check infrastructure status
    try {
      const token = localStorage.getItem('token');
      const infraResponse = await fetch('http://localhost:8000/api/infrastructure/status/', {
        method: 'GET',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (infraResponse.ok) {
        const infraData = await infraResponse.json();
        setSystemStatus(prev => ({ 
          ...prev, 
          infrastructure: infraData.infrastructure_running ? 'running' : 'stopped',
          lastCheck: timestamp 
        }));
        addLog('system', 'Infrastructure Status', infraData);
      } else {
        setSystemStatus(prev => ({ ...prev, infrastructure: 'error', lastCheck: timestamp }));
        addLog('error', `Infrastructure: Error ${infraResponse.status}`);
      }
    } catch (error) {
      setSystemStatus(prev => ({ ...prev, infrastructure: 'offline', lastCheck: timestamp }));
      addLog('error', 'Infrastructure: Offline', { error: error.message });
    }
  };

  // Expose the addLog function globally for other components to use
  useEffect(() => {
    window.debugLog = addLog;
    return () => {
      delete window.debugLog;
    };
  }, []);

  // Check system status on mount and periodically
  useEffect(() => {
    checkSystemStatus();
    const interval = setInterval(checkSystemStatus, 10000); // Check every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const clearLogs = () => {
    setLogs([]);
    addLog('info', 'Debug logs cleared');
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online':
      case 'running':
        return '#4CAF50';
      case 'offline':
      case 'stopped':
        return '#f44336';
      case 'error':
        return '#FF9800';
      default:
        return '#9E9E9E';
    }
  };

  const getLogTypeIcon = (type) => {
    switch (type) {
      case 'error':
        return '❌';
      case 'api-call':
        return '📤';
      case 'api-response':
        return '📥';
      case 'system':
        return '⚙️';
      default:
        return 'ℹ️';
    }
  };

  if (!isVisible) {
    return (
      <div className="debug-toggle">
        <button onClick={onToggle} className="debug-toggle-btn">
          🐛 Debug
        </button>
      </div>
    );
  }

  return (
    <div className="debug-panel">
      <div className="debug-header">
        <h3>🐛 Debug Panel</h3>
        <div className="debug-actions">
          <button onClick={clearLogs} className="debug-btn">Clear</button>
          <button onClick={checkSystemStatus} className="debug-btn">Refresh</button>
          <button onClick={onToggle} className="debug-btn close">✕</button>
        </div>
      </div>

      {/* System Status */}
      <div className="system-status">
        <h4>System Status</h4>
        <div className="status-grid">
          <div className="status-item">
            <span className="status-label">Backend:</span>
            <span 
              className="status-indicator" 
              style={{ color: getStatusColor(systemStatus.backend) }}
            >
              ● {systemStatus.backend}
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Infrastructure:</span>
            <span 
              className="status-indicator" 
              style={{ color: getStatusColor(systemStatus.infrastructure) }}
            >
              ● {systemStatus.infrastructure}
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Last Check:</span>
            <span className="status-value">{systemStatus.lastCheck || 'Never'}</span>
          </div>
        </div>
      </div>

      {/* Logs */}
      <div className="debug-logs">
        <h4>Activity Logs</h4>
        <div className="logs-container">
          {logs.length === 0 ? (
            <div className="no-logs">No activity yet...</div>
          ) : (
            logs.map(log => (
              <div key={log.id} className={`log-entry log-${log.type}`}>
                <span className="log-time">{log.timestamp}</span>
                <span className="log-icon">{getLogTypeIcon(log.type)}</span>
                <span className="log-message">{log.message}</span>
                {log.data && (
                  <details className="log-data">
                    <summary>Data</summary>
                    <pre>{JSON.stringify(log.data, null, 2)}</pre>
                  </details>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default DebugPanel;