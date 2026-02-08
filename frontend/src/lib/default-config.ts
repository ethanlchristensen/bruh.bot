import type { BotConfig } from '@/lib/types'

export const defaultConfig: BotConfig = {
  devDiscordToken: "",
  prodDiscordToken: "",
  adminIds: ["100000000000000000"],
  invisible: false,
  aiConfig: {
    preferredAiProvider: "google",
    boostImagePrompts: false,
    maxDailyImages: 5,
    ollama: {
      endpoint: "localhost:11434",
      preferredModel: "llama3.1",
    },
    openai: {
      apiKey: "",
      preferredModel: "gpt-5-nano",
    },
    antropic: {
      apiKey: "",
      preferredModel: "claude-4-5-sonnet",
    },
    gemini: {
      apiKey: "",
      preferredModel: "gemini-2.5-flash",
    },
    elevenlabs: {
      apiKey: "",
    },
    orchestrator: {
      preferredAiProvider: "google",
      preferredModel: "gemini-2.5-flash",
    },
    realTimeConfig: {
      realTimeModel: "gpt-realtime-mini",
      apiKey: "",
      voice: "sage",
    },
  },
  usersToId: {
    name1: "<@100000000000000000>",
    name2: "<@200000000000000000>",
    name3: "<@300000000000000000>",
  },
  idToUsers: {
    "000000000000000000": "name1",
    "100000000000000000": "name2",
    "200000000000000000": "name3",
  },
  mentionCooldown: 20,
  cooldownBypassList: ["100000000000000000"],
  promptsPath: "prompts.json",
  mongoUri: "mongodb://localhost:27017/",
  mongoDbName: "DB",
  mongoMessagesCollectionName: "COLLECTION",
  mongoMorningConfigsCollectionName: "MORNING_CONFIGS",
  mongoImageLimitsCollectionName: "IMAGE_LIMITS",
  allowedBotsToRespondTo: [],
  deleteUserMessages: {
    enabled: false,
    userIds: ["100000000000000000"],
  },
  globalBlockList: ["100000000000000000"],
}
