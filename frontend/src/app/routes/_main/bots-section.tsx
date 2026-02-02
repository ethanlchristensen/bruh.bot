
"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { BotConfig } from "@/lib/types"
import { Bot, Plus, Trash2 } from "lucide-react"




interface BotsSectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}



export function BotsSection({ config, onUpdate }: BotsSectionProps) {
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
            Bot IDs that your bot is allowed to respond to. Leave empty to ignore all bots.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {config.allowedBotsToRespondTo.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <Bot className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <p className="mt-2 text-sm text-muted-foreground">
                No bots configured. Your bot will ignore all other bots.
              </p>
            </div>
          ) : (
            config.allowedBotsToRespondTo.map((id, index) => (
              <div key={index} className="flex items-center gap-2">
                <Input
                  value={id}
                  onChange={(e) => {
                    const newList = [...config.allowedBotsToRespondTo]
                    newList[index] = e.target.value
                    onUpdate({ allowedBotsToRespondTo: newList })
                  }}
                  placeholder="Bot ID"
                  className="font-mono"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => {
                    const newList = config.allowedBotsToRespondTo.filter((_, i) => i !== index)
                    onUpdate({ allowedBotsToRespondTo: newList })
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
          <Button
            variant="outline"
            className="w-full bg-transparent"
            onClick={() =>
              onUpdate({ allowedBotsToRespondTo: [...config.allowedBotsToRespondTo, ""] })
            }
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Bot
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
