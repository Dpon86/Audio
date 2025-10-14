import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import '../static/CSS/frontpage.css';

const FrontPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  return (
    <div className="frontpage">
      <div className="hero-section">
        <h1>Audio Duplicate Detection</h1>
        <p className="hero-subtitle">
          Automatically remove repetitive words, sentences, and paragraphs from audiobook recordings
        </p>
        <p className="hero-description">
          Upload your PDF document and audio recording. Our AI will identify and remove any duplicated content,
          keeping only the final (best) version of each repeated segment.
        </p>
        
        <div className="cta-buttons">
          {isAuthenticated ? (
            <>
              <button 
                className="primary-cta-btn"
                onClick={() => navigate("/projects")}
              >
                Start New Project
              </button>
              <button 
                className="secondary-cta-btn"
                onClick={() => navigate("/projects")}
              >
                View My Projects
              </button>
            </>
          ) : (
            <>
              <button 
                className="primary-cta-btn"
                onClick={() => navigate("/register")}
              >
                Get Started Free
              </button>
              <button 
                className="secondary-cta-btn"
                onClick={() => navigate("/login")}
              >
                Sign In
              </button>
            </>
          )}
        </div>
      </div>

      <div className="features-section">
        <h2>How It Works</h2>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">📄</div>
            <h3>1. Upload PDF</h3>
            <p>Upload the book or document that was read aloud</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">🎵</div>
            <h3>2. Upload Audio</h3>
            <p>Upload your audio recording with potential repetitions</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">🤖</div>
            <h3>3. AI Processing</h3>
            <p>Our AI compares the audio against the PDF and identifies duplicates</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">✨</div>
            <h3>4. Clean Audio</h3>
            <p>Download your processed audio with duplicates removed</p>
          </div>
        </div>
      </div>

      <div className="benefits-section">
        <h2>Key Features</h2>
        <div className="benefits-list">
          <div className="benefit-item">
            <span className="benefit-icon">🎯</span>
            <div>
              <h4>PDF-Based Detection</h4>
              <p>Compares audio transcription against original text for accurate duplicate detection</p>
            </div>
          </div>
          
          <div className="benefit-item">
            <span className="benefit-icon">🔄</span>
            <div>
              <h4>Smart Duplicate Handling</h4>
              <p>Always keeps the last (final) occurrence of repeated content</p>
            </div>
          </div>
          
          <div className="benefit-item">
            <span className="benefit-icon">⚡</span>
            <div>
              <h4>Fast Processing</h4>
              <p>Advanced algorithms ensure quick and accurate results</p>
            </div>
          </div>
          
          <div className="benefit-item">
            <span className="benefit-icon">🔒</span>
            <div>
              <h4>Secure & Private</h4>
              <p>Your files are processed securely and never shared</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FrontPage;