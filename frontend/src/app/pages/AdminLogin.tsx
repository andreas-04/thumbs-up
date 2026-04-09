import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../../services/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Terminal, AlertCircle } from 'lucide-react';

export default function AdminLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [signupEnabled, setSignupEnabled] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.getSettings().then((s) => {
      setSignupEnabled((s.allowedDomains?.length ?? 0) > 0);
    }).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const userData = await login(username, password);
      if (userData) {
        if (userData.requiresPasswordChange) {
          navigate('/reset-password');
        } else if (userData.role === 'admin') {
          navigate('/admin/dashboard');
        } else {
          window.location.href = '/files';
          return;
        }
      } else {
        setError('invalid credentials');
      }
    } catch {
      setError('connection failed. try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-sm glass">
        <CardHeader className="space-y-1 text-center pb-4">
          <div className="flex justify-center mb-3">
            <Terminal className="h-8 w-8 text-term-green" />
          </div>
          <CardTitle className="text-lg text-foreground tracking-tight">
            TerraCrate
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            authenticate to continue
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
              <Label htmlFor="username" className="text-muted-foreground text-xs">email</Label>
              <Input
                id="username"
                type="email"
                placeholder="user@domain.com"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="glass border-glass-border text-foreground placeholder:text-term-dim h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-muted-foreground text-xs">password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="glass border-glass-border text-foreground h-9 text-sm"
              />
            </div>

            <Button type="submit" className="w-full h-9 text-sm" disabled={loading}>
              {loading ? 'connecting...' : 'login'}
            </Button>

            {signupEnabled && (
              <div className="text-center text-xs pt-2">
                <span className="text-muted-foreground">no account? </span>
                <a href="/signup" className="text-term-blue hover:text-term-cyan transition-colors">
                  sign up
                </a>
              </div>
            )}

            <div className="text-center text-xs pt-1">
              <a href="/guest" className="text-muted-foreground hover:text-foreground transition-colors">
                continue as guest
              </a>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}