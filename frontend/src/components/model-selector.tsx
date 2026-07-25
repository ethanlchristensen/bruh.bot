import { useState } from 'react';
import { OpenRouter, Ollama } from '@lobehub/icons';
import { Spinner } from '@/components/ui/spinner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { ProviderIconRenderer } from '@/components/provider-icon-renderer';
import { useRefreshModels } from '@/hooks/use-config';
import { ChevronDown, RefreshCw, Search, Sparkles, BrainCircuit } from 'lucide-react';

const POPULAR_MODELS = {
  ollama: ['llama3.1', 'llama3.2', 'gemma2', 'mistral', 'phi3'],
  openrouter: [
    'google/gemini-2.5-flash',
    'google/gemini-2.5-pro',
    'anthropic/claude-3.5-sonnet',
    'meta-llama/llama-3.3-70b-instruct',
    'deepseek/deepseek-chat',
    'openai/gpt-4o-mini',
    'openai/gpt-4o',
  ],
};

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

function isVisionModel(name: string) {
  const lower = name.toLowerCase();
  return lower.includes('vision') || lower.includes('gemini') || lower.includes('gpt-4') || lower.includes('claude-3') || lower.includes('pixtral') || lower.includes('llava');
}

function isToolsModel(name: string) {
  const lower = name.toLowerCase();
  return lower.includes('gemini') || lower.includes('gpt-') || lower.includes('claude') || lower.includes('llama3') || lower.includes('mistral') || lower.includes('qwen');
}

function isReasoningModel(name: string) {
  const lower = name.toLowerCase();
  return lower.includes('o1') || lower.includes('o3') || lower.includes('thinking') || lower.includes('gemini') || lower.includes('deepseek-r1') || lower.includes('qwq');
}

export { POPULAR_MODELS };

export function ModelSelector({ selectedProvider, selectedModel, onSelect, groupedModels, isLoading }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'ollama' | 'openrouter'>('all');
  const [filterCapability, setFilterCapability] = useState<'all' | 'vision' | 'tools' | 'reasoning'>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const refreshModels = useRefreshModels();

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        refreshModels.mutateAsync({ provider: 'openrouter' }),
        refreshModels.mutateAsync({ provider: 'ollama' }),
      ]);
    } catch {
      // refresh failed — models stay as-is
    } finally {
      setIsRefreshing(false);
    }
  };

  const filterModel = (m: string) => {
    const matchesSearch = m.toLowerCase().includes(search.toLowerCase());
    const name = m.toLowerCase();

    if (filterCapability === 'vision' && !isVisionModel(name)) return false;
    if (filterCapability === 'tools' && !isToolsModel(name)) return false;
    if (filterCapability === 'reasoning' && !isReasoningModel(name)) return false;

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

            <div className="flex bg-muted p-1 rounded-xl shrink-0">
              {[
                { id: 'all', label: 'All Providers' },
                { id: 'ollama', label: 'Ollama', icon: Ollama },
                { id: 'openrouter', label: 'OpenRouter', icon: OpenRouter },
              ].map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      setActiveTab(t.id as typeof activeTab);
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

          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: 'all', label: 'All Capabilities' },
              { id: 'vision', label: 'Vision / Multimodal' },
              { id: 'tools', label: 'Tool Use / Function Calling' },
              { id: 'reasoning', label: 'Reasoning / Deep Thinking' },
            ].map((f) => (
              <Button
                key={f.id}
                variant={filterCapability === f.id ? 'default' : 'secondary'}
                size="sm"
                onClick={() => setFilterCapability(f.id as typeof filterCapability)}
                className="rounded-full h-8 text-[11px] px-3 font-semibold uppercase tracking-wider"
              >
                {f.label}
              </Button>
            ))}
            <div className="flex-1" />
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="rounded-full h-8 w-8 p-0"
            >
              <RefreshCw className={`size-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

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
                              {isReasoningModel(name) && <span className="text-[9px] font-bold bg-purple-500/10 border border-purple-500/20 text-purple-600 px-1 rounded">Reasoning</span>}
                              {isVisionModel(name) && <span className="text-[9px] font-bold bg-blue-500/10 border border-blue-500/20 text-blue-600 px-1 rounded">Vision</span>}
                              {isToolsModel(name) && <span className="text-[9px] font-bold bg-green-500/10 border border-green-500/20 text-green-600 px-1 rounded">Tools</span>}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

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
                              {isReasoningModel(name) && <span className="text-[9px] font-bold bg-purple-500/10 border border-purple-500/20 text-purple-600 px-1 rounded">Reasoning</span>}
                              {isVisionModel(name) && <span className="text-[9px] font-bold bg-blue-500/10 border border-blue-500/20 text-blue-600 px-1 rounded">Vision</span>}
                              {isToolsModel(name) && <span className="text-[9px] font-bold bg-green-500/10 border border-green-500/20 text-green-600 px-1 rounded">Tools</span>}
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