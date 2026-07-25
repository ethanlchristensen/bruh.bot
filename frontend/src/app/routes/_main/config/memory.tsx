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
import { Save, BrainCircuit } from 'lucide-react';

export const Route = createFileRoute('/_main/config/memory')({
  component: MemoryConfigComponent,
});

function MemoryConfigComponent() {
  const { data, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();
  const queryClient = useQueryClient();

  const [isSaving, setIsSaving] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [memoryExtractionInterval, setMemoryExtractionInterval] = useState(20);
  const [memoryMoodInterval, setMemoryMoodInterval] = useState(5);
  const [memoryExtractionModel, setMemoryExtractionModel] = useState('deepseek/deepseek-v4-flash');
  const [memoryMaxMessages, setMemoryMaxMessages] = useState(50);
  const [memoryMinMessages, setMemoryMinMessages] = useState(5);
  const [memoryMinLength, setMemoryMinLength] = useState(10);
  const [memoryMaxPerUser, setMemoryMaxPerUser] = useState(50);
  const [memoryMaxInjection, setMemoryMaxInjection] = useState(10);

  useEffect(() => {
    if (data?.config && !isSaving) {
      const memCfg = data.config.memoryConfig || {};
      setMemoryEnabled(memCfg.enabled ?? true);
      setMemoryExtractionInterval(memCfg.extractionIntervalMinutes ?? 20);
      setMemoryMoodInterval(memCfg.moodExtractionIntervalMinutes ?? 5);
      setMemoryExtractionModel(memCfg.extractionModel || 'deepseek/deepseek-v4-flash');
      setMemoryMaxMessages(memCfg.maxMessagesPerExtraction ?? 50);
      setMemoryMinMessages(memCfg.minMessagesForExtraction ?? 5);
      setMemoryMinLength(memCfg.minMessageLength ?? 10);
      setMemoryMaxPerUser(memCfg.maxMemoriesPerUser ?? 50);
      setMemoryMaxInjection(memCfg.maxInjectionCount ?? 10);
    }
  }, [data, isSaving]);

  const handleSave = async () => {
    setIsSaving(true);
    const savePromise = new Promise(async (resolve, reject) => {
      try {
        await updateConfig.mutateAsync({
          memoryConfig: {
            enabled: memoryEnabled,
            extractionIntervalMinutes: memoryExtractionInterval,
            moodExtractionIntervalMinutes: memoryMoodInterval,
            extractionModel: memoryExtractionModel,
            maxMessagesPerExtraction: memoryMaxMessages,
            minMessagesForExtraction: memoryMinMessages,
            minMessageLength: memoryMinLength,
            maxMemoriesPerUser: memoryMaxPerUser,
            maxInjectionCount: memoryMaxInjection,
          },
        });
        await queryClient.invalidateQueries({ queryKey: ['config'] });
        setIsSaving(false);
        resolve('Memory configuration saved!');
      } catch (err) {
        setIsSaving(false);
        reject(err instanceof Error ? err.message : 'Error saving memory config');
      }
    });

    toast.promise(savePromise, {
      loading: 'Saving memory configuration...',
      success: (msg) => `${msg}`,
      error: (err) => `Failed to save: ${err}`,
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">Loading memory configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Memory System</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered user memory extraction and context injection.
          </p>
        </div>
        <Button onClick={handleSave} className="gap-2">
          <Save className="h-4 w-4" />
          Save Changes
        </Button>
      </div>

      <Card className="border-primary/20 shadow-md">
        <CardHeader className="flex flex-row items-center gap-4">
          <div className="p-2 bg-primary/10 rounded-lg text-primary">
            <BrainCircuit className="h-6 w-6" />
          </div>
          <div>
            <CardTitle>Memory Extraction</CardTitle>
            <CardDescription>
              Configure how the bot observes messages and extracts user memories.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between p-4 rounded-lg bg-muted/40">
            <div className="space-y-0.5">
              <Label htmlFor="memory-enabled" className="font-semibold cursor-pointer">Enable Extraction</Label>
              <p className="text-xs text-muted-foreground">Auto-extract memories from user messages</p>
            </div>
            <Switch
              id="memory-enabled"
              checked={memoryEnabled}
              onCheckedChange={setMemoryEnabled}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="memory-interval">Extraction Interval (minutes)</Label>
              <Input
                id="memory-interval"
                type="number"
                value={memoryExtractionInterval}
                onChange={(e) => setMemoryExtractionInterval(parseInt(e.target.value) || 20)}
                min={1}
                max={1440}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="memory-mood-interval">Mood Interval (minutes)</Label>
              <Input
                id="memory-mood-interval"
                type="number"
                value={memoryMoodInterval}
                onChange={(e) => setMemoryMoodInterval(parseInt(e.target.value) || 5)}
                min={1}
                max={1440}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="memory-model">Extraction Model</Label>
            <Input
              id="memory-model"
              type="text"
              value={memoryExtractionModel}
              onChange={(e) => setMemoryExtractionModel(e.target.value)}
              placeholder="deepseek/deepseek-v4-flash"
            />
            <p className="text-xs text-muted-foreground">The LLM used to analyze messages and extract memories. Should be cheap and fast.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="memory-max-msgs">Max Messages Per Batch</Label>
              <Input
                id="memory-max-msgs"
                type="number"
                value={memoryMaxMessages}
                onChange={(e) => setMemoryMaxMessages(parseInt(e.target.value) || 50)}
                min={1}
                max={200}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="memory-min-msgs">Min Messages to Trigger</Label>
              <Input
                id="memory-min-msgs"
                type="number"
                value={memoryMinMessages}
                onChange={(e) => setMemoryMinMessages(parseInt(e.target.value) || 5)}
                min={1}
                max={100}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="memory-min-length">Min Message Length (chars)</Label>
              <Input
                id="memory-min-length"
                type="number"
                value={memoryMinLength}
                onChange={(e) => setMemoryMinLength(parseInt(e.target.value) || 10)}
                min={1}
                max={500}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="memory-max-per-user">Max Memories Per User</Label>
              <Input
                id="memory-max-per-user"
                type="number"
                value={memoryMaxPerUser}
                onChange={(e) => setMemoryMaxPerUser(parseInt(e.target.value) || 50)}
                min={1}
                max={500}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="memory-max-injection">Max Injected Into Context</Label>
            <Input
              id="memory-max-injection"
              type="number"
              value={memoryMaxInjection}
              onChange={(e) => setMemoryMaxInjection(parseInt(e.target.value) || 10)}
              min={0}
              max={50}
            />
            <p className="text-xs text-muted-foreground">How many memories to include in the system prompt when users talk to the bot.</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Memory Categories</CardTitle>
          <CardDescription>
            Each category has its own retention policy. MongoDB TTL indexes handle auto-cleanup.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            {[
              { cat: 'identity', retention: 'Permanent', desc: 'Immutable facts like name, age, location' },
              { cat: 'trait', retention: 'Permanent', desc: 'Personality traits, skills, profession' },
              { cat: 'admin', retention: 'Permanent', desc: 'Manually added by server admins' },
              { cat: 'relationship', retention: 'Permanent', desc: 'How they feel about other users' },
              { cat: 'preference', retention: '90 days', desc: 'Likes, dislikes, favorites' },
              { cat: 'fact', retention: '90 days', desc: 'General facts about the user' },
              { cat: 'opinion', retention: '30 days', desc: 'Opinions on topics, beliefs' },
              { cat: 'mood', retention: '7 days', desc: 'Current emotional state, feelings' },
            ].map(({ cat, retention, desc }) => (
              <div key={cat} className="flex items-center justify-between p-3 rounded-lg bg-muted/40">
                <div>
                  <span className="font-semibold text-sm capitalize">{cat}</span>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                <span className={`text-xs font-bold px-2 py-1 rounded ${retention === 'Permanent' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                  {retention}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}