import React, { useState, useEffect } from 'react';
import { useData } from '../contexts/DataContext';
import SystemStatus from '../components/SystemStatus';
import FileBrowser from './FileBrowser';
import { api } from '../../services/api';
import type { DashboardStats } from '../../services/api';

export default function AdminDashboard() {
  const { settings, users } = useData();
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboardStats().then(setDashboardStats).catch((err) => console.error('Failed to load dashboard stats:', err));
  }, []);

  if (!settings) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">
          {settings.deviceName} - File Sharing System
        </p>
      </div>
        <FileBrowser />
      <div>
        <SystemStatus
          settings={settings}
          users={users}
          fileCount={dashboardStats?.fileCount ?? 0}
          folderCount={dashboardStats?.folderCount ?? 0}
        />
      </div>
    </div>
  );
}
