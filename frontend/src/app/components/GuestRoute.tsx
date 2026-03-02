import React from 'react';
import { Navigate, Outlet } from 'react-router';
import { useAuth } from '../contexts/AuthContext';

export function GuestRoute() {
  const { isGuest, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (!isGuest) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
