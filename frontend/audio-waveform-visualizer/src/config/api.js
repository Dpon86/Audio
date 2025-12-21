/**
 * API Configuration
 * Centralized API URL management for all API calls
 */

// Get API URL from environment variable or default to localhost
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Get the full API URL for a given endpoint
 * @param {string} endpoint - API endpoint path (should start with /)
 * @returns {string} Full API URL
 */
export const getApiUrl = (endpoint) => {
  // If endpoint already has a full URL, return as-is
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  
  // Ensure endpoint starts with /
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  return `${API_BASE_URL}${normalizedEndpoint}`;
};

/**
 * Get the base API URL
 * @returns {string} Base API URL
 */
export const getBaseUrl = () => API_BASE_URL;

/**
 * Common fetch wrapper with authentication
 * @param {string} endpoint - API endpoint
 * @param {object} options - Fetch options
 * @returns {Promise} Fetch promise
 */
export const apiFetch = async (endpoint, options = {}) => {
  const url = getApiUrl(endpoint);
  
  // Get token from localStorage
  const token = localStorage.getItem('token');
  
  // Merge headers
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  // Add authorization header if token exists
  if (token) {
    headers['Authorization'] = `Token ${token}`;
  }
  
  // Make the request
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  return response;
};

export default {
  getApiUrl,
  getBaseUrl,
  apiFetch,
};
