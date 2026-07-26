// frontend/src/lib/hooks/useConfig.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAPIClient } from '../lib/api-client';
import type {
  UpdateAIProviderRequest,
  UpdateConfigRequest,
} from '../lib/api-client';

const apiClient = getAPIClient();

// Query keys
export const configKeys = {
  all: ['config'] as const,
  detail: () => [...configKeys.all, 'detail'] as const,
  version: () => [...configKeys.all, 'version'] as const,
};

export const memoryKeys = {
  all: ['memories'] as const,
  user: (userId: string) => [...memoryKeys.all, userId] as const,
};

// Get config
export function useConfig() {
  return useQuery({
    queryKey: configKeys.detail(),
    queryFn: () => apiClient.getConfig(),
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // Refetch every minute
  });
}

// Get version
export function useConfigVersion() {
  return useQuery({
    queryKey: configKeys.version(),
    queryFn: () => apiClient.getVersion(),
    staleTime: 10000,
  });
}

// Update config
export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (updates: UpdateConfigRequest) =>
      apiClient.updateConfig(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

export function useUpdateAIProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAIProviderRequest) =>
      apiClient.updateAIProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

export function useAddAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => apiClient.addAdmin(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

export function useRemoveAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => apiClient.removeAdmin(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

export function useReloadConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => apiClient.reloadConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

export function useGuilds() {
  return useQuery({
    queryKey: ['guilds'],
    queryFn: () => apiClient.getGuilds(),
    staleTime: 60000, // 1 minute
  });
}

export function useModels(provider: string, endpoint?: string, imageGen?: boolean, structuredOutputs?: boolean) {
  return useQuery({
    queryKey: ['models', provider, endpoint, imageGen, structuredOutputs],
    queryFn: () => apiClient.getModels(provider, endpoint, imageGen, structuredOutputs),
    enabled: !!provider,
    staleTime: 30000,
  });
}

export function useRefreshModels() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { provider: string; endpoint?: string; imageGen?: boolean; structuredOutputs?: boolean }) =>
      apiClient.getModels(params.provider, params.endpoint, params.imageGen, params.structuredOutputs, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
    },
  });
}

export function useUserMemories(userId: string) {
  return useQuery({
    queryKey: memoryKeys.user(userId),
    queryFn: () => apiClient.getUserMemories(userId),
    enabled: userId.length > 0,
    staleTime: 10000,
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) => apiClient.deleteMemory(memoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => apiClient.getUsers(),
    staleTime: 30000,
  });
}

export function useUsageLeaderboard(days?: number) {
  return useQuery({
    queryKey: ['usage', 'leaderboard', days],
    queryFn: () => apiClient.getUsageLeaderboard(days),
    staleTime: 30000,
  });
}
