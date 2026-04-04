import { ShieldAlert, ShieldOff } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useAuth } from '../contexts/AuthContext';

export default function CertRequired() {
  const { isAuthenticated, certRevoked } = useAuth();

  const isRevoked = isAuthenticated && certRevoked;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-sm glass">
        <CardHeader className="text-center pb-4">
          <div className="flex justify-center mb-3">
            {isRevoked ? (
              <ShieldOff className="h-8 w-8 text-term-red" />
            ) : (
              <ShieldAlert className="h-8 w-8 text-term-yellow" />
            )}
          </div>
          <CardTitle className="text-lg text-foreground tracking-tight">
            {isRevoked ? 'certificate revoked' : 'certificate required'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {isRevoked ? (
            <>
              <p className="text-muted-foreground text-xs">
                your client certificate has been
                <strong className="text-term-red"> revoked</strong>.
                contact your administrator for a replacement.
              </p>
            </>
          ) : (
            <>
              <p className="text-muted-foreground text-xs">
                install the <strong className="text-foreground">.p12 certificate</strong> from your approval email.
              </p>
              <ol className="text-xs text-muted-foreground text-left space-y-1.5 list-decimal list-inside">
                <li>find the email with your <code className="text-foreground">.p12</code> file</li>
                <li>open and install the certificate on your device</li>
                <li>restart your browser and try again</li>
              </ol>
            </>
          )}
          <div className="flex gap-2 justify-center pt-2">
            <Button variant="outline" className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs" asChild>
              <a href="/login">back to login</a>
            </Button>
            {!isRevoked && (
              <Button className="h-8 text-xs" onClick={() => window.location.reload()}>
                retry
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
