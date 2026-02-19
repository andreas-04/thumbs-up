/**
 * API Service Layer for ThumbsUp Frontend
 * Provides typed functions for all backend REST API endpoints
 */

import { config } from '../config';

// =============================================================================
// TypeScript Interfaces
// =============================================================================

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'user';
  requiresPasswordChange: boolean;
  created_at: string;
  last_login: string | null;
  folderPermissions?: FolderPermission[];
}

export interface SystemSettings {
  id: number;
  mode: 'open' | 'protected';
  authMethod: 'email' | 'email+password' | 'username+password';
  tlsEnabled: boolean;
  httpsPort: number;
  deviceName: string;
  updatedAt: string;
}

export interface FolderPermission {
  id: number;
  userId: number;
  path: string;
  read: boolean;
  write: boolean;
  createdAt: string;
}

export interface FileItem {
  id?: string;
  name: string;
  type: 'file' | 'folder';
  path: string;
  size?: number;
  modifiedAt: string;
  parentPath?: string;
}

export interface DashboardStats {
  userCount: number;
  fileCount: number;
  folderCount: number;
  totalSize: number;
  mode: 'open' | 'protected';
  tlsEnabled: boolean;
}

export interface ApiError {
  error: string;
  code: string;
  details?: Record<string, string>;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignupCredentials {
  email: string;
  password: string;
  username?: string;
}

// =============================================================================
// API Client Class
// =============================================================================

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    // Load token from localStorage on init
    this.token = localStorage.getItem('auth_token');
    console.log('[API] ApiClient initialized with baseUrl:', baseUrl);
    console.log('[API] Token loaded from localStorage:', this.token ? `${this.token.substring(0, 20)}...` : 'null');
  }

  /**
   * Set authentication token
   */
  setToken(token: string | null) {
    console.log('[API] Setting token:', token ? `${token.substring(0, 20)}...` : 'null');
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
      console.log('[API] Token saved to localStorage');
    } else {
      localStorage.removeItem('auth_token');
      console.log('[API] Token removed from localStorage');
    }
  }

  /**
   * Get current token
   */
  getToken(): string | null {
    return this.token;
  }

  /**
   * Make HTTP request with error handling
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add Authorization header if token exists
    // Reload token from localStorage in case it was set after initialization
    if (!this.token) {
      this.token = localStorage.getItem('auth_token');
      console.log('[API] Reloaded token from localStorage:', this.token ? `${this.token.substring(0, 20)}...` : 'null');
    }
    
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      console.log('[API] Request to', endpoint, 'with auth token:', `${this.token.substring(0, 20)}...`);
    } else {
      console.log('[API] Request to', endpoint, 'WITHOUT auth token');
    }

    console.log('[API] Full headers being sent:', headers);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle non-JSON responses (like file downloads)
      const contentType = response.headers.get('content-type');
      if (contentType && !contentType.includes('application/json')) {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response as T;
      }

      // Parse JSON response
      const data = await response.json();

      if (!response.ok) {
        const apiError: ApiError = data;
        throw new Error(apiError.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      return data as T;
    } catch (error) {
      // Network or parsing errors
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Network request failed');
    }
  }

  // ===========================================================================
  // Authentication Endpoints
  // ===========================================================================

  async login(credentials: LoginCredentials): Promise<{ token: string; user: User }> {
    const response = await this.request<{ token: string; user: User }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        body: JSON.stringify(credentials),
      }
    );
    
    // Automatically set token
    this.setToken(response.token);
    
    return response;
  }

  async signup(credentials: SignupCredentials): Promise<{ token: string; user: User }> {
    const response = await this.request<{ token: string; user: User }>(
      '/api/v1/auth/signup',
      {
        method: 'POST',
        body: JSON.stringify(credentials),
      }
    );
    
    // Automatically set token
    this.setToken(response.token);
    
    return response;
  }

  async logout(): Promise<{ success: boolean }> {
    const response = await this.request<{ success: boolean }>(
      '/api/v1/auth/logout',
      {
        method: 'POST',
      }
    );
    
    // Clear token
    this.setToken(null);
    
    return response;
  }

  async getCurrentUser(): Promise<{ user: User }> {
    return this.request<{ user: User }>('/api/v1/auth/me');
  }

  async refreshToken(): Promise<{ token: string }> {
    const response = await this.request<{ token: string }>(
      '/api/v1/auth/refresh',
      {
        method: 'POST',
      }
    );
    
    // Update token
    this.setToken(response.token);
    
    return response;
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<{ token: string; user: User }> {
    const response = await this.request<{ token: string; user: User }>(
      '/api/v1/auth/change-password',
      {
        method: 'POST',
        body: JSON.stringify({ currentPassword, newPassword }),
      }
    );
    
    // Update token
    this.setToken(response.token);
    
    return response;
  }

  // ===========================================================================
  // System Settings Endpoints
  // ===========================================================================

  async getSettings(): Promise<SystemSettings> {
    return this.request<SystemSettings>('/api/v1/settings');
  }

  async updateSettings(settings: Partial<SystemSettings>): Promise<SystemSettings> {
    return this.request<SystemSettings>('/api/v1/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  // ===========================================================================
  // User Management Endpoints
  // ===========================================================================

  async listUsers(params?: {
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<{
    users: User[];
    total: number;
    page: number;
    limit: number;
  }> {
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());

    const queryString = queryParams.toString();
    const endpoint = `/api/v1/users${queryString ? `?${queryString}` : ''}`;

    return this.request(endpoint);
  }

  async createUser(userData: {
    email: string;
    password?: string;
    role?: 'admin' | 'user';
  }): Promise<{ user: User }> {
    return this.request<{ user: User }>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async getUser(userId: number): Promise<{ user: User }> {
    return this.request<{ user: User }>(`/api/v1/users/${userId}`);
  }

  async updateUser(
    userId: number,
    userData: Partial<{ email: string; password: string; role: 'admin' | 'user' }>
  ): Promise<{ user: User }> {
    return this.request<{ user: User }>(`/api/v1/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
  }

  async deleteUser(userId: number): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/api/v1/users/${userId}`, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Folder Permissions Endpoints
  // ===========================================================================

  async getUserPermissions(userId: number): Promise<{ permissions: FolderPermission[] }> {
    return this.request<{ permissions: FolderPermission[] }>(
      `/api/v1/users/${userId}/permissions`
    );
  }

  async updateUserPermissions(
    userId: number,
    permissions: Array<{ path: string; read: boolean; write: boolean }>
  ): Promise<{ permissions: FolderPermission[] }> {
    return this.request<{ permissions: FolderPermission[] }>(
      `/api/v1/users/${userId}/permissions`,
      {
        method: 'PUT',
        body: JSON.stringify({ permissions }),
      }
    );
  }

  async listFolders(): Promise<{ folders: Array<{ path: string; name: string }> }> {
    return this.request<{ folders: Array<{ path: string; name: string }> }>(
      '/api/v1/folders'
    );
  }

  // ===========================================================================
  // File Operations Endpoints
  // ===========================================================================

  async listFiles(params?: {
    path?: string;
    search?: string;
  }): Promise<{
    files: FileItem[];
    currentPath: string;
    parentPath: string | null;
  }> {
    const queryParams = new URLSearchParams();
    if (params?.path) queryParams.append('path', params.path);
    if (params?.search) queryParams.append('search', params.search);

    const queryString = queryParams.toString();
    const endpoint = `/api/v1/files${queryString ? `?${queryString}` : ''}`;

    return this.request(endpoint);
  }

  async uploadFile(file: File, path: string = ''): Promise<{ file: FileItem }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', path);

    const url = `${this.baseUrl}/api/v1/files/upload`;
    const headers: HeadersInit = {};
    
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Upload failed');
    }

    return response.json();
  }

  async downloadFile(path: string): Promise<Response> {
    const queryParams = new URLSearchParams({ path });
    const endpoint = `/api/v1/files/download?${queryParams.toString()}`;
    
    return this.request<Response>(endpoint);
  }

  async createDirectory(path: string, name: string): Promise<{ folder: { name: string; path: string } }> {
    return this.request<{ folder: { name: string; path: string } }>(
      '/api/v1/files/mkdir',
      {
        method: 'POST',
        body: JSON.stringify({ path, name }),
      }
    );
  }

  async deleteFile(path: string): Promise<{ success: boolean }> {
    const queryParams = new URLSearchParams({ path });
    const endpoint = `/api/v1/files?${queryParams.toString()}`;
    
    return this.request<{ success: boolean }>(endpoint, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Dashboard Stats Endpoint
  // ===========================================================================

  async getDashboardStats(): Promise<DashboardStats> {
    return this.request<DashboardStats>('/api/v1/stats/dashboard');
  }
}

// =============================================================================
// Export singleton instance
// =============================================================================

export const api = new ApiClient(config.apiBaseUrl);
export default api;
