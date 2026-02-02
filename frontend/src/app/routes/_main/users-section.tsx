"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { BotConfig } from "@/lib/types"
import { ArrowLeftRight, Plus, Trash2, UserCircle } from "lucide-react"

interface UsersSectionProps {
  config: BotConfig
  onUpdate: (updates: Partial<BotConfig>) => void
}

export function UsersSection({ config, onUpdate }: UsersSectionProps) {
  const usersToIdEntries = Object.entries(config.usersToId)
  const idToUsersEntries = Object.entries(config.idToUsers)

  const updateUsersToId = (entries: [string, string][]) => {
    const newMapping: Record<string, string> = {}
    entries.forEach(([key, value]) => {
      if (key) newMapping[key] = value
    })
    onUpdate({ usersToId: newMapping })
  }

  const updateIdToUsers = (entries: [string, string][]) => {
    const newMapping: Record<string, string> = {}
    entries.forEach(([key, value]) => {
      if (key) newMapping[key] = value
    })
    onUpdate({ idToUsers: newMapping })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">User Mappings</h2>
        <p className="text-muted-foreground">
          Configure name-to-ID and ID-to-name mappings for Discord users.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCircle className="h-5 w-5 text-primary" />
            Users to ID
          </CardTitle>
          <CardDescription>
            Map display names to Discord mention strings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {usersToIdEntries.map(([name, mention], index) => (
            <div key={index} className="flex items-center gap-3">
              <div className="flex-1 space-y-1">
                <Label className="text-xs text-muted-foreground">Name</Label>
                <Input
                  value={name}
                  onChange={(e) => {
                    const newEntries = [...usersToIdEntries]
                    newEntries[index] = [e.target.value, mention]
                    updateUsersToId(newEntries)
                  }}
                  placeholder="username"
                />
              </div>
              <ArrowLeftRight className="h-4 w-4 text-muted-foreground shrink-0 mt-6" />
              <div className="flex-1 space-y-1">
                <Label className="text-xs text-muted-foreground">Mention</Label>
                <Input
                  value={mention}
                  onChange={(e) => {
                    const newEntries = [...usersToIdEntries]
                    newEntries[index] = [name, e.target.value]
                    updateUsersToId(newEntries)
                  }}
                  placeholder="<@000000000000000000>"
                  className="font-mono"
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 mt-6 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  const newEntries = usersToIdEntries.filter((_, i) => i !== index)
                  updateUsersToId(newEntries)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="w-full bg-transparent"
            onClick={() => {
              updateUsersToId([...usersToIdEntries, ["", ""]])
            }}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Mapping
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-primary" />
            ID to Users
          </CardTitle>
          <CardDescription>
            Map Discord user IDs to display names.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {idToUsersEntries.map(([id, name], index) => (
            <div key={index} className="flex items-center gap-3">
              <div className="flex-1 space-y-1">
                <Label className="text-xs text-muted-foreground">User ID</Label>
                <Input
                  value={id}
                  onChange={(e) => {
                    const newEntries = [...idToUsersEntries]
                    newEntries[index] = [e.target.value, name]
                    updateIdToUsers(newEntries)
                  }}
                  placeholder="000000000000000000"
                  className="font-mono"
                />
              </div>
              <ArrowLeftRight className="h-4 w-4 text-muted-foreground shrink-0 mt-6" />
              <div className="flex-1 space-y-1">
                <Label className="text-xs text-muted-foreground">Name</Label>
                <Input
                  value={name}
                  onChange={(e) => {
                    const newEntries = [...idToUsersEntries]
                    newEntries[index] = [id, e.target.value]
                    updateIdToUsers(newEntries)
                  }}
                  placeholder="username"
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0 mt-6 text-muted-foreground hover:text-destructive"
                onClick={() => {
                  const newEntries = idToUsersEntries.filter((_, i) => i !== index)
                  updateIdToUsers(newEntries)
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            className="w-full bg-transparent"
            onClick={() => {
              updateIdToUsers([...idToUsersEntries, ["", ""]])
            }}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Mapping
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
