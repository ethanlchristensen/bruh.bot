import { createFileRoute } from '@tanstack/react-router';
import { AlertTriangle, BrainCircuit, CheckCircle, Clock, Search, Shield, Trash2, Users } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import type { MemoryItem } from '@/lib/api-client';
import { useDeleteMemory, useUserMemories, useUsers } from '@/hooks/use-config';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';

export const Route = createFileRoute('/_main/config/memories')({
  component: MemoriesViewerComponent,
});

const CATEGORY_COLORS: Record<string, string> = {
  identity: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  trait: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  admin: 'bg-red-500/10 text-red-400 border-red-500/20',
  relationship: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  preference: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  fact: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  opinion: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  mood: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
};

const CATEGORY_RETENTION: Record<string, string> = {
  identity: 'Permanent',
  trait: 'Permanent',
  admin: 'Permanent',
  relationship: 'Permanent',
  preference: '90 days',
  fact: '90 days',
  opinion: '30 days',
  mood: '7 days',
};

function getExpiryStatus(memory: MemoryItem): { label: string; icon: typeof Shield; className: string } {
  if (memory.is_permanent) {
    return { label: 'Permanent', icon: Shield, className: 'text-violet-400' };
  }
  if (memory.is_expired) {
    return { label: 'Expired', icon: AlertTriangle, className: 'text-red-400' };
  }
  if (memory.expires_at) {
    const expiresDate = new Date(memory.expires_at);
    const now = new Date();
    const daysLeft = Math.ceil((expiresDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (daysLeft <= 1) {
      return { label: `Expires in ${daysLeft}d`, icon: AlertTriangle, className: 'text-red-400' };
    }
    if (daysLeft <= 7) {
      return { label: `Expires in ${daysLeft}d`, icon: Clock, className: 'text-yellow-400' };
    }
    return { label: `Expires in ${daysLeft}d`, icon: Clock, className: 'text-muted-foreground' };
  }
  return { label: 'No expiry', icon: Clock, className: 'text-muted-foreground' };
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleString();
}

function MemoriesViewerComponent() {
  const { data: usersData, isLoading: usersLoading } = useUsers();
  const [searchUserId, setSearchUserId] = useState<string | null>(null);
  const [manualUserId, setManualUserId] = useState('');
  const { data, isLoading, isError, error } = useUserMemories(searchUserId ?? '');
  const deleteMemory = useDeleteMemory();

  const handleSelectUser = (value: string) => {
    setSearchUserId(value);
    setManualUserId('');
  };

  const handleManualSearch = () => {
    const id = manualUserId.trim();
    if (!id) {
      toast.error('Please enter a valid Discord user ID');
      return;
    }
    setSearchUserId(id);
  };

  const handleDelete = async (memoryId: string) => {
    try {
      await deleteMemory.mutateAsync(memoryId);
      toast.success('Memory deleted');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete memory');
    }
  };

  const users = useMemo(
    () => [...(usersData?.users ?? [])].sort((a, b) => b.memory_count - a.memory_count),
    [usersData],
  );
  const memories = data?.memories ?? [];

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">User Memories</h1>
          <p className="text-sm text-muted-foreground">
            View and manage extracted memories for any Discord user.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-4">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <Users className="h-6 w-6" />
          </div>
          <div>
            <CardTitle>Select User</CardTitle>
            <CardDescription>Choose a known user or enter a Discord ID manually.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Users with Memories</Label>
            <Select onValueChange={handleSelectUser} value={searchUserId ?? ''}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={usersLoading ? 'Loading users...' : 'Select a user...'} />
              </SelectTrigger>
              <SelectContent>
                {users.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    <span className="flex items-center justify-between w-full gap-2">
                      <span className="truncate">{user.username}</span>
                      <span className="text-xs text-muted-foreground shrink-0">{user.memory_count} memories</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {users.length} {users.length === 1 ? 'user' : 'users'} found in memories collection
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Separator className="flex-1" />
            <span className="text-xs text-muted-foreground px-2">or</span>
            <Separator className="flex-1" />
          </div>

          <div className="space-y-2">
            <Label htmlFor="manual-user-id">Manual Discord ID</Label>
            <div className="flex gap-2">
              <Input
                id="manual-user-id"
                type="text"
                value={manualUserId}
                onChange={(e) => setManualUserId(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleManualSearch(); }}
                placeholder="Enter Discord user ID..."
              />
              <Button onClick={handleManualSearch} className="gap-2 shrink-0">
                <Search className="h-4 w-4" />
                Lookup
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <div className="flex h-40 flex-col items-center justify-center gap-4">
          <Spinner className="h-8 w-8 text-primary" />
          <p className="text-sm text-muted-foreground animate-pulse">Loading memories...</p>
        </div>
      )}

      {
  searchUserId && !isLoading && isError && (
    <Card className="border-destructive/20">
          <CardContent className="py-8 text-center">
            <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              Failed to load memories: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </CardContent>
        </Card>
      )}

      {searchUserId && !isLoading && !isError && (
        <>
          <div className="flex items-center gap-3">
            <CheckCircle className="h-5 w-5 text-emerald-400" />
            <div>
              <p className="text-sm font-medium">
                User ID: <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{searchUserId}</code>
              </p>
              <p className="text-xs text-muted-foreground">
                {memories.length} {memories.length === 1 ? 'memory' : 'memories'} found
              </p>
            </div>
          </div>

          <Separator />

          {memories.length === 0 ? (
            <Card className="border-muted">
              <CardContent className="py-8 text-center">
                <BrainCircuit className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No memories found for this user.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {memories.map((memory) => {
                const expiry = getExpiryStatus(memory);
                return (
                  <Card key={memory.id} className={`border-border/40 ${memory.is_expired ? 'opacity-50' : ''}`}>
                    <CardContent className="py-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0 space-y-2">
                          <p className="text-sm leading-relaxed">{memory.memory}</p>

                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className={`text-xs capitalize ${CATEGORY_COLORS[memory.category] || 'bg-muted'}`}>
                              {memory.category}
                            </Badge>

                            <div className={`flex items-center gap-1 text-xs ${expiry.className}`}>
                              <expiry.icon className="h-3 w-3" />
                              {expiry.label}
                            </div>

                            <span className="text-xs text-muted-foreground">
                              {Math.round(memory.confidence * 100)}% confidence
                            </span>

                            {memory.created_by === 'admin' && (
                              <Badge variant="secondary" className="text-xs">Manual</Badge>
                            )}
                          </div>

                          <div className="flex gap-4 text-xs text-muted-foreground">
                            <span>Created: {formatDate(memory.created_at)}</span>
                            {memory.updated_at && memory.updated_at !== memory.created_at && (
                              <span>Updated: {formatDate(memory.updated_at)}</span>
                            )}
                          </div>

                          {memory.target_user_id && (
                            <p className="text-xs text-muted-foreground">
                              Target user: <code className="text-xs">{memory.target_user_id}</code>
                            </p>
                          )}
                        </div>

                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive shrink-0"
                          onClick={() => handleDelete(memory.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          <Card className="border-muted bg-muted/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Category Retention Reference</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(CATEGORY_RETENTION).map(([cat, retention]) => (
                  <div key={cat} className="flex items-center justify-between p-2 rounded bg-muted/30 text-xs">
                    <span className="capitalize font-medium">{cat}</span>
                    <span className="text-muted-foreground">{retention}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}