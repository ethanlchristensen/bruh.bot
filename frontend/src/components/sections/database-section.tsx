import { Database, FileText, FolderOpen, Save } from 'lucide-react'
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

interface DatabaseSectionProps {
  config: DynamicConfig
  onUpdate: (updates: Partial<DynamicConfig>) => void
}

export function DatabaseSection({ config, onUpdate }: DatabaseSectionProps) {
  const [localPromptsPath, setLocalPromptsPath] = useState(config.promptsPath)
  const [localMessagesDb, setLocalMessagesDb] = useState(
    config.mongoMessagesDbName,
  )
  const [localMessagesCollection, setLocalMessagesCollection] = useState(
    config.mongoMessagesCollectionName,
  )
  const [localMorningCollection, setLocalMorningCollection] = useState(
    config.mongoMorningConfigsCollectionName,
  )
  const [localImageLimitsCollection, setLocalImageLimitsCollection] = useState(
    config.mongoImageLimitsCollectionName,
  )

  useEffect(() => {
    setLocalPromptsPath(config.promptsPath)
    setLocalMessagesDb(config.mongoMessagesDbName)
    setLocalMessagesCollection(config.mongoMessagesCollectionName)
    setLocalMorningCollection(config.mongoMorningConfigsCollectionName)
    setLocalImageLimitsCollection(config.mongoImageLimitsCollectionName)
  }, [config])

  const hasChanges =
    localPromptsPath !== config.promptsPath ||
    localMessagesDb !== config.mongoMessagesDbName ||
    localMessagesCollection !== config.mongoMessagesCollectionName ||
    localMorningCollection !== config.mongoMorningConfigsCollectionName ||
    localImageLimitsCollection !== config.mongoImageLimitsCollectionName

  const handleSave = () => {
    onUpdate({
      promptsPath: localPromptsPath,
      mongoMessagesDbName: localMessagesDb,
      mongoMessagesCollectionName: localMessagesCollection,
      mongoMorningConfigsCollectionName: localMorningCollection,
      mongoImageLimitsCollectionName: localImageLimitsCollection,
    })
  }

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
            MongoDB Database
          </CardTitle>
          <CardDescription>Database name for storing bot data.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="mongoMessagesDb">Messages Database Name</Label>
            <Input
              id="mongoMessagesDb"
              value={localMessagesDb}
              onChange={(e) => setLocalMessagesDb(e.target.value)}
              placeholder="DB"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              Note: MongoDB URI is configured in environment variables
            </p>
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
              value={localMessagesCollection}
              onChange={(e) => setLocalMessagesCollection(e.target.value)}
              placeholder="COLLECTION"
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="morningCollection">
              Morning Configs Collection
            </Label>
            <Input
              id="morningCollection"
              value={localMorningCollection}
              onChange={(e) => setLocalMorningCollection(e.target.value)}
              placeholder="MORNING_CONFIGS"
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="imageLimitsCollection">
              Image Limits Collection
            </Label>
            <Input
              id="imageLimitsCollection"
              value={localImageLimitsCollection}
              onChange={(e) => setLocalImageLimitsCollection(e.target.value)}
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
              value={localPromptsPath}
              onChange={(e) => setLocalPromptsPath(e.target.value)}
              placeholder="prompts.json"
              className="font-mono"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={!hasChanges}
          className="min-w-30"
        >
          <Save className="h-4 w-4 mr-2" />
          Save Changes
        </Button>
      </div>
    </div>
  )
}
