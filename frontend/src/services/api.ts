/**
 * API Service Layer for TerraCrate Frontend
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
  isApproved: boolean;
  created_at: string;
  last_login: string | null;
  folderPermissions?: FolderPermission[];
  groups?: { id: number; name: string }[];
  certRevoked?: boolean;
  certIssuedAt?: string | null;
  certExpiresAt?: string | null;
}

export interface SystemSettings {
  id: number;
  authMethod: 'email' | 'email+password' | 'username+password';
  tlsEnabled: boolean;
  httpsPort: number;
  deviceName: string;
  updatedAt: string;
  smtpEnabled: boolean;
  smtpHost: string;
  smtpPort: number;
  smtpUsername: string;
  smtpPassword: string;
  smtpFromEmail: string;
  smtpUseTls: boolean;
  allowedDomains: string[];
}

export type PermissionState = 'allow' | 'deny' | null;

export interface FolderPermission {
  id: number;
  userId: number;
  path: string;
  read: PermissionState;
  write: PermissionState;
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

// --- Domain Config ---

export interface DomainPermission {
  id: number;
  domainId: number;
  path: string;
  read: boolean;
  write: boolean;
  createdAt: string;
}

export interface DomainConfig {
  id: number;
  domain: string;
  permissions: DomainPermission[];
  createdAt: string;
  updatedAt: string;
}

// --- Groups ---

export interface GroupPermission {
  id: number;
  groupId: number;
  path: string;
  read: boolean;
  write: boolean;
  createdAt: string;
}

export interface GroupSummary {
  id: number;
  name: string;
  description: string | null;
  memberCount: number;
  permissionCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface GroupDetail extends GroupSummary {
  members: { id: number; email: string }[];
  permissions: GroupPermission[];
}

// --- Effective Permissions ---

export interface EffectivePermissionEntry {
  domain: { canRead: boolean; canWrite: boolean } | null;
  groups: { groupId: number; groupName: string; canRead: boolean; canWrite: boolean }[];
  groupMerged: { canRead: boolean; canWrite: boolean } | null;
  user: { canRead: boolean; canWrite: boolean } | null;
  effective: { canRead: boolean; canWrite: boolean; source: string };
}

export type EffectivePermissions = Record<string, EffectivePermissionEntry>;

// --- Audit Logs ---

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  userId: number | null;
  userEmail: string | null;
  action: string;
  targetType: string | null;
  targetId: string | null;
  description: string | null;
  ipAddress: string | null;
  status: 'success' | 'failure';
  metadata: Record<string, unknown> | null;
}

export interface AuditLogResponse {
  logs: AuditLogEntry[];
  total: number;
  page: number;
  perPage: number;
  pages: number;
}

export interface AuditLogStats {
  total: number;
  today: number;
  failedAuthToday: number;
  activeUsersToday: number;
}

export interface AuditLogFilters {
  page?: number;
  perPage?: number;
  action?: string;
  category?: string;
  userEmail?: string;
  status?: string;
  since?: string;
  search?: string;
}

export interface SystemLogEntry {
  timestamp: string;
  line: string;
}

export interface SystemLogResponse {
  container: string;
  logs: SystemLogEntry[];
  available: boolean;
}

export type AuditTab = 'all' | 'files' | 'security' | 'system';

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
  }

  /**
   * Set authentication token
   */
  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
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
    
    // Normalize headers to a plain object
    let normalizedHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
    if (options.headers) {
      if (options.headers instanceof Headers) {
        options.headers.forEach((value, key) => {
          normalizedHeaders[key] = value;
        });
      } else if (Array.isArray(options.headers)) {
        options.headers.forEach(([key, value]) => {
          normalizedHeaders[key] = value;
        });
      } else {
        normalizedHeaders = { ...normalizedHeaders, ...(options.headers as Record<string, string>) };
      }
    }

    // Add Authorization header if token exists
    // Reload token from localStorage in case it was set after initialization
    if (!this.token) {
      this.token = localStorage.getItem('auth_token');
    }
    
    if (this.token) {
      normalizedHeaders['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers: normalizedHeaders,
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
    userData: Partial<{ email: string; password: string; role: 'admin' | 'user'; approved: boolean }>
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
  // Certificate Revocation & Re-issue Endpoints
  // ===========================================================================

  async revokeCert(userId: number): Promise<{ message: string; revokedSerial: string | null; user: User }> {
    return this.request(`/api/v1/users/${userId}/revoke-cert`, {
      method: 'POST',
    });
  }

  async reissueCert(userId: number): Promise<{ message: string; user: User }> {
    return this.request(`/api/v1/users/${userId}/reissue-cert`, {
      method: 'POST',
    });
  }

  async getCertStatus(userId: number): Promise<{
    serial: string | null;
    issuedAt: string | null;
    expiresAt: string | null;
    isRevoked: boolean;
    revocationHistory: Array<{
      id: number;
      serialNumber: string;
      userId: number | null;
      revokedAt: string;
      reason: string;
      revokedBy: number | null;
    }>;
  }> {
    return this.request(`/api/v1/users/${userId}/cert-status`);
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
    permissions: Array<{ path: string; read: PermissionState; write: PermissionState }>
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
  // Guest File Endpoints (no auth required)
  // ===========================================================================

  async listGuestFiles(params?: {
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
    const endpoint = `/api/v1/guest/files${queryString ? `?${queryString}` : ''}`;

    return this.request(endpoint);
  }

  getGuestDownloadUrl(path: string): string {
    const queryParams = new URLSearchParams({ path });
    return `${this.baseUrl}/api/v1/guest/files/download?${queryParams.toString()}`;
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
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        const error = await response.json();
        throw new Error(error.error || 'Upload failed');
      }
      throw new Error(`Upload failed (HTTP ${response.status})`);
    }

    return response.json();
  }

  async downloadFile(path: string): Promise<Response> {
    const queryParams = new URLSearchParams({ path });
    const endpoint = `/api/v1/files/download?${queryParams.toString()}`;
    
    return this.request<Response>(endpoint);
  }

  async previewFile(path: string): Promise<Response> {
    const url = `${this.baseUrl}/api/v1/files/preview?path=${encodeURIComponent(path)}`;
    const headers: Record<string, string> = {};
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
    const response = await fetch(url, { headers });
    if (!response.ok) throw new Error(`Preview failed (HTTP ${response.status})`);
    return response;
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

  async renameFile(path: string, newName: string): Promise<{ success: boolean; newPath: string; newName: string }> {
    return this.request<{ success: boolean; newPath: string; newName: string }>(
      '/api/v1/files/rename',
      {
        method: 'POST',
        body: JSON.stringify({ path, newName }),
      }
    );
  }

  async moveFile(srcPath: string, destDir: string): Promise<{ success: boolean; newPath: string }> {
    return this.request<{ success: boolean; newPath: string }>(
      '/api/v1/files/move',
      {
        method: 'POST',
        body: JSON.stringify({ srcPath, destDir }),
      }
    );
  }

  // ===========================================================================
  // Domain Config Endpoints
  // ===========================================================================

  async listDomains(): Promise<{ domains: DomainConfig[] }> {
    return this.request<{ domains: DomainConfig[] }>('/api/v1/domains');
  }

  async createDomain(data: {
    domain: string;
    permissions?: Array<{ path: string; read: boolean; write: boolean }>;
  }): Promise<{ domain: DomainConfig }> {
    return this.request<{ domain: DomainConfig }>('/api/v1/domains', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getDomain(domainId: number): Promise<{ domain: DomainConfig }> {
    return this.request<{ domain: DomainConfig }>(`/api/v1/domains/${domainId}`);
  }

  async updateDomain(
    domainId: number,
    data: {
      domain?: string;
      permissions?: Array<{ path: string; read: boolean; write: boolean }>;
    }
  ): Promise<{ domain: DomainConfig }> {
    return this.request<{ domain: DomainConfig }>(`/api/v1/domains/${domainId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteDomain(domainId: number): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/api/v1/domains/${domainId}`, {
      method: 'DELETE',
    });
  }

  // ===========================================================================
  // Group Endpoints
  // ===========================================================================

  async listGroups(): Promise<{ groups: GroupSummary[] }> {
    return this.request<{ groups: GroupSummary[] }>('/api/v1/groups');
  }

  async createGroup(data: { name: string; description?: string }): Promise<{ group: GroupSummary }> {
    return this.request<{ group: GroupSummary }>('/api/v1/groups', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getGroup(groupId: number): Promise<{ group: GroupDetail }> {
    return this.request<{ group: GroupDetail }>(`/api/v1/groups/${groupId}`);
  }

  async updateGroup(
    groupId: number,
    data: { name?: string; description?: string }
  ): Promise<{ group: GroupDetail }> {
    return this.request<{ group: GroupDetail }>(`/api/v1/groups/${groupId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteGroup(groupId: number): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/api/v1/groups/${groupId}`, {
      method: 'DELETE',
    });
  }

  async updateGroupPermissions(
    groupId: number,
    permissions: Array<{ path: string; read: boolean; write: boolean }>
  ): Promise<{ permissions: GroupPermission[] }> {
    return this.request<{ permissions: GroupPermission[] }>(
      `/api/v1/groups/${groupId}/permissions`,
      {
        method: 'PUT',
        body: JSON.stringify({ permissions }),
      }
    );
  }

  async updateGroupMembers(
    groupId: number,
    userIds: number[]
  ): Promise<{ group: GroupDetail }> {
    return this.request<{ group: GroupDetail }>(
      `/api/v1/groups/${groupId}/members`,
      {
        method: 'PUT',
        body: JSON.stringify({ userIds }),
      }
    );
  }

  // ===========================================================================
  // Enhanced User Permission Endpoints
  // ===========================================================================

  async getEffectivePermissions(userId: number): Promise<{ permissions: EffectivePermissions }> {
    return this.request<{ permissions: EffectivePermissions }>(
      `/api/v1/users/${userId}/effective-permissions`
    );
  }

  async updateUserGroups(userId: number, groupIds: number[]): Promise<{ user: User }> {
    return this.request<{ user: User }>(
      `/api/v1/users/${userId}/groups`,
      {
        method: 'PUT',
        body: JSON.stringify({ groupIds }),
      }
    );
  }

  // ===========================================================================
  // Dashboard Stats Endpoint
  // ===========================================================================

  async getDashboardStats(): Promise<DashboardStats> {
    return this.request<DashboardStats>('/api/v1/stats/dashboard');
  }

  // ===========================================================================
  // Audit Log Endpoints
  // ===========================================================================

  async getAuditLogs(filters: AuditLogFilters = {}): Promise<AuditLogResponse> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', String(filters.page));
    if (filters.perPage) params.set('per_page', String(filters.perPage));
    if (filters.action) params.set('action', filters.action);
    if (filters.category) params.set('category', filters.category);
    if (filters.userEmail) params.set('user_email', filters.userEmail);
    if (filters.status) params.set('status', filters.status);
    if (filters.since) params.set('since', filters.since);
    if (filters.search) params.set('search', filters.search);
    const qs = params.toString();
    return this.request<AuditLogResponse>(`/api/v1/audit-logs${qs ? `?${qs}` : ''}`);
  }

  async getAuditLogStats(): Promise<AuditLogStats> {
    return this.request<AuditLogStats>('/api/v1/audit-logs/stats');
  }

  async getSystemLogs(container = 'backend', tail = 200): Promise<SystemLogResponse> {
    return this.request<SystemLogResponse>(
      `/api/v1/system/logs?container=${encodeURIComponent(container)}&tail=${tail}`
    );
  }
}

// =============================================================================
// Export singleton instance
// =============================================================================

export const api = new ApiClient(config.apiBaseUrl);
export default api;
