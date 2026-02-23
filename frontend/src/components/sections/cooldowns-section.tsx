import { Clock, Plus, Shield, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
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
import { Slider } from '@/components/ui/slider';

interface CooldownsSectionProps {
  config: DynamicConfig;
  onUpdate: (updates: Partial<DynamicConfig>) => void;
}

export function CooldownsSection({ config, onUpdate }: CooldownsSectionProps) {
  const [localBypassList, setLocalBypassList] = useState<Array<number>>(
    config.cooldownBypassList,
  );

  useEffect(() => {
    setLocalBypassList(config.cooldownBypassList);
  }, [config.cooldownBypassList]);

  const handleBypassChange = (index: number, value: string) => {
    const newList = [...localBypassList];
    newList[index] = parseInt(value) || 0;
    setLocalBypassList(newList);
  };

  const handleAddBypass = () => {
    setLocalBypassList([...localBypassList, 0]);
  };

  const handleRemoveBypass = (index: number) => {
    const newList = localBypassList.filter((_, i) => i !== index);
    setLocalBypassList(newList);
    onUpdate({ cooldownBypassList: newList });
  };

  const handleSaveBypassList = () => {
    onUpdate({ cooldownBypassList: localBypassList });
  };

  const handleCooldownChange = (value: number) => {
    onUpdate({ mentionCooldown: value });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Cooldowns</h2>
        <p className="text-muted-foreground">
          Configure mention cooldowns and bypass permissions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Mention Cooldown
          </CardTitle>
          <CardDescription>
            Time in seconds before a user can mention the bot again.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Cooldown Duration</Label>
              <span className="text-sm font-medium tabular-nums">
                {config.mentionCooldown}s
              </span>
            </div>
            <Slider
              value={[config.mentionCooldown]}
              onValueChange={([value]) => handleCooldownChange(value)}
              max={120}
              min={0}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>0s (No cooldown)</span>
              <span>120s (2 minutes)</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Cooldown Bypass List
          </CardTitle>
          <CardDescription>
            User IDs that can bypass the mention cooldown.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {localBypassList.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                type="number"
                value={id || ''}
                onChange={(e) => handleBypassChange(index, e.target.value)}
                placeholder="Discord User ID"
                className="font-mono"
              />
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => handleRemoveBypass(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 bg-transparent"
              onClick={handleAddBypass}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add User
            </Button>
            <Button
              onClick={handleSaveBypassList}
              disabled={
                JSON.stringify(localBypassList) ===
                JSON.stringify(config.cooldownBypassList)
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
