import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { getAPIClient } from '@/lib/api-client';
import { env } from '@/config/env';

interface GuildContextType {
  selectedGuildId: string;
  setSelectedGuildId: (guildId: string) => void;
}

const GuildContext = createContext<GuildContextType | undefined>(undefined);

export function GuildProvider({ children }: { children: ReactNode }) {
  const [selectedGuildId, setSelectedGuildIdState] = useState<string>(
    () => localStorage.getItem('selectedGuildId') || env.DEFAULT_GUILD_ID,
  );

  const setSelectedGuildId = (guildId: string) => {
    setSelectedGuildIdState(guildId);
    localStorage.setItem('selectedGuildId', guildId);
    // Update the API client
    const apiClient = getAPIClient();
    apiClient.setGuildId(guildId);
  };

  useEffect(() => {
    // Set initial guild ID on mount
    const apiClient = getAPIClient();
    apiClient.setGuildId(selectedGuildId);
  }, [selectedGuildId]);

  return (
    <GuildContext.Provider value={{ selectedGuildId, setSelectedGuildId }}>
      {children}
    </GuildContext.Provider>
  );
}

export function useGuild() {
  const context = useContext(GuildContext);
  if (!context) {
    throw new Error('useGuild must be used within a GuildProvider');
  }
  return context;
}
