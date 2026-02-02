"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AIConfig, BotConfig } from "@/lib/types"
import { Bot, Eye, EyeOff, Mic, Sparkles, Zap } from "lucide-react"
import { useState } from "react"

interface AISectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}

const aiProviders = [
  { value: "ollama", label: "Ollama" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google (Gemini)" },
]

export function AISection({ config, onUpdate }: AISectionProps) {
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})

  const toggleShowKey = (key: string) => {
    setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const updateAIConfig = (updates: Partial<AIConfig>) => {
    onUpdate({ aiConfig: { ...config.aiConfig, ...updates } })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">AI Configuration</h2>
        <p className="text-muted-foreground">
          Configure AI providers, models, and generation settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            General AI Settings
          </CardTitle>
          <CardDescription>
            Global AI preferences and image generation limits.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="preferredProvider">Preferred AI Provider</Label>
              <Select
                value={config.aiConfig.preferredAiProvider}
                onValueChange={(value) => updateAIConfig({ preferredAiProvider: value })}
              >
                <SelectTrigger id="preferredProvider">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {aiProviders.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="maxImages">Max Daily Images</Label>
              <Input
                id="maxImages"
                type="number"
                min={0}
                value={config.aiConfig.maxDailyImages}
                onChange={(e) => updateAIConfig({ maxDailyImages: parseInt(e.target.value) || 0 })}
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="space-y-0.5">
              <Label htmlFor="boostPrompts">Boost Image Prompts</Label>
              <p className="text-sm text-muted-foreground">
                Enhance prompts for better image generation results.
              </p>
            </div>
            <Switch
              id="boostPrompts"
              checked={config.aiConfig.boostImagePrompts}
              onCheckedChange={(checked) => updateAIConfig({ boostImagePrompts: checked })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            Provider Settings
          </CardTitle>
          <CardDescription>
            Configure individual AI provider credentials and models.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="ollama" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="ollama">Ollama</TabsTrigger>
              <TabsTrigger value="openai">OpenAI</TabsTrigger>
              <TabsTrigger value="anthropic">Anthropic</TabsTrigger>
              <TabsTrigger value="gemini">Gemini</TabsTrigger>
            </TabsList>

            <TabsContent value="ollama" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="ollamaEndpoint">Endpoint</Label>
                <Input
                  id="ollamaEndpoint"
                  value={config.aiConfig.ollama.endpoint}
                  onChange={(e) =>
                    updateAIConfig({
                      ollama: { ...config.aiConfig.ollama, endpoint: e.target.value },
                    })
                  }
                  placeholder="localhost:11434"
                  className="font-mono"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ollamaModel">Preferred Model</Label>
                <Input
                  id="ollamaModel"
                  value={config.aiConfig.ollama.preferredModel}
                  onChange={(e) =>
                    updateAIConfig({
                      ollama: { ...config.aiConfig.ollama, preferredModel: e.target.value },
                    })
                  }
                  placeholder="llama3.1"
                />
              </div>
            </TabsContent>

            <TabsContent value="openai" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="openaiKey">API Key</Label>
                <div className="relative">
                  <Input
                    id="openaiKey"
                    type={showKeys.openai ? "text" : "password"}
                    value={config.aiConfig.openai.apiKey}
                    onChange={(e) =>
                      updateAIConfig({
                        openai: { ...config.aiConfig.openai, apiKey: e.target.value },
                      })
                    }
                    placeholder="sk-..."
                    className="pr-10 font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => toggleShowKey("openai")}
                  >
                    {showKeys.openai ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="openaiModel">Preferred Model</Label>
                <Input
                  id="openaiModel"
                  value={config.aiConfig.openai.preferredModel}
                  onChange={(e) =>
                    updateAIConfig({
                      openai: { ...config.aiConfig.openai, preferredModel: e.target.value },
                    })
                  }
                  placeholder="gpt-5-nano"
                />
              </div>
            </TabsContent>

            <TabsContent value="anthropic" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="anthropicKey">API Key</Label>
                <div className="relative">
                  <Input
                    id="anthropicKey"
                    type={showKeys.anthropic ? "text" : "password"}
                    value={config.aiConfig.antropic.apiKey}
                    onChange={(e) =>
                      updateAIConfig({
                        antropic: { ...config.aiConfig.antropic, apiKey: e.target.value },
                      })
                    }
                    placeholder="sk-ant-..."
                    className="pr-10 font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => toggleShowKey("anthropic")}
                  >
                    {showKeys.anthropic ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="anthropicModel">Preferred Model</Label>
                <Input
                  id="anthropicModel"
                  value={config.aiConfig.antropic.preferredModel}
                  onChange={(e) =>
                    updateAIConfig({
                      antropic: { ...config.aiConfig.antropic, preferredModel: e.target.value },
                    })
                  }
                  placeholder="claude-4-5-sonnet"
                />
              </div>
            </TabsContent>

            <TabsContent value="gemini" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="geminiKey">API Key</Label>
                <div className="relative">
                  <Input
                    id="geminiKey"
                    type={showKeys.gemini ? "text" : "password"}
                    value={config.aiConfig.gemini.apiKey}
                    onChange={(e) =>
                      updateAIConfig({
                        gemini: { ...config.aiConfig.gemini, apiKey: e.target.value },
                      })
                    }
                    placeholder="API Key"
                    className="pr-10 font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => toggleShowKey("gemini")}
                  >
                    {showKeys.gemini ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="geminiModel">Preferred Model</Label>
                <Input
                  id="geminiModel"
                  value={config.aiConfig.gemini.preferredModel}
                  onChange={(e) =>
                    updateAIConfig({
                      gemini: { ...config.aiConfig.gemini, preferredModel: e.target.value },
                    })
                  }
                  placeholder="gemini-2.5-flash"
                />
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mic className="h-5 w-5 text-primary" />
              ElevenLabs
            </CardTitle>
            <CardDescription>Voice synthesis configuration.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="elevenKey">API Key</Label>
              <div className="relative">
                <Input
                  id="elevenKey"
                  type={showKeys.elevenlabs ? "text" : "password"}
                  value={config.aiConfig.elevenlabs.apiKey}
                  onChange={(e) =>
                    updateAIConfig({
                      elevenlabs: { apiKey: e.target.value },
                    })
                  }
                  placeholder="API Key"
                  className="pr-10 font-mono"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                  onClick={() => toggleShowKey("elevenlabs")}
                >
                  {showKeys.elevenlabs ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Orchestrator
            </CardTitle>
            <CardDescription>AI orchestration settings.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="orchProvider">Provider</Label>
              <Select
                value={config.aiConfig.orchestrator.preferredAiProvider}
                onValueChange={(value) =>
                  updateAIConfig({
                    orchestrator: { ...config.aiConfig.orchestrator, preferredAiProvider: value },
                  })
                }
              >
                <SelectTrigger id="orchProvider">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {aiProviders.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="orchModel">Model</Label>
              <Input
                id="orchModel"
                value={config.aiConfig.orchestrator.preferredModel}
                onChange={(e) =>
                  updateAIConfig({
                    orchestrator: { ...config.aiConfig.orchestrator, preferredModel: e.target.value },
                  })
                }
                placeholder="gemini-2.5-flash"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Real-Time Configuration</CardTitle>
          <CardDescription>
            Settings for real-time AI voice interactions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="rtModel">Model</Label>
              <Input
                id="rtModel"
                value={config.aiConfig.realTimeConfig.realTimeModel}
                onChange={(e) =>
                  updateAIConfig({
                    realTimeConfig: { ...config.aiConfig.realTimeConfig, realTimeModel: e.target.value },
                  })
                }
                placeholder="gpt-realtime-mini"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rtKey">API Key</Label>
              <div className="relative">
                <Input
                  id="rtKey"
                  type={showKeys.realtime ? "text" : "password"}
                  value={config.aiConfig.realTimeConfig.apiKey}
                  onChange={(e) =>
                    updateAIConfig({
                      realTimeConfig: { ...config.aiConfig.realTimeConfig, apiKey: e.target.value },
                    })
                  }
                  placeholder="sk-..."
                  className="pr-10 font-mono"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                  onClick={() => toggleShowKey("realtime")}
                >
                  {showKeys.realtime ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rtVoice">Voice</Label>
              <Input
                id="rtVoice"
                value={config.aiConfig.realTimeConfig.voice}
                onChange={(e) =>
                  updateAIConfig({
                    realTimeConfig: { ...config.aiConfig.realTimeConfig, voice: e.target.value },
                  })
                }
                placeholder="sage"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
