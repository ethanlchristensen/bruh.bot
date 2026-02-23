import { Shield } from 'lucide-react';
import { useState } from 'react';
import type { DynamicConfig } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

interface GeneralSectionProps {
  config: DynamicConfig;
  onUpdate: (updates: Partial<DynamicConfig>) => void;
}

export function GeneralSection({ config, onUpdate }: GeneralSectionProps) {
  const [localAdmins, setLocalAdmins] = useState<Array<number>>(
    config.adminIds,
  );

  const handleAdminChange = (index: number, value: string) => {
    const newAdmins = [...localAdmins];
    newAdmins[index] = parseInt(value) || 0;
    setLocalAdmins(newAdmins);
  };

  const handleAddAdmin = () => {
    setLocalAdmins([...localAdmins, 0]);
  };

  const handleRemoveAdmin = (index: number) => {
    const newAdmins = localAdmins.filter((_, i) => i !== index);
    setLocalAdmins(newAdmins);
    onUpdate({ adminIds: newAdmins });
  };

  const handleSaveAdmins = () => {
    onUpdate({ adminIds: localAdmins });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          General Settings
        </h2>
        <p className="text-muted-foreground">
          Configure basic bot settings and permissions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Bot Visibility</CardTitle>
          <CardDescription>
            Control whether the bot appears online or invisible.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="invisible">Invisible Mode</Label>
              <p className="text-sm text-muted-foreground">
                When enabled, the bot will appear offline to other users.
              </p>
            </div>
            <Switch
              id="invisible"
              checked={config.invisible}
              onCheckedChange={(checked) => onUpdate({ invisible: checked })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Admin Users
          </CardTitle>
          <CardDescription>
            Discord user IDs with administrative privileges.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {localAdmins.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                type="number"
                value={id || ''}
                onChange={(e) => handleAdminChange(index, e.target.value)}
                placeholder="Discord User ID"
                className="font-mono"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleRemoveAdmin(index)}
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleAddAdmin}>
              Add Admin
            </Button>
            <Button
              onClick={handleSaveAdmins}
              disabled={
                JSON.stringify(localAdmins) === JSON.stringify(config.adminIds)
              }
            >
              Save Changes
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
