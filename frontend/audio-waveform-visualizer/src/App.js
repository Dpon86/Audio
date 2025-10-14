import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import Layout from "./components/layouts/Layout";
import ProtectedRoute from "./components/Auth/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";

// Authentication pages
import LoginPage from "./components/Auth/LoginPage";
import RegisterPage from "./components/Auth/RegisterPage";
import ProfilePage from "./components/Auth/ProfilePage";

// Main application pages
import FrontPage from "./screens/frontpage";
import ProjectPage from "./screens/ProjectPage";
import ProjectDetailPage from "./screens/ProjectDetailPage";

// Legacy pages (for backward compatibility)
import AudioPage from "./screens/AudioPage";
import EditPage from "./screens/EditPage";
import PDFAnalysisPage from "./screens/PDFAnalysisPage";

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <Layout>
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<FrontPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            
            {/* Protected Routes */}
            <Route 
              path="/projects" 
              element={
                <ProtectedRoute>
                  <ProjectPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/project/:projectId" 
              element={
                <ProtectedRoute>
                  <ProjectDetailPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/profile" 
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              } 
            />
            
            {/* Legacy Routes (for backward compatibility) */}
            <Route path="/AudioUpload" element={<AudioPage />} />
            <Route path="/EditPage" element={<EditPage />} />
            <Route path="/PDFAnalysis" element={<PDFAnalysisPage />} />
            
            {/* Catch all route - redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </Router>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;