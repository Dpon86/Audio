import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import '../../static/CSS/HeaderNew.css';

const Header = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();
  const userMenuRef = useRef(null);

  const toggleMenu = () => setMenuOpen(!menuOpen);
  const toggleUserMenu = () => setUserMenuOpen(!userMenuOpen);

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <>
      <header className="Hd-header">
        <div className="Hd-left-section">
          <div className="Hd-hamburger-menu" onClick={toggleMenu}>
            <div className="Hd-line"></div>
            <div className="Hd-line"></div>
            <div className="Hd-line"></div>
          </div>
          <div 
            className="Hd-title"
            onClick={() => navigate(isAuthenticated ? '/projects' : '/')}
            style={{ cursor: 'pointer' }}
          >
            Audio Duplicate Detection
          </div>
        </div>
        
        <div className="Hd-header-right">
          {isAuthenticated ? (
            <div className="Hd-user-section" ref={userMenuRef}>
              <div className="Hd-user-info">
                <span className="Hd-welcome-text">
                  Welcome, {user?.first_name || user?.username || 'User'}!
                </span>
                <button 
                  onClick={toggleUserMenu} 
                  className="Hd-user-avatar"
                >
                  {(user?.first_name?.charAt(0) || user?.username?.charAt(0) || 'U').toUpperCase()}
                </button>
              </div>
              
              {userMenuOpen && (
                <div className="Hd-user-dropdown">
                  <div className="Hd-user-details">
                    <p><strong>{user?.username}</strong></p>
                    <p>{user?.email}</p>
                  </div>
                  <div className="Hd-dropdown-divider"></div>
                  <button 
                    onClick={() => {
                      setUserMenuOpen(false);
                      navigate('/profile');
                    }}
                    className="Hd-dropdown-item"
                  >
                    <i className="icon-user"></i>
                    Account Settings
                  </button>
                  <button 
                    onClick={() => {
                      setUserMenuOpen(false);
                      navigate('/projects');
                    }}
                    className="Hd-dropdown-item"
                  >
                    <i className="icon-folder"></i>
                    My Projects
                  </button>
                  <div className="Hd-dropdown-divider"></div>
                  <button 
                    onClick={handleSignOut}
                    className="Hd-dropdown-item Hd-logout-item"
                  >
                    <i className="icon-logout"></i>
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="Hd-auth-buttons">
              <button 
                onClick={() => navigate('/login')} 
                className="Hd-login-button"
              >
                Sign In
              </button>
              <button 
                onClick={() => navigate('/register')} 
                className="Hd-signup-button"
              >
                Sign Up
              </button>
            </div>
          )}
        </div>
      </header>
      <Menu isOpen={menuOpen} toggle={toggleMenu} navigate={navigate} isAuthenticated={isAuthenticated} />
    </>
  );
};

const Menu = ({ isOpen, toggle, navigate, isAuthenticated }) => (
  <div className={`Hd-sidebar-bottom ${isOpen ? 'open' : ''}`}>
    <div className="Hd-sidebar-content">
      {/* Navigation Section */}
      <div className="Hd-nav-section">
        <h3 className="Hd-nav-title">Navigation</h3>
        <ul className="Hd-nav-list">
          <li>
            <a
              href="/"
              onClick={e => {
                e.preventDefault();
                toggle();
                navigate('/');
              }}
              className="Hd-nav-item"
            >
              <i className="icon-home"></i>
              Home
            </a>
          </li>
          {isAuthenticated ? (
            <>
              <li>
                <a
                  href="/projects"
                  onClick={e => {
                    e.preventDefault();
                    toggle();
                    navigate('/projects');
                  }}
                  className="Hd-nav-item"
                >
                  <i className="icon-folder"></i>
                  My Projects
                </a>
              </li>
              <li>
                <a
                  href="/profile"
                  onClick={e => {
                    e.preventDefault();
                    toggle();
                    navigate('/profile');
                  }}
                  className="Hd-nav-item"
                >
                  <i className="icon-user"></i>
                  Account Settings
                </a>
              </li>
            </>
          ) : (
            <>
              <li>
                <a
                  href="/login"
                  onClick={e => {
                    e.preventDefault();
                    toggle();
                    navigate('/login');
                  }}
                  className="Hd-nav-item"
                >
                  <i className="icon-login"></i>
                  Sign In
                </a>
              </li>
              <li>
                <a
                  href="/register"
                  onClick={e => {
                    e.preventDefault();
                    toggle();
                    navigate('/register');
                  }}
                  className="Hd-nav-item"
                >
                  <i className="icon-user-plus"></i>
                  Sign Up
                </a>
              </li>
            </>
          )}
        </ul>
      </div>

      {/* Tools Section */}
      <div className="Hd-nav-section">
        <h3 className="Hd-nav-title">Tools</h3>
        <ul className="Hd-nav-list">
          <li>
            <a
              href="/AudioUpload"
              onClick={e => {
                e.preventDefault();
                toggle();
                navigate('/AudioUpload');
              }}
              className="Hd-nav-item legacy-item"
            >
              <i className="icon-upload"></i>
              Audio Upload (Legacy)
            </a>
          </li>
          <li>
            <a
              href="/PDFAnalysis"
              onClick={e => {
                e.preventDefault();
                toggle();
                navigate('/PDFAnalysis');
              }}
              className="Hd-nav-item legacy-item"
            >
              <i className="icon-file-text"></i>
              PDF Analysis (Legacy)
            </a>
          </li>
          <li>
            <a
              href="/EditPage"
              onClick={e => {
                e.preventDefault();
                toggle();
                navigate('/EditPage');
              }}
              className="Hd-nav-item legacy-item"
            >
              <i className="icon-edit"></i>
              Edit Page (Legacy)
            </a>
          </li>
        </ul>
      </div>

      {/* Help Section */}
      <div className="Hd-nav-section">
        <h3 className="Hd-nav-title">Help</h3>
        <ul className="Hd-nav-list">
          <li>
            <button
              type="button"
              onClick={() => {
                // Add help functionality - could open help modal or navigate to help page
                console.log('Help functionality not implemented yet');
              }}
              className="Hd-nav-item"
            >
              <i className="icon-help"></i>
              Documentation
            </button>
          </li>
          <li>
            <button
              type="button"
              onClick={() => {
                // Add support functionality - could open support modal or navigate to support page
                console.log('Support functionality not implemented yet');
              }}
              className="Hd-nav-item"
            >
              <i className="icon-support"></i>
              Support
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
);

export default Header;