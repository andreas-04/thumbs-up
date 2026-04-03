import React from 'react';
import { Outlet, Link, useLocation } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import {
  LayoutDashboard,
  Users,
  Settings,
  LogOut,
  Menu,
  X,
  Globe,
  UsersRound,
  Shield,
  Terminal,
} from 'lucide-react';

export function AdminLayout() {
  const { logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  const navItems = [
    { path: '/admin/dashboard', label: 'dashboard', icon: LayoutDashboard },
    { path: '/admin/settings', label: 'settings', icon: Settings },
    { path: '/admin/users', label: 'users', icon: Users },
    { path: '/admin/permissions', label: 'permissions', icon: Shield },
    { path: '/admin/domains', label: 'domains', icon: Globe },
    { path: '/admin/groups', label: 'groups', icon: UsersRound },
  ];

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="flex h-screen bg-background">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-56 glass border-r border-glass-border
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-glass-border">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-term-green" />
              <span className="text-sm font-medium text-foreground tracking-tight">thumbs-up</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden text-muted-foreground hover:text-foreground h-7 w-7"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-2 space-y-0.5">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                onClick={() => setSidebarOpen(false)}
                className={`
                  flex items-center gap-2.5 px-3 py-2 rounded text-sm
                  transition-colors duration-100
                  ${
                    isActive(path)
                      ? 'bg-glass-highlight text-term-green border border-glass-border'
                      : 'text-muted-foreground hover:text-foreground hover:bg-glass-highlight border border-transparent'
                  }
                `}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          {/* Logout */}
          <div className="p-2 border-t border-glass-border">
            <button
              className="flex items-center gap-2.5 px-3 py-2 rounded text-sm w-full text-term-red/70 hover:text-term-red hover:bg-glass-highlight transition-colors"
              onClick={logout}
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>logout</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden glass border-b border-glass-border px-4 py-3 flex items-center justify-between">
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground h-7 w-7"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">thumbs-up</span>
          <div className="w-7" />
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}