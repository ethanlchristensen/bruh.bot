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
    // We now route /ws/ through nginx (or Vite dev server)
    const isBrowser = typeof window !== 'undefined';
    if (isBrowser) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        envVars.MUSIC_WS_URL = `${protocol}//${window.location.host}/ws`;
    } else {
        envVars.MUSIC_WS_URL = 'ws://localhost:8003/ws';
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
