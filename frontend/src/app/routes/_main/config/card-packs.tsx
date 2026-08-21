import { useCallback, useEffect, useMemo, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ArrowRight,
  Grid2X2,
  Images,
  Layers3,
  Maximize2,
  Package,
  Plus,
  RefreshCw,
  Save,
  UserRound,
} from 'lucide-react';

import type { TradingCardPackCard } from '@/lib/api-client';
import {
  economyKeys,
  useCreateTradingCardPack,
  useGuildMembers,
  useTradingCardCollection,
  useTradingCardSet,
  useTradingCardSets,
  useUpdateTradingCardPack,
} from '@/hooks/use-economy';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardIcon,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { PageHeader } from '@/components/layouts/page-header';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export const Route = createFileRoute('/_main/config/card-packs')({
  component: CardPacksComponent,
});

const RARITY_ORDER = [
  'basic',
  'common',
  'rare',
  'epic',
  'legendary',
  'diamond',
  'platinum',
] as const;

const RARITY_COLORS: Record<string, string> = {
  basic: '#9B9B9B',
  common: '#1EFF00',
  rare: '#0070DD',
  epic: '#A335EE',
  legendary: '#FF8000',
  diamond: '#00F0FF',
  platinum: '#E5CC80',
};

function cardImageUrl(
  cardId: string,
  assetSha256: string,
  renderVersion?: string,
): string {
  const v = [assetSha256 || '0', renderVersion || '0'].join('-');
  return `/api/trading-cards/card/${encodeURIComponent(cardId)}/image?v=${encodeURIComponent(v)}`;
}

function CardArtwork({
  card,
  renderVersion,
  className,
}: {
  card: TradingCardPackCard;
  renderVersion?: string;
  className?: string;
}) {
  return (
    <div className="relative flex aspect-[3/4] items-center justify-center overflow-hidden bg-muted/30">
      <img
        src={cardImageUrl(card.card_id, card.asset_sha256, renderVersion)}
        alt={card.name}
        className={className ?? 'h-full w-full object-cover'}
        loading="lazy"
        decoding="async"
        onError={(e) => {
          const target = e.currentTarget;
          target.style.display = 'none';
          const placeholder = target.nextElementSibling as HTMLElement;
          placeholder.style.display = 'flex';
        }}
      />
      <div className="absolute inset-0 hidden h-full w-full flex-col items-center justify-center gap-1 text-muted-foreground">
        <Package className="h-6 w-6 opacity-30" />
        <span className="text-xs">No art</span>
      </div>
    </div>
  );
}

function CardPacksComponent() {
  const queryClient = useQueryClient();
  const { data: setsData, isLoading: setsLoading } = useTradingCardSets();
  const [selectedSeriesId, setSelectedSeriesId] = useState<string | null>(null);
  const { data: setDetail, isLoading: setLoading } =
    useTradingCardSet(selectedSeriesId);
  const { data: membersData, isLoading: membersLoading } = useGuildMembers();
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const { data: memberCollection, isLoading: memberCollectionLoading, isError: memberCollectionError } =
    useTradingCardCollection(selectedMemberId);
  const updatePack = useUpdateTradingCardPack();
  const createPack = useCreateTradingCardPack();

  const refreshCatalog = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardSets }),
      queryClient.invalidateQueries({ queryKey: economyKeys.tradingCardPacks }),
    ]);
    toast.success('Card catalog refreshed.');
  };

  const [editPrices, setEditPrices] = useState<Record<string, number>>({});
  const [editGuarantees, setEditGuarantees] = useState<Record<string, string>>(
    {},
  );

  const [showAddForm, setShowAddForm] = useState(false);
  const [newPackId, setNewPackId] = useState('');
  const [newPackName, setNewPackName] = useState('');
  const [newPackPrice, setNewPackPrice] = useState(350);
  const [newPackCardsPer, setNewPackCardsPer] = useState(3);
  const [newPackGuarantee, setNewPackGuarantee] = useState('none');
  const [newPackDesc, setNewPackDesc] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'stack'>('grid');
  const [selectedCard, setSelectedCard] = useState<TradingCardPackCard | null>(
    null,
  );
  const [stackIndex, setStackIndex] = useState(0);

  const sets = setsData?.sets ?? [];
  const selectedMember = membersData?.members.find(
    (member) => member.user_id === selectedMemberId,
  );

  const stackCards = useMemo(() => {
    if (!setDetail) return [];
    return RARITY_ORDER.flatMap((rarity) => setDetail.eligible_cards[rarity] ?? []);
  }, [setDetail]);

  useEffect(() => {
    setStackIndex(0);
    setSelectedCard(null);
  }, [selectedSeriesId]);

  useEffect(() => {
    setSelectedCard(null);
  }, [selectedMemberId]);

  useEffect(() => {
    setStackIndex((index) => Math.min(index, Math.max(0, stackCards.length - 1)));
  }, [stackCards.length]);

  useEffect(() => {
    if (viewMode !== 'stack') return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        setStackIndex((index) => Math.max(0, index - 1));
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        setStackIndex((index) => Math.min(stackCards.length - 1, index + 1));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, stackCards.length]);

  useEffect(() => {
    if (sets.length && !selectedSeriesId) {
      setSelectedSeriesId(sets[0].series_id);
    }
  }, [sets, selectedSeriesId]);

  useEffect(() => {
    if (setDetail?.packs) {
      const prices: Record<string, number> = {};
      const guarantees: Record<string, string> = {};
      for (const p of setDetail.packs) {
        prices[p.pack_id] = p.price;
        guarantees[p.pack_id] = p.guaranteed_rarity ?? 'none';
      }
      setEditPrices(prices);
      setEditGuarantees(guarantees);
    }
  }, [setDetail]);

  const handleSavePack = useCallback(
    async (packId: string) => {
      const original = setDetail?.packs.find((p) => p.pack_id === packId);
      if (!original) return;

      const newPrice = editPrices[packId];
      const newGuarantee = editGuarantees[packId];
      const updates: Record<string, unknown> = {};

      if (newPrice !== original.price) updates.price = newPrice;
      const origGuarantee = original.guaranteed_rarity ?? 'none';
      if (newGuarantee !== origGuarantee) {
        updates.guaranteed_rarity = newGuarantee === 'none' ? '' : newGuarantee;
      }

      if (Object.keys(updates).length === 0) {
        toast.info('No changes to save.');
        return;
      }

      toast.promise(updatePack.mutateAsync({ packId, data: updates }), {
        loading: `Saving ${original.name}...`,
        success: `${original.name} updated.`,
        error: (err) =>
          `Failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
      });
    },
    [setDetail, editPrices, editGuarantees, updatePack],
  );

  const handleAddPack = useCallback(async () => {
    if (!newPackId.trim() || !newPackName.trim() || !selectedSeriesId) {
      toast.error('Pack ID, name, and collection are required.');
      return;
    }

    toast.promise(
      createPack.mutateAsync({
        pack_id: newPackId.trim(),
        series_id: selectedSeriesId,
        name: newPackName.trim(),
        price: newPackPrice,
        cards_per_pack: newPackCardsPer,
        guaranteed_rarity:
          newPackGuarantee === 'none' ? null : newPackGuarantee,
        description: newPackDesc.trim(),
        released: false,
      }),
      {
        loading: 'Creating pack...',
        success: () => {
          setShowAddForm(false);
          setNewPackId('');
          setNewPackName('');
          setNewPackPrice(350);
          setNewPackCardsPer(3);
          setNewPackGuarantee('none');
          setNewPackDesc('');
          return 'Pack created. Run /bruh-cards-admin reload and publish to release.';
        },
        error: (err) =>
          `Failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
      },
    );
  }, [
    newPackId,
    newPackName,
    newPackPrice,
    newPackCardsPer,
    newPackGuarantee,
    newPackDesc,
    selectedSeriesId,
    createPack,
  ]);

  if (setsLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">
          Loading collections...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20" data-page="card-packs">
      <PageHeader
        icon={<Images />}
        title="Card Pack Catalog"
        description="Browse collections, edit packs, and add new pack types."
        children={
          <Button variant="outline" size="sm" onClick={refreshCatalog}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh Catalog
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <CardIcon>
              <UserRound />
            </CardIcon>
            <div>
              <CardTitle>Collection Inspector</CardTitle>
              <CardDescription>
                Select a guild member to review their complete card collection by set.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <Select value={selectedMemberId} onValueChange={setSelectedMemberId}>
            <SelectTrigger className="w-full sm:max-w-md">
              <SelectValue
                placeholder={
                  membersLoading ? 'Loading guild members...' : 'Select a guild member...'
                }
              />
            </SelectTrigger>
            <SelectContent>
              {(membersData?.members ?? []).map((member) => (
                <SelectItem key={member.user_id} value={member.user_id}>
                  <span className="flex items-center gap-2">
                    {member.avatar_url && (
                      <img src={member.avatar_url} alt="" className="size-5 rounded-full" />
                    )}
                    {member.display_name || member.username}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {memberCollectionLoading && (
            <div className="flex justify-center py-8">
              <Spinner className="size-7" />
            </div>
          )}
          {memberCollectionError && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              Unable to load this member&apos;s collection.
            </p>
          )}
          {memberCollection && (
            <div className="space-y-8">
              <div className="flex flex-wrap items-center gap-4 rounded-xl border bg-muted/20 p-4">
                {selectedMember?.avatar_url && (
                  <img
                    src={selectedMember.avatar_url}
                    alt=""
                    className="size-12 rounded-full"
                  />
                )}
                <div className="mr-auto">
                  <p className="font-semibold">
                    {selectedMember?.display_name || selectedMember?.username || selectedMemberId}
                  </p>
                  <p className="text-xs text-muted-foreground">{memberCollection.user_id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Cards</p>
                  <p className="text-xl font-semibold">{memberCollection.total_cards}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Unique</p>
                  <p className="text-xl font-semibold">
                    {memberCollection.unique_cards}/{memberCollection.series_total}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Completion</p>
                  <p className="text-xl font-semibold">{memberCollection.completion_pct}%</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {RARITY_ORDER.filter((rarity) => memberCollection.rarity_counts[rarity]).map(
                  (rarity) => (
                    <span
                      key={rarity}
                      className="rounded-full border px-3 py-1 text-xs capitalize"
                      style={{ borderColor: `${RARITY_COLORS[rarity]}80` }}
                    >
                      {rarity}: {memberCollection.rarity_counts[rarity]}
                    </span>
                  ),
                )}
              </div>

              {memberCollection.unopened_packs.length > 0 && (
                <div className="space-y-3">
                  <div>
                    <h3 className="font-semibold">Unopened Packs</h3>
                    <p className="text-sm text-muted-foreground">Packs still available to open.</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {memberCollection.unopened_packs.map((pack) => (
                      <div key={pack.pack_id} className="flex items-center gap-3 rounded-lg border bg-muted/20 p-3">
                        <Package className="size-5 text-muted-foreground" />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{pack.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {sets.find((set) => set.series_id === pack.series_id)?.display_name ?? pack.series_id}
                          </p>
                        </div>
                        <span className="ml-auto rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold">
                          x{pack.quantity}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {memberCollection.cards.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  This member has no collected cards yet.
                </p>
              ) : (
                <div className="space-y-10">
                  {memberCollection.sets
                    .filter((set) => memberCollection.cards.some((card) => card.series_id === set.series_id))
                    .map((set) => {
                      const setCards = memberCollection.cards
                        .filter((card) => card.series_id === set.series_id)
                        .sort(
                          (a, b) =>
                            RARITY_ORDER.indexOf(a.rarity as (typeof RARITY_ORDER)[number]) -
                              RARITY_ORDER.indexOf(b.rarity as (typeof RARITY_ORDER)[number]) ||
                            a.number - b.number,
                        );
                      return (
                        <section key={set.series_id} className="space-y-4">
                          <div className="flex flex-wrap items-baseline gap-2">
                            <h3 className="text-lg font-semibold">{set.display_name}</h3>
                            <span className="text-sm text-muted-foreground">
                              {set.owned_unique}/{set.total_cards} unique · {set.completion_pct}%
                            </span>
                          </div>
                          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                            {setCards.map((card) => (
                              <button
                                key={card.card_id}
                                type="button"
                                className="relative overflow-hidden rounded-xl border bg-card text-left outline-none transition-shadow hover:shadow-lg focus-visible:ring-2 focus-visible:ring-primary"
                                style={{ borderColor: `${RARITY_COLORS[card.rarity] ?? '#9B9B9B'}60` }}
                                onClick={() => setSelectedCard(card)}
                                aria-label={`Open ${card.name} fullscreen`}
                              >
                                <CardArtwork card={card} renderVersion={memberCollection.render_version} />
                                <div className="space-y-1 p-3">
                                  <div className="flex items-center gap-2">
                                    <span className="shrink-0 font-mono text-xs text-muted-foreground">#{card.number}</span>
                                    <span className="truncate text-sm font-medium">{card.name}</span>
                                  </div>
                                  <p className="text-xs capitalize text-muted-foreground">{card.rarity}</p>
                                </div>
                                <span className="absolute right-3 top-3 rounded-full bg-background/90 px-2 py-1 text-xs font-bold shadow">
                                  x{card.quantity}
                                </span>
                              </button>
                            ))}
                          </div>
                        </section>
                      );
                    })}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {!sets.length ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            <Package className="h-10 w-10 mx-auto mb-3 opacity-20" />
            <p>
              No card packs available. Publish a set or create a pack below.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-end gap-4 flex-wrap">
            <div className="max-w-sm w-full">
              <Select
                value={selectedSeriesId ?? ''}
                onValueChange={setSelectedSeriesId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a collection..." />
                </SelectTrigger>
                <SelectContent>
                  {sets.map((s) => (
                    <SelectItem key={s.series_id} value={s.series_id}>
                      {s.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedSeriesId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddForm((v) => !v)}
              >
                <Plus className="h-4 w-4 mr-1.5" />
                {showAddForm ? 'Cancel' : 'Add Pack'}
              </Button>
            )}
            <div className="ml-auto flex items-center rounded-lg border bg-muted/30 p-1">
              <Button
                type="button"
                variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                size="sm"
                aria-label="Grid view"
                aria-pressed={viewMode === 'grid'}
                onClick={() => setViewMode('grid')}
              >
                <Grid2X2 className="mr-1.5 h-4 w-4" />
                Grid
              </Button>
              <Button
                type="button"
                variant={viewMode === 'stack' ? 'secondary' : 'ghost'}
                size="sm"
                aria-label="Stacked card view"
                aria-pressed={viewMode === 'stack'}
                onClick={() => setViewMode('stack')}
              >
                <Layers3 className="mr-1.5 h-4 w-4" />
                Stack
              </Button>
            </div>
          </div>

          {showAddForm && selectedSeriesId && (
            <Card variant="inset">
              <CardHeader>
                <CardTitle className="text-base">
                  New Pack in{' '}
                  {sets.find((s) => s.series_id === selectedSeriesId)
                    ?.display_name ?? selectedSeriesId}
                </CardTitle>
                <CardDescription>
                  Create a new pack type. It will be unreleased by default.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="space-y-2">
                    <Label className="text-sm">Pack ID</Label>
                    <Input
                      value={newPackId}
                      onChange={(e) => setNewPackId(e.target.value)}
                      placeholder="e.g. my_set_standard"
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Display Name</Label>
                    <Input
                      value={newPackName}
                      onChange={(e) => setNewPackName(e.target.value)}
                      placeholder="e.g. My Standard Pack"
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Price (coins)</Label>
                    <Input
                      type="number"
                      value={newPackPrice}
                      onChange={(e) =>
                        setNewPackPrice(parseInt(e.target.value) || 0)
                      }
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Cards per Pack</Label>
                    <Input
                      type="number"
                      value={newPackCardsPer}
                      onChange={(e) =>
                        setNewPackCardsPer(parseInt(e.target.value) || 1)
                      }
                      className="h-10"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Guaranteed Rarity</Label>
                    <Select
                      value={newPackGuarantee}
                      onValueChange={setNewPackGuarantee}
                    >
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        {RARITY_ORDER.map((r) => (
                          <SelectItem key={r} value={r}>
                            {r.charAt(0).toUpperCase() + r.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm">Description</Label>
                    <Input
                      value={newPackDesc}
                      onChange={(e) => setNewPackDesc(e.target.value)}
                      placeholder="Short description"
                      className="h-10"
                    />
                  </div>
                </div>
                <Button onClick={handleAddPack} className="mt-4">
                  <Plus className="h-4 w-4 mr-1.5" />
                  Create Pack
                </Button>
              </CardContent>
            </Card>
          )}

          {selectedSeriesId && (
            <>
              {setLoading ? (
                <Card>
                  <CardContent className="py-16 flex items-center justify-center">
                    <Spinner className="h-6 w-6 text-muted-foreground" />
                  </CardContent>
                </Card>
              ) : setDetail ? (
                <>
                  <div className="space-y-1">
                    <h2 className="text-xl font-bold">
                      {setDetail.display_name}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {setDetail.packs.length} pack
                      {setDetail.packs.length !== 1 ? 's' : ''} in this
                      collection
                    </p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {setDetail.packs.map((pack) => (
                      <Card key={pack.pack_id} variant="inset">
                        <CardHeader>
                          <CardTitle className="text-base">
                            {pack.name}
                          </CardTitle>
                          <CardDescription>{pack.description}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div className="space-y-2">
                            <Label className="text-xs">Price</Label>
                            <Input
                              type="number"
                              value={editPrices[pack.pack_id] ?? pack.price}
                              onChange={(e) =>
                                setEditPrices((prev) => ({
                                  ...prev,
                                  [pack.pack_id]: parseInt(e.target.value) || 0,
                                }))
                              }
                              className="h-9"
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                              <Label className="text-xs">Cards/Pack</Label>
                              <p className="text-sm font-medium">
                                {pack.cards_per_pack}
                              </p>
                            </div>
                            <div className="space-y-2">
                              <Label className="text-xs">Guarantee</Label>
                              <Select
                                value={
                                  editGuarantees[pack.pack_id] ||
                                  pack.guaranteed_rarity ||
                                  'none'
                                }
                                onValueChange={(v) =>
                                  setEditGuarantees((prev) => ({
                                    ...prev,
                                    [pack.pack_id]: v,
                                  }))
                                }
                              >
                                <SelectTrigger className="h-9">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">None</SelectItem>
                                  {RARITY_ORDER.map((r) => (
                                    <SelectItem key={r} value={r}>
                                      {r.charAt(0).toUpperCase() + r.slice(1)}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full"
                            onClick={() => handleSavePack(pack.pack_id)}
                          >
                            <Save className="h-3.5 w-3.5 mr-1.5" />
                            Save
                          </Button>
                        </CardContent>
                      </Card>
                    ))}
                  </div>

                   {stackCards.length === 0 ? (
                     <Card>
                      <CardContent className="py-16 text-center text-muted-foreground">
                        <p>No eligible cards found for this collection.</p>
                      </CardContent>
                    </Card>
                   ) : viewMode === 'stack' ? (
                     <section
                       className="flex min-h-[min(70vh,680px)] flex-col items-center justify-center gap-6 rounded-2xl border bg-muted/10 px-4 py-8"
                       aria-label="Stacked card viewer"
                     >
                       <div className="relative flex h-[min(58vh,560px)] w-full max-w-sm items-center justify-center">
                         {stackCards.slice(stackIndex + 1, stackIndex + 3).reverse().map((card, offset) => (
                           <div
                             key={card.card_id}
                             className="absolute w-[min(78vw,320px)] overflow-hidden rounded-2xl border bg-card shadow-xl transition-transform motion-reduce:transition-none"
                             style={{
                               transform: `translateY(${(offset + 1) * -12}px) scale(${1 - (offset + 1) * 0.04})`,
                               zIndex: offset,
                             }}
                           >
                             <CardArtwork card={card} renderVersion={setDetail.render_version} />
                           </div>
                         ))}
                         {stackCards[stackIndex] && (
                           <button
                             type="button"
                             className="group relative z-10 w-[min(78vw,320px)] overflow-hidden rounded-2xl border-2 bg-card text-left shadow-2xl outline-none transition-transform hover:scale-[1.01] focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transition-none"
                             onClick={() => setSelectedCard(stackCards[stackIndex])}
                             aria-label={`Open ${stackCards[stackIndex].name} fullscreen`}
                           >
                             <CardArtwork card={stackCards[stackIndex]} renderVersion={setDetail.render_version} />
                             <div className="space-y-1 p-4">
                               <p className="text-xs font-mono text-muted-foreground">
                                 #{stackCards[stackIndex].number} · {stackCards[stackIndex].rarity}
                               </p>
                               <h3 className="font-semibold">{stackCards[stackIndex].name}</h3>
                               <p className="line-clamp-2 text-sm text-muted-foreground">
                                 {stackCards[stackIndex].description || 'No description available.'}
                               </p>
                             </div>
                             <span className="absolute right-3 top-3 rounded-full bg-background/80 p-2 opacity-0 shadow transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                               <Maximize2 className="h-4 w-4" />
                             </span>
                           </button>
                         )}
                       </div>
                       <div className="flex items-center gap-4">
                         <Button
                           type="button"
                           variant="outline"
                           size="icon"
                           onClick={() => setStackIndex((index) => Math.max(0, index - 1))}
                           disabled={stackIndex === 0}
                           aria-label="Previous card"
                         >
                           <ArrowLeft className="h-4 w-4" />
                         </Button>
                         <span className="min-w-20 text-center text-sm text-muted-foreground">
                           {stackIndex + 1} of {stackCards.length}
                         </span>
                         <Button
                           type="button"
                           variant="outline"
                           size="icon"
                           onClick={() => setStackIndex((index) => Math.min(stackCards.length - 1, index + 1))}
                           disabled={stackIndex === stackCards.length - 1}
                           aria-label="Next card"
                         >
                           <ArrowRight className="h-4 w-4" />
                         </Button>
                       </div>
                       <p className="text-xs text-muted-foreground">Use the arrow keys or buttons to browse. Click a card to expand it.</p>
                     </section>
                   ) : (
                     <div className="space-y-10">
                      {RARITY_ORDER.filter(
                        (r) => (setDetail.eligible_cards[r] ?? []).length,
                      ).map((rarity) => {
                        const cards = setDetail.eligible_cards[rarity];
                        const color = RARITY_COLORS[rarity] ?? '#9B9B9B';
                        return (
                          <section key={rarity}>
                            <div className="flex items-center gap-3 mb-4">
                              <span
                                className="inline-block h-3 w-3 rounded-full shrink-0"
                                style={{ backgroundColor: color }}
                              />
                              <h2 className="text-lg font-semibold capitalize">
                                {rarity}
                              </h2>
                              <span className="text-sm text-muted-foreground">
                                ({cards.length} cards)
                              </span>
                            </div>
                            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                               {cards.map((card) => (
                                 <button
                                   type="button"
                                   key={card.card_id}
                                   className="w-full overflow-hidden rounded-xl border bg-card text-left outline-none transition-shadow hover:shadow-lg focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transition-none"
                                   style={{ borderColor: color + '60' }}
                                   onClick={() => setSelectedCard(card)}
                                   aria-label={`Open ${card.name} fullscreen`}
                                 >
                                   <CardArtwork card={card} renderVersion={setDetail.render_version} />
                                   <div className="p-3 space-y-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground font-mono shrink-0">
                                        #{card.number}
                                      </span>
                                      <span className="font-medium text-sm truncate">
                                        {card.name}
                                      </span>
                                    </div>
                                    {card.description && (
                                      <p className="text-xs text-muted-foreground line-clamp-2">
                                        {card.description}
                                      </p>
                                    )}
                                  </div>
                                 </button>
                               ))}
                            </div>
                          </section>
                        );
                      })}
                    </div>
                   )}
                   <Dialog
                     open={selectedCard !== null}
                     onOpenChange={(open) => !open && setSelectedCard(null)}
                   >
                     <DialogContent className="max-h-[95vh] w-[min(96vw,1100px)] max-w-none overflow-y-auto p-0 sm:rounded-2xl">
                       {selectedCard && (
                         <div className="grid gap-0 md:grid-cols-[minmax(280px,0.9fr)_1.1fr]">
                           <CardArtwork
                             card={selectedCard}
                             renderVersion={setDetail.render_version}
                             className="h-full min-h-[360px] w-full object-cover md:min-h-[620px]"
                           />
                           <DialogHeader className="justify-center gap-4 p-6 sm:p-10">
                             <div className="flex items-center gap-2 text-sm font-medium capitalize text-muted-foreground">
                               <span
                                 className="h-3 w-3 rounded-full"
                                 style={{ backgroundColor: RARITY_COLORS[selectedCard.rarity] ?? '#9B9B9B' }}
                               />
                               {selectedCard.rarity} · #{selectedCard.number}
                             </div>
                             <DialogTitle className="text-3xl">{selectedCard.name}</DialogTitle>
                             <DialogDescription className="text-base leading-7">
                                 {selectedCard.description}
                             </DialogDescription>
                             <p className="text-xs text-muted-foreground">Card ID: {selectedCard.card_id}</p>
                           </DialogHeader>
                         </div>
                       )}
                     </DialogContent>
                   </Dialog>
                </>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
