import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { api, SystemSettings, FileItem as ApiFileItem, FolderPermission as ApiFolderPermission } from '../../services/api';
import { useAuth } from './AuthContext';

export type AuthMethod = 'email' | 'email+password' | 'username+password';

// Re-export API types for backward compatibility
export type FolderPermission = ApiFolderPermission;

export interface User {
  id: number;
  email: string;
  username?: string;
  password?: string;
  createdAt: string;
  folderPermissions: FolderPermission[];
  role?: 'admin' | 'user';
  last_login?: string | null;
  isApproved?: boolean;
}

export type SystemSettingsType = SystemSettings;

export type FileItem = ApiFileItem;

interface DataContextType {
  // System settings
  settings: SystemSettingsType | null;
  updateSettings: (settings: Partial<SystemSettingsType>) => Promise<void>;
  refreshSettings: () => Promise<void>;
  
  // User management
  users: User[];
  addUser: (userData: { email: string; password?: string; role?: 'admin' | 'user' }) => Promise<{ approved?: boolean }>;
  updateUser: (id: number, updates: Partial<{ email: string; password: string; role: 'admin' | 'user'; approved: boolean }>) => Promise<void>;
  deleteUser: (id: number) => Promise<void>;
  refreshUsers: () => Promise<void>;
  
  // User permissions
  updateUserPermissions: (userId: number, permissions: Array<{ path: string; read: boolean; write: boolean }>) => Promise<void>;
  
  // File system
  files: FileItem[];
  currentPath: string;
  setCurrentPath: (path: string) => void;
  refreshFiles: (path?: string) => Promise<void>;
  
  // Loading states
  loading: boolean;
  error: string | null;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export function DataProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, isGuest } = useAuth();
  const [settings, setSettings] = useState<SystemSettingsType | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('/');
  const currentPathRef = useRef(currentPath);
  currentPathRef.current = currentPath;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshSettings = async () => {
    try {
      const settingsData = await api.getSettings();
      setSettings(settingsData);
    } catch (err) {
      console.error('Failed to refresh settings:', err);
      throw err;
    }
  };

  const updateSettings = async (newSettings: Partial<SystemSettingsType>) => {
    try {
      const updated = await api.updateSettings(newSettings);
      setSettings(updated);
    } catch (err) {
      console.error('Failed to update settings:', err);
      throw err;
    }
  };

  const refreshUsers = useCallback(async () => {
    try {
      const { users: usersData } = await api.listUsers();
      // Convert API user format to context format
      const formattedUsers: User[] = usersData.map(u => ({
        id: u.id,
        email: u.email,
        role: u.role,
        createdAt: u.created_at,
        last_login: u.last_login,
        isApproved: u.isApproved,
        folderPermissions: u.folderPermissions || [],
      }));
      setUsers(formattedUsers);
    } catch (err) {
      console.error('Failed to refresh users:', err);
      throw err;
    }
  }, []);

  const addUser = async (userData: { email: string; password?: string; role?: 'admin' | 'user' }): Promise<{ approved?: boolean }> => {
    try {
      const result = await api.createUser(userData);
      // Refresh user list
      await refreshUsers();
      return { approved: (result as any).approved };
    } catch (err) {
      console.error('Failed to add user:', err);
      throw err;
    }
  };

  const updateUser = async (id: number, updates: Partial<{ email: string; password: string; role: 'admin' | 'user'; approved: boolean }>) => {
    try {
      await api.updateUser(id, updates);
      // Refresh user list
      await refreshUsers();
    } catch (err) {
      console.error('Failed to update user:', err);
      throw err;
    }
  };

  const deleteUser = async (id: number) => {
    try {
      await api.deleteUser(id);
      // Update local state
      setUsers(prev => prev.filter(user => user.id !== id));
    } catch (err) {
      console.error('Failed to delete user:', err);
      throw err;
    }
  };

  const updateUserPermissions = async (userId: number, permissions: Array<{ path: string; read: boolean; write: boolean }>) => {
    try {
      await api.updateUserPermissions(userId, permissions);
      // Refresh users to get updated permissions
      await refreshUsers();
    } catch (err) {
      console.error('Failed to update permissions:', err);
      throw err;
    }
  };

  const refreshFiles = useCallback(async (path?: string) => {
    try {
      const targetPath = path || currentPathRef.current;
      // Normalize: ensure leading slash
      const normalizedPath = targetPath === '/' ? '/' : '/' + targetPath.replace(/^\/+/, '');
      // Remove leading slash for API call
      const apiPath = normalizedPath === '/' ? '' : normalizedPath.replace(/^\//, '');
      
      const { files: filesData } = await api.listFiles({ path: apiPath });
      setFiles(filesData);
      if (path !== undefined) {
        setCurrentPath(normalizedPath);
      }
    } catch (err) {
      console.error('Failed to refresh files:', err);
      // In open mode, this might fail without auth - set empty files
      setFiles([]);
    }
  }, []);

  // Re-run whenever authentication state changes so that data is always
  // fresh after login (avoids the "shows 0 until reload" race condition).
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Settings are a public endpoint – always load them.
        try {
          const settingsData = await api.getSettings();
          setSettings(settingsData);
        } catch (err) {
          console.error('Failed to load settings:', err);
        }

        if (isAuthenticated) {
          // Load users (admin only, fails silently for regular users).
          try {
            const { users: usersData } = await api.listUsers();
            const formattedUsers: User[] = usersData.map(u => ({
              id: u.id,
              email: u.email,
              role: u.role,
              createdAt: u.created_at,
              last_login: u.last_login,
              isApproved: u.isApproved,
              folderPermissions: u.folderPermissions || [],
            }));
            setUsers(formattedUsers);
          } catch (err) {
            console.error('Failed to load users:', err);
          }

          // Load files for root directory.
          await refreshFiles('/');
        } else if (isGuest) {
          // Guests can browse unprotected files (no auth token needed).
          setUsers([]);
          await refreshFiles('/');
        } else {
          // Clear protected data when logged out.
          setUsers([]);
          setFiles([]);
        }
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isGuest]);

  return (
    <DataContext.Provider
      value={{
        settings,
        updateSettings,
        refreshSettings,
        users,
        addUser,
        updateUser,
        deleteUser,
        refreshUsers,
        updateUserPermissions,
        files,
        currentPath,
        setCurrentPath,
        refreshFiles,
        loading,
        error,
      }}
    >
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const context = useContext(DataContext);
  if (context === undefined) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
}
