import React, { createContext, useContext, useState, useCallback } from 'react';
import type { UpdateConfigRequest, UpdateAIProviderRequest } from '@/lib/api-client';

interface PendingChanges {
  config?: Partial<UpdateConfigRequest>;
  aiProvider?: UpdateAIProviderRequest;
}

interface ConfigChangesContextType {
  pendingChanges: PendingChanges;
  hasPendingChanges: boolean;
  addConfigChange: (updates: Partial<UpdateConfigRequest>) => void;
  addAIProviderChange: (updates: UpdateAIProviderRequest) => void;
  clearChanges: () => void;
  getPendingChanges: () => PendingChanges;
}

const ConfigChangesContext = createContext<ConfigChangesContextType | undefined>(undefined);

export function ConfigChangesProvider({ children }: { children: React.ReactNode }) {
  const [pendingChanges, setPendingChanges] = useState<PendingChanges>({});

  const addConfigChange = useCallback((updates: Partial<UpdateConfigRequest>) => {
    setPendingChanges((prev) => ({
      ...prev,
      config: { ...prev.config, ...updates },
    }));
  }, []);

  const addAIProviderChange = useCallback((updates: UpdateAIProviderRequest) => {
    setPendingChanges((prev) => ({
      ...prev,
      aiProvider: { ...prev.aiProvider, ...updates },
    }));
  }, []);

  const clearChanges = useCallback(() => {
    setPendingChanges({});
  }, []);

  const getPendingChanges = useCallback(() => {
    return pendingChanges;
  }, [pendingChanges]);

  const hasPendingChanges = Object.keys(pendingChanges.config || {}).length > 0 || 
                           Object.keys(pendingChanges.aiProvider || {}).length > 0;

  return (
    <ConfigChangesContext.Provider
      value={{
        pendingChanges,
        hasPendingChanges,
        addConfigChange,
        addAIProviderChange,
        clearChanges,
        getPendingChanges,
      }}
    >
      {children}
    </ConfigChangesContext.Provider>
  );
}

export function useConfigChanges() {
  const context = useContext(ConfigChangesContext);
  if (!context) {
    throw new Error('useConfigChanges must be used within ConfigChangesProvider');
  }
  return context;
}
