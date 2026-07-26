import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAPIClient } from '../lib/api-client';
import type { UpdateEconomyProfileRequest } from '../lib/api-client';

const apiClient = getAPIClient();

export const economyKeys = {
  all: ['economy'] as const,
  leaderboard: (sortBy: string) => [...economyKeys.all, 'leaderboard', sortBy] as const,
  profile: (userId: string) => [...economyKeys.all, 'profile', userId] as const,
  rank: (userId: string) => [...economyKeys.all, 'rank', userId] as const,
};

export const memberKeys = {
  all: ['members'] as const,
  list: (search?: string) => [...memberKeys.all, search] as const,
};

export function useGuildMembers(search?: string) {
  return useQuery({
    queryKey: memberKeys.list(search),
    queryFn: () => apiClient.getMembers(search),
    staleTime: 60000,
  });
}

export function useEconomyLeaderboard(sortBy: string = 'xp', limit: number = 25) {
  return useQuery({
    queryKey: economyKeys.leaderboard(sortBy),
    queryFn: () => apiClient.getEconomyLeaderboard(sortBy, limit),
    staleTime: 30000,
  });
}

export function useEconomyProfile(userId: string) {
  return useQuery({
    queryKey: economyKeys.profile(userId),
    queryFn: () => apiClient.getEconomyProfile(userId),
    enabled: userId.length > 0,
    staleTime: 10000,
  });
}

export function useEconomyRank(userId: string) {
  return useQuery({
    queryKey: economyKeys.rank(userId),
    queryFn: () => apiClient.getEconomyRank(userId),
    enabled: userId.length > 0,
    staleTime: 30000,
  });
}

export function useUpdateEconomyProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateEconomyProfileRequest }) =>
      apiClient.updateEconomyProfile(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: economyKeys.all });
    },
  });
}