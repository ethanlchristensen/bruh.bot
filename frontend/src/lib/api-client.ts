import { env } from '@/config/env';

export type AIProvider = 'ollama' | 'openai' | 'antropic' | 'google';

export interface ProviderConfig {
  apiKey: string;
  endpoint: string;
  preferredModel: string;
  voice: string;
  realTimeModel: string;
}

export interface OrchestratorConfig {
  preferredAiProvider: AIProvider;
  preferredModel: string;
}

export interface AIConfig {
  preferredAiProvider: AIProvider;
  ollama: ProviderConfig;
  openai: ProviderConfig;
  antropic: ProviderConfig;
  google: ProviderConfig;
  elevenlabs: ProviderConfig;
  realTimeConfig: ProviderConfig;
  orchestrator: OrchestratorConfig;
  boostImagePrompts: boolean;
  maxDailyImages: number;
}

export interface DeleteUserMessagesConfig {
  enabled: boolean;
  userIds: Array<number>;
}

export interface DynamicConfig {
  configVersion: number;
  lastUpdated: string | null;
  adminIds: Array<string>;
  invisible: boolean;
  aiConfig: AIConfig;
  usersToId: Record<string, string>;
  idToUsers: Record<string, string>;
  mentionCooldown: number;
  cooldownBypassList: Array<string>;
  promptsPath: string;
  mongoMessagesDbName: string;
  mongoMessagesCollectionName: string;
  mongoMorningConfigsCollectionName: string;
  mongoImageLimitsCollectionName: string;
  allowedBotsToRespondTo: Array<number>;
  deleteUserMessages: DeleteUserMessagesConfig;
  globalBlockList: Array<string>;
}

export interface ConfigResponse {
  success: boolean;
  version: number;
  config?: DynamicConfig;
  message?: string;
  changed?: boolean;
}

export interface UpdateConfigRequest {
  invisible?: boolean;
  mentionCooldown?: number;
  adminIds?: Array<string>;
  cooldownBypassList?: Array<string>;
  globalBlockList?: Array<string>;
  promptsPath?: string;
  mongoMessagesDbName?: string;
  mongoMessagesCollectionName?: string;
  allowedBotsToRespondTo?: Array<string>;
}

export interface UpdateAIProviderRequest {
  provider: AIProvider;
  apiKey?: string;
  preferredModel?: string;
  endpoint?: string;
  voice?: string;
}

export interface AddAdminRequest {
  userId: number;
}

export interface VersionResponse {
  version: number;
  lastUpdated: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export class ConfigAPIClient {
  private baseUrl: string;
  private adminKey: string;

  constructor(baseUrl?: string, adminKey?: string) {
    this.baseUrl =
      baseUrl ||
      import.meta.env.VITE_BACKEND_API_URL ||
      'http://localhost:5000';
    this.adminKey = adminKey || import.meta.env.VITE_API_ADMIN_KEY || '';
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const headers = {
      'Content-Type': 'application/json',
      'X-Admin-Key': this.adminKey,
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>('/health', {
      method: 'GET',
      headers: {}, // No auth needed for health check
    });
  }

  // Get current config
  async getConfig(): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>('/config', {
      method: 'GET',
    });
  }

  // Update config
  async updateConfig(updates: UpdateConfigRequest): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>('/config', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  // Reload config from MongoDB
  async reloadConfig(): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>('/config/reload', {
      method: 'POST',
    });
  }

  // Update AI provider
  async updateAIProvider(
    data: UpdateAIProviderRequest,
  ): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>('/config/ai-provider', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // Add admin
  async addAdmin(userId: number): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>('/config/admins', {
      method: 'POST',
      body: JSON.stringify({ userId }),
    });
  }

  // Remove admin
  async removeAdmin(userId: number): Promise<ConfigResponse> {
    return this.fetch<ConfigResponse>(`/config/admins/${userId}`, {
      method: 'DELETE',
    });
  }

  // Get config version
  async getVersion(): Promise<VersionResponse> {
    return this.fetch<VersionResponse>('/config/version', {
      method: 'GET',
    });
  }

  // Helper: Update invisible mode
  async setInvisible(invisible: boolean): Promise<ConfigResponse> {
    return this.updateConfig({ invisible });
  }

  // Helper: Update mention cooldown
  async setMentionCooldown(seconds: number): Promise<ConfigResponse> {
    return this.updateConfig({ mentionCooldown: seconds });
  }

  // Helper: Add to block list
  async addToBlockList(userId: string): Promise<ConfigResponse> {
    const config = await this.getConfig();
    const currentList = config.config?.globalBlockList || [];

    if (currentList.includes(userId)) {
      throw new Error('User already blocked');
    }

    return this.updateConfig({
      globalBlockList: [...currentList, userId],
    });
  }

  // Helper: Remove from block list
  async removeFromBlockList(userId: string): Promise<ConfigResponse> {
    const config = await this.getConfig();
    const currentList = config.config?.globalBlockList || [];

    return this.updateConfig({
      globalBlockList: currentList.filter((id) => id !== userId),
    });
  }

  // Helper: Add to cooldown bypass
  async addToCooldownBypass(userId: string): Promise<ConfigResponse> {
    const config = await this.getConfig();
    const currentList = config.config?.cooldownBypassList || [];

    if (currentList.includes(userId)) {
      throw new Error('User already in bypass list');
    }

    return this.updateConfig({
      cooldownBypassList: [...currentList, userId],
    });
  }

  // Helper: Remove from cooldown bypass
  async removeFromCooldownBypass(userId: string): Promise<ConfigResponse> {
    const config = await this.getConfig();
    const currentList = config.config?.cooldownBypassList || [];

    return this.updateConfig({
      cooldownBypassList: currentList.filter((id) => id !== userId),
    });
  }
}

// Singleton instance
let apiClient: ConfigAPIClient | null = null;

export function getAPIClient(): ConfigAPIClient {
  if (!apiClient) {
    apiClient = new ConfigAPIClient('/api', env.ADMIN_API_KEY);
  }
  return apiClient;
}

// Default export
export default getAPIClient;
