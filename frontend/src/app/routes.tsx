import { createBrowserRouter } from 'react-router';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AdminLayout } from './components/AdminLayout';
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import SystemSettings from './pages/SystemSettings';
import UserManagement from './pages/UserManagement';
import FolderPermissions from './pages/FolderPermissions';
import DomainConfigPage from './pages/DomainConfig';
import GroupManagement from './pages/GroupManagement';
import AuditLog from './pages/AuditLog';
import UserFileBrowser from './pages/UserFileBrowser';
import Signup from './pages/Signup';
import PasswordReset from './pages/PasswordReset';
import CertRequired from './pages/CertRequired';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AdminLogin,
  },
  {
    path: '/login',
    Component: AdminLogin,
  },
  {
    path: '/signup',
    Component: Signup,
  },
  {
    path: '/reset-password',
    Component: PasswordReset,
  },
  {
    path: '/cert-required',
    Component: CertRequired,
  },
  {
    path: '/files',
    Component: ProtectedRoute,
    children: [
      {
        path: '',
        Component: UserFileBrowser,
      },
    ],
  },
  {
    path: '/admin',
    Component: ProtectedRoute,
    children: [
      {
        path: '',
        Component: AdminLayout,
        children: [
          {
            path: 'dashboard',
            Component: AdminDashboard,
          },
          {
            path: 'settings',
            Component: SystemSettings,
          },
          {
            path: 'users',
            Component: UserManagement,
          },
          {
            path: 'permissions',
            Component: FolderPermissions,
          },
          {
            path: 'domains',
            Component: DomainConfigPage,
          },
          {
            path: 'groups',
            Component: GroupManagement,
          },
          {
            path: 'audit-log',
            Component: AuditLog,
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-2xl font-medium mb-2 text-foreground">404</h1>
        <p className="text-muted-foreground text-sm mb-4">not found</p>
        <a href="/login" className="text-term-blue hover:text-term-cyan transition-colors text-sm">
          back to login
        </a>
      </div>
    </div>,
  },
]);