import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useUpdateAIProvider, useModels } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardIcon } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { OpenRouter, Ollama } from '@lobehub/icons';
import { ModelSelector, POPULAR_MODELS } from '@/components/model-selector';
import { PageHeader } from '@/components/layouts/page-header';
import { StickySaveBar } from '@/components/layouts/sticky-save-bar';
import { Sparkles, BrainCircuit, FileText, Server, Eye, EyeOff, Gauge } from 'lucide-react';

export const Route = createFileRoute('/_main/config/ai')({
  component: AIConfigComponent,
});

function AIConfigComponent() {
  const { data, isLoading } = useConfig();
  const updateProvider = useUpdateAIProvider();
  const queryClient = useQueryClient();

  const [isSaving, setIsSaving] = useState(false);
  const [preferredProvider, setPreferredProvider] = useState<'ollama' | 'openrouter'>('openrouter');
  const [orchestratorProvider, setOrchestratorProvider] = useState<'ollama' | 'openrouter'>('openrouter');
  const [orchestratorModel, setOrchestratorModel] = useState('');
  const [boostImagePrompts, setBoostImagePrompts] = useState(false);
  const [maxDailyImages, setMaxDailyImages] = useState(5);
  const [imageGenModel, setImageGenModel] = useState('');
  const [ollamaEndpoint, setOllamaEndpoint] = useState('');
  const [ollamaModel, setOllamaModel] = useState('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState('');
  const [openrouterModel, setOpenrouterModel] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [realtimePrompt, setRealtimePrompt] = useState('');
  const [usageLimitEnabled, setUsageLimitEnabled] = useState(true);
  const [maxRequestsPerMinute, setMaxRequestsPerMinute] = useState(5);
  const [maxRequestsPerHour, setMaxRequestsPerHour] = useState(50);

  const { data: ollamaModelsData, isLoading: isLoadingOllamaModels } = useModels('ollama', ollamaEndpoint);
  const { data: openrouterModelsData, isLoading: isLoadingOpenrouterModels } = useModels('openrouter');
  const { data: openrouterImageModelsData, isLoading: isLoadingOpenrouterImageModels } = useModels('openrouter', undefined, true);
  const { data: openrouterOrchestratorModelsData, isLoading: isLoadingOpenrouterOrchestratorModels } = useModels('openrouter', undefined, false, true);
  const { data: ollamaOrchestratorModelsData, isLoading: isLoadingOllamaOrchestratorModels } = useModels('ollama', ollamaEndpoint, false, true);

  const availableOllamaModels = ollamaModelsData?.models?.length ? ollamaModelsData.models : POPULAR_MODELS.ollama;
  const availableOpenrouterModels = openrouterModelsData?.models?.length ? openrouterModelsData.models : POPULAR_MODELS.openrouter;
  const availableOpenrouterImageModels = openrouterImageModelsData?.models?.length ? openrouterImageModelsData.models : POPULAR_MODELS.openrouter;
  const availableOpenrouterOrchestratorModels = openrouterOrchestratorModelsData?.models?.length ? openrouterOrchestratorModelsData.models : POPULAR_MODELS.openrouter;
  const availableOllamaOrchestratorModels = ollamaOrchestratorModelsData?.models?.length ? ollamaOrchestratorModelsData.models : POPULAR_MODELS.ollama;

  const initialValuesRef = useRef<{
    preferredProvider: string;
    orchestratorProvider: string;
    orchestratorModel: string;
    boostImagePrompts: boolean;
    maxDailyImages: number;
    imageGenModel: string;
    ollamaEndpoint: string;
    ollamaModel: string;
    openrouterApiKey: string;
    openrouterModel: string;
    systemPrompt: string;
    realtimePrompt: string;
    usageLimitEnabled: boolean;
    maxRequestsPerMinute: number;
    maxRequestsPerHour: number;
  } | null>(null);

  useEffect(() => {
    if (data?.config && !isSaving) {
      const config = data.config;
      const vals = {
        preferredProvider: (config.aiConfig.preferredAiProvider as string) || 'openrouter',
        orchestratorProvider: (config.aiConfig.orchestrator?.preferredAiProvider as string) || 'openrouter',
        orchestratorModel: config.aiConfig.orchestrator?.preferredModel || 'deepseek/deepseek-v4-flash',
        boostImagePrompts: config.aiConfig.boostImagePrompts || false,
        maxDailyImages: config.aiConfig.maxDailyImages || 5,
        imageGenModel: config.aiConfig.imageGeneration?.preferredModel || '',
        ollamaEndpoint: config.aiConfig.ollama?.endpoint || 'http://localhost:11434',
        ollamaModel: config.aiConfig.ollama?.preferredModel || 'llama3.1',
        openrouterApiKey: config.aiConfig.openrouter?.apiKey || '',
        openrouterModel: config.aiConfig.openrouter?.preferredModel || 'google/gemini-2.5-flash',
        systemPrompt: config.aiConfig.systemPrompt || '',
        realtimePrompt: config.aiConfig.realtimePrompt || '',
        usageLimitEnabled: config.aiConfig.usageLimits?.enabled ?? true,
        maxRequestsPerMinute: config.aiConfig.usageLimits?.maxRequestsPerMinute ?? 5,
        maxRequestsPerHour: config.aiConfig.usageLimits?.maxRequestsPerHour ?? 50,
      };
      if (!initialValuesRef.current) {
        initialValuesRef.current = vals;
      }
      setPreferredProvider(vals.preferredProvider as 'ollama' | 'openrouter');
      setOrchestratorProvider(vals.orchestratorProvider as 'ollama' | 'openrouter');
      setOrchestratorModel(vals.orchestratorModel);
      setBoostImagePrompts(vals.boostImagePrompts);
      setMaxDailyImages(vals.maxDailyImages);
      setImageGenModel(vals.imageGenModel);
      setOllamaEndpoint(vals.ollamaEndpoint);
      setOllamaModel(vals.ollamaModel);
      setOpenrouterApiKey(vals.openrouterApiKey);
      setOpenrouterModel(vals.openrouterModel);
      setSystemPrompt(vals.systemPrompt);
      setRealtimePrompt(vals.realtimePrompt);
      setUsageLimitEnabled(vals.usageLimitEnabled);
      setMaxRequestsPerMinute(vals.maxRequestsPerMinute);
      setMaxRequestsPerHour(vals.maxRequestsPerHour);
    }
  }, [data, isSaving]);

  const hasChanges = useMemo(() => {
    const iv = initialValuesRef.current;
    if (!iv) return false;
    return (
      preferredProvider !== iv.preferredProvider ||
      orchestratorProvider !== iv.orchestratorProvider ||
      orchestratorModel !== iv.orchestratorModel ||
      boostImagePrompts !== iv.boostImagePrompts ||
      maxDailyImages !== iv.maxDailyImages ||
      imageGenModel !== iv.imageGenModel ||
      ollamaEndpoint !== iv.ollamaEndpoint ||
      ollamaModel !== iv.ollamaModel ||
      openrouterApiKey !== iv.openrouterApiKey ||
      openrouterModel !== iv.openrouterModel ||
      systemPrompt !== iv.systemPrompt ||
      realtimePrompt !== iv.realtimePrompt ||
      usageLimitEnabled !== iv.usageLimitEnabled ||
      maxRequestsPerMinute !== iv.maxRequestsPerMinute ||
      maxRequestsPerHour !== iv.maxRequestsPerHour
    );
  }, [
    preferredProvider, orchestratorProvider, orchestratorModel,
    boostImagePrompts, maxDailyImages, imageGenModel,
    ollamaEndpoint, ollamaModel, openrouterApiKey, openrouterModel,
    systemPrompt, realtimePrompt, usageLimitEnabled,
    maxRequestsPerMinute, maxRequestsPerHour,
  ]);

  const handleSave = async () => {
    setIsSaving(true);
    const savePromise = new Promise(async (resolve, reject) => {
      try {
        const providerPayload: any = {
          provider: preferredProvider,
          preferredModel: preferredProvider === 'ollama' ? ollamaModel : openrouterModel,
          orchestratorProvider,
          orchestratorModel,
          systemPrompt,
          realtimePrompt,
          boostImagePrompts,
          maxDailyImages,
          imageGenProvider: 'openrouter',
          imageGenModel,
        };

        if (preferredProvider === 'ollama') {
          providerPayload.endpoint = ollamaEndpoint;
        } else {
          providerPayload.apiKey = openrouterApiKey;
        }

        providerPayload.maxRequestsPerMinute = maxRequestsPerMinute;
        providerPayload.maxRequestsPerHour = maxRequestsPerHour;
        providerPayload.aiUsageLimitEnabled = usageLimitEnabled;

        await updateProvider.mutateAsync(providerPayload);
        await queryClient.invalidateQueries({ queryKey: ['config'] });
        setIsSaving(false);
        initialValuesRef.current = {
          preferredProvider,
          orchestratorProvider,
          orchestratorModel,
          boostImagePrompts,
          maxDailyImages,
          imageGenModel,
          ollamaEndpoint,
          ollamaModel,
          openrouterApiKey,
          openrouterModel,
          systemPrompt,
          realtimePrompt,
          usageLimitEnabled,
          maxRequestsPerMinute,
          maxRequestsPerHour,
        };
        resolve('AI configuration saved!');
      } catch (err) {
        setIsSaving(false);
        reject(err instanceof Error ? err.message : 'Error saving AI config');
      }
    });

    toast.promise(savePromise, {
      loading: 'Saving AI configuration...',
      success: (msg) => `${msg}`,
      error: (err) => `Failed to save: ${err}`,
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">Loading AI configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20" data-page="ai">
      <PageHeader
        icon={<Sparkles />}
        title="AI & Models"
        description="Configure LLM providers, models, and bot personality."
      />

      <StickySaveBar onSave={handleSave} isSaving={isSaving} hasChanges={hasChanges} />

      <div className="grid gap-8 lg:grid-cols-2 xl:grid-cols-3">
        {/* Primary AI Core — Hero */}
        <Card variant="hero" className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Sparkles /></CardIcon>
              <div>
                <CardTitle>Primary AI Core</CardTitle>
                <CardDescription>Configure your preferred provider and model for conversations.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-8">
            <div className="space-y-4">
              <Label className="text-base font-semibold">Preferred AI Provider</Label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={() => setPreferredProvider('ollama')}
                  className={`flex flex-col items-center justify-center gap-3 p-5 rounded-xl border-2 text-center transition-all ${
                    preferredProvider === 'ollama'
                      ? 'border-primary bg-primary/5 text-primary shadow-sm scale-[1.02]'
                      : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                  }`}
                >
                  <Ollama size={44} />
                  <div>
                    <div className="font-semibold text-foreground">Ollama</div>
                    <div className="text-xs">Self-hosted local models</div>
                  </div>
                </button>
                <button
                  onClick={() => setPreferredProvider('openrouter')}
                  className={`flex flex-col items-center justify-center gap-3 p-5 rounded-xl border-2 text-center transition-all ${
                    preferredProvider === 'openrouter'
                      ? 'border-primary bg-primary/5 text-primary shadow-sm scale-[1.02]'
                      : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                  }`}
                >
                  <OpenRouter size={44} />
                  <div>
                    <div className="font-semibold text-foreground">OpenRouter</div>
                    <div className="text-xs">Any LLM cloud endpoint</div>
                  </div>
                </button>
              </div>
            </div>

            <Separator />

            <div className="grid gap-8 md:grid-cols-2">
              <div className="space-y-3">
                <Label className="font-semibold">Conversation Model</Label>
                <ModelSelector
                  selectedProvider={preferredProvider}
                  selectedModel={preferredProvider === 'ollama' ? ollamaModel : openrouterModel}
                  onSelect={(prov, model) => {
                    setPreferredProvider(prov);
                    if (prov === 'ollama') setOllamaModel(model);
                    else setOpenrouterModel(model);
                  }}
                  groupedModels={{ ollama: availableOllamaModels, openrouter: availableOpenrouterModels }}
                  isLoading={isLoadingOllamaModels || isLoadingOpenrouterModels}
                />
              </div>
              <div className="space-y-3">
                <Label className="font-semibold">Image Generation Model</Label>
                <ModelSelector
                  selectedProvider="openrouter"
                  selectedModel={imageGenModel}
                  onSelect={(_, model) => setImageGenModel(model)}
                  groupedModels={{ ollama: [], openrouter: availableOpenrouterImageModels }}
                  isLoading={isLoadingOpenrouterImageModels}
                />
              </div>
            </div>

            <Separator />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
                <div className="space-y-1">
                  <Label className="font-semibold cursor-pointer">Boost Image Prompts</Label>
                  <p className="text-xs text-muted-foreground">Refines prompt before image generation</p>
                </div>
                <Switch checked={boostImagePrompts} onCheckedChange={setBoostImagePrompts} />
              </div>
              <div className="space-y-2 p-4 rounded-xl bg-muted/30">
                <Label className="font-semibold">Max Daily Images</Label>
                <Input type="number" value={maxDailyImages} onChange={(e) => setMaxDailyImages(parseInt(e.target.value) || 5)} className="h-10 max-w-[140px]" min={1} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* AI Orchestrator */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><BrainCircuit /></CardIcon>
              <div>
                <CardTitle>AI Orchestrator</CardTitle>
                <CardDescription>Intent classification routing for message interpretation.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <Label className="text-base font-semibold">Orchestrator AI Provider</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setOrchestratorProvider('ollama')}
                  className={`flex flex-col items-center justify-center gap-2 p-3 rounded-xl border-2 text-center transition-all ${
                    orchestratorProvider === 'ollama'
                      ? 'border-primary bg-primary/5 text-primary shadow-sm'
                      : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                  }`}
                >
                  <Ollama size={32} />
                  <div><div className="font-semibold text-foreground text-sm">Ollama</div></div>
                </button>
                <button
                  onClick={() => setOrchestratorProvider('openrouter')}
                  className={`flex flex-col items-center justify-center gap-2 p-3 rounded-xl border-2 text-center transition-all ${
                    orchestratorProvider === 'openrouter'
                      ? 'border-primary bg-primary/5 text-primary shadow-sm'
                      : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                  }`}
                >
                  <OpenRouter size={32} />
                  <div><div className="font-semibold text-foreground text-sm">OpenRouter</div></div>
                </button>
              </div>
            </div>
            <Separator />
            <div className="space-y-3">
              <Label className="font-semibold">Orchestrator Model</Label>
              <ModelSelector
                selectedProvider={orchestratorProvider}
                selectedModel={orchestratorModel}
                onSelect={(prov, model) => { setOrchestratorProvider(prov); setOrchestratorModel(model); }}
                groupedModels={{ ollama: availableOllamaOrchestratorModels, openrouter: availableOpenrouterOrchestratorModels }}
                isLoading={orchestratorProvider === 'ollama' ? isLoadingOllamaOrchestratorModels : isLoadingOpenrouterOrchestratorModels}
              />
            </div>
          </CardContent>
        </Card>

        {/* System Personas & Prompts — spans 2 cols */}
        <Card variant="hero" className="lg:col-span-2 xl:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><FileText /></CardIcon>
              <div>
                <CardTitle>System Personas & Prompts</CardTitle>
                <CardDescription>Core bot behavior, characteristics, and styling.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-8">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="font-semibold text-base">Primary Conversation Prompt</Label>
                <span className="text-[10px] text-muted-foreground uppercase bg-muted px-2 py-0.5 rounded font-bold">systemPrompt</span>
              </div>
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="e.g. Your name is Juno. You are a friendly AI companion..."
                className="min-h-[180px] max-h-[400px] overflow-y-auto font-mono text-sm leading-relaxed rounded-xl resize-none border-border/80 focus-visible:ring-primary bg-background field-sizing-fixed"
              />
              <p className="text-xs text-muted-foreground">Core consciousness for Discord chat. Supports <code>{"{{BOTNAME}}"}</code> substitution.</p>
            </div>
            <Separator />
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="font-semibold text-base">Real-time Voice Prompt</Label>
                <span className="text-[10px] text-muted-foreground uppercase bg-muted px-2 py-0.5 rounded font-bold">realtimePrompt</span>
              </div>
              <Textarea
                value={realtimePrompt}
                onChange={(e) => setRealtimePrompt(e.target.value)}
                placeholder="Speak briefly, clearly, and concisely..."
                className="min-h-[120px] max-h-[300px] overflow-y-auto font-mono text-sm leading-relaxed rounded-xl resize-none border-border/80 focus-visible:ring-primary bg-background field-sizing-fixed"
              />
            </div>
          </CardContent>
        </Card>

        {/* AI Usage Rate Limits */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Gauge /></CardIcon>
              <div>
                <CardTitle>Rate Limits</CardTitle>
                <CardDescription>Control how often users can interact with the AI.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
              <div className="space-y-1">
                <Label className="font-semibold cursor-pointer">Enable Rate Limiting</Label>
                <p className="text-xs text-muted-foreground">Enforce per-user request limits for AI chat</p>
              </div>
              <Switch checked={usageLimitEnabled} onCheckedChange={setUsageLimitEnabled} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 p-4 rounded-xl bg-muted/30">
                <Label className="font-semibold">Max / Minute</Label>
                <Input type="number" value={maxRequestsPerMinute} onChange={(e) => setMaxRequestsPerMinute(parseInt(e.target.value) || 1)} className="h-10" min={1} />
              </div>
              <div className="space-y-2 p-4 rounded-xl bg-muted/30">
                <Label className="font-semibold">Max / Hour</Label>
                <Input type="number" value={maxRequestsPerHour} onChange={(e) => setMaxRequestsPerHour(parseInt(e.target.value) || 1)} className="h-10" min={1} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Provider Settings — full width section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <CardIcon><Server /></CardIcon>
            <div>
              <CardTitle>Provider Settings</CardTitle>
              <CardDescription>Credentials and endpoints for active models.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-8 lg:grid-cols-2">
            {/* Ollama Configuration — Inset */}
            <Card variant="inset">
              <CardContent className="space-y-5 pt-5">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary"><Ollama size={22} /></div>
                  <h3 className="font-bold">Ollama Configuration</h3>
                  <div className="flex gap-1.5 ml-auto">
                    {preferredProvider === 'ollama' && <span className="text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Core Active</span>}
                    {orchestratorProvider === 'ollama' && <span className="text-[9px] bg-primary/10 text-primary/70 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Orch Active</span>}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Server Endpoint</Label>
                  <Input value={ollamaEndpoint} onChange={(e) => setOllamaEndpoint(e.target.value)} placeholder="http://localhost:11434" className="h-10" />
                </div>
                <div className="space-y-2">
                  <Label>Default Model</Label>
                  <ModelSelector
                    selectedProvider="ollama"
                    selectedModel={ollamaModel}
                    onSelect={(_, model) => setOllamaModel(model)}
                    groupedModels={{ ollama: availableOllamaModels, openrouter: [] }}
                    isLoading={isLoadingOllamaModels}
                  />
                </div>
              </CardContent>
            </Card>

            {/* OpenRouter Configuration — Inset */}
            <Card variant="inset">
              <CardContent className="space-y-5 pt-5">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="p-2 rounded-lg bg-primary/10 text-primary"><OpenRouter size={22} /></div>
                  <h3 className="font-bold">OpenRouter Configuration</h3>
                  <div className="flex gap-1.5 ml-auto">
                    {preferredProvider === 'openrouter' && <span className="text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Core Active</span>}
                    {orchestratorProvider === 'openrouter' && <span className="text-[9px] bg-primary/10 text-primary/70 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Orch Active</span>}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>API Key</Label>
                  <div className="relative">
                    <Input type={showApiKey ? 'text' : 'password'} value={openrouterApiKey} onChange={(e) => setOpenrouterApiKey(e.target.value)} placeholder="sk-or-..." className="pr-10 h-10" />
                    <button type="button" onClick={() => setShowApiKey(!showApiKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                      {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Default Model</Label>
                  <ModelSelector
                    selectedProvider="openrouter"
                    selectedModel={openrouterModel}
                    onSelect={(_, model) => setOpenrouterModel(model)}
                    groupedModels={{ ollama: [], openrouter: availableOpenrouterModels }}
                    isLoading={isLoadingOpenrouterModels}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Separator() {
  return <div className="h-px bg-gradient-to-r from-border/80 via-border/40 to-transparent" />;
}