import React, { createContext, useCallback, useContext, useState } from 'react';
import type { AIConfig, UpdateConfigRequest } from '@/lib/api-client';

type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

interface PendingChanges {
  config?: Partial<UpdateConfigRequest>;
  aiConfig?: DeepPartial<AIConfig>;
}

interface ConfigChangesContextType {
  pendingChanges: PendingChanges;
  hasPendingChanges: boolean;
  addConfigChange: (updates: Partial<UpdateConfigRequest>) => void;
  addAIConfigChange: (updates: DeepPartial<AIConfig>) => void;
  clearChanges: () => void;
}

const ConfigChangesContext = createContext<
  ConfigChangesContextType | undefined
>(undefined);

export function ConfigChangesProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [pendingChanges, setPendingChanges] = useState<PendingChanges>({});

  const addConfigChange = useCallback(
    (updates: Partial<UpdateConfigRequest>) => {
      setPendingChanges((prev) => ({
        ...prev,
        config: { ...prev.config, ...updates },
      }));
    },
    [],
  );

  const addAIConfigChange = useCallback((updates: DeepPartial<AIConfig>) => {
    setPendingChanges((prev) => {
      const currentAi = prev.aiConfig || {};

      const mergedAi: any = { ...currentAi };

      (Object.keys(updates) as Array<keyof AIConfig>).forEach((key) => {
        const updateValue = updates[key];
        const currentValue = mergedAi[key];

        if (
          typeof updateValue === 'object' &&
          currentValue &&
          typeof currentValue === 'object' &&
          !Array.isArray(updateValue)
        ) {
          mergedAi[key] = { ...currentValue, ...updateValue };
        } else {
          mergedAi[key] = updateValue;
        }
      });

      return {
        ...prev,
        aiConfig: mergedAi,
      };
    });
  }, []);

  const clearChanges = useCallback(() => {
    setPendingChanges({});
  }, []);

  const hasPendingChanges =
    Object.keys(pendingChanges.config || {}).length > 0 ||
    Object.keys(pendingChanges.aiConfig || {}).length > 0;

  return (
    <ConfigChangesContext.Provider
      value={{
        pendingChanges,
        hasPendingChanges,
        addConfigChange,
        addAIConfigChange,
        clearChanges,
      }}
    >
      {children}
    </ConfigChangesContext.Provider>
  );
}

export function useConfigChanges() {
  const context = useContext(ConfigChangesContext);
  if (!context) {
    throw new Error(
      'useConfigChanges must be used within ConfigChangesProvider',
    );
  }
  return context;
}
