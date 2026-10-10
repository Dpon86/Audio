import React from 'react';
import './Profile.css';
import './AISettings.css';
import AIApiKeySection from './AIApiKeySection';

const AISettingsPage = () => (
  <div className="profile-container ai-settings-container">
    <div className="profile-header">
      <h1>AI Settings</h1>
      <p>Connect your own AI provider so duplicate detection and PDF comparison run on your account.</p>
    </div>

    <div className="profile-content">
      <AIApiKeySection />
    </div>
  </div>
);

export default AISettingsPage;

