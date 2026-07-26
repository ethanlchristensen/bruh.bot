import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useUpdateConfig } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardIcon } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { Server, Settings, Shield, Database, Users, Plus, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/layouts/page-header';
import { StickySaveBar } from '@/components/layouts/sticky-save-bar';

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

  const initialValuesRef = useRef<{
    invisible: boolean;
    mentionCooldown: number;
    adminIds: string;
    globalBlockList: string;
    dbName: string;
    collectionName: string;
    usersToId: string;
    idToUsers: string;
  } | null>(null);

  useEffect(() => {
    if (data?.config && !isSaving) {
      const config = data.config;
      const vals = {
        invisible: config.invisible || false,
        mentionCooldown: config.mentionCooldown || 0,
        adminIds: JSON.stringify(config.adminIds || []),
        globalBlockList: JSON.stringify(config.globalBlockList || []),
        dbName: config.mongoMessagesDbName || '',
        collectionName: config.mongoMessagesCollectionName || '',
        usersToId: JSON.stringify(config.usersToId || {}),
        idToUsers: JSON.stringify(config.idToUsers || {}),
      };
      if (!initialValuesRef.current) {
        initialValuesRef.current = vals;
      }
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

  const hasChanges = useMemo(() => {
    const iv = initialValuesRef.current;
    if (!iv) return false;
    return (
      invisible !== iv.invisible ||
      mentionCooldown !== iv.mentionCooldown ||
      JSON.stringify(adminIds) !== iv.adminIds ||
      JSON.stringify(globalBlockList) !== iv.globalBlockList ||
      dbName !== iv.dbName ||
      collectionName !== iv.collectionName ||
      JSON.stringify(usersToId) !== iv.usersToId ||
      JSON.stringify(idToUsers) !== iv.idToUsers
    );
  }, [invisible, mentionCooldown, adminIds, globalBlockList, dbName, collectionName, usersToId, idToUsers]);

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
        initialValuesRef.current = {
          invisible, mentionCooldown,
          adminIds: JSON.stringify(adminIds),
          globalBlockList: JSON.stringify(globalBlockList),
          dbName, collectionName,
          usersToId: JSON.stringify(usersToId),
          idToUsers: JSON.stringify(idToUsers),
        };
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
    <div className="space-y-8 pb-20" data-page="server">
      <PageHeader
        icon={<Server />}
        title="Server Settings"
        description="General configuration, security, and user management."
      />

      <StickySaveBar onSave={handleSave} isSaving={isSaving} hasChanges={hasChanges} />

      <div className="grid gap-8 lg:grid-cols-2">
        {/* General */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Settings /></CardIcon>
              <div>
                <CardTitle>General</CardTitle>
                <CardDescription>Visibility, timers, and basic controls.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
              <div className="space-y-1">
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
                className="h-10"
              />
            </div>
          </CardContent>
        </Card>

        {/* Security & Access */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Shield /></CardIcon>
              <div>
                <CardTitle>Security & Access</CardTitle>
                <CardDescription>Admin IDs and global block list.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Label className="font-semibold">Admin IDs</Label>
              <div className="flex gap-2">
                <Input value={newAdminId} onChange={(e) => setNewAdminId(e.target.value)} placeholder="Discord user ID" className="h-10" />
                <Button size="sm" className="h-10" onClick={() => { if (newAdminId.trim()) { setAdminIds([...adminIds, newAdminId.trim()]); setNewAdminId(''); } }}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {adminIds.map((id) => (
                  <div key={id} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 text-sm">
                    <code className="text-xs">{id}</code>
                    <button onClick={() => setAdminIds(adminIds.filter((a) => a !== id))} className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <Label className="font-semibold">Global Block List</Label>
              <div className="flex gap-2">
                <Input value={newBlockId} onChange={(e) => setNewBlockId(e.target.value)} placeholder="Discord user ID" className="h-10" />
                <Button size="sm" className="h-10" onClick={() => { if (newBlockId.trim()) { setGlobalBlockList([...globalBlockList, newBlockId.trim()]); setNewBlockId(''); } }}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {globalBlockList.map((id) => (
                  <div key={id} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 text-sm">
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

        {/* User Mappings */}
        <Card variant="hero" className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Users /></CardIcon>
              <div>
                <CardTitle>Discord User Mappings</CardTitle>
                <CardDescription>Map display names to Discord IDs for @mention resolution.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="Display name" className="flex-1 h-10" />
              <Input value={newDiscordId} onChange={(e) => setNewDiscordId(e.target.value)} placeholder="Discord ID" className="flex-1 h-10" />
              <Button size="sm" className="h-10" onClick={handleAddMapping}><Plus className="h-4 w-4" /></Button>
            </div>
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {Object.entries(usersToId).length === 0 ? (
                <p className="text-sm text-muted-foreground p-4 text-center">No mappings configured.</p>
              ) : (
                Object.entries(usersToId).map(([name, id]) => (
                  <div key={name} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 text-sm">
                    <span>{name} <span className="text-muted-foreground">→</span> <code className="text-xs">{id}</code></span>
                    <button onClick={() => handleRemoveMapping(name)} className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Database */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Database /></CardIcon>
              <div>
                <CardTitle>Database</CardTitle>
                <CardDescription>MongoDB collection names.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="db-name">Messages Database</Label>
                <Input id="db-name" value={dbName} onChange={(e) => setDbName(e.target.value)} placeholder="DiscordScrapeBot" className="h-10" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="collection-name">Messages Collection</Label>
                <Input id="collection-name" value={collectionName} onChange={(e) => setCollectionName(e.target.value)} placeholder="Messages" className="h-10" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Separator() {
  return <div className="h-px bg-gradient-to-r from-border/60 via-border/30 to-transparent" />;
}