import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Terminal, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function Signup() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('password must be at least 8 characters');
      return;
    }

    setLoading(true);

    try {
      const { api } = await import('../../services/api');
      await api.signup({ email, password, username });
      
      toast.success('account created -- check email for certificate', { duration: 8000 });
      navigate('/login');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'registration failed';
      setError(errorMessage);
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
          <CardTitle className="text-lg text-foreground tracking-tight">sign up</CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            create an account
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
              <Label htmlFor="username" className="text-muted-foreground text-xs">username</Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="glass border-glass-border text-foreground h-9 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-muted-foreground text-xs">email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="glass border-glass-border text-foreground h-9 text-sm"
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
              {loading ? 'creating...' : 'sign up'}
            </Button>

            <div className="text-center text-xs pt-2">
              <span className="text-muted-foreground">have an account? </span>
              <a href="/login" className="text-term-blue hover:text-term-cyan transition-colors">
                sign in
              </a>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
