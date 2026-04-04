import { ShieldAlert, ShieldOff } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useAuth } from '../contexts/AuthContext';

export default function CertRequired() {
  const { isAuthenticated, certRevoked } = useAuth();

  const isRevoked = isAuthenticated && certRevoked;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-blue-950 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-gray-900 border-gray-800">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className={`h-16 w-16 ${isRevoked ? 'bg-red-600' : 'bg-amber-600'} rounded-full flex items-center justify-center`}>
              {isRevoked ? (
                <ShieldOff className="h-8 w-8 text-white" />
              ) : (
                <ShieldAlert className="h-8 w-8 text-white" />
              )}
            </div>
          </div>
          <CardTitle className="text-2xl text-white">
            {isRevoked ? 'Certificate Revoked' : 'Certificate Required'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {isRevoked ? (
            <>
              <p className="text-gray-400">
                Your client certificate has been
                <strong className="text-red-400"> revoked </strong>
                by an administrator. You cannot access protected files until a new certificate is issued.
              </p>
              <p className="text-sm text-gray-500">
                Please contact your administrator to receive a replacement certificate.
              </p>
            </>
          ) : (
            <>
              <p className="text-gray-400">
                This page requires a client certificate to access. Please install the
                <strong className="text-gray-200"> .p12 certificate </strong>
                that was emailed to you when your account was approved.
              </p>
              <ol className="text-sm text-gray-400 text-left space-y-2 list-decimal list-inside">
                <li>Find the email with your <code className="text-gray-300">.p12</code> certificate file</li>
                <li>Open the file and follow your device's prompts to install it</li>
                <li>Restart your browser, then try again</li>
              </ol>
            </>
          )}
          <div className="flex gap-3 justify-center pt-2">
            <Button variant="outline" className="border-gray-700 text-gray-300 hover:bg-gray-800" asChild>
              <a href="/login">Back to Login</a>
            </Button>
            {!isRevoked && (
              <Button className="bg-blue-600 hover:bg-blue-700" onClick={() => window.location.reload()}>
                Try Again
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
