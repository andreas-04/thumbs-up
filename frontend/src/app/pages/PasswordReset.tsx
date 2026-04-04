import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../../services/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Terminal, AlertCircle } from 'lucide-react';

export default function PasswordReset() {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, updateUser } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('passwords do not match');
      return;
    }

    if (newPassword.length < 6) {
      setError('password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      const response = await api.changePassword('', newPassword);
      updateUser(response.user);
      navigate(user?.role === 'admin' ? '/admin/dashboard' : '/files');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-sm glass">
        <CardHeader className="space-y-1 text-center pb-4">
          <div className="flex justify-center mb-3">
            <Terminal className="h-8 w-8 text-term-yellow" />
          </div>
          <CardTitle className="text-lg text-foreground tracking-tight">reset password</CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            change your default password to continue
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3">
            {error && (
              <Alert variant="destructive" className="glass border-term-red/20 py-2">
                <AlertCircle className="h-3.5 w-3.5" />
                <AlertDescription className="text-term-red text-xs">{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="newPassword" className="text-muted-foreground text-xs">new password</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoFocus
                className="glass border-glass-border text-foreground h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="confirmPassword" className="text-muted-foreground text-xs">confirm password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="glass border-glass-border text-foreground h-9 text-sm"
              />
            </div>

            <Button type="submit" className="w-full h-9 text-sm" disabled={loading}>
              {loading ? 'updating...' : 'change password'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
