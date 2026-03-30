import { ShieldAlert } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';

export default function CertRequired() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-blue-950 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-gray-900 border-gray-800">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-amber-600 rounded-full flex items-center justify-center">
              <ShieldAlert className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl text-white">Certificate Required</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
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
          <div className="flex gap-3 justify-center pt-2">
            <Button variant="outline" className="border-gray-700 text-gray-300 hover:bg-gray-800" asChild>
              <a href="/login">Back to Login</a>
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={() => window.location.reload()}>
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
