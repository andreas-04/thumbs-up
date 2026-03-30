import React, { useState } from 'react';
import { useData, SystemSettingsType } from '../contexts/DataContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Lock, 
  CheckCircle, 
  AlertTriangle,
  Server,
  Mail,
  Globe,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';

export default function SystemSettings() {
  const { settings, updateSettings } = useData();
  const [localSettings, setLocalSettings] = useState(settings);
  const [hasChanges, setHasChanges] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [domainInput, setDomainInput] = useState('');

  if (!localSettings) return null;

  const handleChange = <K extends keyof SystemSettingsType>(
    key: K,
    value: SystemSettingsType[K]
  ) => {
    setLocalSettings({ ...localSettings, [key]: value });
    setHasChanges(true);
  };

  const handleSave = () => {
    if (!localSettings) return;
    updateSettings(localSettings);
    setHasChanges(false);
    setShowSuccess(true);
    toast.success('System settings saved successfully');
    
    setTimeout(() => {
      setShowSuccess(false);
    }, 3000);
  };

  const handleReset = () => {
    setLocalSettings(settings);
    setHasChanges(false);
    setDomainInput('');
  };

  const handleAddDomain = () => {
    const domain = domainInput.trim().replace(/^@/, '').toLowerCase();
    if (!domain || !domain.includes('.')) {
      toast.error('Please enter a valid domain (e.g. mycorp.com)');
      return;
    }
    const current = localSettings.allowedDomains || [];
    if (current.includes(domain)) {
      toast.error('Domain already in the list');
      return;
    }
    handleChange('allowedDomains', [...current, domain]);
    setDomainInput('');
  };

  const handleRemoveDomain = (domain: string) => {
    const current = localSettings.allowedDomains || [];
    handleChange('allowedDomains', current.filter((d) => d !== domain));
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-semibold text-white">System Settings</h1>
        <p className="text-gray-400 mt-1">
          Configure device settings
        </p>
      </div>

      {showSuccess && (
        <Alert className="bg-green-950 border-green-900">
          <CheckCircle className="h-4 w-4 text-green-400" />
          <AlertDescription className="text-green-300">
            System settings have been saved successfully
          </AlertDescription>
        </Alert>
      )}
      {/* Domain Allowlist */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-purple-400" />
            <CardTitle className="text-white">Domain Allowlist</CardTitle>
          </div>
          <CardDescription className="text-gray-400">
            Users signing up with an allowed email domain are automatically approved and sent a client certificate.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="corporation.com"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddDomain(); } }}
              className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
            />
            <Button type="button" onClick={handleAddDomain} variant="secondary" className="shrink-0">
              Add Domain
            </Button>
          </div>
          {(localSettings.allowedDomains?.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-2">
              {localSettings.allowedDomains.map((domain) => (
                <Badge
                  key={domain}
                  variant="secondary"
                  className="bg-purple-900/50 text-purple-200 border-purple-800 pl-3 pr-1.5 py-1.5 text-sm flex items-center gap-1.5"
                >
                  @{domain}
                  <button
                    type="button"
                    onClick={() => handleRemoveDomain(domain)}
                    className="rounded-full p-0.5 hover:bg-purple-700/50 transition-colors"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">
              No domains configured. Only admin-invited users can access the system.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Email Notifications */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-blue-400" />
            <CardTitle className="text-white">Email Notifications</CardTitle>
          </div>
          <CardDescription className="text-gray-400">
            Configure SMTP to email users when their account is approved
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-gray-200">Enable SMTP</Label>
              <p className="text-xs text-gray-500">Send email notifications when accounts are approved</p>
            </div>
            <Switch
              checked={localSettings.smtpEnabled}
              onCheckedChange={(checked) => handleChange('smtpEnabled', checked)}
            />
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="smtp-host" className="text-gray-200">SMTP Host</Label>
                <Input
                  id="smtp-host"
                  placeholder="smtp.example.com"
                  value={localSettings.smtpHost}
                  onChange={(e) => handleChange('smtpHost', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="bg-gray-800 border-gray-700 text-white disabled:opacity-50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-port" className="text-gray-200">SMTP Port</Label>
                <Input
                  id="smtp-port"
                  type="number"
                  value={localSettings.smtpPort}
                  onChange={(e) => handleChange('smtpPort', parseInt(e.target.value) || 587)}
                  disabled={!localSettings.smtpEnabled}
                  className="bg-gray-800 border-gray-700 text-white disabled:opacity-50"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp-from" className="text-gray-200">From Email</Label>
              <Input
                id="smtp-from"
                type="email"
                placeholder="noreply@example.com"
                value={localSettings.smtpFromEmail}
                onChange={(e) => handleChange('smtpFromEmail', e.target.value)}
                disabled={!localSettings.smtpEnabled}
                className="bg-gray-800 border-gray-700 text-white disabled:opacity-50"
              />
              <p className="text-xs text-gray-500">The sender address for notification emails</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="smtp-username" className="text-gray-200">Username</Label>
                <Input
                  id="smtp-username"
                  placeholder="username"
                  value={localSettings.smtpUsername}
                  onChange={(e) => handleChange('smtpUsername', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="bg-gray-800 border-gray-700 text-white disabled:opacity-50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smtp-password" className="text-gray-200">Password</Label>
                <Input
                  id="smtp-password"
                  type="password"
                  placeholder="••••••••"
                  value={localSettings.smtpPassword}
                  onChange={(e) => handleChange('smtpPassword', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="bg-gray-800 border-gray-700 text-white disabled:opacity-50"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label className="text-gray-200">Use STARTTLS</Label>
                <p className="text-xs text-gray-500">Enable TLS encryption for the SMTP connection</p>
              </div>
              <Switch
                checked={localSettings.smtpUseTls}
                onCheckedChange={(checked) => handleChange('smtpUseTls', checked)}
                disabled={!localSettings.smtpEnabled}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={!hasChanges}>
          Save Settings
        </Button>
        <Button
          variant="outline"
          onClick={handleReset}
          disabled={!hasChanges}
          className="bg-gray-800 border-gray-700 text-white hover:bg-gray-700"
        >
          Reset Changes
        </Button>
      </div>

      {hasChanges && (
        <Alert className="bg-yellow-950 border-yellow-900">
          <AlertTriangle className="h-4 w-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300">
            You have unsaved changes. Click "Save Settings" to apply them.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
