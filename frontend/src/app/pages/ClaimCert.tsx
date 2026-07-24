import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { ShieldCheck, ShieldX, Copy, Download, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { api, ClaimCertResult } from '../../services/api';

function downloadP12(result: ClaimCertResult) {
  const bytes = Uint8Array.from(atob(result.p12), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: 'application/x-pkcs12' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = result.filename || 'terracrate-client.p12';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * One-time certificate claim page. The link in the invite/approval email
 * lands here; redeeming it generates the client certificate on the server,
 * downloads the .p12, and (for invited accounts) reveals the temporary
 * login password. The link works exactly once.
 */
export default function ClaimCert() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<'idle' | 'claiming' | 'done' | 'error'>('idle');
  const [result, setResult] = useState<ClaimCertResult | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const claimedRef = useRef(false);

  const claim = useCallback(async () => {
    if (!token || claimedRef.current) return;
    claimedRef.current = true;
    setState('claiming');
    try {
      const res = await api.claimCert(token);
      setResult(res);
      setState('done');
      downloadP12(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to claim certificate');
      setState('error');
    }
  }, [token]);

  useEffect(() => {
    claim();
  }, [claim]);

  const copyPassword = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-sm glass">
        <CardHeader className="text-center pb-4">
          <div className="flex justify-center mb-3">
            {state === 'error' ? (
              <ShieldX className="h-8 w-8 text-term-red" />
            ) : state === 'done' ? (
              <ShieldCheck className="h-8 w-8 text-term-green" />
            ) : (
              <Loader2 className="h-8 w-8 text-muted-foreground animate-spin" />
            )}
          </div>
          <CardTitle className="text-lg text-foreground tracking-tight">
            {state === 'error'
              ? 'link not valid'
              : state === 'done'
                ? 'certificate ready'
                : 'preparing your certificate'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {state === 'error' && (
            <>
              <p className="text-muted-foreground text-xs">{error}</p>
              <p className="text-muted-foreground text-xs">
                claim links work <strong className="text-foreground">once</strong> and expire after 7 days.
                contact your administrator for a new one.
              </p>
            </>
          )}

          {state === 'done' && result && (
            <>
              <p className="text-muted-foreground text-xs">
                your certificate for <strong className="text-foreground">{result.email}</strong> was
                downloaded. import it with this password:
              </p>
              <div className="flex items-center justify-center gap-2">
                <code className="text-sm text-term-green bg-glass-highlight px-2 py-1 rounded">
                  {result.password}
                </code>
                <Button variant="ghost" size="sm" onClick={copyPassword} aria-label="copy password">
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
              {copied && <p className="text-xs text-term-green">copied</p>}
              {result.passwordIsLogin && (
                <p className="text-muted-foreground text-xs">
                  this is also your <strong className="text-foreground">temporary login password</strong>;
                  you'll set a new one on first login.
                </p>
              )}
              <p className="text-muted-foreground text-xs">
                save the password now — this page cannot be opened again.
              </p>
              <div className="flex justify-center gap-2">
                <Button variant="outline" size="sm" onClick={() => result && downloadP12(result)}>
                  <Download className="h-3.5 w-3.5 mr-1" />
                  download again
                </Button>
                <Button variant="default" size="sm" asChild>
                  <Link to="/login">go to login</Link>
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
