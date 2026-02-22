import { Bot, Plus, Trash2 } from 'lucide-react'
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

interface BotsSectionProps {
  config: DynamicConfig
  onUpdate: (updates: Partial<DynamicConfig>) => void
}

export function BotsSection({ config, onUpdate }: BotsSectionProps) {
  const [localBotList, setLocalBotList] = useState<Array<number>>(
    config.allowedBotsToRespondTo,
  )

  useEffect(() => {
    setLocalBotList(config.allowedBotsToRespondTo)
  }, [config.allowedBotsToRespondTo])

  const handleBotIdChange = (index: number, value: string) => {
    const newList = [...localBotList]
    newList[index] = parseInt(value) || 0
    setLocalBotList(newList)
  }

  const handleAddBot = () => {
    setLocalBotList([...localBotList, 0])
  }

  const handleRemoveBot = (index: number) => {
    const newList = localBotList.filter((_, i) => i !== index)
    setLocalBotList(newList)
    onUpdate({ allowedBotsToRespondTo: newList })
  }

  const handleSave = () => {
    onUpdate({ allowedBotsToRespondTo: localBotList })
  }
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Bot Settings</h2>
        <p className="text-muted-foreground">
          Configure which bots your bot can interact with.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            Allowed Bots to Respond To
          </CardTitle>
          <CardDescription>
            Bot IDs that your bot is allowed to respond to. Leave empty to
            ignore all bots.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {localBotList.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <Bot className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No bots configured. Your bot will ignore all other bots.
              </p>
            </div>
          ) : (
            localBotList.map((id, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  type="number"
                  value={id || ''}
                  onChange={(e) => handleBotIdChange(index, e.target.value)}
                  placeholder="Discord Bot ID"
                  className="font-mono"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => handleRemoveBot(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 bg-transparent"
              onClick={handleAddBot}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Bot
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                JSON.stringify(localBotList) ===
                JSON.stringify(config.allowedBotsToRespondTo)
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
