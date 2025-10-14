import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import './Profile.css';

const ProfilePage = () => {
  const { user, subscription, updateUser } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    email: user?.email || '',
  });
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleProfileChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handlePasswordChange = (e) => {
    setPasswordData({
      ...passwordData,
      [e.target.name]: e.target.value
    });
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/api/auth/profile/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (response.ok) {
        updateUser(data);
        setIsEditing(false);
        setMessage('Profile updated successfully!');
      } else {
        setError(data.detail || 'Failed to update profile');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    if (passwordData.new_password !== passwordData.confirm_password) {
      setError("New passwords don't match");
      setLoading(false);
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/api/auth/change-password/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${token}`
        },
        body: JSON.stringify({
          current_password: passwordData.current_password,
          new_password: passwordData.new_password
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setPasswordData({
          current_password: '',
          new_password: '',
          confirm_password: ''
        });
        setMessage('Password changed successfully!');
      } else {
        setError(data.detail || 'Failed to change password');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return <div className="loading-container">Loading...</div>;
  }

  return (
    <div className="profile-container">
      <div className="profile-header">
        <h1>Account Settings</h1>
        <p>Manage your account information and preferences</p>
      </div>

      {message && <div className="success-message">{message}</div>}
      {error && <div className="error-message">{error}</div>}

      <div className="profile-content">
        {/* Profile Information Section */}
        <div className="profile-section">
          <div className="section-header">
            <h2>Profile Information</h2>
            {!isEditing && (
              <button 
                className="edit-button" 
                onClick={() => setIsEditing(true)}
              >
                Edit
              </button>
            )}
          </div>

          {!isEditing ? (
            <div className="profile-info">
              <div className="info-item">
                <label>Username:</label>
                <span>{user.username}</span>
              </div>
              <div className="info-item">
                <label>Email:</label>
                <span>{user.email}</span>
              </div>
              <div className="info-item">
                <label>First Name:</label>
                <span>{user.first_name || 'Not set'}</span>
              </div>
              <div className="info-item">
                <label>Last Name:</label>
                <span>{user.last_name || 'Not set'}</span>
              </div>
              <div className="info-item">
                <label>Member Since:</label>
                <span>{new Date(user.date_joined).toLocaleDateString()}</span>
              </div>
            </div>
          ) : (
            <form onSubmit={handleProfileSubmit} className="profile-form">
              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleProfileChange}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="first_name">First Name</label>
                <input
                  type="text"
                  id="first_name"
                  name="first_name"
                  value={formData.first_name}
                  onChange={handleProfileChange}
                />
              </div>
              <div className="form-group">
                <label htmlFor="last_name">Last Name</label>
                <input
                  type="text"
                  id="last_name"
                  name="last_name"
                  value={formData.last_name}
                  onChange={handleProfileChange}
                />
              </div>
              <div className="form-actions">
                <button 
                  type="button" 
                  className="cancel-button"
                  onClick={() => {
                    setIsEditing(false);
                    setFormData({
                      first_name: user.first_name || '',
                      last_name: user.last_name || '',
                      email: user.email || '',
                    });
                  }}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="save-button"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Subscription Information */}
        {subscription && (
          <div className="profile-section">
            <h2>Subscription</h2>
            <div className="subscription-info">
              <div className="info-item">
                <label>Plan:</label>
                <span className={`plan-badge ${subscription.plan_type}`}>
                  {subscription.plan_type?.charAt(0).toUpperCase() + subscription.plan_type?.slice(1)}
                </span>
              </div>
              <div className="info-item">
                <label>Status:</label>
                <span className={`status-badge ${subscription.is_active ? 'active' : 'inactive'}`}>
                  {subscription.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              {subscription.expires_at && (
                <div className="info-item">
                  <label>Expires:</label>
                  <span>{new Date(subscription.expires_at).toLocaleDateString()}</span>
                </div>
              )}
              <div className="info-item">
                <label>Projects Limit:</label>
                <span>{subscription.max_projects === -1 ? 'Unlimited' : subscription.max_projects}</span>
              </div>
            </div>
          </div>
        )}

        {/* Change Password Section */}
        <div className="profile-section">
          <h2>Change Password</h2>
          <form onSubmit={handlePasswordSubmit} className="password-form">
            <div className="form-group">
              <label htmlFor="current_password">Current Password</label>
              <input
                type="password"
                id="current_password"
                name="current_password"
                value={passwordData.current_password}
                onChange={handlePasswordChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="new_password">New Password</label>
              <input
                type="password"
                id="new_password"
                name="new_password"
                value={passwordData.new_password}
                onChange={handlePasswordChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="confirm_password">Confirm New Password</label>
              <input
                type="password"
                id="confirm_password"
                name="confirm_password"
                value={passwordData.confirm_password}
                onChange={handlePasswordChange}
                required
              />
            </div>
            <button 
              type="submit" 
              className="change-password-button"
              disabled={loading}
            >
              {loading ? 'Changing Password...' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;