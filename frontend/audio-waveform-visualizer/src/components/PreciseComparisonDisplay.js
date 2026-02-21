import React, { useState } from 'react';
import './PreciseComparisonDisplay.css';

/**
 * PreciseComparisonDisplay
 * 
 * Displays results from the precise word-by-word PDF comparison algorithm
 * Shows:
 * - Matched regions (with timestamps)
 * - Abnormal regions (mismatches with timestamps)
 * - Missing content (in PDF but not in audio)
 * - Extra content (in audio but not in PDF)
 * - Statistics and quality ratings
 * 
 * Features:
 * - Click timestamps to play audio at that point
 * - Filter by region type
 * - Color-coded regions
 * - Expandable details
 * 
 * Props:
 * - results: Comparison results object from backend
 * - onPlayAudio: Callback when user clicks a timestamp (time in seconds)
 */
const PreciseComparisonDisplay = ({ results, onPlayAudio }) => {
  const [filter, setFilter] = useState('all'); // 'all', 'matched', 'abnormal', 'missing', 'extra'
  const [expandedRegions, setExpandedRegions] = useState(new Set());
  
  if (!results) {
    return null;
  }
  
  const {
    matched_regions = [],
    abnormal_regions = [],
    missing_content = [],
    extra_content = [],
    statistics = {}
  } = results;
  
  /**
   * Toggle expansion of a region
   */
  const toggleRegion = (regionId) => {
    const newExpanded = new Set(expandedRegions);
    if (newExpanded.has(regionId)) {
      newExpanded.delete(regionId);
    } else {
      newExpanded.add(regionId);
    }
    setExpandedRegions(newExpanded);
  };
  
  /**
   * Format time in seconds to MM:SS or HH:MM:SS
   */
  const formatTime = (seconds) => {
    if (!seconds && seconds !== 0) return 'N/A';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };
  
  /**
   * Get quality color based on rating
   */
  const getQualityColor = (quality) => {
    const colors = {
      'excellent': '#10b981',
      'good': '#3b82f6',
      'fair': '#f59e0b',
      'poor': '#ef4444'
    };
    return colors[quality] || '#6b7280';
  };
  
  /**
   * Render matched regions
   */
  const renderMatchedRegions = () => {
    if (filter !== 'all' && filter !== 'matched') return null;
    
    return (
      <div className="region-section matched-section">
        <h3 className="section-header">
          <span className="section-icon">✓</span>
          Matched Regions ({matched_regions.length})
        </h3>
        <p className="section-description">
          Text that matches between PDF and audio transcription
        </p>
        
        <div className="regions-list">
          {matched_regions.map((region, index) => (
            <div 
              key={`match-${index}`} 
              className="region-card matched-card"
            >
              <div className="region-header" onClick={() => toggleRegion(`match-${index}`)}>
                <div className="region-title">
                  Region {index + 1}
                  <span className="word-count">{region.word_count} words</span>
                </div>
                <div className="region-time">
                  <button 
                    className="time-badge"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onPlayAudio) onPlayAudio(region.start_time);
                    }}
                    title="Click to play audio"
                  >
                    ▶ {formatTime(region.start_time)}
                  </button>
                  <span className="time-separator">→</span>
                  <button 
                    className="time-badge"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onPlayAudio) onPlayAudio(region.end_time);
                    }}
                    title="Click to play audio"
                  >
                    {formatTime(region.end_time)}
                  </button>
                </div>
                <div className="expand-icon">
                  {expandedRegions.has(`match-${index}`) ? '▼' : '▶'}
                </div>
              </div>
              
              {expandedRegions.has(`match-${index}`) && (
                <div className="region-content">
                  <div className="content-text">
                    {region.text || '(No text preview available)'}
                  </div>
                  {region.segments && region.segments.length > 0 && (
                    <div className="segments-info">
                      Segments: {region.segments.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  /**
   * Render abnormal regions (mismatches)
   */
  const renderAbnormalRegions = () => {
    if (filter !== 'all' && filter !== 'abnormal') return null;
    
    return (
      <div className="region-section abnormal-section">
        <h3 className="section-header">
          <span className="section-icon">⚠</span>
          Abnormal Regions ({abnormal_regions.length})
        </h3>
        <p className="section-description">
          Sections where PDF and transcription diverged, then re-matched
        </p>
        
        <div className="regions-list">
          {abnormal_regions.map((region, index) => (
            <div 
              key={`abnormal-${index}`} 
              className="region-card abnormal-card"
            >
              <div className="region-header" onClick={() => toggleRegion(`abnormal-${index}`)}>
                <div className="region-title">
                  Abnormal Region {index + 1}
                  <span className="reason-badge">{region.reason || 'Mismatch'}</span>
                </div>
                <div className="region-time">
                  <button 
                    className="time-badge"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onPlayAudio) onPlayAudio(region.start_time);
                    }}
                    title="Click to play audio"
                  >
                    ▶ {formatTime(region.start_time)}
                  </button>
                  <span className="time-separator">→</span>
                  <button 
                    className="time-badge"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onPlayAudio) onPlayAudio(region.end_time);
                    }}
                    title="Click to play audio"
                  >
                    {formatTime(region.end_time)}
                  </button>
                </div>
                <div className="expand-icon">
                  {expandedRegions.has(`abnormal-${index}`) ? '▼' : '▶'}
                </div>
              </div>
              
              {expandedRegions.has(`abnormal-${index}`) && (
                <div className="region-content">
                  <div className="content-text">
                    {region.text || '(No text preview available)'}
                  </div>
                  {region.segments && region.segments.length > 0 && (
                    <div className="segments-info">
                      Segments: {region.segments.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  /**
   * Render missing content (in PDF but not in audio)
   */
  const renderMissingContent = () => {
    if (filter !== 'all' && filter !== 'missing') return null;
    if (!missing_content || missing_content.length === 0) return null;
    
    return (
      <div className="region-section missing-section">
        <h3 className="section-header">
          <span className="section-icon">📄</span>
          Missing Content ({missing_content.length})
        </h3>
        <p className="section-description">
          Text found in PDF but not in audio transcription
        </p>
        
        <div className="regions-list">
          {missing_content.map((item, index) => (
            <div 
              key={`missing-${index}`} 
              className="region-card missing-card"
            >
              <div className="region-header" onClick={() => toggleRegion(`missing-${index}`)}>
                <div className="region-title">
                  Missing Item {index + 1}
                </div>
                <div className="expand-icon">
                  {expandedRegions.has(`missing-${index}`) ? '▼' : '▶'}
                </div>
              </div>
              
              {expandedRegions.has(`missing-${index}`) && (
                <div className="region-content">
                  <div className="content-text">
                    {item.text || item}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  /**
   * Render extra content (in audio but not in PDF)
   */
  const renderExtraContent = () => {
    if (filter !== 'all' && filter !== 'extra') return null;
    if (!extra_content || extra_content.length === 0) return null;
    
    return (
      <div className="region-section extra-section">
        <h3 className="section-header">
          <span className="section-icon">🎤</span>
          Extra Content ({extra_content.length})
        </h3>
        <p className="section-description">
          Text found in audio transcription but not in PDF
        </p>
        
        <div className="regions-list">
          {extra_content.map((item, index) => (
            <div 
              key={`extra-${index}`} 
              className="region-card extra-card"
            >
              <div className="region-header" onClick={() => toggleRegion(`extra-${index}`)}>
                <div className="region-title">
                  Extra Item {index + 1}
                  {item.start_time !== undefined && (
                    <button 
                      className="time-badge small"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onPlayAudio) onPlayAudio(item.start_time);
                      }}
                      title="Click to play audio"
                    >
                      ▶ {formatTime(item.start_time)}
                    </button>
                  )}
                </div>
                <div className="expand-icon">
                  {expandedRegions.has(`extra-${index}`) ? '▼' : '▶'}
                </div>
              </div>
              
              {expandedRegions.has(`extra-${index}`) && (
                <div className="region-content">
                  <div className="content-text">
                    {item.text || item}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  return (
    <div className="precise-comparison-display">
      {/* Statistics Summary */}
      <div className="statistics-panel">
        <h2 className="panel-title">Comparison Results</h2>
        
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{statistics.match_percentage?.toFixed(1) || 0}%</div>
            <div className="stat-label">Match Accuracy</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value" style={{ color: getQualityColor(statistics.quality) }}>
              {statistics.quality || 'N/A'}
            </div>
            <div className="stat-label">Quality Rating</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{matched_regions.length}</div>
            <div className="stat-label">Matched Regions</div>
          </div>
          
          <div className="stat-card">
            <div className="stat-value">{abnormal_regions.length}</div>
            <div className="stat-label">Abnormal Regions</div>
          </div>
        </div>
      </div>
      
      {/* Filter Controls */}
      <div className="filter-controls">
        <label className="filter-label">Show:</label>
        <div className="filter-buttons">
          <button 
            className={filter === 'all' ? 'filter-btn active' : 'filter-btn'}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button 
            className={filter === 'matched' ? 'filter-btn active matched' : 'filter-btn matched'}
            onClick={() => setFilter('matched')}
          >
            Matched ({matched_regions.length})
          </button>
          <button 
            className={filter === 'abnormal' ? 'filter-btn active abnormal' : 'filter-btn abnormal'}
            onClick={() => setFilter('abnormal')}
          >
            Abnormal ({abnormal_regions.length})
          </button>
          {missing_content.length > 0 && (
            <button 
              className={filter === 'missing' ? 'filter-btn active missing' : 'filter-btn missing'}
              onClick={() => setFilter('missing')}
            >
              Missing ({missing_content.length})
            </button>
          )}
          {extra_content.length > 0 && (
            <button 
              className={filter === 'extra' ? 'filter-btn active extra' : 'filter-btn extra'}
              onClick={() => setFilter('extra')}
            >
              Extra ({extra_content.length})
            </button>
          )}
        </div>
      </div>
      
      {/* Regions Display */}
      <div className="regions-container">
        {renderMatchedRegions()}
        {renderAbnormalRegions()}
        {renderMissingContent()}
        {renderExtraContent()}
      </div>
    </div>
  );
};

export default PreciseComparisonDisplay;
