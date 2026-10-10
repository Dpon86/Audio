import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getApiUrl, apiFetch, resetSessionExpiredGuard } from '../config/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);

  useEffect(() => {
    // Check if user is already logged in (cookie handles the actual auth token)
    const userData = localStorage.getItem('user');
    const subscriptionData = localStorage.getItem('subscription');

    if (userData) {
      try {
        const parsedUser = JSON.parse(userData);
        const parsedSubscription = subscriptionData ? JSON.parse(subscriptionData) : null;
        setUser(parsedUser);
        setSubscription(parsedSubscription);
        // Use a sentinel value — the real token lives in the httpOnly cookie
        setToken('cookie-auth');
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Error parsing stored user data:', error);
        localStorage.removeItem('user');
        localStorage.removeItem('subscription');
      }
    }
    setLoading(false);
  }, []);

  // Listen for session-expired events from apiFetch (triggered on 401/403 responses)
  useEffect(() => {
    const handleSessionExpired = async (event) => {
      console.warn('[AuthContext] Session expired — auto-logging out (status:', event.detail?.status, ')');

      // Clear local auth state
      setUser(null);
      setSubscription(null);
      setToken(null);
      setIsAuthenticated(false);
      localStorage.removeItem('user');
      localStorage.removeItem('subscription');

      // Reset the guard so future session-expired events can fire again after relogin
      resetSessionExpiredGuard();

      // Best-effort: tell backend to clear the cookie
      try {
        await fetch(getApiUrl('/api/accounts/logout/'), {
          method: 'POST',
          credentials: 'include',
        });
      } catch (err) {
        // Ignore — network may already be unavailable
      }

      // Show a brief toast notification before redirecting.
      // Use react-toastify's imperative API (works outside React component tree).
      try {
        const { toast } = await import('react-toastify');
        toast.warning('Your session has expired. Please log in again.', {
          autoClose: 4000,
          toastId: 'session-expired',
        });
      } catch (importErr) {
        // react-toastify may not be available — fallback to console only
        console.warn('[AuthContext] react-toastify not available for session-expired toast');
      }

      // Redirect to login page
      window.location.href = '/login';
    };

    window.addEventListener('auth:session-expired', handleSessionExpired);
    return () => window.removeEventListener('auth:session-expired', handleSessionExpired);
  }, []);

  const login = useCallback((userData, subscriptionData, authToken) => {
    setUser(userData);
    setSubscription(subscriptionData);
    // Keep token in memory as a truthy sentinel; never persist to localStorage
    setToken(authToken || 'cookie-auth');
    setIsAuthenticated(true);
    localStorage.setItem('user', JSON.stringify(userData));
    if (subscriptionData) {
      localStorage.setItem('subscription', JSON.stringify(subscriptionData));
    }
    // Reset the session-expired guard on successful login
    resetSessionExpiredGuard();
    // Token is NOT stored in localStorage — auth is via httpOnly cookie only
  }, []);

  const logout = useCallback(async () => {
    try {
      // Ask the backend to delete the token and clear the cookie
      await fetch(getApiUrl('/api/accounts/logout/'), {
        method: 'POST',
        credentials: 'include',
      });
    } catch (err) {
      // Best-effort: still clear local state even if request fails
      console.warn('Logout request failed:', err);
    }
    setUser(null);
    setSubscription(null);
    setToken(null);
    setIsAuthenticated(false);
    localStorage.removeItem('user');
    localStorage.removeItem('subscription');
    // Reset the guard on explicit logout so it can fire again if needed
    resetSessionExpiredGuard();
  }, []);

  const updateUser = useCallback((userData) => {
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
  }, []);

  const value = {
    user,
    subscription,
    isAuthenticated,
    loading,
    token,
    login,
    logout,
    updateUser
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
