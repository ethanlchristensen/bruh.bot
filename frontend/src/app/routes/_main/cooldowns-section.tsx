"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import type { BotConfig } from "@/lib/types"
import { Clock, Plus, Shield, Trash2 } from "lucide-react"

interface CooldownsSectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}

export function CooldownsSection({ config, onUpdate }: CooldownsSectionProps) {
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
              onValueChange={([value]) => onUpdate({ mentionCooldown: value })}
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
          {config.cooldownBypassList.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={id}
                onChange={(e) => {
                  const newList = [...config.cooldownBypassList]
                  newList[index] = e.target.value
                  onUpdate({ cooldownBypassList: newList })
                }}
                placeholder="User ID"
                className="font-mono"
              />
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  const newList = config.cooldownBypassList.filter((_, i) => i !== index)
                  onUpdate({ cooldownBypassList: newList })
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="w-full bg-transparent"
            onClick={() => onUpdate({ cooldownBypassList: [...config.cooldownBypassList, ""] })}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
