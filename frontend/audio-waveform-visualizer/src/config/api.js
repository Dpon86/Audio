/**
 * API Configuration
 * Centralized API URL management for all API calls
 * Auto-detects production vs development environment
 */

// In production (served from domain), use same origin as frontend
// In development (localhost), use explicit backend URL
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';

export const API_BASE_URL = isProduction 
  ? window.location.origin  // Use same domain as frontend in production
  : (process.env.REACT_APP_API_URL || 'http://localhost:8000'); // Use env var or default in dev

/**
 * Normalize media URLs from the backend for browser use.
 * In production, rewrite localhost/127.0.0.1/port-only media URLs back to the current origin.
 * This protects the frontend from malformed absolute or protocol-relative URLs.
 * @param {string} mediaPath
 * @returns {string}
 */
export const resolveMediaUrl = (mediaPath) => {
  if (!mediaPath || typeof mediaPath !== 'string') {
    return mediaPath;
  }

  if (mediaPath.startsWith('blob:') || mediaPath.startsWith('data:')) {
    return mediaPath;
  }

  try {
    const resolvedUrl = new URL(mediaPath, API_BASE_URL);
    const isLocalBackendHost = ['localhost', '127.0.0.1', '0.0.0.0'].includes(resolvedUrl.hostname);

    if (isProduction && isLocalBackendHost) {
      return `${window.location.origin}${resolvedUrl.pathname}${resolvedUrl.search}${resolvedUrl.hash}`;
    }

    return resolvedUrl.toString();
  } catch (error) {
    const normalizedPath = mediaPath.startsWith('/') ? mediaPath : `/${mediaPath}`;
    return `${API_BASE_URL}${normalizedPath}`;
  }
};

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
  
  // Set Content-Type only when NOT sending FormData (browser sets it with multipart boundary)
  const headers = {
    ...(!(options.body instanceof FormData) && { 'Content-Type': 'application/json' }),
    ...options.headers,
  };
  
  // Make the request — auth is handled by the httpOnly cookie automatically
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });
  
  return response;
};

export default {
  getApiUrl,
  getBaseUrl,
  resolveMediaUrl,
  apiFetch,
};
