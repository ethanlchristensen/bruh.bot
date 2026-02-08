// frontend/src/lib/hooks/useConfig.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAPIClient } from "../lib/api-client";
import type {
  UpdateConfigRequest,
  UpdateAIProviderRequest,
} from  "../lib/api-client";

const apiClient = getAPIClient();

// Query keys
export const configKeys = {
  all: ["config"] as const,
  detail: () => [...configKeys.all, "detail"] as const,
  version: () => [...configKeys.all, "version"] as const,
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
    mutationFn: (updates: UpdateConfigRequest) => apiClient.updateConfig(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

// Update AI provider
export function useUpdateAIProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAIProviderRequest) => apiClient.updateAIProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

// Add admin
export function useAddAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => apiClient.addAdmin(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

// Remove admin
export function useRemoveAdmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: number) => apiClient.removeAdmin(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}

// Reload config
export function useReloadConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => apiClient.reloadConfig(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all });
    },
  });
}