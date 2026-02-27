import React from 'react';
import { useData } from '../contexts/DataContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Link } from 'react-router';
import {
  Shield,
  Users,
  FolderOpen,
  Activity,
  Globe,
} from 'lucide-react';

export default function AdminDashboard() {
  const { settings, users, files } = useData();

  if (!settings) return null;

  const folderCount = files.filter((f) => f.type === 'folder').length;
  const fileCount = files.filter((f) => f.type === 'file').length;

  const stats = [
    {
      title: 'System Mode',
      value: settings.mode === 'open' ? 'Open' : 'Protected',
      description: settings.mode === 'open' ? 'All users can access' : 'Approval required',
      icon: settings.mode === 'open' ? Globe : Shield,
      color: settings.mode === 'open' ? 'text-green-400' : 'text-blue-400',
      bgColor: settings.mode === 'open' ? 'bg-green-950' : 'bg-blue-950',
      link: '/admin/settings',
    },
    {
      title: 'Approved Users',
      value: users.length,
      description: 'Can access in Protected Mode',
      icon: Users,
      color: 'text-purple-400',
      bgColor: 'bg-purple-950',
      link: '/admin/users',
    },
    {
      title: 'Shared Folders',
      value: folderCount,
      description: 'Available directories',
      icon: FolderOpen,
      color: 'text-orange-400',
      bgColor: 'bg-orange-950',
      link: '/admin/files',
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">
          {settings.deviceName} - File Sharing System
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <Link key={stat.title} to={stat.link}>
            <Card className="hover:shadow-lg hover:shadow-blue-900/20 transition-shadow cursor-pointer bg-gray-900 border-gray-800">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400 mb-1">{stat.title}</p>
                    <p className="text-3xl font-semibold text-white">{stat.value}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {stat.description}
                    </p>
                  </div>
                  <div className={`h-12 w-12 rounded-full ${stat.bgColor} flex items-center justify-center`}>
                    <stat.icon className={`h-6 w-6 ${stat.color}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* System Status */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <CardTitle className="text-white">System Status</CardTitle>
          <CardDescription className="text-gray-400">
            File sharing system overview
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <FolderOpen className="h-4 w-4 text-orange-400" />
                <span className="text-sm text-gray-400">Total Folders</span>
              </div>
              <p className="text-2xl font-semibold text-white">{folderCount}</p>
            </div>
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4 text-blue-400" />
                <span className="text-sm text-gray-400">Total Files</span>
              </div>
              <p className="text-2xl font-semibold text-white">{fileCount}</p>
            </div>
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Users className="h-4 w-4 text-purple-400" />
                <span className="text-sm text-gray-400">Registered Users</span>
              </div>
              <p className="text-2xl font-semibold text-white">{users.length}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
