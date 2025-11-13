import React, { useState } from 'react';
import './index.css';

// Sidebar Component
function Sidebar({ activePage, setActivePage }) {
  const pages = ['Dashboard', 'Files', 'Encryption', 'Users', 'Logs', 'Settings'];
  
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
    </div>
  );
}

// Dashboard Page
function Dashboard() {
  const drives = [
    { name: "Drive A", encrypted: true, size: "250GB", used: "120GB" },
    { name: "Drive B", encrypted: false, size: "500GB", used: "450GB" }
  ];
  const recentActivity = [
    { user: "Alice", action: "uploaded File1.txt", time: "10:05 AM" },
    { user: "Bob", action: "downloaded File2.docx", time: "09:42 AM" }
  ];

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="flex">
        {drives.map(d => (
          <div key={d.name} className="card" style={{ marginRight: '20px' }}>
            <h3>{d.name}</h3>
            <p>Status: {d.encrypted ? <span className="status success">Encrypted 🔒</span> : <span className="status warning">Unencrypted ⚠️</span>}</p>
            <p>{d.used} / {d.size}</p>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Recent Activity</h3>
        <ul>
          {recentActivity.map((act, i) => (
            <li key={i}>{act.time} - {act.user} {act.action}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// Files Page
function Files() {
  const [files, setFiles] = useState([
    { name: "File1.txt", status: "Available" },
    { name: "File2.docx", status: "Downloading" }
  ]);

  const simulateUpload = (fileName) => {
    setFiles(prev => prev.map(f => f.name === fileName ? { ...f, status: "Uploading..." } : f));
    setTimeout(() => {
      setFiles(prev => prev.map(f => f.name === fileName ? { ...f, status: "Available" } : f));
    }, 1500);
  };

  return (
    <div>
      <h1>Files</h1>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {files.map(file => (
            <tr key={file.name}>
              <td>{file.name}</td>
              <td>
                <span className={`status ${file.status === "Available" ? "success" : "info"}`}>{file.status}</span>
              </td>
              <td>
                <button onClick={() => simulateUpload(file.name)}>Upload</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Main App Component
export default function App() {
  const [activePage, setActivePage] = useState('Dashboard');

  const renderPage = () => {
    switch(activePage) {
      case 'Dashboard': return <Dashboard />;
      case 'Files': return <Files />;
      case 'Encryption': return <div className="card"><h1>Encryption Control</h1></div>;
      case 'Users': return <div className="card"><h1>User Permissions</h1></div>;
      case 'Logs': return <div className="card"><h1>Monitoring / Logs</h1></div>;
      case 'Settings': return <div className="card"><h1>Settings</h1></div>;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="flex">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      <main className="main">
        {renderPage()}
      </main>
    </div>
  );
}
