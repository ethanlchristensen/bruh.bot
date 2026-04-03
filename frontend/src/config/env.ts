import * as z from 'zod';

const createEnv = () => {
  const EnvSchema = z.object({
    BACKEND_API_URL: z.string(),
    APP_URL: z.string().optional().default('http://localhost:6969'),
    ADMIN_API_KEY: z.string(),
    DISCORD_CLIENT_ID: z.string(),
    DISCORD_CLIENT_SECRET: z.string(),
    DISCORD_REDIRECT_URI: z.string(),
    DEFAULT_GUILD_ID: z.string(),
    MUSIC_WS_URL: z.string().optional(),
  });

  const envVars = Object.entries(import.meta.env).reduce<
    Record<string, string>
  >((acc, curr) => {
    const [key, value] = curr;
    if (key.startsWith('VITE_')) {
      acc[key.replace('VITE_', '')] = value;
    }
    return acc;
  }, {});

  // Default music WS URL if not provided
  if (!envVars.MUSIC_WS_URL) {
    // If BACKEND_API_URL is http://localhost:5000, we want ws://localhost:8001
    // This is a bit of a guess, but common for local dev.
    // For production, the user should provide VITE_MUSIC_WS_URL.
    const apiUrl = envVars.BACKEND_API_URL || 'http://localhost:5000';
    try {
      const url = new URL(apiUrl);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      // Default to port 8001 for music WS as seen in the bot code
      envVars.MUSIC_WS_URL = `${wsProtocol}//${url.hostname}:8001/ws`;
    } catch {
      envVars.MUSIC_WS_URL = 'ws://localhost:8001/ws';
    }
  }

  const parsedEnv = EnvSchema.safeParse(envVars);

  if (!parsedEnv.success) {
    throw new Error(
      `Invalid env provided. The following variables are missing or invalid:
${Object.entries(parsedEnv.error.flatten().fieldErrors)
  .map(([k, v]) => `- ${k}: ${v}`)
  .join('\n')}
`,
    );
  }

  return parsedEnv.data;
};

export const env = createEnv();
