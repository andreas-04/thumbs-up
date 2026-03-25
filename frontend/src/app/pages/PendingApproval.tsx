import { Shield, Clock, Mail } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';

export default function PendingApproval() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-blue-950 flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-gray-900 border-gray-800">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-amber-600 rounded-full flex items-center justify-center">
              <Clock className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl text-white">Pending Approval</CardTitle>
          <CardDescription className="text-gray-400">
            Your account has been created successfully
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
            <Shield className="h-5 w-5 text-blue-400 mt-0.5 shrink-0" />
            <p className="text-sm text-gray-300">
              An administrator will review your request. Once approved, you'll
              receive full access to protected files.
            </p>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
            <Mail className="h-5 w-5 text-blue-400 mt-0.5 shrink-0" />
            <p className="text-sm text-gray-300">
              You'll receive an email with a client certificate
              (<code className="text-blue-400">.p12</code>) to install on your
              device for secure access.
            </p>
          </div>

          <div className="text-center text-sm mt-6">
            <a href="/login" className="text-blue-400 hover:text-blue-300 font-medium">
              Back to Login
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
