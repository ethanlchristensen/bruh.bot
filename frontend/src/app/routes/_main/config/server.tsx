import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useUpdateConfig } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { Save, Settings, Shield, Database, Users, Plus, Trash2 } from 'lucide-react';

export const Route = createFileRoute('/_main/config/server')({
  component: ServerConfigComponent,
});

function ServerConfigComponent() {
  const { data, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();
  const queryClient = useQueryClient();

  const [isSaving, setIsSaving] = useState(false);
  const [invisible, setInvisible] = useState(false);
  const [mentionCooldown, setMentionCooldown] = useState(0);
  const [adminIds, setAdminIds] = useState<string[]>([]);
  const [globalBlockList, setGlobalBlockList] = useState<string[]>([]);
  const [newAdminId, setNewAdminId] = useState('');
  const [newBlockId, setNewBlockId] = useState('');
  const [dbName, setDbName] = useState('');
  const [collectionName, setCollectionName] = useState('');
  const [usersToId, setUsersToId] = useState<Record<string, string>>({});
  const [idToUsers, setIdToUsers] = useState<Record<string, string>>({});
  const [newUsername, setNewUsername] = useState('');
  const [newDiscordId, setNewDiscordId] = useState('');

  useEffect(() => {
    if (data?.config && !isSaving) {
      const config = data.config;
      setInvisible(config.invisible || false);
      setMentionCooldown(config.mentionCooldown || 0);
      setAdminIds(config.adminIds || []);
      setGlobalBlockList(config.globalBlockList || []);
      setDbName(config.mongoMessagesDbName || '');
      setCollectionName(config.mongoMessagesCollectionName || '');
      setUsersToId(config.usersToId || {});
      setIdToUsers(config.idToUsers || {});
    }
  }, [data, isSaving]);

  const handleSave = async () => {
    setIsSaving(true);
    const savePromise = new Promise(async (resolve, reject) => {
      try {
        await updateConfig.mutateAsync({
          invisible,
          mentionCooldown,
          adminIds,
          globalBlockList,
          mongoMessagesDbName: dbName,
          mongoMessagesCollectionName: collectionName,
          usersToId,
          idToUsers,
        });
        await queryClient.invalidateQueries({ queryKey: ['config'] });
        setIsSaving(false);
        resolve('Server configuration saved!');
      } catch (err) {
        setIsSaving(false);
        reject(err instanceof Error ? err.message : 'Error saving server config');
      }
    });

    toast.promise(savePromise, {
      loading: 'Saving server configuration...',
      success: (msg) => `${msg}`,
      error: (err) => `Failed to save: ${err}`,
    });
  };

  const handleAddMapping = () => {
    if (!newUsername || !newDiscordId) {
      toast.error('Please enter both username and Discord ID.');
      return;
    }
    const username = newUsername.trim();
    const discordId = newDiscordId.trim();
    setUsersToId((prev) => ({ ...prev, [username]: discordId }));
    setIdToUsers((prev) => {
      if (prev[discordId]) return prev;
      return { ...prev, [discordId]: username };
    });
    setNewUsername('');
    setNewDiscordId('');
    toast.success(`Added mapping: ${username} -> ${discordId}`);
  };

  const handleRemoveMapping = (username: string) => {
    const discordId = usersToId[username];
    const nextUsersToId = { ...usersToId };
    delete nextUsersToId[username];
    setUsersToId(nextUsersToId);
    if (discordId) {
      const nextIdToUsers = { ...idToUsers };
      const remaining = Object.entries(nextUsersToId).filter(([, id]) => id === discordId).map(([u]) => u);
      if (remaining.length > 0) {
        nextIdToUsers[discordId] = remaining[0];
      } else {
        delete nextIdToUsers[discordId];
      }
      setIdToUsers(nextIdToUsers);
    }
    toast.success(`Removed mapping for ${username}`);
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">Loading server configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Server Settings</h1>
          <p className="text-sm text-muted-foreground">
            General configuration, security, and user management.
          </p>
        </div>
        <Button onClick={handleSave} className="gap-2">
          <Save className="h-4 w-4" />
          Save Changes
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Settings className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>General</CardTitle>
                <CardDescription>Visibility, timers, and basic controls.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40">
                <div className="space-y-0.5">
                  <Label htmlFor="invisible-mode" className="font-semibold cursor-pointer">Invisible Mode</Label>
                  <p className="text-xs text-muted-foreground">Bot stays hidden from server lists</p>
                </div>
                <Switch id="invisible-mode" checked={invisible} onCheckedChange={setInvisible} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cooldown">Mention Cooldown (seconds)</Label>
                <Input
                  id="cooldown"
                  type="number"
                  value={mentionCooldown}
                  onChange={(e) => setMentionCooldown(parseInt(e.target.value) || 0)}
                  min={0}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Security & Access</CardTitle>
                <CardDescription>Admin IDs and global block list.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="font-semibold">Admin IDs</Label>
                <div className="flex gap-2">
                  <Input value={newAdminId} onChange={(e) => setNewAdminId(e.target.value)} placeholder="Discord user ID" />
                  <Button size="sm" onClick={() => { if (newAdminId.trim()) { setAdminIds([...adminIds, newAdminId.trim()]); setNewAdminId(''); } }}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {adminIds.map((id) => (
                    <div key={id} className="flex items-center justify-between p-2 rounded bg-muted/40 text-sm">
                      <code className="text-xs">{id}</code>
                      <button onClick={() => setAdminIds(adminIds.filter((a) => a !== id))} className="text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2 border-t border-border/40 pt-4">
                <Label className="font-semibold">Global Block List</Label>
                <div className="flex gap-2">
                  <Input value={newBlockId} onChange={(e) => setNewBlockId(e.target.value)} placeholder="Discord user ID" />
                  <Button size="sm" onClick={() => { if (newBlockId.trim()) { setGlobalBlockList([...globalBlockList, newBlockId.trim()]); setNewBlockId(''); } }}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {globalBlockList.map((id) => (
                    <div key={id} className="flex items-center justify-between p-2 rounded bg-muted/40 text-sm">
                      <code className="text-xs">{id}</code>
                      <button onClick={() => setGlobalBlockList(globalBlockList.filter((b) => b !== id))} className="text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Users className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Discord User Mappings</CardTitle>
                <CardDescription>Map display names to Discord IDs for @mention resolution.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="Display name" className="flex-1" />
                <Input value={newDiscordId} onChange={(e) => setNewDiscordId(e.target.value)} placeholder="Discord ID" className="flex-1" />
                <Button size="sm" onClick={handleAddMapping}><Plus className="h-4 w-4" /></Button>
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {Object.entries(usersToId).length === 0 ? (
                  <p className="text-sm text-muted-foreground p-2">No mappings configured.</p>
                ) : (
                  Object.entries(usersToId).map(([name, id]) => (
                    <div key={name} className="flex items-center justify-between p-2 rounded bg-muted/40 text-sm">
                      <span>{name} → <code className="text-xs">{id}</code></span>
                      <button onClick={() => handleRemoveMapping(name)} className="text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Database className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Database</CardTitle>
                <CardDescription>MongoDB collection names.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="db-name">Messages Database</Label>
                <Input id="db-name" value={dbName} onChange={(e) => setDbName(e.target.value)} placeholder="DiscordScrapeBot" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="collection-name">Messages Collection</Label>
                <Input id="collection-name" value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="Messages" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}