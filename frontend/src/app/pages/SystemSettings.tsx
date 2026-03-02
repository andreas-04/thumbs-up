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
