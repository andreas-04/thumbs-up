/**
 * Application configuration from environment variables
 */

export const config = {
  // Use empty string for relative URLs - nginx will proxy /api/* to backend
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;
