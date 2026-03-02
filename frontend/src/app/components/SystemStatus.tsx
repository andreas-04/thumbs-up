import React from 'react';
import { Link } from 'react-router';
import { Users, FolderOpen, Activity } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import type { SystemSettingsType, User } from '../contexts/DataContext';

interface SystemStatusProps {
  settings: SystemSettingsType;
  users: User[];
  fileCount: number;
  folderCount: number;
}

export default function SystemStatus({ settings, users, fileCount, folderCount }: SystemStatusProps) {

  const items = [
    {
      title: 'Registered Users',
      value: users.length,
      description: 'Authenticated users',
      icon: Users,
      color: 'text-purple-400',
      link: '/admin/users',
    },
    {
      title: 'Shared Folders',
      value: folderCount,
      description: 'Available directories',
      icon: FolderOpen,
      color: 'text-orange-400',
      link: '/admin/files',
    },
    {
      title: 'Total Files',
      value: fileCount,
      description: 'Files across all folders',
      icon: Activity,
      color: 'text-blue-400',
      link: '/admin/files',
    },
  ];

  return (
    <Card className="bg-gray-900 border-gray-800">
      <CardHeader>
        <CardTitle className="text-white">System Status</CardTitle>
        <CardDescription className="text-gray-400">
          {settings.deviceName} - File sharing system overview
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {items.map((item) => (
            <Link key={item.title} to={item.link}>
              <div className="p-4 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors cursor-pointer">
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className={`h-4 w-4 ${item.color}`} />
                  <span className="text-sm text-gray-400">{item.title}</span>
                </div>
                <p className="text-2xl font-semibold text-white">{item.value}</p>
                <p className="text-xs text-gray-500 mt-1">{item.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
