import React from 'react';
import { useData } from '../contexts/DataContext';
import SystemStatus from '../components/SystemStatus';

export default function AdminDashboard() {
  const { settings, users, files } = useData();

  if (!settings) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">
          {settings.deviceName} - File Sharing System
        </p>
      </div>

      <SystemStatus settings={settings} users={users} files={files} />
    </div>
  );
}
