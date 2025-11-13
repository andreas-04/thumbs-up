import React, { useState } from 'react';
import './index.css';

// Sidebar Component
function Sidebar({ activePage, setActivePage, darkMode, setDarkMode }) {
  const pages = ['Dashboard', 'Diagnostics', 'Synchronization', 'Users', 'Files', 'Logs', 'Settings'];
  
  return (
    <div className="sidebar">
      <h2>MyNAS</h2>
      <ul>
        {pages.map(page => (
          <li key={page}>
            <a
              href="#!"
              className={activePage === page ? 'active' : ''}
              onClick={() => setActivePage(page)}
            >
              {page}
            </a>
          </li>
        ))}
      </ul>
      <div className="dark-mode-toggle">
        <button onClick={() => setDarkMode(!darkMode)} className="toggle-btn">
          {darkMode ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </button>
      </div>
    </div>
  );
}

// Dashboard Page
function Dashboard() {
  const piServers = [
    { 
      id: 1,
      name: "NAS Server 1", 
      status: "active", // active, warning, error
      totalStorage: 500, // GB
      usedStorage: 320, // GB
      clients: 2,
      ipAddress: "192.168.1.101",
      uptime: "15 days",
      lastSync: "2 hours ago",
      encryption: "LUKS Encrypted"
    },
    { 
      id: 2,
      name: "NAS Server 2", 
      status: "warning",
      totalStorage: 1000,
      usedStorage: 850,
      clients: 3,
      ipAddress: "192.168.1.102",
      uptime: "45 days",
      lastSync: "30 minutes ago",
      encryption: "LUKS Encrypted"
    },
    { 
      id: 3,
      name: "NAS Server 3", 
      status: "active",
      totalStorage: 250,
      usedStorage: 75,
      clients: 1,
      ipAddress: "192.168.1.103",
      uptime: "8 days",
      lastSync: "1 hour ago",
      encryption: "LUKS Encrypted"
    },
    { 
      id: 4,
      name: "NAS Server 4", 
      status: "error",
      totalStorage: 500,
      usedStorage: 0,
      clients: 0,
      ipAddress: "192.168.1.104",
      uptime: "Offline",
      lastSync: "Never",
      encryption: "Not Available"
    }
  ];

  const getStatusColor = (status) => {
    switch(status) {
      case 'active': return '#16a34a'; // green
      case 'warning': return '#eab308'; // yellow
      case 'error': return '#dc2626'; // red
      default: return '#9ca3af'; // gray
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'active': return 'Active';
      case 'warning': return 'Warning';
      case 'error': return 'Offline';
      default: return 'Unknown';
    }
  };

  const calculatePercentage = (used, total) => {
    return Math.round((used / total) * 100);
  };

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="card full-height">
        <h3>NAS Servers</h3>
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Pi Name</th>
              <th>IP Address</th>
              <th>Uptime</th>
              <th>Storage Usage</th>
              <th>Clients</th>
            </tr>
          </thead>
          <tbody>
            {piServers.map(pi => {
              const percentage = calculatePercentage(pi.usedStorage, pi.totalStorage);
              return (
                <tr key={pi.id}>
                  <td>
                    <div 
                      className="status-circle" 
                      style={{ backgroundColor: getStatusColor(pi.status) }}
                      title={getStatusText(pi.status)}
                    ></div>
                  </td>
                  <td><strong>{pi.name}</strong></td>
                  <td>{pi.ipAddress}</td>
                  <td>{pi.uptime}</td>
                  <td>
                    <div className="storage-info">
                      <div className="progress-container">
                        <div 
                          className="progress-bar" 
                          style={{ width: `${percentage}%` }}
                        >
                        </div>
                      </div>
                      <span className="storage-text">{pi.usedStorage}GB / {pi.totalStorage}GB</span>
                    </div>
                  </td>
                  <td>
                    <span className="client-count">{pi.clients} client{pi.clients !== 1 ? 's' : ''}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Diagnostics Page
function Diagnostics() {
  const networkStats = [
    { server: "NAS Server 1", bandwidth: "45.2 MB/s", latency: "2ms", packets: "15,234", errors: 0 },
    { server: "NAS Server 2", bandwidth: "78.5 MB/s", latency: "3ms", packets: "28,456", errors: 2 },
    { server: "NAS Server 3", bandwidth: "23.1 MB/s", latency: "1ms", packets: "9,871", errors: 0 },
    { server: "NAS Server 4", bandwidth: "0 MB/s", latency: "N/A", packets: "0", errors: 0 }
  ];

  return (
    <div className="diagnostics-container">
      <h1>Diagnostics</h1>
      
      <div className="card full-height">
        <div className="diagnostics-sections">
          {/* Network Statistics Section */}
          <div className="diagnostic-section">
            <h3>Network Statistics</h3>
            <table>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>Bandwidth</th>
                  <th>Latency</th>
                  <th>Packets</th>
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {networkStats.map((stat, idx) => (
                  <tr key={idx}>
                    <td><strong>{stat.server}</strong></td>
                    <td>{stat.bandwidth}</td>
                    <td>{stat.latency}</td>
                    <td>{stat.packets}</td>
                    <td>
                      <span style={{ color: stat.errors > 0 ? '#dc2626' : '#16a34a', fontWeight: 'bold' }}>
                        {stat.errors}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// Logs Page
function Logs() {
  const fileActivity = [
    { timestamp: "2025-11-13 14:32:15", user: "alice@nas1", action: "Write", file: "/data/documents/report.pdf", size: "2.4 MB", status: "success" },
    { timestamp: "2025-11-13 14:31:48", user: "bob@nas2", action: "Read", file: "/data/photos/vacation.jpg", size: "5.1 MB", status: "success" },
    { timestamp: "2025-11-13 14:30:22", user: "charlie@nas2", action: "Write", file: "/data/videos/demo.mp4", size: "125.3 MB", status: "success" },
    { timestamp: "2025-11-13 14:29:55", user: "alice@nas1", action: "Delete", file: "/data/temp/cache.tmp", size: "512 KB", status: "success" },
    { timestamp: "2025-11-13 14:28:31", user: "david@nas4", action: "Read", file: "/data/files/data.csv", size: "1.2 MB", status: "error" },
    { timestamp: "2025-11-13 14:27:12", user: "bob@nas2", action: "Write", file: "/data/backup/archive.zip", size: "450 MB", status: "success" },
    { timestamp: "2025-11-13 14:26:45", user: "alice@nas1", action: "Read", file: "/data/config/settings.json", size: "15 KB", status: "success" },
    { timestamp: "2025-11-13 14:25:33", user: "charlie@nas2", action: "Write", file: "/data/logs/server.log", size: "3.2 MB", status: "success" },
    { timestamp: "2025-11-13 14:24:18", user: "bob@nas2", action: "Delete", file: "/data/old/backup.tar.gz", size: "2.1 GB", status: "success" },
    { timestamp: "2025-11-13 14:23:02", user: "david@nas4", action: "Write", file: "/data/uploads/image.png", size: "842 KB", status: "error" }
  ];

  const getActionColor = (action) => {
    switch(action) {
      case 'Write': return '#2563eb'; // blue
      case 'Read': return '#16a34a'; // green
      case 'Delete': return '#dc2626'; // red
      default: return '#6b7280'; // gray
    }
  };

  const getStatusBadge = (status) => {
    return status === 'success' ? 
      <span className="status success">✓</span> : 
      <span className="status warning">✗</span>;
  };

  return (
    <div className="diagnostics-container">
      <h1>Logs</h1>
      
      <div className="card full-height">
        <div className="diagnostics-sections">
          {/* File Activity Section */}
          <div className="diagnostic-section">
            <h3>Recent File Activity</h3>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>File</th>
                  <th>Size</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {fileActivity.map((activity, idx) => (
                  <tr key={idx}>
                    <td><span className="timestamp">{activity.timestamp}</span></td>
                    <td>{activity.user}</td>
                    <td>
                      <span className="action-badge" style={{ backgroundColor: getActionColor(activity.action) }}>
                        {activity.action}
                      </span>
                    </td>
                    <td className="file-path">{activity.file}</td>
                    <td>{activity.size}</td>
                    <td>{getStatusBadge(activity.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

// Files Page
function Files() {
  const [currentPath, setCurrentPath] = useState('/');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');

  // Simple file tree structure for NAS Server 1
  const fileTree = {
    '/': [
      { name: 'documents', type: 'folder', size: '-', modified: '2025-11-10' },
      { name: 'photos', type: 'folder', size: '-', modified: '2025-11-12' },
      { name: 'videos', type: 'folder', size: '-', modified: '2025-11-08' },
      { name: 'README.md', type: 'file', size: '4.2 KB', modified: '2025-11-13' }
    ],
    '/documents': [
      { name: '..', type: 'folder', size: '-', modified: '-' },
      { name: 'reports', type: 'folder', size: '-', modified: '2025-11-09' },
      { name: 'quarterly_report.pdf', type: 'file', size: '2.4 MB', modified: '2025-11-13' },
      { name: 'budget_2025.xlsx', type: 'file', size: '1.8 MB', modified: '2025-11-12' },
      { name: 'notes.txt', type: 'file', size: '3.1 KB', modified: '2025-11-10' }
    ],
    '/documents/reports': [
      { name: '..', type: 'folder', size: '-', modified: '-' },
      { name: 'Q1_2025.pdf', type: 'file', size: '3.2 MB', modified: '2025-03-31' },
      { name: 'Q2_2025.pdf', type: 'file', size: '2.9 MB', modified: '2025-06-30' },
      { name: 'Q3_2025.pdf', type: 'file', size: '3.5 MB', modified: '2025-09-30' }
    ],
    '/photos': [
      { name: '..', type: 'folder', size: '-', modified: '-' },
      { name: 'vacation_2025', type: 'folder', size: '-', modified: '2025-08-20' },
      { name: 'profile_pic.jpg', type: 'file', size: '2.1 MB', modified: '2025-11-12' },
      { name: 'office_building.png', type: 'file', size: '5.3 MB', modified: '2025-11-10' }
    ],
    '/photos/vacation_2025': [
      { name: '..', type: 'folder', size: '-', modified: '-' },
      { name: 'beach_sunset.jpg', type: 'file', size: '4.2 MB', modified: '2025-08-15' },
      { name: 'mountain_view.jpg', type: 'file', size: '5.8 MB', modified: '2025-08-16' }
    ],
    '/videos': [
      { name: '..', type: 'folder', size: '-', modified: '-' },
      { name: 'demo.mp4', type: 'file', size: '125.3 MB', modified: '2025-11-08' },
      { name: 'presentation_recording.mp4', type: 'file', size: '342.8 MB', modified: '2025-11-05' }
    ]
  };

  const getCurrentFiles = () => {
    return fileTree[currentPath] || [];
  };

  const handleNavigate = (itemName) => {
    if (itemName === '..') {
      const pathParts = currentPath.split('/').filter(p => p);
      pathParts.pop();
      setCurrentPath('/' + pathParts.join('/'));
    } else {
      const newPath = currentPath === '/' ? `/${itemName}` : `${currentPath}/${itemName}`;
      setCurrentPath(newPath);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    setUploadFile(file);
    setUploadStatus('');
  };

  const handleUpload = () => {
    if (!uploadFile) {
      setUploadStatus('Please select a file first');
      return;
    }
    
    // Simulate upload
    setUploadStatus('Uploading...');
    setTimeout(() => {
      setUploadStatus(`✓ Successfully uploaded ${uploadFile.name} to ${currentPath}`);
      setUploadFile(null);
    }, 1500);
  };

  const getFileIcon = (type, name) => {
    if (type === 'folder') return '📁';
    const ext = name.split('.').pop().toLowerCase();
    const icons = {
      'pdf': '📄', 'txt': '📃', 'md': '📃',
      'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️',
      'mp4': '🎬', 'avi': '🎬',
      'xlsx': '📊', 'xls': '📊'
    };
    return icons[ext] || '📄';
  };

  const getBreadcrumbs = () => {
    if (currentPath === '/') return [{ name: 'Home', path: '/' }];
    const parts = currentPath.split('/').filter(p => p);
    const breadcrumbs = [{ name: 'Home', path: '/' }];
    let path = '';
    parts.forEach(part => {
      path += '/' + part;
      breadcrumbs.push({ name: part, path });
    });
    return breadcrumbs;
  };

  return (
    <div className="files-container">
      <h1>Files - NAS Server 1</h1>
      
      <div className="card full-height">
        {/* Upload Section */}
        <div className="upload-section">
          <h3>Upload File to {currentPath}</h3>
          <div className="upload-controls">
            <input 
              type="file" 
              onChange={handleFileSelect}
              className="file-input"
            />
            <button 
              onClick={handleUpload}
              className="upload-btn"
              disabled={!uploadFile}
            >
              Upload
            </button>
          </div>
          {uploadStatus && (
            <div className={`upload-status ${uploadStatus.includes('✓') ? 'success' : ''}`}>
              {uploadStatus}
            </div>
          )}
        </div>

        {/* Breadcrumb Navigation */}
        <div className="breadcrumb">
          {getBreadcrumbs().map((crumb, idx) => (
            <span key={idx}>
              <a 
                href="#!" 
                onClick={(e) => { e.preventDefault(); setCurrentPath(crumb.path); }}
                className="breadcrumb-link"
              >
                {crumb.name}
              </a>
              {idx < getBreadcrumbs().length - 1 && <span className="breadcrumb-separator"> / </span>}
            </span>
          ))}
        </div>

        {/* File Tree Table */}
        <table>
          <thead>
            <tr>
              <th style={{width: '50px'}}></th>
              <th>Name</th>
              <th style={{width: '120px'}}>Size</th>
              <th style={{width: '140px'}}>Last Modified</th>
            </tr>
          </thead>
          <tbody>
            {getCurrentFiles().map((item, idx) => (
              <tr key={idx}>
                <td className="file-icon">{getFileIcon(item.type, item.name)}</td>
                <td>
                  {item.type === 'folder' ? (
                    <a 
                      href="#!" 
                      onClick={(e) => { e.preventDefault(); handleNavigate(item.name); }}
                      className="folder-link"
                    >
                      <strong>{item.name}</strong>
                    </a>
                  ) : (
                    <span>{item.name}</span>
                  )}
                </td>
                <td>{item.size}</td>
                <td>{item.modified}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Main App Component
export default function App() {
  const [activePage, setActivePage] = useState('Dashboard');
  const [darkMode, setDarkMode] = useState(false);

  const renderPage = () => {
    switch(activePage) {
      case 'Dashboard': return <Dashboard />;
      case 'Diagnostics': return <Diagnostics />;
      case 'Synchronization': return <div className="card"><h1>Synchronization Control</h1></div>;
      case 'Users': return <div className="card"><h1>User Permissions</h1></div>;
      case 'Files': return <Files />;
      case 'Logs': return <Logs />;
      case 'Settings': return <div className="card"><h1>Settings</h1></div>;
      default: return <Dashboard />;
    }
  };

  return (
    <div className={`flex ${darkMode ? 'dark-mode' : ''}`}>
      <Sidebar 
        activePage={activePage} 
        setActivePage={setActivePage}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
      />
      <main className="main">
        {renderPage()}
      </main>
    </div>
  );
}
