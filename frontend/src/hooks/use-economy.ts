import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAPIClient } from '../lib/api-client';
import type { UpdateEconomyProfileRequest } from '../lib/api-client';

const apiClient = getAPIClient();

export const economyKeys = {
  all: ['economy'] as const,
  leaderboard: (sortBy: string) => [...economyKeys.all, 'leaderboard', sortBy] as const,
  profile: (userId: string) => [...economyKeys.all, 'profile', userId] as const,
  rank: (userId: string) => [...economyKeys.all, 'rank', userId] as const,
  tradingCardPacks: ['trading-card-packs'] as const,
  tradingCardSets: ['trading-card-sets'] as const,
  tradingCardSet: (seriesId: string) => [...economyKeys.tradingCardSets, seriesId] as const,
  tradingCardCollection: (userId: string) => [...economyKeys.all, 'trading-card-collection', userId] as const,
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

export function useTradingCardPacks() {
  return useQuery({
    queryKey: economyKeys.tradingCardPacks,
    queryFn: () => apiClient.getTradingCardPacks(),
    staleTime: 60000,
  });
}

export function useTradingCardSets() {
  return useQuery({
    queryKey: economyKeys.tradingCardSets,
    queryFn: () => apiClient.getTradingCardSets(),
    staleTime: 60000,
  });
}

export function useTradingCardSet(seriesId: string | null) {
  return useQuery({
    queryKey: economyKeys.tradingCardSet(seriesId ?? ''),
    queryFn: () => apiClient.getTradingCardSet(seriesId!),
    enabled: !!seriesId,
    staleTime: 30000,
  });
}

export function useTradingCardCollection(userId: string) {
  return useQuery({
    queryKey: economyKeys.tradingCardCollection(userId),
    queryFn: () => apiClient.getTradingCardCollection(userId),
    enabled: userId.length > 0,
    staleTime: 10000,
  });
}

export function useCreateTradingCardPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      pack_id: string;
      series_id: string;
      name: string;
      price: number;
      cards_per_pack?: number;
      guaranteed_rarity?: string | null;
      description?: string;
      released?: boolean;
    }) => apiClient.createTradingCardPack(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardPacks });
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardSets });
    },
  });
}

export function useUpdateTradingCardPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ packId, data }: { packId: string; data: Record<string, unknown> }) =>
      apiClient.updateTradingCardPack(packId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardPacks });
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardSets });
    },
  });
}
