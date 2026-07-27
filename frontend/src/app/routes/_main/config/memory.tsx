import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useUpdateConfig } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardIcon } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { BrainCircuit } from 'lucide-react';
import { PageHeader } from '@/components/layouts/page-header';
import { StickySaveBar } from '@/components/layouts/sticky-save-bar';

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
  const [embeddingModel, setEmbeddingModel] = useState('openai/text-embedding-3-small');
  const [maxToolRounds, setMaxToolRounds] = useState(8);
  const [maxToolCallsPerBatch, setMaxToolCallsPerBatch] = useState(40);
  const [maxAddsPerUserPerBatch, setMaxAddsPerUserPerBatch] = useState(10);
  const [dedupeThreshold, setDedupeThreshold] = useState(0.92);
  const [semanticRetrieval, setSemanticRetrieval] = useState(true);
  const [retrievalMinScore, setRetrievalMinScore] = useState(0.35);

  const initialValuesRef = useRef<{
    memoryEnabled: boolean;
    memoryExtractionInterval: number;
    memoryMoodInterval: number;
    memoryExtractionModel: string;
    memoryMaxMessages: number;
    memoryMinMessages: number;
    memoryMinLength: number;
    memoryMaxPerUser: number;
    memoryMaxInjection: number;
    embeddingModel: string;
    maxToolRounds: number;
    maxToolCallsPerBatch: number;
    maxAddsPerUserPerBatch: number;
    dedupeThreshold: number;
    semanticRetrieval: boolean;
    retrievalMinScore: number;
  } | null>(null);

  useEffect(() => {
    if (data?.config && !isSaving) {
      const memCfg = data.config.memoryConfig || {};
      const vals = {
        memoryEnabled: memCfg.enabled ?? true,
        memoryExtractionInterval: memCfg.extractionIntervalMinutes ?? 20,
        memoryMoodInterval: memCfg.moodExtractionIntervalMinutes ?? 5,
        memoryExtractionModel: memCfg.extractionModel || 'deepseek/deepseek-v4-flash',
        memoryMaxMessages: memCfg.maxMessagesPerExtraction ?? 50,
        memoryMinMessages: memCfg.minMessagesForExtraction ?? 5,
        memoryMinLength: memCfg.minMessageLength ?? 10,
        memoryMaxPerUser: memCfg.maxMemoriesPerUser ?? 50,
        memoryMaxInjection: memCfg.maxInjectionCount ?? 10,
        embeddingModel: memCfg.embeddingModel || 'openai/text-embedding-3-small',
        maxToolRounds: memCfg.maxToolRounds ?? 8,
        maxToolCallsPerBatch: memCfg.maxToolCallsPerBatch ?? 40,
        maxAddsPerUserPerBatch: memCfg.maxAddsPerUserPerBatch ?? 10,
        dedupeThreshold: memCfg.dedupeThreshold ?? 0.92,
        semanticRetrieval: memCfg.semanticRetrieval ?? true,
        retrievalMinScore: memCfg.retrievalMinScore ?? 0.35,
      };
      if (!initialValuesRef.current) {
        initialValuesRef.current = vals;
      }
      setMemoryEnabled(vals.memoryEnabled);
      setMemoryExtractionInterval(vals.memoryExtractionInterval);
      setMemoryMoodInterval(vals.memoryMoodInterval);
      setMemoryExtractionModel(vals.memoryExtractionModel);
      setMemoryMaxMessages(vals.memoryMaxMessages);
      setMemoryMinMessages(vals.memoryMinMessages);
      setMemoryMinLength(vals.memoryMinLength);
      setMemoryMaxPerUser(vals.memoryMaxPerUser);
      setMemoryMaxInjection(vals.memoryMaxInjection);
      setEmbeddingModel(vals.embeddingModel);
      setMaxToolRounds(vals.maxToolRounds);
      setMaxToolCallsPerBatch(vals.maxToolCallsPerBatch);
      setMaxAddsPerUserPerBatch(vals.maxAddsPerUserPerBatch);
      setDedupeThreshold(vals.dedupeThreshold);
      setSemanticRetrieval(vals.semanticRetrieval);
      setRetrievalMinScore(vals.retrievalMinScore);
    }
  }, [data, isSaving]);

  const hasChanges = useMemo(() => {
    const iv = initialValuesRef.current;
    if (!iv) return false;
    return (
      memoryEnabled !== iv.memoryEnabled ||
      memoryExtractionInterval !== iv.memoryExtractionInterval ||
      memoryMoodInterval !== iv.memoryMoodInterval ||
      memoryExtractionModel !== iv.memoryExtractionModel ||
      memoryMaxMessages !== iv.memoryMaxMessages ||
      memoryMinMessages !== iv.memoryMinMessages ||
      memoryMinLength !== iv.memoryMinLength ||
      memoryMaxPerUser !== iv.memoryMaxPerUser ||
      memoryMaxInjection !== iv.memoryMaxInjection ||
      embeddingModel !== iv.embeddingModel ||
      maxToolRounds !== iv.maxToolRounds ||
      maxToolCallsPerBatch !== iv.maxToolCallsPerBatch ||
      maxAddsPerUserPerBatch !== iv.maxAddsPerUserPerBatch ||
      dedupeThreshold !== iv.dedupeThreshold ||
      semanticRetrieval !== iv.semanticRetrieval ||
      retrievalMinScore !== iv.retrievalMinScore
    );
  }, [
    memoryEnabled, memoryExtractionInterval, memoryMoodInterval,
    memoryExtractionModel, memoryMaxMessages, memoryMinMessages,
    memoryMinLength, memoryMaxPerUser, memoryMaxInjection,
    embeddingModel, maxToolRounds, maxToolCallsPerBatch,
    maxAddsPerUserPerBatch, dedupeThreshold, semanticRetrieval, retrievalMinScore,
  ]);

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
            embeddingModel,
            maxToolRounds,
            maxToolCallsPerBatch,
            maxAddsPerUserPerBatch,
            dedupeThreshold,
            semanticRetrieval,
            retrievalMinScore,
          },
        });
        await queryClient.invalidateQueries({ queryKey: ['config'] });
        setIsSaving(false);
        initialValuesRef.current = {
          memoryEnabled, memoryExtractionInterval, memoryMoodInterval,
          memoryExtractionModel, memoryMaxMessages, memoryMinMessages,
          memoryMinLength, memoryMaxPerUser, memoryMaxInjection,
          embeddingModel, maxToolRounds, maxToolCallsPerBatch,
          maxAddsPerUserPerBatch, dedupeThreshold, semanticRetrieval, retrievalMinScore,
        };
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
    <div className="space-y-8 pb-20" data-page="memory">
      <PageHeader
        icon={<BrainCircuit />}
        title="Memory System"
        description="AI-powered user memory extraction and context injection."
      />

      <StickySaveBar onSave={handleSave} isSaving={isSaving} hasChanges={hasChanges} />

      <Card variant="hero">
        <CardHeader>
          <div className="flex items-center gap-4">
            <CardIcon><BrainCircuit /></CardIcon>
            <div>
              <CardTitle>Memory Extraction</CardTitle>
              <CardDescription>
                Configure how the bot observes messages and extracts user memories.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between p-5 rounded-xl bg-muted/30">
            <div className="space-y-1">
              <Label htmlFor="memory-enabled" className="font-semibold cursor-pointer text-base">Enable Extraction</Label>
              <p className="text-xs text-muted-foreground">Auto-extract memories from user messages</p>
            </div>
            <Switch
              id="memory-enabled"
              checked={memoryEnabled}
              onCheckedChange={setMemoryEnabled}
            />
          </div>

          <Separator label="Scheduling" />

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="memory-interval">Extraction Interval (minutes)</Label>
              <Input
                id="memory-interval"
                type="number"
                value={memoryExtractionInterval}
                onChange={(e) => setMemoryExtractionInterval(parseInt(e.target.value) || 20)}
                min={1}
                max={1440}
                className="h-10"
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
                className="h-10"
              />
            </div>
          </div>

          <Separator label="Model" />

          <div className="space-y-2">
            <Label htmlFor="memory-model">Extraction Model</Label>
            <Input
              id="memory-model"
              type="text"
              value={memoryExtractionModel}
              onChange={(e) => setMemoryExtractionModel(e.target.value)}
              placeholder="deepseek/deepseek-v4-flash"
              className="h-10"
            />
            <p className="text-xs text-muted-foreground">The LLM used to analyze messages and extract memories. Should be cheap and fast.</p>
          </div>

          <Separator label="Extraction Behavior" />

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="memory-max-msgs">Max Messages Per Batch</Label>
              <Input
                id="memory-max-msgs"
                type="number"
                value={memoryMaxMessages}
                onChange={(e) => setMemoryMaxMessages(parseInt(e.target.value) || 50)}
                min={1}
                max={200}
                className="h-10"
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
                className="h-10"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="memory-min-length">Min Message Length (chars)</Label>
              <Input
                id="memory-min-length"
                type="number"
                value={memoryMinLength}
                onChange={(e) => setMemoryMinLength(parseInt(e.target.value) || 10)}
                min={1}
                max={500}
                className="h-10"
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
                className="h-10"
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
              className="h-10"
            />
            <p className="text-xs text-muted-foreground">How many memories to include in the system prompt when users talk to the bot.</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Embeddings & Semantic Search</CardTitle>
          <CardDescription>
            Embeddings power semantic similarity search across memories. Requires MongoDB Atlas vector search index.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="embedding-model">Embedding Model</Label>
            <Input
              id="embedding-model"
              type="text"
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              placeholder="openai/text-embedding-3-small"
              className="h-10"
            />
            <p className="text-xs text-muted-foreground">OpenRouter model ID for generating memory embeddings. 1536-dimension models recommended.</p>
          </div>
          <div className="flex items-center justify-between p-5 rounded-xl bg-muted/30">
            <div className="space-y-1">
              <Label htmlFor="semantic-retrieval" className="font-semibold cursor-pointer text-base">Semantic Retrieval</Label>
              <p className="text-xs text-muted-foreground">Use vector search at chat time to find the most relevant memories for the current conversation</p>
            </div>
            <Switch
              id="semantic-retrieval"
              checked={semanticRetrieval}
              onCheckedChange={setSemanticRetrieval}
            />
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="retrieval-min-score">Retrieval Min Score</Label>
              <Input
                id="retrieval-min-score"
                type="number"
                step={0.01}
                value={retrievalMinScore}
                onChange={(e) => setRetrievalMinScore(parseFloat(e.target.value) || 0.35)}
                min={0}
                max={1}
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">Minimum cosine similarity for chat-time retrieval (0.0-1.0).</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="dedupe-threshold">Semantic Dedupe Threshold</Label>
              <Input
                id="dedupe-threshold"
                type="number"
                step={0.01}
                value={dedupeThreshold}
                onChange={(e) => setDedupeThreshold(parseFloat(e.target.value) || 0.92)}
                min={0}
                max={1}
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">When adding, auto-update existing memory if similarity {">="} this value.</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tool Agent Configuration</CardTitle>
          <CardDescription>
            The extraction LLM uses tool calling to search, add, update, and remove memories in an agentic loop.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="max-tool-rounds">Max Tool Rounds</Label>
              <Input
                id="max-tool-rounds"
                type="number"
                value={maxToolRounds}
                onChange={(e) => setMaxToolRounds(parseInt(e.target.value) || 8)}
                min={1}
                max={20}
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">Maximum number of LLM→tool→result loops per extraction batch.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="max-tool-calls">Max Tool Calls Per Batch</Label>
              <Input
                id="max-tool-calls"
                type="number"
                value={maxToolCallsPerBatch}
                onChange={(e) => setMaxToolCallsPerBatch(parseInt(e.target.value) || 40)}
                min={1}
                max={200}
                className="h-10"
              />
              <p className="text-xs text-muted-foreground">Hard limit on total tool calls to prevent runaway costs.</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="max-adds-per-user">Max Adds Per User Per Batch</Label>
              <Input
                id="max-adds-per-user"
                type="number"
                value={maxAddsPerUserPerBatch}
                onChange={(e) => setMaxAddsPerUserPerBatch(parseInt(e.target.value) || 10)}
                min={1}
                max={50}
                className="h-10"
              />
            </div>
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
          <div className="grid gap-3 md:grid-cols-2">
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
              <div key={cat} className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
                <div>
                  <span className="font-semibold text-sm capitalize">{cat}</span>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${retention === 'Permanent' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
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

function Separator({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-px flex-1 bg-gradient-to-r from-border/60 to-transparent" />
      {label && <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground shrink-0">{label}</span>}
      {label && <div className="h-px flex-1 bg-gradient-to-l from-border/60 to-transparent" />}
    </div>
  );
}