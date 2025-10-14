import React, { createContext, useContext, useState, useEffect } from 'react';

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
    // Check if user is already logged in
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');
    const subscriptionData = localStorage.getItem('subscription');

    if (token && userData) {
      try {
        const parsedUser = JSON.parse(userData);
        const parsedSubscription = subscriptionData ? JSON.parse(subscriptionData) : null;
        setUser(parsedUser);
        setSubscription(parsedSubscription);
        setToken(token);
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Error parsing stored user data:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('subscription');
      }
    }
    setLoading(false);
  }, []);

  const login = (userData, subscriptionData, authToken) => {
    setUser(userData);
    setSubscription(subscriptionData);
    setToken(authToken);
    setIsAuthenticated(true);
    localStorage.setItem('user', JSON.stringify(userData));
    if (subscriptionData) {
      localStorage.setItem('subscription', JSON.stringify(subscriptionData));
    }
    if (authToken) {
      localStorage.setItem('token', authToken);
    }
  };

  const logout = () => {
    setUser(null);
    setSubscription(null);
    setToken(null);
    setIsAuthenticated(false);
    localStorage.removeItem('token');
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