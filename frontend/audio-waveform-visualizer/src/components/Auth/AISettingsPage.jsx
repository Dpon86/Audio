import React, { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../../config/api';
import './Profile.css';
import './AISettings.css';

const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', helpUrl: 'https://platform.deepseek.com/api_keys' },
  { value: 'anthropic', label: 'Anthropic Claude', helpUrl: 'https://console.anthropic.com/settings/keys' },
  { value: 'openai', label: 'OpenAI', helpUrl: 'https://platform.openai.com/api-keys' },
];

const providerInfo = (value) => PROVIDERS.find((p) => p.value === value) || PROVIDERS[0];

const AISettingsPage = () => {
  const [keys, setKeys] = useState([]);
  const [provider, setProvider] = useState('deepseek');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadKeys = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/api/auth/ai-keys/'), { credentials: 'include' });
      const data = await response.json();
      if (response.ok) {
        setKeys(data.keys || []);
      }
    } catch (err) {
      // Non-critical - the form still works without the current list.
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const existingKey = keys.find((k) => k.provider === provider);

  const resetMessages = () => {
    setMessage('');
    setError('');
  };

  const handleTest = async () => {
    resetMessages();
    if (!apiKey.trim()) {
      setError('Enter an API key first.');
      return;
    }
    setTesting(true);
    try {
      const response = await fetch(getApiUrl('/api/auth/ai-keys/test/'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setMessage(data.message || 'API key is valid.');
      } else {
        setError(data.error || 'Could not verify this API key.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    resetMessages();
    if (!apiKey.trim()) {
      setError('Enter an API key first.');
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(getApiUrl('/api/auth/ai-keys/'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('API key saved securely. It is encrypted and will never be shown again.');
        setApiKey('');
        loadKeys();
      } else {
        setError(data.error || (data.api_key && data.api_key[0]) || 'Failed to save API key.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (providerToDelete) => {
    resetMessages();
    if (!window.confirm(`Remove the saved ${providerInfo(providerToDelete).label} API key?`)) {
      return;
    }
    try {
      const response = await fetch(
        getApiUrl(`/api/auth/ai-keys/?provider=${encodeURIComponent(providerToDelete)}`),
        { method: 'DELETE', credentials: 'include' }
      );
      const data = await response.json();
      if (response.ok) {
        setMessage(data.message || 'API key removed.');
        loadKeys();
      } else {
        setError(data.error || 'Failed to remove API key.');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    }
  };

  const selected = providerInfo(provider);

  return (
    <div className="profile-container ai-settings-container">
      <div className="profile-header">
        <h1>AI Settings</h1>
        <p>Connect your own AI provider so duplicate detection and PDF comparison run on your account.</p>
      </div>

      {message && <div className="success-message">{message}</div>}
      {error && <div className="error-message">{error}</div>}

      <div className="profile-content">
        <div className="profile-section">
          <h2>Your API Keys</h2>
          {keys.length === 0 ? (
            <p className="ai-settings-empty">
              No AI provider keys configured yet. Processing will use the shared server key until you add your own.
            </p>
          ) : (
            <ul className="ai-key-list">
              {keys.map((k) => (
                <li key={k.provider} className="ai-key-item">
                  <span className="ai-key-provider">{providerInfo(k.provider).label}</span>
                  <span className="ai-key-masked">•••• {k.key_last_four}</span>
                  <span className={`ai-key-status ${k.is_active ? 'active' : 'inactive'}`}>
                    {k.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <button
                    type="button"
                    className="cancel-button ai-key-remove"
                    onClick={() => handleDelete(k.provider)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="profile-section">
          <h2>Add / Update a Key</h2>
          <form onSubmit={handleSave} className="profile-form">
            <div className="form-group">
              <label htmlFor="provider">AI Provider</label>
              <select
                id="provider"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  resetMessages();
                }}
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="api_key">API Key</label>
              <input
                type="password"
                id="api_key"
                name="api_key"
                autoComplete="off"
                placeholder={
                  existingKey
                    ? `Saved (•••• ${existingKey.key_last_four}) - enter a new key to replace it`
                    : 'Paste your API key'
                }
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="ai-settings-hint">
                Get a key from{' '}
                <a href={selected.helpUrl} target="_blank" rel="noopener noreferrer">
                  {selected.label}
                </a>
                . Your key is encrypted before it is stored and is never shown again or shared with anyone.
              </p>
            </div>

            <div className="form-actions">
              <button type="button" className="cancel-button" onClick={handleTest} disabled={testing}>
                {testing ? 'Testing...' : 'Test Key'}
              </button>
              <button type="submit" className="save-button" disabled={loading}>
                {loading ? 'Saving...' : 'Save Key'}
              </button>
            </div>
          </form>
        </div>

        <div className="profile-section ai-settings-security">
          <h2>How we protect your key</h2>
          <ul>
            <li>Your API key is encrypted at rest (AES via Fernet) using a server-side secret key.</li>
            <li>It is never logged, never returned by any API response, and never visible to other users or staff.</li>
            <li>Only the last 4 characters are stored separately so you can recognise which key is saved.</li>
            <li>Requests to the AI provider are made directly from our backend using your encrypted key - it never touches your browser again after saving.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default AISettingsPage;
