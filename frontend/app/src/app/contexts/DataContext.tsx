import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api, SystemSettings, User as ApiUser, FileItem as ApiFileItem, FolderPermission as ApiFolderPermission } from '../../services/api';

export type SystemMode = 'open' | 'protected';
export type AuthMethod = 'email' | 'email+password' | 'username+password';

// Re-export API types for backward compatibility
export interface FolderPermission extends ApiFolderPermission {}

export interface User {
  id: number;
  email: string;
  username?: string;
  password?: string;
  createdAt: string;
  folderPermissions: FolderPermission[];
  role?: 'admin' | 'user';
  last_login?: string | null;
}

export interface SystemSettingsType extends SystemSettings {}

export interface FileItem extends ApiFileItem {}

interface DataContextType {
  // System settings
  settings: SystemSettingsType | null;
  updateSettings: (settings: Partial<SystemSettingsType>) => Promise<void>;
  refreshSettings: () => Promise<void>;
  
  // User management
  users: User[];
  addUser: (userData: { email: string; password?: string; role?: 'admin' | 'user' }) => Promise<void>;
  updateUser: (id: number, updates: Partial<{ email: string; password: string; role: 'admin' | 'user' }>) => Promise<void>;
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
  const [settings, setSettings] = useState<SystemSettingsType | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [currentPath, setCurrentPath] = useState('/');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Load settings (non-admin can also read settings)
        try {
          const settingsData = await api.getSettings();
          setSettings(settingsData);
        } catch (err) {
          console.error('Failed to load settings:', err);
          // Don't fail completely if settings can't be loaded
        }
        
        // Load users (admin only, will fail silently for non-admins)
        try {
          const { users: usersData } = await api.listUsers();
          const formattedUsers: User[] = usersData.map(u => ({
            id: u.id,
            email: u.email,
            role: u.role,
            createdAt: u.created_at,
            last_login: u.last_login,
            folderPermissions: u.folderPermissions || [],
          }));
          setUsers(formattedUsers);
        } catch (err) {
          console.error('Failed to load users:', err);
          // Non-admins won't have access to users list
        }
        
        // Load files for root directory
        await refreshFiles('/');
        
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, []);

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

  const refreshUsers = async () => {
    try {
      const { users: usersData } = await api.listUsers();
      // Convert API user format to context format
      const formattedUsers: User[] = usersData.map(u => ({
        id: u.id,
        email: u.email,
        role: u.role,
        createdAt: u.created_at,
        last_login: u.last_login,
        folderPermissions: u.folderPermissions || [],
      }));
      setUsers(formattedUsers);
    } catch (err) {
      console.error('Failed to refresh users:', err);
      throw err;
    }
  };

  const addUser = async (userData: { email: string; password?: string; role?: 'admin' | 'user' }) => {
    try {
      await api.createUser(userData);
      // Refresh user list
      await refreshUsers();
    } catch (err) {
      console.error('Failed to add user:', err);
      throw err;
    }
  };

  const updateUser = async (id: number, updates: Partial<{ email: string; password: string; role: 'admin' | 'user' }>) => {
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

  const refreshFiles = async (path?: string) => {
    try {
      const targetPath = path || currentPath;
      // Remove leading slash for API call
      const apiPath = targetPath === '/' ? '' : targetPath.replace(/^\//, '');
      
      const { files: filesData } = await api.listFiles({ path: apiPath });
      setFiles(filesData);
      if (path !== undefined) {
        setCurrentPath(targetPath);
      }
    } catch (err) {
      console.error('Failed to refresh files:', err);
      // In open mode, this might fail without auth - set empty files
      setFiles([]);
    }
  };

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
