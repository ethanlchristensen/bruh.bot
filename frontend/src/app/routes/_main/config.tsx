import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useConfig, useUpdateConfig, useUpdateAIProvider, useModels } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { GuildSelector } from '@/components/guild-selector';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { OpenRouter, Ollama } from '@lobehub/icons';
import { ProviderIconRenderer } from '@/components/provider-icon-renderer';
import { 
  Settings, 
  Save, 
  Server, 
  Shield, 
  Sparkles, 
  Eye, 
  EyeOff, 
  Plus, 
  Trash2, 
  Database,
  ChevronDown,
  Search,
  BrainCircuit,
  FileText
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

export const Route = createFileRoute('/_main/config')({
  component: ConfigComponent,
});

interface ModelSelectorProps {
  selectedProvider: 'ollama' | 'openrouter';
  selectedModel: string;
  onSelect: (provider: 'ollama' | 'openrouter', model: string) => void;
  groupedModels: {
    ollama: string[];
    openrouter: string[];
  };
  isLoading: boolean;
}

function ModelSelector({ selectedProvider, selectedModel, onSelect, groupedModels, isLoading }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'ollama' | 'openrouter'>('all');
  const [filterCapability, setFilterCapability] = useState<'all' | 'vision' | 'tools' | 'reasoning'>('all');

  const filterModel = (m: string) => {
    const matchesSearch = m.toLowerCase().includes(search.toLowerCase());
    const name = m.toLowerCase();
    const isVision = name.includes('vision') || name.includes('gemini') || name.includes('gpt-4') || name.includes('claude-3') || name.includes('pixtral') || name.includes('llava');
    const isTools = name.includes('gemini') || name.includes('gpt-') || name.includes('claude') || name.includes('llama3') || name.includes('mistral') || name.includes('qwen');
    const isReasoning = name.includes('o1') || name.includes('o3') || name.includes('thinking') || name.includes('gemini') || name.includes('deepseek-r1') || name.includes('qwq');

    if (filterCapability === 'vision' && !isVision) return false;
    if (filterCapability === 'tools' && !isTools) return false;
    if (filterCapability === 'reasoning' && !isReasoning) return false;

    return matchesSearch;
  };

  const filteredOllama = activeTab === 'openrouter' ? [] : groupedModels.ollama.filter(filterModel);
  const filteredOpenrouter = activeTab === 'ollama' ? [] : groupedModels.openrouter.filter(filterModel);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full justify-between h-14 px-4 border border-input rounded-xl bg-background hover:bg-accent hover:text-accent-foreground text-left font-normal">
          <div className="flex items-center gap-3">
            <ProviderIconRenderer 
              provider={selectedProvider === 'ollama' ? 'ollama' : (selectedModel ? selectedModel.split('/')[0] : 'openrouter')} 
              size={24} 
            />
            <div className="flex flex-col">
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{selectedProvider}</span>
              <span className="font-bold text-sm truncate text-foreground">
                {selectedModel || 'Select a model...'}
              </span>
            </div>
          </div>
          <ChevronDown className="h-4 w-4 opacity-50 shrink-0" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-5xl w-[92vw] rounded-2xl p-0 overflow-hidden flex flex-col max-h-[85vh]">
        <DialogHeader className="p-6 pb-4 border-b border-border/40 bg-muted/20">
          <div className="flex items-center gap-3">
            <Sparkles className="h-7 w-7 text-primary" />
            <div>
              <DialogTitle className="text-lg font-bold">Select Orchestration Model</DialogTitle>
              <DialogDescription className="text-xs">
                Switch between self-hosted Ollama models and OpenRouter cloud models.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Search and Filters */}
        <div className="p-4 space-y-4 border-b border-border/40 shrink-0 bg-muted/5">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 opacity-40" />
              <Input
                placeholder="Search models..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 h-10 rounded-xl"
              />
            </div>
            
            {/* Provider Tabs */}
            <div className="flex bg-muted p-1 rounded-xl shrink-0">
              {[
                { id: 'all', label: 'All Providers' },
                { id: 'ollama', label: 'Ollama', icon: Ollama },
                { id: 'openrouter', label: 'OpenRouter', icon: OpenRouter }
              ].map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      setActiveTab(t.id as any);
                      // Clear search when switching tabs for better UX
                      setSearch('');
                    }}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      activeTab === t.id
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {Icon && <Icon size={14} />}
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>
          
          {/* Capability Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: 'all', label: 'All Capabilities' },
              { id: 'vision', label: 'Vision / Multimodal' },
              { id: 'tools', label: 'Tool Use / Function Calling' },
              { id: 'reasoning', label: 'Reasoning / Deep Thinking' }
            ].map((f) => (
              <Button
                key={f.id}
                variant={filterCapability === f.id ? 'default' : 'secondary'}
                size="sm"
                onClick={() => setFilterCapability(f.id as any)}
                className="rounded-full h-8 text-[11px] px-3 font-semibold uppercase tracking-wider"
              >
                {f.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Grouped Scrollable list */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6 min-h-[300px]">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Spinner className="h-6 w-6 text-primary" />
              <p className="text-xs text-muted-foreground animate-pulse">Querying server registries...</p>
            </div>
          ) : filteredOllama.length === 0 && filteredOpenrouter.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center opacity-60">
              <BrainCircuit className="h-12 w-12 opacity-30 mb-3" />
              <p className="font-bold text-sm">No models match your filter criteria</p>
              <p className="text-xs text-muted-foreground max-w-xs mt-1">Try generic keywords or switch provider filters.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Ollama Group */}
              {filteredOllama.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 opacity-50 px-1">
                    <Ollama size={16} />
                    <span className="text-[10px] font-black uppercase tracking-[0.2em]">Ollama Registry ({filteredOllama.length})</span>
                    <div className="h-px flex-1 bg-border/20 ml-2" />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {filteredOllama.map((m) => {
                      const isSelected = selectedProvider === 'ollama' && selectedModel === m;
                      const name = m.toLowerCase();
                      const isVision = name.includes('vision') || name.includes('gemini') || name.includes('gpt-4') || name.includes('claude-3') || name.includes('pixtral') || name.includes('llava');
                      const isTools = name.includes('gemini') || name.includes('gpt-') || name.includes('claude') || name.includes('llama3') || name.includes('mistral') || name.includes('qwen');
                      const isReasoning = name.includes('o1') || name.includes('o3') || name.includes('thinking') || name.includes('gemini') || name.includes('deepseek-r1') || name.includes('qwq');

                      return (
                        <button
                          key={`ollama:${m}`}
                          onClick={() => {
                            onSelect('ollama', m);
                            setOpen(false);
                          }}
                          className={`flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all ${
                            isSelected
                              ? 'border-primary bg-primary/5 text-primary shadow-sm scale-[1.01]'
                              : 'border-border/40 hover:border-border hover:bg-muted/40 hover:scale-[1.01]'
                          }`}
                        >
                          <div className={`p-2 rounded-lg border ${isSelected ? 'bg-primary/10 border-primary/20' : 'bg-background border-border/60'}`}>
                            <Ollama size={20} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-bold truncate text-foreground mb-1">{m}</div>
                            <div className="flex flex-wrap gap-1.5 opacity-80">
                              {isReasoning && <span className="text-[9px] font-bold bg-purple-500/10 border border-purple-500/20 text-purple-600 px-1 rounded">Reasoning</span>}
                              {isVision && <span className="text-[9px] font-bold bg-blue-500/10 border border-blue-500/20 text-blue-600 px-1 rounded">Vision</span>}
                              {isTools && <span className="text-[9px] font-bold bg-green-500/10 border border-green-500/20 text-green-600 px-1 rounded">Tools</span>}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* OpenRouter Group */}
              {filteredOpenrouter.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 opacity-50 px-1">
                    <OpenRouter size={16} />
                    <span className="text-[10px] font-black uppercase tracking-[0.2em]">OpenRouter Registry ({filteredOpenrouter.length})</span>
                    <div className="h-px flex-1 bg-border/20 ml-2" />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {filteredOpenrouter.map((m) => {
                      const isSelected = selectedProvider === 'openrouter' && selectedModel === m;
                      const name = m.toLowerCase();
                      const isVision = name.includes('vision') || name.includes('gemini') || name.includes('gpt-4') || name.includes('claude-3') || name.includes('pixtral') || name.includes('llava');
                      const isTools = name.includes('gemini') || name.includes('gpt-') || name.includes('claude') || name.includes('llama3') || name.includes('mistral') || name.includes('qwen');
                      const isReasoning = name.includes('o1') || name.includes('o3') || name.includes('thinking') || name.includes('gemini') || name.includes('deepseek-r1') || name.includes('qwq');

                      return (
                        <button
                          key={`openrouter:${m}`}
                          onClick={() => {
                            onSelect('openrouter', m);
                            setOpen(false);
                          }}
                          className={`flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all ${
                            isSelected
                              ? 'border-primary bg-primary/5 text-primary shadow-sm scale-[1.01]'
                              : 'border-border/40 hover:border-border hover:bg-muted/40 hover:scale-[1.01]'
                          }`}
                        >
                          <div className={`p-2 rounded-lg border ${isSelected ? 'bg-primary/10 border-primary/20' : 'bg-background border-border/60'}`}>
                            <ProviderIconRenderer provider={m.split('/')[0]} size={20} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-bold truncate text-foreground mb-1">{m}</div>
                            <div className="flex flex-wrap gap-1.5 opacity-80">
                              {isReasoning && <span className="text-[9px] font-bold bg-purple-500/10 border border-purple-500/20 text-purple-600 px-1 rounded">Reasoning</span>}
                              {isVision && <span className="text-[9px] font-bold bg-blue-500/10 border border-blue-500/20 text-blue-600 px-1 rounded">Vision</span>}
                              {isTools && <span className="text-[9px] font-bold bg-green-500/10 border border-green-500/20 text-green-600 px-1 rounded">Tools</span>}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

const POPULAR_MODELS = {
  ollama: ['llama3.1', 'llama3.2', 'gemma2', 'mistral', 'phi3'],
  openrouter: [
    'google/gemini-2.5-flash',
    'google/gemini-2.5-pro',
    'anthropic/claude-3.5-sonnet',
    'meta-llama/llama-3.3-70b-instruct',
    'deepseek/deepseek-chat',
    'openai/gpt-4o-mini',
    'openai/gpt-4o'
  ]
};

function ConfigComponent() {
  const { data, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();
  const updateProvider = useUpdateAIProvider();
  const queryClient = useQueryClient();

  // Local state for configuration fields
  const [isSaving, setIsSaving] = useState(false);
  const [preferredProvider, setPreferredProvider] = useState<'ollama' | 'openrouter'>('openrouter');
  const [orchestratorProvider, setOrchestratorProvider] = useState<'ollama' | 'openrouter'>('openrouter');
  const [orchestratorModel, setOrchestratorModel] = useState('');
  const [boostImagePrompts, setBoostImagePrompts] = useState(false);
  const [maxDailyImages, setMaxDailyImages] = useState(5);
  const [invisible, setInvisible] = useState(false);
  const [mentionCooldown, setMentionCooldown] = useState(0);

  // Image Generation States
  const [imageGenModel, setImageGenModel] = useState('');
  
  // Provider configs
  const [ollamaEndpoint, setOllamaEndpoint] = useState('');
  const [ollamaModel, setOllamaModel] = useState('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState('');
  const [openrouterModel, setOpenrouterModel] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  // System Personas & Prompts
  const [systemPrompt, setSystemPrompt] = useState('');
  const [realtimePrompt, setRealtimePrompt] = useState('');

  // List management fields
  const [newAdminId, setNewAdminId] = useState('');
  const [newBlockId, setNewBlockId] = useState('');
  const [adminIds, setAdminIds] = useState<string[]>([]);
  const [globalBlockList, setGlobalBlockList] = useState<string[]>([]);
  const [cooldownBypassList, setCooldownBypassList] = useState<string[]>([]);

  // DB Settings fields
  const [dbName, setDbName] = useState('');
  const [collectionName, setCollectionName] = useState('');

  // Fetch models for both providers dynamically using our query hook
  const { data: ollamaModelsData, isLoading: isLoadingOllamaModels } = useModels('ollama', ollamaEndpoint);
  const { data: openrouterModelsData, isLoading: isLoadingOpenrouterModels } = useModels('openrouter');
  const { data: openrouterImageModelsData, isLoading: isLoadingOpenrouterImageModels } = useModels('openrouter', undefined, true);
  const { data: openrouterOrchestratorModelsData, isLoading: isLoadingOpenrouterOrchestratorModels } = useModels('openrouter', undefined, false, true);
  const { data: ollamaOrchestratorModelsData, isLoading: isLoadingOllamaOrchestratorModels } = useModels('ollama', ollamaEndpoint, false, true);

  const availableOllamaModels = ollamaModelsData?.models?.length 
    ? ollamaModelsData.models 
    : POPULAR_MODELS.ollama;

  const availableOpenrouterModels = openrouterModelsData?.models?.length 
    ? openrouterModelsData.models 
    : POPULAR_MODELS.openrouter;

  const availableOpenrouterImageModels = openrouterImageModelsData?.models?.length 
    ? openrouterImageModelsData.models 
    : POPULAR_MODELS.openrouter;

  const availableOpenrouterOrchestratorModels = openrouterOrchestratorModelsData?.models?.length 
    ? openrouterOrchestratorModelsData.models 
    : POPULAR_MODELS.openrouter;

  const availableOllamaOrchestratorModels = ollamaOrchestratorModelsData?.models?.length 
    ? ollamaOrchestratorModelsData.models 
    : POPULAR_MODELS.ollama;

  // Set default values when config data loads
  useEffect(() => {
    if (data?.config && !isSaving) {
      const config = data.config;
      setPreferredProvider((config.aiConfig.preferredAiProvider as 'ollama' | 'openrouter') || 'openrouter');
      setOrchestratorProvider((config.aiConfig.orchestrator?.preferredAiProvider as 'ollama' | 'openrouter') || 'openrouter');
      setOrchestratorModel(config.aiConfig.orchestrator?.preferredModel || 'deepseek/deepseek-v4-flash');
      setBoostImagePrompts(config.aiConfig.boostImagePrompts || false);
      setMaxDailyImages(config.aiConfig.maxDailyImages || 5);
      setInvisible(config.invisible || false);
      setMentionCooldown(config.mentionCooldown || 0);

      // Populate Image Gen configs
      const imgConfig = config.aiConfig.imageGeneration || {};
      setImageGenModel(imgConfig.preferredModel || '');

      // Populate provider-specific settings
      setOllamaEndpoint(config.aiConfig.ollama?.endpoint || 'http://localhost:11434');
      setOllamaModel(config.aiConfig.ollama?.preferredModel || 'llama3.1');
      
      setOpenrouterApiKey(config.aiConfig.openrouter?.apiKey || '');
      setOpenrouterModel(config.aiConfig.openrouter?.preferredModel || 'google/gemini-2.5-flash');

      // Lists
      setAdminIds(config.adminIds || []);
      setGlobalBlockList(config.globalBlockList || []);
      setCooldownBypassList(config.cooldownBypassList || []);

      // Prompts
      setSystemPrompt(config.aiConfig.systemPrompt || '');
      setRealtimePrompt(config.aiConfig.realtimePrompt || '');

      // DB Settings
      setDbName(config.mongoMessagesDbName || '');
      setCollectionName(config.mongoMessagesCollectionName || '');
    }
  }, [data, isSaving]);

  const handleSaveAll = async () => {
    setIsSaving(true);
    const savePromise = new Promise(async (resolve, reject) => {
      try {
        // 1. Save general config updates
        await updateConfig.mutateAsync({
          invisible,
          mentionCooldown,
          adminIds,
          globalBlockList,
          cooldownBypassList,
          mongoMessagesDbName: dbName,
          mongoMessagesCollectionName: collectionName,
        });

        // 2. Save active preferred provider details AND prompts
        if (preferredProvider === 'ollama') {
          await updateProvider.mutateAsync({
            provider: 'ollama',
            endpoint: ollamaEndpoint,
            preferredModel: ollamaModel,
            orchestratorProvider,
            orchestratorModel,
            systemPrompt,
            realtimePrompt,
            boostImagePrompts,
            maxDailyImages,
            imageGenProvider: 'openrouter',
            imageGenModel,
          });
        } else {
          await updateProvider.mutateAsync({
            provider: 'openrouter',
            apiKey: openrouterApiKey,
            preferredModel: openrouterModel,
            orchestratorProvider,
            orchestratorModel,
            systemPrompt,
            realtimePrompt,
            boostImagePrompts,
            maxDailyImages,
            imageGenProvider: 'openrouter',
            imageGenModel,
          });
        }

        await queryClient.invalidateQueries({ queryKey: ['config'] });
        setIsSaving(false);
        resolve('Configuration saved successfully!');
      } catch (err) {
        setIsSaving(false);
        reject(err instanceof Error ? err.message : 'Error saving config');
      }
    });

    toast.promise(savePromise, {
      loading: 'Saving bot configuration...',
      success: (msg) => `${msg}`,
      error: (err) => `Failed to save: ${err}`,
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">
          Uplinking to Configuration Database...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bot Configuration</h1>
          <p className="text-sm text-muted-foreground">
            Configure dynamic rules, credentials, and LLM preferences for this server.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <GuildSelector />
          <Button onClick={handleSaveAll} className="gap-2">
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Left Column: AI Orchestration (Primary Settings) */}
        <div className="md:col-span-2 space-y-6">
          {/* Primary AI Core Card */}
          <Card className="border-primary/20 shadow-md">
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Sparkles className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Primary AI Core</CardTitle>
                <CardDescription>
                  Configure preferred provider and model defaults for user conversations.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Preferred AI Provider Selection with brand icons */}
              <div className="space-y-3">
                <Label className="text-base font-semibold">Preferred AI Provider</Label>
                <div className="grid grid-cols-2 gap-4">
                  {/* Ollama Select Option */}
                  <button
                    onClick={() => setPreferredProvider('ollama')}
                    className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border-2 text-center transition-all ${
                      preferredProvider === 'ollama'
                        ? 'border-primary bg-primary/5 text-primary shadow-sm'
                        : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <Ollama size={40} className={preferredProvider === 'ollama' ? 'animate-bounce-short' : ''} />
                    <div>
                      <div className="font-semibold text-foreground">Ollama</div>
                      <div className="text-xs">Self-hosted local models</div>
                    </div>
                  </button>

                  {/* OpenRouter Select Option */}
                  <button
                    onClick={() => setPreferredProvider('openrouter')}
                    className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border-2 text-center transition-all ${
                      preferredProvider === 'openrouter'
                        ? 'border-primary bg-primary/5 text-primary shadow-sm'
                        : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <OpenRouter size={40} className={preferredProvider === 'openrouter' ? 'animate-bounce-short' : ''} />
                    <div>
                      <div className="font-semibold text-foreground">OpenRouter</div>
                      <div className="text-xs">Any LLM cloud endpoint</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Dynamic Model Dropdown depending on selection */}
              <div className="space-y-2 border-t border-border/40 pt-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="model-select" className="font-semibold">Preferred Conversation Model</Label>
                  {(preferredProvider === 'ollama' ? isLoadingOllamaModels : isLoadingOpenrouterModels) && (
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Spinner className="h-3 w-3" /> Fetching models...
                    </span>
                  )}
                </div>
                <ModelSelector
                  selectedProvider={preferredProvider}
                  selectedModel={preferredProvider === 'ollama' ? ollamaModel : openrouterModel}
                  onSelect={(prov, model) => {
                    setPreferredProvider(prov);
                    if (prov === 'ollama') {
                      setOllamaModel(model);
                    } else {
                      setOpenrouterModel(model);
                    }
                  }}
                  groupedModels={{
                    ollama: availableOllamaModels,
                    openrouter: availableOpenrouterModels
                  }}
                  isLoading={isLoadingOllamaModels || isLoadingOpenrouterModels}
                />
                <p className="text-xs text-muted-foreground">
                  The model that will be used for direct conversations in user channels.
                </p>
              </div>

              {/* Image Generation Model Selection */}
              <div className="space-y-2 border-t border-border/40 pt-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="image-model-select" className="font-semibold">Preferred Image Generation Model (OpenRouter)</Label>
                  {isLoadingOpenrouterImageModels && (
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Spinner className="h-3 w-3" /> Fetching image models...
                    </span>
                  )}
                </div>
                <ModelSelector
                  selectedProvider="openrouter"
                  selectedModel={imageGenModel}
                  onSelect={(_, model) => {
                    setImageGenModel(model);
                  }}
                  groupedModels={{
                    ollama: [],
                    openrouter: availableOpenrouterImageModels
                  }}
                  isLoading={isLoadingOpenrouterImageModels}
                />
                <p className="text-xs text-muted-foreground">
                  The model that will be used for generating and editing images. Filtered for image-gen capable models.
                </p>
              </div>

              {/* Additional AI Settings */}
              <div className="grid gap-6 sm:grid-cols-2 border-t border-border/40 pt-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40">
                  <div className="space-y-0.5">
                    <Label htmlFor="boost-prompts" className="font-semibold cursor-pointer">Boost Image Prompts</Label>
                    <p className="text-xs text-muted-foreground">Refines prompt before image generation</p>
                  </div>
                  <Switch
                    id="boost-prompts"
                    checked={boostImagePrompts}
                    onCheckedChange={setBoostImagePrompts}
                  />
                </div>

                <div className="space-y-2 p-3 rounded-lg bg-muted/40 flex flex-col justify-center">
                  <Label htmlFor="max-images" className="font-semibold">Max Daily Images</Label>
                  <Input
                    id="max-images"
                    type="number"
                    value={maxDailyImages}
                    onChange={(e) => setMaxDailyImages(parseInt(e.target.value) || 5)}
                    className="h-8 max-w-[120px]"
                    min={1}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* AI Orchestrator Card */}
          <Card className="border-primary/20 shadow-md">
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <BrainCircuit className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>AI Orchestrator</CardTitle>
                <CardDescription>
                  Configure provider and model for intent classification routing.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Orchestrator Provider Selection */}
              <div className="space-y-3">
                <Label className="text-base font-semibold">Orchestrator AI Provider</Label>
                <div className="grid grid-cols-2 gap-4">
                  {/* Ollama Select Option */}
                  <button
                    onClick={() => setOrchestratorProvider('ollama')}
                    className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border-2 text-center transition-all ${
                      orchestratorProvider === 'ollama'
                        ? 'border-primary bg-primary/5 text-primary shadow-sm'
                        : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <Ollama size={40} className={orchestratorProvider === 'ollama' ? 'animate-bounce-short' : ''} />
                    <div>
                      <div className="font-semibold text-foreground">Ollama</div>
                      <div className="text-xs">Self-hosted local models</div>
                    </div>
                  </button>

                  {/* OpenRouter Select Option */}
                  <button
                    onClick={() => setOrchestratorProvider('openrouter')}
                    className={`flex flex-col items-center justify-center gap-3 p-4 rounded-xl border-2 text-center transition-all ${
                      orchestratorProvider === 'openrouter'
                        ? 'border-primary bg-primary/5 text-primary shadow-sm'
                        : 'border-border/60 hover:border-border hover:bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    <OpenRouter size={40} className={orchestratorProvider === 'openrouter' ? 'animate-bounce-short' : ''} />
                    <div>
                      <div className="font-semibold text-foreground">OpenRouter</div>
                      <div className="text-xs">Any LLM cloud endpoint</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Orchestrator Model Selector */}
              <div className="space-y-2 border-t border-border/40 pt-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="orchestrator-model-select" className="font-semibold">Orchestrator AI Model</Label>
                  {(orchestratorProvider === 'ollama' ? isLoadingOllamaOrchestratorModels : isLoadingOpenrouterOrchestratorModels) && (
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Spinner className="h-3 w-3" /> Fetching structured models...
                    </span>
                  )}
                </div>
                <ModelSelector
                  selectedProvider={orchestratorProvider}
                  selectedModel={orchestratorModel}
                  onSelect={(prov, model) => {
                    setOrchestratorProvider(prov);
                    setOrchestratorModel(model);
                  }}
                  groupedModels={{
                    ollama: availableOllamaOrchestratorModels,
                    openrouter: availableOpenrouterOrchestratorModels
                  }}
                  isLoading={orchestratorProvider === 'ollama' ? isLoadingOllamaOrchestratorModels : isLoadingOpenrouterOrchestratorModels}
                />
                <p className="text-xs text-muted-foreground">
                  The model that will be used for interpreting user messages and executing prompt routing. Filtered for models that support structured outputs.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* System Personas & Prompts Card */}
          <Card className="border-primary/20 shadow-md">
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <FileText className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>System Personas & Prompts</CardTitle>
                <CardDescription>
                  Configure core behaviors, characteristics, and styling instructions for the bot directly in the database.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Core Chat Persona Textarea */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="system-prompt" className="font-semibold text-base">Primary Conversation Prompt</Label>
                  <span className="text-[10px] text-muted-foreground uppercase bg-muted px-1.5 py-0.5 rounded font-bold">systemPrompt</span>
                </div>
                <Textarea
                  id="system-prompt"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="e.g. Your name is Juno. You are a friendly AI companion..."
                  className="min-h-[220px] font-mono text-sm leading-relaxed rounded-xl resize-y border-border/80 focus-visible:ring-primary bg-background"
                />
                <p className="text-xs text-muted-foreground">
                  This forms the core consciousness, guidelines, and behavioral traits for chat interactions in Discord. Supports <code>{"{{BOTNAME}}"}</code> substitution.
                </p>
              </div>

              {/* Real-time Voice Persona Textarea */}
              <div className="space-y-2 border-t border-border/40 pt-6">
                <div className="flex items-center justify-between">
                  <Label htmlFor="realtime-prompt" className="font-semibold text-base">Real-time Voice Assistant Prompt</Label>
                  <span className="text-[10px] text-muted-foreground uppercase bg-muted px-1.5 py-0.5 rounded font-bold">realtimePrompt</span>
                </div>
                <Textarea
                  id="realtime-prompt"
                  value={realtimePrompt}
                  onChange={(e) => setRealtimePrompt(e.target.value)}
                  placeholder="Speak briefly, clearly, and concisely. Emulate a friendly voice..."
                  className="min-h-[120px] font-mono text-sm leading-relaxed rounded-xl resize-y border-border/80 focus-visible:ring-primary bg-background"
                />
                <p className="text-xs text-muted-foreground">
                  The behavioral instructions passed directly to the low-latency OpenAI Realtime Voice connection.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Provider Specific Settings */}
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Server className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Provider Settings</CardTitle>
                <CardDescription>
                  Credentials, keys, and specific hosts for active models.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Ollama Block */}
              <div className="space-y-4 p-4 rounded-xl border border-primary/10 bg-primary/5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Ollama size={24} />
                  <h3 className="font-bold">Ollama Configuration</h3>
                  <div className="flex gap-1.5 ml-auto">
                    {preferredProvider === 'ollama' && <span className="text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Core Active</span>}
                    {orchestratorProvider === 'ollama' && <span className="text-[9px] bg-purple-500/20 text-purple-600 dark:text-purple-400 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Orchestrator Active</span>}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ollama-host">Ollama Server Endpoint</Label>
                  <Input
                    id="ollama-host"
                    value={ollamaEndpoint}
                    onChange={(e) => setOllamaEndpoint(e.target.value)}
                    placeholder="e.g. http://localhost:11434"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ollama-model-fallback">Ollama Default Model</Label>
                  <ModelSelector
                    selectedProvider="ollama"
                    selectedModel={ollamaModel}
                    onSelect={(_, model) => setOllamaModel(model)}
                    groupedModels={{
                      ollama: availableOllamaModels,
                      openrouter: []
                    }}
                    isLoading={isLoadingOllamaModels}
                  />
                </div>
              </div>

              {/* OpenRouter Block */}
              <div className="space-y-4 p-4 rounded-xl border border-primary/10 bg-primary/5">
                <div className="flex items-center gap-2 flex-wrap">
                  <OpenRouter size={24} />
                  <h3 className="font-bold">OpenRouter Configuration</h3>
                  <div className="flex gap-1.5 ml-auto">
                    {preferredProvider === 'openrouter' && <span className="text-[9px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Core Active</span>}
                    {orchestratorProvider === 'openrouter' && <span className="text-[9px] bg-purple-500/20 text-purple-600 dark:text-purple-400 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Orchestrator Active</span>}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="or-key">OpenRouter API Key</Label>
                  <div className="relative">
                    <Input
                      id="or-key"
                      type={showApiKey ? 'text' : 'password'}
                      value={openrouterApiKey}
                      onChange={(e) => setOpenrouterApiKey(e.target.value)}
                      placeholder="sk-or-..."
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="or-model-fallback">OpenRouter Default Model</Label>
                  <ModelSelector
                    selectedProvider="openrouter"
                    selectedModel={openrouterModel}
                    onSelect={(_, model) => setOpenrouterModel(model)}
                    groupedModels={{
                      ollama: [],
                      openrouter: availableOpenrouterModels
                    }}
                    isLoading={isLoadingOpenrouterModels}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Global Rules, Lists, and General */}
        <div className="space-y-6">
          {/* General Bot Rules Card */}
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Settings className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>General Configs</CardTitle>
                <CardDescription>
                  Visibility, timers, and basic controls.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40">
                <div className="space-y-0.5">
                  <Label htmlFor="invisible-mode" className="font-semibold cursor-pointer">Invisible Mode</Label>
                  <p className="text-xs text-muted-foreground">Bot stays hidden from server lists</p>
                </div>
                <Switch
                  id="invisible-mode"
                  checked={invisible}
                  onCheckedChange={setInvisible}
                />
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

          {/* Access Lists Cards */}
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Security & Access</CardTitle>
                <CardDescription>
                  Manage bot admins and block rules.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Admins manager */}
              <div className="space-y-3">
                <Label className="font-semibold">Bot Administrators</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add Admin User ID"
                    value={newAdminId}
                    onChange={(e) => setNewAdminId(e.target.value)}
                  />
                  <Button
                    size="icon"
                    variant="secondary"
                    onClick={() => {
                      if (!newAdminId.trim()) return;
                      if (adminIds.includes(newAdminId)) {
                        toast.error('User already registered as Admin');
                        return;
                      }
                      setAdminIds([...adminIds, newAdminId.trim()]);
                      setNewAdminId('');
                    }}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                  {adminIds.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic p-2 bg-muted/20 rounded">No admins registered</p>
                  ) : (
                    adminIds.map((id) => (
                      <div key={id} className="flex items-center justify-between text-sm p-1.5 bg-muted/40 rounded border border-border/20">
                        <span className="font-mono">{id}</span>
                        <button
                          onClick={() => setAdminIds(adminIds.filter((item) => item !== id))}
                          className="text-destructive hover:text-destructive/80 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Blocklist manager */}
              <div className="space-y-3 border-t border-border/40 pt-4">
                <Label className="font-semibold">Global Block List</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Block User ID"
                    value={newBlockId}
                    onChange={(e) => setNewBlockId(e.target.value)}
                  />
                  <Button
                    size="icon"
                    variant="secondary"
                    onClick={() => {
                      if (!newBlockId.trim()) return;
                      if (globalBlockList.includes(newBlockId)) return;
                      setGlobalBlockList([...globalBlockList, newBlockId.trim()]);
                      setNewBlockId('');
                    }}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1">
                  {globalBlockList.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic p-2 bg-muted/20 rounded">Blocklist is empty</p>
                  ) : (
                    globalBlockList.map((id) => (
                      <div key={id} className="flex items-center justify-between text-sm p-1.5 bg-muted/40 rounded border border-border/20">
                        <span className="font-mono">{id}</span>
                        <button
                          onClick={() => setGlobalBlockList(globalBlockList.filter((item) => item !== id))}
                          className="text-destructive hover:text-destructive/80 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Infrastructure Settings */}
          <Card>
            <CardHeader className="flex flex-row items-center gap-4">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Database className="h-6 w-6" />
              </div>
              <div>
                <CardTitle>Database & Files</CardTitle>
                <CardDescription>
                  Internal storage mappings.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="space-y-2">
                <Label htmlFor="db-name">Mongo DB Name</Label>
                <Input
                  id="db-name"
                  value={dbName}
                  onChange={(e) => setDbName(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="collection-name">Messages Collection</Label>
                <Input
                  id="collection-name"
                  value={collectionName}
                  onChange={(e) => setCollectionName(e.target.value)}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}