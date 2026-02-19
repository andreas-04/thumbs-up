# Thumbs-Up Frontend

Web interface for the Thumbs-Up file sharing and management system.

## Features

- **Admin Dashboard**: System overview and management
- **User Management**: Create, edit, and manage user accounts
- **File Browser**: Browse and manage shared files
- **Folder Permissions**: Configure access control for folders
- **System Settings**: Configure system-wide settings

## Tech Stack

- React 18 with TypeScript
- React Router for navigation
- Radix UI components
- TailwindCSS for styling
- Vite for build tooling

## Getting Started

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The development server will start at `http://localhost:5173`

### Build

```bash
npm run build
```

## Project Structure

```
src/
├── app/
│   ├── App.tsx              # Main application component
│   ├── routes.tsx           # Route configuration
│   ├── components/          # Reusable components
│   │   ├── AdminLayout.tsx  # Admin panel layout wrapper
│   │   ├── ProtectedRoute.tsx # Route protection
│   │   └── ui/              # UI component library
│   ├── contexts/            # React contexts
│   │   ├── AuthContext.tsx  # Authentication state
│   │   └── DataContext.tsx  # Global data state
│   └── pages/               # Page components
│       ├── AdminDashboard.tsx
│       ├── AdminLogin.tsx
│       ├── FileBrowser.tsx
│       ├── FolderPermissions.tsx
│       ├── SystemSettings.tsx
│       └── UserManagement.tsx
└── styles/                  # Global styles
```

## Backend Integration

This frontend connects to the Thumbs-Up backend API located in `/backend/apiv2/`.
