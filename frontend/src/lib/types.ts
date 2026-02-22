export interface BotConfig {
  devDiscordToken: string
  prodDiscordToken: string
  adminIds: Array<string>
  invisible: boolean
  aiConfig: AIConfig
  usersToId: Record<string, string>
  idToUsers: Record<string, string>
  mentionCooldown: number
  cooldownBypassList: Array<string>
  promptsPath: string
  mongoUri: string
  mongoDbName: string
  mongoMessagesCollectionName: string
  mongoMorningConfigsCollectionName: string
  mongoImageLimitsCollectionName: string
  allowedBotsToRespondTo: Array<string>
  deleteUserMessages: DeleteUserMessagesConfig
  globalBlockList: Array<string>
}

export interface AIConfig {
  preferredAiProvider: string
  boostImagePrompts: boolean
  maxDailyImages: number
  ollama: OllamaConfig
  openai: OpenAIConfig
  antropic: AntropicConfig
  gemini: GeminiConfig
  elevenlabs: ElevenLabsConfig
  orchestrator: OrchestratorConfig
  realTimeConfig: RealTimeConfig
}

export interface OllamaConfig {
  endpoint: string
  preferredModel: string
}

export interface OpenAIConfig {
  apiKey: string
  preferredModel: string
}

export interface AntropicConfig {
  apiKey: string
  preferredModel: string
}

export interface GeminiConfig {
  apiKey: string
  preferredModel: string
}

export interface ElevenLabsConfig {
  apiKey: string
}

export interface OrchestratorConfig {
  preferredAiProvider: string
  preferredModel: string
}

export interface RealTimeConfig {
  realTimeModel: string
  apiKey: string
  voice: string
}

export interface DeleteUserMessagesConfig {
  enabled: boolean
  userIds: Array<string>
}
