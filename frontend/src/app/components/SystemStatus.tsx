import React from 'react';
import { Link } from 'react-router';
import { Users, FolderOpen, Activity } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
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
      title: 'users',
      value: users.length,
      icon: Users,
      color: 'text-term-purple',
      link: '/admin/users',
    },
    {
      title: 'folders',
      value: folderCount,
      icon: FolderOpen,
      color: 'text-term-yellow',
      link: '/admin/files',
    },
    {
      title: 'files',
      value: fileCount,
      icon: Activity,
      color: 'text-term-blue',
      link: '/admin/files',
    },
  ];

  return (
    <Card className="glass">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-foreground">status</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-3">
          {items.map((item) => (
            <Link key={item.title} to={item.link}>
              <div className="p-3 rounded border border-glass-border hover:bg-glass-highlight transition-colors">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <item.icon className={`h-3.5 w-3.5 ${item.color}`} />
                  <span className="text-xs text-muted-foreground">{item.title}</span>
                </div>
                <p className="text-xl font-medium text-foreground tabular-nums">{item.value}</p>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
