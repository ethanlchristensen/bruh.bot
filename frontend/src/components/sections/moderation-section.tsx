import { Ban, MessageSquareX, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { DynamicConfig } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

interface ModerationSectionProps {
  config: DynamicConfig
  onUpdate: (updates: Partial<DynamicConfig>) => void
}

export function ModerationSection({
  config,
  onUpdate,
}: ModerationSectionProps) {
  const [localDeleteUserIds, setLocalDeleteUserIds] = useState<Array<number>>(
    config.deleteUserMessages.userIds,
  )
  const [localBlockList, setLocalBlockList] = useState<Array<number>>(
    config.globalBlockList,
  )

  useEffect(() => {
    setLocalDeleteUserIds(config.deleteUserMessages.userIds)
    setLocalBlockList(config.globalBlockList)
  }, [config.deleteUserMessages.userIds, config.globalBlockList])

  const handleDeleteUserIdChange = (index: number, value: string) => {
    const newIds = [...localDeleteUserIds]
    newIds[index] = parseInt(value) || 0
    setLocalDeleteUserIds(newIds)
  }

  const handleAddDeleteUserId = () => {
    setLocalDeleteUserIds([...localDeleteUserIds, 0])
  }

  const handleRemoveDeleteUserId = (index: number) => {
    const newIds = localDeleteUserIds.filter((_, i) => i !== index)
    setLocalDeleteUserIds(newIds)
    onUpdate({
      deleteUserMessages: {
        enabled: config.deleteUserMessages.enabled,
        userIds: newIds,
      },
    })
  }

  const handleSaveDeleteUserIds = () => {
    onUpdate({
      deleteUserMessages: {
        enabled: config.deleteUserMessages.enabled,
        userIds: localDeleteUserIds,
      },
    })
  }

  const handleBlockListChange = (index: number, value: string) => {
    const newList = [...localBlockList]
    newList[index] = parseInt(value) || 0
    setLocalBlockList(newList)
  }

  const handleAddToBlockList = () => {
    setLocalBlockList([...localBlockList, 0])
  }

  const handleRemoveFromBlockList = (index: number) => {
    const newList = localBlockList.filter((_, i) => i !== index)
    setLocalBlockList(newList)
    onUpdate({ globalBlockList: newList })
  }

  const handleSaveBlockList = () => {
    onUpdate({ globalBlockList: localBlockList })
  }

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
                  deleteUserMessages: {
                    ...config.deleteUserMessages,
                    enabled: checked,
                  },
                })
              }
            />
          </div>

          <div className="space-y-3 pt-2">
            <Label>User IDs</Label>
            {localDeleteUserIds.map((id, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  type="number"
                  value={id || ''}
                  onChange={(e) =>
                    handleDeleteUserIdChange(index, e.target.value)
                  }
                  placeholder="Discord User ID"
                  className="font-mono"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => handleRemoveDeleteUserId(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="flex-1 bg-transparent"
                onClick={handleAddDeleteUserId}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add User
              </Button>
              <Button
                onClick={handleSaveDeleteUserIds}
                disabled={
                  JSON.stringify(localDeleteUserIds) ===
                  JSON.stringify(config.deleteUserMessages.userIds)
                }
              >
                Save Changes
              </Button>
            </div>
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
          {localBlockList.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                type="number"
                value={id || ''}
                onChange={(e) => handleBlockListChange(index, e.target.value)}
                placeholder="Discord User ID"
                className="font-mono"
              />
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => handleRemoveFromBlockList(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 bg-transparent"
              onClick={handleAddToBlockList}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Blocked User
            </Button>
            <Button
              onClick={handleSaveBlockList}
              disabled={
                JSON.stringify(localBlockList) ===
                JSON.stringify(config.globalBlockList)
              }
            >
              Save Changes
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
