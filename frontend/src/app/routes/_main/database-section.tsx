"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { BotConfig } from "@/lib/types"
import { Database, Eye, EyeOff, FileText, FolderOpen } from "lucide-react"
import { useState } from "react"

interface DatabaseSectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}

export function DatabaseSection({ config, onUpdate }: DatabaseSectionProps) {
  const [showUri, setShowUri] = useState(false)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Database</h2>
        <p className="text-muted-foreground">
          Configure MongoDB connection and collection settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            MongoDB Connection
          </CardTitle>
          <CardDescription>
            Database connection string and name.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="mongoUri">Connection URI</Label>
            <div className="relative">
              <Input
                id="mongoUri"
                type={showUri ? "text" : "password"}
                value={config.mongoUri}
                onChange={(e) => onUpdate({ mongoUri: e.target.value })}
                placeholder="mongodb://localhost:27017/"
                className="pr-10 font-mono"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                onClick={() => setShowUri(!showUri)}
              >
                {showUri ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="mongoDb">Database Name</Label>
            <Input
              id="mongoDb"
              value={config.mongoDbName}
              onChange={(e) => onUpdate({ mongoDbName: e.target.value })}
              placeholder="DB"
              className="font-mono"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5 text-primary" />
            Collections
          </CardTitle>
          <CardDescription>
            MongoDB collection names for different data types.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="messagesCollection">Messages Collection</Label>
            <Input
              id="messagesCollection"
              value={config.mongoMessagesCollectionName}
              onChange={(e) => onUpdate({ mongoMessagesCollectionName: e.target.value })}
              placeholder="COLLECTION"
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="morningCollection">Morning Configs Collection</Label>
            <Input
              id="morningCollection"
              value={config.mongoMorningConfigsCollectionName}
              onChange={(e) => onUpdate({ mongoMorningConfigsCollectionName: e.target.value })}
              placeholder="MORNING_CONFIGS"
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="imageLimitsCollection">Image Limits Collection</Label>
            <Input
              id="imageLimitsCollection"
              value={config.mongoImageLimitsCollectionName}
              onChange={(e) => onUpdate({ mongoImageLimitsCollectionName: e.target.value })}
              placeholder="IMAGE_LIMITS"
              className="font-mono"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Prompts
          </CardTitle>
          <CardDescription>
            Path to the prompts configuration file.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="promptsPath">Prompts File Path</Label>
            <Input
              id="promptsPath"
              value={config.promptsPath}
              onChange={(e) => onUpdate({ promptsPath: e.target.value })}
              placeholder="prompts.json"
              className="font-mono"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
