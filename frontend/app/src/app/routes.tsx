import { createBrowserRouter } from 'react-router';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AdminLayout } from './components/AdminLayout';
import AdminLogin from './pages/AdminLogin';
import AdminDashboard from './pages/AdminDashboard';
import SystemSettings from './pages/SystemSettings';
import UserManagement from './pages/UserManagement';
import FolderPermissions from './pages/FolderPermissions';
import FileBrowser from './pages/FileBrowser';
import UserFileBrowser from './pages/UserFileBrowser';
import Signup from './pages/Signup';
import PasswordReset from './pages/PasswordReset';

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
    path: '/files',
    Component: UserFileBrowser,
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
            path: 'files',
            Component: FileBrowser,
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4 text-white">404</h1>
        <p className="text-gray-400 mb-4">Page not found</p>
        <a href="/login" className="text-blue-400 hover:underline">
          Go to Login
        </a>
      </div>
    </div>,
  },
]);