import React, { useState } from 'react';
import { useData, SystemMode, SystemSettingsType } from '../contexts/DataContext';
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
import { Switch } from '../components/ui/switch';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Shield, 
  Globe, 
  Lock, 
  CheckCircle, 
  AlertTriangle,
  Server,
} from 'lucide-react';
import { toast } from 'sonner';

export default function SystemSettings() {
  const { settings, updateSettings } = useData();
  const [localSettings, setLocalSettings] = useState(settings);
  const [hasChanges, setHasChanges] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  if (!localSettings) return null;

  const handleChange = <K extends keyof SystemSettingsType>(
    key: K,
    value: SystemSettingsType[K]
  ) => {
    setLocalSettings({ ...localSettings, [key]: value });
    setHasChanges(true);
  };

  const handleModeToggle = (checked: boolean) => {
    const newMode: SystemMode = checked ? 'protected' : 'open';
    handleChange('mode', newMode);
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
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-semibold text-white">System Settings</h1>
        <p className="text-gray-400 mt-1">
          Configure access mode and device settings
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

      {/* Access Mode */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <div className="flex items-center gap-2">
            {localSettings.mode === 'open' ? (
              <Globe className="h-5 w-5 text-green-400" />
            ) : (
              <Shield className="h-5 w-5 text-blue-400" />
            )}
            <CardTitle className="text-white">Access Mode</CardTitle>
          </div>
          <CardDescription className="text-gray-400">
            Control who can access shared files on this device
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Label htmlFor="mode-toggle" className="text-lg text-white">
                  Protected Mode
                </Label>
                {localSettings.mode === 'protected' && (
                  <span className="text-xs bg-blue-950 text-blue-300 px-2 py-0.5 rounded-full">
                    Active
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-400">
                {localSettings.mode === 'open' 
                  ? 'Currently in Open Mode - anyone can access files over TLS'
                  : 'Only pre-approved users can access files'}
              </p>
            </div>
            <Switch
              id="mode-toggle"
              checked={localSettings.mode === 'protected'}
              onCheckedChange={handleModeToggle}
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 border border-gray-700 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="h-5 w-5 text-green-400" />
                <h3 className="font-medium text-white">Open Mode</h3>
              </div>
              <p className="text-sm text-gray-400 mb-2">
                Any user connected to the device can access shared files over TLS without individual approval.
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>• No user registration required</li>
                <li>• Automatic access via HTTPS</li>
                <li>• Best for trusted networks</li>
              </ul>
            </div>

            <div className="p-4 border border-gray-700 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="h-5 w-5 text-blue-400" />
                <h3 className="font-medium text-white">Protected Mode</h3>
              </div>
              <p className="text-sm text-gray-400 mb-2">
                Only users added to the approved list can access files. Requires authentication.
              </p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>• User authentication required</li>
                <li>• Admin must approve each user</li>
                <li>• Granular access control</li>
              </ul>
            </div>
          </div>

          {localSettings.mode === 'protected' && (
            <Alert className="bg-blue-950 border-blue-900">
              <AlertTriangle className="h-4 w-4 text-blue-400" />
              <AlertDescription className="text-blue-300">
                Protected Mode is enabled. Only approved users can access files.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Security & Network */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-green-400" />
            <CardTitle className="text-white">Security & Network</CardTitle>
          </div>
          <CardDescription className="text-gray-400">
            Configure network settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="device-name" className="text-gray-200">Device Name</Label>
            <Input
              id="device-name"
              value={localSettings.deviceName}
              onChange={(e) => handleChange('deviceName', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
            />
            <p className="text-xs text-gray-500">
              Friendly name for this device
            </p>
          </div>
        </CardContent>
      </Card>

      {/* System Information */}
      <Card className="bg-gray-900 border-gray-800">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5 text-orange-400" />
            <CardTitle className="text-white">System Information</CardTitle>
          </div>
          <CardDescription className="text-gray-400">
            Device details and specifications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between py-2 border-b border-gray-800">
            <span className="text-sm text-gray-400">Device Type</span>
            <span className="text-sm font-medium text-gray-200">Raspberry Pi</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-800">
            <span className="text-sm text-gray-400">Admin Panel Version</span>
            <span className="text-sm font-medium text-gray-200">2.0.0</span>
          </div>
          <div className="flex justify-between py-2 border-b border-gray-800">
            <span className="text-sm text-gray-400">Protocol</span>
            <span className="text-sm font-medium text-gray-200">HTTPS/TLS</span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-sm text-gray-400">Last Updated</span>
            <span className="text-sm font-medium text-gray-200">February 16, 2026</span>
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
