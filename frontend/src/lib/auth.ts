import { env } from "@/config/env";

const DISCORD_API_BASE = 'https://discord.com/api/v10';

export interface DiscordUser {
  id: string;
  username: string;
  discriminator: string;
  avatar: string | null;
  email?: string;
  verified?: boolean;
  global_name?: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  scope: string;
}

export interface AuthState {
  user: DiscordUser | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// Generate Discord OAuth URL
export const getDiscordAuthUrl = (): string => {
  const params = new URLSearchParams({
    client_id: env.DISCORD_CLIENT_ID || '',
    redirect_uri: env.DISCORD_REDIRECT_URI,
    response_type: 'code',
    scope: 'identify email',
  });
  
  return `https://discord.com/oauth2/authorize?${params.toString()}`;
};

// Exchange code for tokens
export const exchangeCodeForTokens = async (code: string): Promise<AuthTokens> => {
  const response = await fetch(`${DISCORD_API_BASE}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_id: env.DISCORD_CLIENT_ID || '',
      client_secret: import.meta.env.VITE_DISCORD_CLIENT_SECRET || '',
      grant_type: 'authorization_code',
      code,
      redirect_uri: env.DISCORD_REDIRECT_URI,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to exchange code for tokens');
  }

  return response.json();
};

// Get user info from Discord
export const getDiscordUser = async (accessToken: string): Promise<DiscordUser> => {
  const response = await fetch(`${DISCORD_API_BASE}/users/@me`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch user info');
  }

  return response.json();
};

// Refresh access token
export const refreshAccessToken = async (refreshToken: string): Promise<AuthTokens> => {
  const response = await fetch(`${DISCORD_API_BASE}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_id: env.DISCORD_CLIENT_ID || '',
      client_secret: import.meta.env.VITE_DISCORD_CLIENT_SECRET || '',
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to refresh access token');
  }

  return response.json();
};

// Revoke token
export const revokeToken = async (token: string): Promise<void> => {
  await fetch(`${DISCORD_API_BASE}/oauth2/token/revoke`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_id: env.DISCORD_CLIENT_ID || '',
      client_secret: env.DISCORD_CLIENT_SECRET || '',
      token,
    }),
  });
};

// Storage helpers
export const AUTH_STORAGE_KEY = 'discord_auth_state';

export const saveAuthState = (state: { user: DiscordUser; tokens: AuthTokens }): void => {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(state));
};

export const loadAuthState = (): { user: DiscordUser; tokens: AuthTokens } | null => {
  const stored = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!stored) return null;
  
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
};

export const clearAuthState = (): void => {
  localStorage.removeItem(AUTH_STORAGE_KEY);
};

// Get Discord avatar URL
export const getAvatarUrl = (user: DiscordUser, size = 128): string => {
  if (!user.avatar) {
    // Default avatar
    const defaultAvatarNumber = user.discriminator === '0' 
      ? (parseInt(user.id) >> 22) % 6
      : parseInt(user.discriminator) % 5;
    return `https://cdn.discordapp.com/embed/avatars/${defaultAvatarNumber}.png`;
  }
  
  const extension = user.avatar.startsWith('a_') ? 'gif' : 'png';
  return `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.${extension}?size=${size}`;
};
