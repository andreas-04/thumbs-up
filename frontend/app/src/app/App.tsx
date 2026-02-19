import { RouterProvider } from 'react-router';
import { AuthProvider } from './contexts/AuthContext';
import { DataProvider } from './contexts/DataContext';
import { router } from './routes';
import { Toaster } from './components/ui/sonner';

export default function App() {
  return (
    <AuthProvider>
      <DataProvider>
        <RouterProvider router={router} />
        <Toaster />
      </DataProvider>
    </AuthProvider>
  );
}