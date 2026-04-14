import React, { createContext, useContext, useState, useEffect } from 'react';
import { getApiUrl } from '../config/api';

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

  const login = (userData, subscriptionData, authToken) => {
    setUser(userData);
    setSubscription(subscriptionData);
    // Keep token in memory as a truthy sentinel; never persist to localStorage
    setToken(authToken || 'cookie-auth');
    setIsAuthenticated(true);
    localStorage.setItem('user', JSON.stringify(userData));
    if (subscriptionData) {
      localStorage.setItem('subscription', JSON.stringify(subscriptionData));
    }
    // Token is NOT stored in localStorage — auth is via httpOnly cookie only
  };

  const logout = async () => {
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
  };

  const updateUser = (userData) => {
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
  };

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