import React from 'react';
import './ProjectTabs.css';

/**
 * Tab Navigation Component
 * Provides tab switching UI for the 5-tab architecture
 */
const ProjectTabs = ({ activeTab, onTabChange, tabCounts = {} }) => {
  const tabs = [
    { id: 'files', label: 'Upload & Transcribe', icon: '📁', description: 'Upload & transcribe audio files' },
    { id: 'duplicates', label: 'Duplicates', icon: '🔍', description: 'Find & remove repeats' },
    { id: 'results', label: 'Results', icon: '✅', description: 'View processed audio' },
    { id: 'review', label: 'Review', icon: '👁️', description: 'Compare processed vs original' },
    { id: 'compare', label: 'Compare PDF', icon: '📄', description: 'Validate against PDF' }
  ];

  return (
    <div className="project-tabs-container">
      <div className="project-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`project-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
            aria-label={`Switch to ${tab.label} tab`}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
            {tabCounts[tab.id] !== undefined && (
              <span className="tab-badge">{tabCounts[tab.id]}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
};

export default ProjectTabs;
