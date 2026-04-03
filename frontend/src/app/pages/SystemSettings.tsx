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
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="text-lg font-medium text-foreground">settings</h1>
        <p className="text-muted-foreground text-xs mt-0.5">
          system configuration
        </p>
      </div>

      {showSuccess && (
        <Alert className="glass border-term-green/20 py-2">
          <CheckCircle className="h-3.5 w-3.5 text-term-green" />
          <AlertDescription className="text-term-green text-xs">
            settings saved
          </AlertDescription>
        </Alert>
      )}
      {/* Domain Allowlist */}
      <Card className="glass">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Globe className="h-3.5 w-3.5 text-term-purple" />
            <CardTitle className="text-sm text-foreground">domain allowlist</CardTitle>
          </div>
          <CardDescription className="text-xs text-muted-foreground">
            allowed email domains for auto-approval
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="corporation.com"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddDomain(); } }}
              className="glass border-glass-border text-foreground placeholder:text-term-dim h-8 text-xs"
            />
            <Button type="button" onClick={handleAddDomain} variant="secondary" className="shrink-0 h-8 text-xs">
              add
            </Button>
          </div>
          {(localSettings.allowedDomains?.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {localSettings.allowedDomains.map((domain) => (
                <Badge
                  key={domain}
                  variant="secondary"
                  className="glass border-term-purple/20 text-term-purple pl-2 pr-1 py-0.5 text-xs flex items-center gap-1"
                >
                  @{domain}
                  <button
                    type="button"
                    onClick={() => handleRemoveDomain(domain)}
                    className="rounded p-0.5 hover:bg-glass-highlight transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              no domains configured -- invite-only mode
            </p>
          )}
        </CardContent>
      </Card>

      {/* Email Notifications */}
      <Card className="glass">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Mail className="h-3.5 w-3.5 text-term-blue" />
            <CardTitle className="text-sm text-foreground">smtp</CardTitle>
          </div>
          <CardDescription className="text-xs text-muted-foreground">
            email delivery configuration
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-foreground text-xs">enabled</Label>
              <p className="text-[11px] text-muted-foreground">send cert emails on approval</p>
            </div>
            <Switch
              checked={localSettings.smtpEnabled}
              onCheckedChange={(checked) => handleChange('smtpEnabled', checked)}
            />
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="smtp-host" className="text-muted-foreground text-xs">host</Label>
                <Input
                  id="smtp-host"
                  placeholder="smtp.example.com"
                  value={localSettings.smtpHost}
                  onChange={(e) => handleChange('smtpHost', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="glass border-glass-border text-foreground h-8 text-xs disabled:opacity-40"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="smtp-port" className="text-muted-foreground text-xs">port</Label>
                <Input
                  id="smtp-port"
                  type="number"
                  value={localSettings.smtpPort}
                  onChange={(e) => handleChange('smtpPort', parseInt(e.target.value) || 587)}
                  disabled={!localSettings.smtpEnabled}
                  className="glass border-glass-border text-foreground h-8 text-xs disabled:opacity-40"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="smtp-from" className="text-muted-foreground text-xs">from address</Label>
              <Input
                id="smtp-from"
                type="email"
                placeholder="noreply@example.com"
                value={localSettings.smtpFromEmail}
                onChange={(e) => handleChange('smtpFromEmail', e.target.value)}
                disabled={!localSettings.smtpEnabled}
                className="glass border-glass-border text-foreground h-8 text-xs disabled:opacity-40"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="smtp-username" className="text-muted-foreground text-xs">username</Label>
                <Input
                  id="smtp-username"
                  placeholder="username"
                  value={localSettings.smtpUsername}
                  onChange={(e) => handleChange('smtpUsername', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="glass border-glass-border text-foreground h-8 text-xs disabled:opacity-40"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="smtp-password" className="text-muted-foreground text-xs">password</Label>
                <Input
                  id="smtp-password"
                  type="password"
                  placeholder="--------"
                  value={localSettings.smtpPassword}
                  onChange={(e) => handleChange('smtpPassword', e.target.value)}
                  disabled={!localSettings.smtpEnabled}
                  className="glass border-glass-border text-foreground h-8 text-xs disabled:opacity-40"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label className="text-foreground text-xs">starttls</Label>
                <p className="text-[11px] text-muted-foreground">tls encryption</p>
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
      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={!hasChanges} className="h-8 text-xs">
          save
        </Button>
        <Button
          variant="outline"
          onClick={handleReset}
          disabled={!hasChanges}
          className="glass border-glass-border text-foreground hover:bg-glass-highlight h-8 text-xs"
        >
          reset
        </Button>
      </div>

      {hasChanges && (
        <Alert className="glass border-term-yellow/20 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-term-yellow" />
          <AlertDescription className="text-term-yellow text-xs">
            unsaved changes
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
