import { useCallback, useEffect, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Images, Package, Plus, RefreshCw, Save } from 'lucide-react';

import {
  economyKeys,
  useCreateTradingCardPack,
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

function CardPacksComponent() {
  const queryClient = useQueryClient();
  const { data: setsData, isLoading: setsLoading } = useTradingCardSets();
  const [selectedSeriesId, setSelectedSeriesId] = useState<string | null>(null);
  const { data: setDetail, isLoading: setLoading } =
    useTradingCardSet(selectedSeriesId);
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

  const sets = setsData?.sets ?? [];

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
                                  editGuarantees[pack.pack_id] ??
                                  pack.guaranteed_rarity ??
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

                  {Object.keys(setDetail.eligible_cards).length === 0 ? (
                    <Card>
                      <CardContent className="py-16 text-center text-muted-foreground">
                        <p>No eligible cards found for this collection.</p>
                      </CardContent>
                    </Card>
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
                                <div
                                  key={card.card_id}
                                  className="rounded-xl border bg-card overflow-hidden hover:shadow-lg transition-shadow"
                                  style={{ borderColor: color + '60' }}
                                >
                                  <div className="aspect-[3/4] bg-muted/30 flex items-center justify-center overflow-hidden">
                                    <img
                                      src={cardImageUrl(
                                        card.card_id,
                                        card.asset_sha256,
                                        setDetail.render_version,
                                      )}
                                      alt={card.name}
                                      className="w-full h-full object-cover"
                                      loading="lazy"
                                      decoding="async"
                                      onError={(e) => {
                                        const target = e.currentTarget;
                                        target.style.display = 'none';
                                        const placeholder =
                                          target.nextElementSibling as HTMLElement;
                                        placeholder.style.display = 'flex';
                                      }}
                                    />
                                    <div className="hidden w-full h-full flex-col items-center justify-center gap-1 text-muted-foreground">
                                      <Package className="h-6 w-6 opacity-30" />
                                      <span className="text-xs">No art</span>
                                    </div>
                                  </div>
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
                                </div>
                              ))}
                            </div>
                          </section>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
