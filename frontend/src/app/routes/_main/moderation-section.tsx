"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { BotConfig } from "@/lib/types"
import { Ban, MessageSquareX, Plus, Trash2 } from "lucide-react"

interface ModerationSectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}

export function ModerationSection({ config, onUpdate }: ModerationSectionProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Moderation</h2>
        <p className="text-muted-foreground">
          Configure message deletion and user blocking settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquareX className="h-5 w-5 text-primary" />
            Delete User Messages
          </CardTitle>
          <CardDescription>
            Automatically delete messages from specified users.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="deleteEnabled">Enable Auto-Delete</Label>
              <p className="text-sm text-muted-foreground">
                Delete messages from users in the list below.
              </p>
            </div>
            <Switch
              id="deleteEnabled"
              checked={config.deleteUserMessages.enabled}
              onCheckedChange={(checked) =>
                onUpdate({
                  deleteUserMessages: { ...config.deleteUserMessages, enabled: checked },
                })
              }
            />
          </div>

          <div className="space-y-3 pt-2">
            <Label>User IDs</Label>
            {config.deleteUserMessages.userIds.map((id, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  value={id}
                  onChange={(e) => {
                    const newIds = [...config.deleteUserMessages.userIds]
                    newIds[index] = e.target.value
                    onUpdate({
                      deleteUserMessages: { ...config.deleteUserMessages, userIds: newIds },
                    })
                  }}
                  placeholder="User ID"
                  className="font-mono"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => {
                    const newIds = config.deleteUserMessages.userIds.filter((_, i) => i !== index)
                    onUpdate({
                      deleteUserMessages: { ...config.deleteUserMessages, userIds: newIds },
                    })
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              className="w-full bg-transparent"
              onClick={() =>
                onUpdate({
                  deleteUserMessages: {
                    ...config.deleteUserMessages,
                    userIds: [...config.deleteUserMessages.userIds, ""],
                  },
                })
              }
            >
              <Plus className="h-4 w-4 mr-2" />
              Add User
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ban className="h-5 w-5 text-destructive" />
            Global Block List
          </CardTitle>
          <CardDescription>
            User IDs that are completely blocked from interacting with the bot.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {config.globalBlockList.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={id}
                onChange={(e) => {
                  const newList = [...config.globalBlockList]
                  newList[index] = e.target.value
                  onUpdate({ globalBlockList: newList })
                }}
                placeholder="User ID"
                className="font-mono"
              />
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  const newList = config.globalBlockList.filter((_, i) => i !== index)
                  onUpdate({ globalBlockList: newList })
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="w-full bg-transparent"
            onClick={() => onUpdate({ globalBlockList: [...config.globalBlockList, ""] })}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Blocked User
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
