import { createFileRoute } from '@tanstack/react-router'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import type { BotConfig } from "@/lib/types"
import { Eye, EyeOff, Key } from "lucide-react"
import { useState } from "react"

export const Route = createFileRoute('/_main/general')({
  component: GeneralPage,
})

const defaultConfig: BotConfig = {
  devDiscordToken: "",
  prodDiscordToken: "",
  adminIds: ["100000000000000000"],
  invisible: false,
  aiConfig: {
    preferredAiProvider: "google",
    boostImagePrompts: false,
    maxDailyImages: 5,
    ollama: {
      endpoint: "localhost:11434",
      preferredModel: "llama3.1",
    },
    openai: {
      apiKey: "",
      preferredModel: "gpt-5-nano",
    },
    antropic: {
      apiKey: "",
      preferredModel: "claude-4-5-sonnet",
    },
    gemini: {
      apiKey: "",
      preferredModel: "gemini-2.5-flash",
    },
    elevenlabs: {
      apiKey: "",
    },
    orchestrator: {
      preferredAiProvider: "google",
      preferredModel: "gemini-2.5-flash",
    },
    realTimeConfig: {
      realTimeModel: "gpt-realtime-mini",
      apiKey: "",
      voice: "sage",
    },
  },
  usersToId: {
    name1: "<@100000000000000000>",
    name2: "<@200000000000000000>",
    name3: "<@300000000000000000>",
  },
  idToUsers: {
    "000000000000000000": "name1",
    "100000000000000000": "name2",
    "200000000000000000": "name3",
  },
  mentionCooldown: 20,
  cooldownBypassList: ["100000000000000000"],
  promptsPath: "prompts.json",
  mongoUri: "mongodb://localhost:27017/",
  mongoDbName: "DB",
  mongoMessagesCollectionName: "COLLECTION",
  mongoMorningConfigsCollectionName: "MORNING_CONFIGS",
  mongoImageLimitsCollectionName: "IMAGE_LIMITS",
  allowedBotsToRespondTo: [],
  deleteUserMessages: {
    enabled: false,
    userIds: ["100000000000000000"],
  },
  globalBlockList: ["100000000000000000"],
}

function GeneralPage() {
  const [config, setConfig] = useState<BotConfig>(defaultConfig)
  const [showDevToken, setShowDevToken] = useState(false)
  const [showProdToken, setShowProdToken] = useState(false)

  const updateConfig = (updates: Partial<BotConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">General Settings</h2>
        <p className="text-muted-foreground">
          Configure your Discord bot tokens and basic settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            Discord Tokens
          </CardTitle>
          <CardDescription>
            Your bot authentication tokens for development and production environments.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="devToken">Development Token</Label>
            <div className="relative">
              <Input
                id="devToken"
                type={showDevToken ? "text" : "password"}
                value={config.devDiscordToken}
                onChange={(e) => updateConfig({ devDiscordToken: e.target.value })}
                placeholder="Enter development Discord token"
                className="pr-10 font-mono"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                onClick={() => setShowDevToken(!showDevToken)}
              >
                {showDevToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="prodToken">Production Token</Label>
            <div className="relative">
              <Input
                id="prodToken"
                type={showProdToken ? "text" : "password"}
                value={config.prodDiscordToken}
                onChange={(e) => updateConfig({ prodDiscordToken: e.target.value })}
                placeholder="Enter production Discord token"
                className="pr-10 font-mono"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                onClick={() => setShowProdToken(!showProdToken)}
              >
                {showProdToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

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
              onCheckedChange={(checked) => updateConfig({ invisible: checked })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Admin Users</CardTitle>
          <CardDescription>
            Discord user IDs with administrative privileges.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {config.adminIds.map((id, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={id}
                onChange={(e) => {
                  const newIds = [...config.adminIds]
                  newIds[index] = e.target.value
                  updateConfig({ adminIds: newIds })
                }}
                placeholder="User ID"
                className="font-mono"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const newIds = config.adminIds.filter((_, i) => i !== index)
                  updateConfig({ adminIds: newIds })
                }}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            onClick={() => updateConfig({ adminIds: [...config.adminIds, ""] })}
          >
            Add Admin
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
