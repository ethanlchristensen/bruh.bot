import { env } from '@/config/env';

export type AIProvider = 'ollama' | 'openrouter' | 'mesh_router';

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

export interface ImageGenerationConfig {
  preferredAiProvider?: 'google' | 'openrouter';
  preferredAiProvidder?: string;
  preferredModel?: string;
  maxDailyImages?: number;
  boostImagePrompts?: boolean;
}

export interface AIUsageLimitConfig {
  enabled: boolean;
  maxRequestsPerMinute: number;
  maxRequestsPerHour: number;
}

export interface AIConfig {
  preferredAiProvider: AIProvider;
  ollama: ProviderConfig;
  openrouter: ProviderConfig;
  mesh_router: ProviderConfig;
  elevenlabs: ProviderConfig;
  realTimeConfig: ProviderConfig;
  orchestrator: OrchestratorConfig;
  boostImagePrompts: boolean;
  maxDailyImages: number;
  systemPrompt?: string;
  realtimePrompt?: string;
  imageGeneration?: ImageGenerationConfig;
  usageLimits?: AIUsageLimitConfig;
}

export interface DeleteUserMessagesConfig {
  enabled: boolean;
  userIds: Array<number>;
}

export interface MemoryConfig {
  enabled: boolean;
  extractionIntervalMinutes: number;
  moodExtractionIntervalMinutes: number;
  extractionProvider: string;
  extractionModel: string;
  orchestratorProvider: string;
  orchestratorModel: string;
  maxMessagesPerExtraction: number;
  minMessagesForExtraction: number;
  minMessageLength: number;
  maxMemoriesPerUser: number;
  maxInjectionCount: number;
  enabledCategories: Array<string>;
  embeddingModel: string;
  embeddingDimensions: number;
  maxToolRounds: number;
  maxToolCallsPerBatch: number;
  maxAddsPerUserPerBatch: number;
  dedupeThreshold: number;
  semanticRetrieval: boolean;
  retrievalMinScore: number;
}

export interface EconomyConfig {
  xpEnabled: boolean;
  coinsEnabled: boolean;
  baseXpRange: [number, number];
  imageXpBonus: number;
  reactionXp: number;
  mentionXpRange: [number, number];
  messageCoinRange: [number, number];
  imageCoinBonus: number;
  reactionCoin: number;
  mentionCoinRange: [number, number];
  dailyCoinMin: number;
  dailyCoinMax: number;
  levelUpAnnounceInChannel: boolean;
  spamCoinThreshold: number;
  spamCoinPenaltyIncrement: number;
  spamCoinPenaltyRecovery: number;
  spamCoinPenaltyMax: number;
  gamblingMaxCoinflipsPerDay: number;
  gamblingMaxDicePerDay: number;
  gamblingMaxSlotsPerDay: number;
  cardPacksEnabled: boolean;
  tradingEnabled: boolean;
  marketplaceEnabled: boolean;
  marketplaceFeeRate: number;
  tradeCooldownMinutes: number;
  cardSellbackRate: number;
  cosmeticsShopEnabled: boolean;
  bruhCardsEnabled: boolean;
  tradingCardPacksEnabled: boolean;
  tradingCardTradingEnabled: boolean;
  tradingCardMarketEnabled: boolean;
  tradingCardMarketFeeRate: number;
  tradingCardSellbackRate: number;
  tradingCardMaxActiveListings: number;
}

export interface ReputationConfig {
  enabled: boolean;
  extractionProvider: AIProvider;
  extractionModel: string;
  minMessagesForExtraction: number;
  maxMessagesPerExtraction: number;
  maxExtractionWaitMinutes: number;
  extractionIntervalMinutes: number;
  minConfidence: number;
  warningThreshold: number;
  blockThreshold: number;
  blockDurationHours: number;
  noticeCooldownHours: number;
}

export interface ReputationProfile {
  user_id: string;
  score: number;
  status: 'active' | 'warning' | 'blocked' | 'manual_blocked';
  blocked_until: string | null;
  updated_at: string | null;
}

export interface ReputationEvent {
  id: string;
  summary: string;
  reason_code: string;
  score_delta: number;
  source: string;
  created_at: string | null;
}

export interface ReputationResponse {
  success: boolean;
  profile: ReputationProfile;
  events: Array<ReputationEvent>;
}

export interface EconomyProfile {
  user_id: string;
  guild_id: number;
  xp: number;
  level: number;
  bruh_coins: number;
  total_messages: number;
  total_images: number;
  total_reactions_given: number;
  total_bot_mentions: number;
  last_xp_grant: string | null;
  last_daily_claim: string | null;
  xp_for_next_level: number;
  xp_for_current_level: number;
  rank?: number;
}

export interface EconomyLeaderboardEntry {
  user_id: string;
  username: string;
  avatar_url: string;
  xp: number;
  level: number;
  bruh_coins: number;
  total_messages: number;
  total_images: number;
  total_reactions_given: number;
  rank: number;
}

export interface EconomyLeaderboardResponse {
  success: boolean;
  guild_id: string;
  sort_by: string;
  leaderboard: Array<EconomyLeaderboardEntry>;
}

export interface EconomyProfileResponse {
  success: boolean;
  guild_id: string;
  profile: EconomyProfile;
}

export interface EconomyRankResponse {
  success: boolean;
  guild_id: string;
  user_id: string;
  rank: number;
}

export interface GuildMember {
  user_id: string;
  username: string;
  display_name: string;
  global_name: string | null;
  avatar_url: string;
}

export interface MembersResponse {
  success: boolean;
  guild_id: string;
  members: Array<GuildMember>;
  count: number;
}

export interface UpdateEconomyProfileRequest {
  xp?: number;
  bruh_coins?: number;
  level?: number;
}

export interface UpdateEconomyProfileResponse {
  success: boolean;
  guild_id: string;
  profile: EconomyProfile;
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
  memoryConfig: MemoryConfig;
  economyConfig?: EconomyConfig;
  reputationConfig: ReputationConfig;
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
  mongoMessagesDbName?: string;
  mongoMessagesCollectionName?: string;
  allowedBotsToRespondTo?: Array<string>;
  usersToId?: Record<string, string>;
  idToUsers?: Record<string, string>;
  memoryConfig?: Partial<MemoryConfig>;
  economyConfig?: Partial<EconomyConfig>;
  reputationConfig?: Partial<ReputationConfig>;
}

export interface UpdateAIProviderRequest {
  provider: AIProvider;
  apiKey?: string;
  preferredModel?: string;
  endpoint?: string;
  voice?: string;
  orchestratorProvider?: AIProvider;
  orchestratorModel?: string;
  systemPrompt?: string;
  realtimePrompt?: string;
  boostImagePrompts?: boolean;
  maxDailyImages?: number;
  imageGenProvider?: 'google' | 'openrouter';
  imageGenModel?: string;
  maxRequestsPerMinute?: number;
  maxRequestsPerHour?: number;
  aiUsageLimitEnabled?: boolean;
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

export interface MemoryItem {
  id: string;
  guild_id: string;
  user_id: string;
  memory: string;
  category: string;
  confidence: number;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
  expires_at: string | null;
  source_message_id: string | null;
  target_user_id: string | null;
  ttl_days: number | null;
  is_permanent: boolean;
  is_expired: boolean;
}

export interface MemoriesResponse {
  success: boolean;
  user_id: string;
  memories: Array<MemoryItem>;
  count: number;
}

export interface DeleteMemoryResponse {
  success: boolean;
  message: string;
}

export interface UserEntry {
  id: string;
  username: string;
  avatar_url: string;
  memory_count: number;
}

export interface UsersResponse {
  success: boolean;
  users: Array<UserEntry>;
}

export interface Guild {
  id: string;
  name: string;
  icon: string;
}

export interface GuildsResponse {
  success: boolean;
  guilds: Array<Guild>;
}

export interface LeaderboardEntry {
  user_id: string;
  username: string;
  avatar_url: string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  models_used: Record<
    string,
    {
      requests: number;
      input_tokens: number;
      output_tokens: number;
      cost: number;
    }
  >;
}

export interface UsageLeaderboardResponse {
  success: boolean;
  guild_id: string;
  days: number | null;
  leaderboard: Array<LeaderboardEntry>;
  summary: { total_requests: number; total_cost: number };
}

export interface TradingCardPackCard {
  card_id: string;
  number: number;
  name: string;
  rarity: string;
  description: string;
  asset_sha256: string;
}

export interface TradingCardPack {
  pack_id: string;
  series_id: string;
  name: string;
  price: number;
  cards_per_pack: number;
  guaranteed_rarity: string | null;
  description: string;
  eligible_cards: Record<string, Array<TradingCardPackCard>>;
}

export interface TradingCardPacksResponse {
  success: boolean;
  packs: Array<TradingCardPack>;
  render_version?: string;
}

export interface TradingCardSet {
  series_id: string;
  display_name: string;
  pack_count: number;
}

export interface TradingCardSetsResponse {
  success: boolean;
  sets: Array<TradingCardSet>;
  render_version?: string;
}

export interface TradingCardSetPack {
  pack_id: string;
  name: string;
  price: number;
  cards_per_pack: number;
  guaranteed_rarity: string | null;
  description: string;
}

export interface TradingCardSetDetailResponse {
  success: boolean;
  series_id: string;
  display_name: string;
  packs: Array<TradingCardSetPack>;
  eligible_cards: Record<string, Array<TradingCardPackCard>>;
  render_version?: string;
}

export class ConfigAPIClient {
  private baseUrl: string;
  private adminKey: string;
  private currentGuildId: string;

  constructor(baseUrl?: string, adminKey?: string, defaultGuildId?: string) {
    this.baseUrl =
      baseUrl ||
      import.meta.env.VITE_BACKEND_API_URL ||
      'http://localhost:5000';
    this.adminKey = adminKey || import.meta.env.VITE_API_ADMIN_KEY || '';
    this.currentGuildId =
      defaultGuildId || import.meta.env.VITE_DEFAULT_GUILD_ID || '';
  }

  setGuildId(guildId: string) {
    this.currentGuildId = guildId;
  }

  getGuildId(): string {
    return this.currentGuildId;
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const headers = {
      'Content-Type': 'application/json',
      'X-Admin-Key': this.adminKey,
      'X-Guild-ID': this.currentGuildId,
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

  // Get available models for a provider
  async getModels(
    provider: string,
    endpoint?: string,
    imageGen?: boolean,
    structuredOutputs?: boolean,
    refresh?: boolean,
  ): Promise<{ success: boolean; models: Array<string>; error?: string }> {
    const ep = endpoint ? encodeURIComponent(endpoint) : '';
    const ig = imageGen ? '&image_gen=true' : '';
    const so = structuredOutputs ? '&structured_outputs=true' : '';
    const rf = refresh ? '&refresh=true' : '';
    return this.fetch<{
      success: boolean;
      models: Array<string>;
      error?: string;
    }>(`/config/models?provider=${provider}&endpoint=${ep}${ig}${so}${rf}`, {
      method: 'GET',
    });
  }

  // Get available guilds
  async getGuilds(): Promise<GuildsResponse> {
    return this.fetch<GuildsResponse>('/guilds', {
      method: 'GET',
    });
  }

  // Get usage leaderboard
  async getUsageLeaderboard(days?: number): Promise<UsageLeaderboardResponse> {
    const params = days ? `?days=${days}` : '';
    return this.fetch<UsageLeaderboardResponse>(`/usage/leaderboard${params}`, {
      method: 'GET',
    });
  }

  // Get memories for a specific user
  async getUserMemories(userId: string): Promise<MemoriesResponse> {
    return this.fetch<MemoriesResponse>(`/memories/${userId}`, {
      method: 'GET',
    });
  }

  // Get all known users
  async getUsers(): Promise<UsersResponse> {
    return this.fetch<UsersResponse>('/users', {
      method: 'GET',
    });
  }

  // Delete a specific memory
  async deleteMemory(memoryId: string): Promise<DeleteMemoryResponse> {
    return this.fetch<DeleteMemoryResponse>(`/memories/${memoryId}`, {
      method: 'DELETE',
    });
  }

  // Get economy leaderboard
  async getEconomyLeaderboard(
    sortBy: string = 'xp',
    limit: number = 25,
  ): Promise<EconomyLeaderboardResponse> {
    return this.fetch<EconomyLeaderboardResponse>(
      `/economy/leaderboard?sort_by=${sortBy}&limit=${limit}`,
      { method: 'GET' },
    );
  }

  // Get economy profile
  async getEconomyProfile(userId: string): Promise<EconomyProfileResponse> {
    return this.fetch<EconomyProfileResponse>(`/economy/profile/${userId}`, {
      method: 'GET',
    });
  }

  // Update economy profile
  async updateEconomyProfile(
    userId: string,
    data: UpdateEconomyProfileRequest,
  ): Promise<UpdateEconomyProfileResponse> {
    return this.fetch<UpdateEconomyProfileResponse>(
      `/economy/profile/${userId}`,
      {
        method: 'PUT',
        body: JSON.stringify(data),
      },
    );
  }

  // Get economy rank
  async getEconomyRank(userId: string): Promise<EconomyRankResponse> {
    return this.fetch<EconomyRankResponse>(`/economy/rank/${userId}`, {
      method: 'GET',
    });
  }

  // Get guild members
  async getMembers(search?: string): Promise<MembersResponse> {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    return this.fetch<MembersResponse>(`/members${params}`, {
      method: 'GET',
    });
  }

  // Get trading card packs with eligible cards
  async getTradingCardPacks(): Promise<TradingCardPacksResponse> {
    return this.fetch<TradingCardPacksResponse>('/trading-cards/packs', {
      method: 'GET',
    });
  }

  // Get trading card sets (lightweight — just series list)
  async getTradingCardSets(): Promise<TradingCardSetsResponse> {
    return this.fetch<TradingCardSetsResponse>('/trading-cards/sets', {
      method: 'GET',
    });
  }

  // Get a single trading card set with packs and eligible cards
  async getTradingCardSet(seriesId: string): Promise<TradingCardSetDetailResponse> {
    return this.fetch<TradingCardSetDetailResponse>(`/trading-cards/sets/${seriesId}`, {
      method: 'GET',
    });
  }

  // Create a new trading card pack
  async createTradingCardPack(data: {
    pack_id: string;
    series_id: string;
    name: string;
    price: number;
    cards_per_pack?: number;
    guaranteed_rarity?: string | null;
    description?: string;
    released?: boolean;
  }): Promise<{ success: boolean; message: string }> {
    return this.fetch('/trading-cards/packs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Update a trading card pack
  async updateTradingCardPack(
    packId: string,
    data: {
      name?: string;
      price?: number;
      cards_per_pack?: number;
      guaranteed_rarity?: string;
      description?: string;
      released?: boolean;
    },
  ): Promise<{ success: boolean; message: string; updates: Record<string, unknown> }> {
    return this.fetch(`/trading-cards/packs/${packId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async getReputation(userId: string): Promise<ReputationResponse> {
    return this.fetch<ReputationResponse>(`/reputation/${userId}`, {
      method: 'GET',
    });
  }

  async updateReputation(
    userId: string,
    data: {
      score?: number;
      status?: ReputationProfile['status'];
      reason: string;
    },
  ): Promise<{ success: boolean; profile: ReputationProfile }> {
    return this.fetch(`/reputation/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
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
    apiClient = new ConfigAPIClient(
      '/api',
      env.ADMIN_API_KEY,
      env.DEFAULT_GUILD_ID,
    );
  }
  return apiClient;
}

// Default export
export default getAPIClient;
