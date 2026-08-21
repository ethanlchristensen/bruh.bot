import { useMemo, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Images, Package, UserRound } from 'lucide-react';

import {
  useGuildMembers,
  useTradingCardCollection,
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
  CardArtwork,
  CardPreviewDialog,
  RARITY_COLORS,
  RARITY_ORDER,
} from '@/components/trading-cards/card-display';

export const Route = createFileRoute('/_main/config/card-collections')({
  component: CardCollectionsComponent,
});

function CardCollectionsComponent() {
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const { data: membersData, isLoading: membersLoading } = useGuildMembers();
  const {
    data: collection,
    isLoading: collectionLoading,
    isError: collectionError,
  } = useTradingCardCollection(selectedMemberId);

  const selectedMember = membersData?.members.find(
    (member) => member.user_id === selectedMemberId,
  );
  const selectedCard = collection?.cards.find(
    (card) => card.card_id === selectedCardId,
  );
  const cardsBySet = useMemo(() => {
    if (!collection) return new Map<string, typeof collection.cards>();
    return collection.cards.reduce((groups, card) => {
      const cards = groups.get(card.series_id) ?? [];
      cards.push(card);
      groups.set(card.series_id, cards);
      return groups;
    }, new Map<string, typeof collection.cards>());
  }, [collection]);

  return (
    <div className="space-y-8 pb-20" data-page="card-collections">
      <PageHeader
        icon={<Images />}
        title="Member Collections"
        description="Inspect a guild member's cards, progress, and unopened packs."
        children={
          <Button variant="outline" size="sm" asChild>
            <a href="/config/card-packs">Manage Catalog</a>
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
              <CardTitle>Select Member</CardTitle>
              <CardDescription>
                Choose a member from the selected guild to inspect their collection.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Select
            value={selectedMemberId}
            onValueChange={(value) => {
              setSelectedMemberId(value);
              setSelectedCardId(null);
            }}
          >
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
        </CardContent>
      </Card>

      {collectionLoading && (
        <div className="flex justify-center py-12">
          <Spinner className="size-8" />
        </div>
      )}
      {collectionError && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-destructive">
            Unable to load this member&apos;s collection.
          </CardContent>
        </Card>
      )}

      {collection && (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center gap-4 p-5">
              {selectedMember?.avatar_url && (
                <img src={selectedMember.avatar_url} alt="" className="size-12 rounded-full" />
              )}
              <div className="mr-auto">
                <p className="font-semibold">
                  {selectedMember?.display_name || selectedMember?.username || selectedMemberId}
                </p>
                <p className="text-xs text-muted-foreground">{collection.user_id}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cards</p>
                <p className="text-xl font-semibold">{collection.total_cards}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Unique</p>
                <p className="text-xl font-semibold">{collection.unique_cards}/{collection.series_total}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Completion</p>
                <p className="text-xl font-semibold">{collection.completion_pct}%</p>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-2">
            {RARITY_ORDER.filter((rarity) => collection.rarity_counts[rarity]).map((rarity) => (
              <span
                key={rarity}
                className="rounded-full border px-3 py-1 text-xs capitalize"
                style={{ borderColor: `${RARITY_COLORS[rarity]}80` }}
              >
                {rarity}: {collection.rarity_counts[rarity]}
              </span>
            ))}
          </div>

          {collection.unopened_packs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Unopened Packs</CardTitle>
                <CardDescription>Packs still available to open.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {collection.unopened_packs.map((pack) => (
                  <div key={pack.pack_id} className="flex items-center gap-3 rounded-lg border bg-muted/20 p-3">
                    <Package className="size-5 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{pack.name}</p>
                      <p className="text-xs text-muted-foreground">{pack.series_id}</p>
                    </div>
                    <span className="ml-auto rounded-full bg-primary/10 px-2 py-1 text-xs font-semibold">
                      x{pack.quantity}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {collection.cards.length === 0 ? (
            <Card>
              <CardContent className="py-16 text-center text-muted-foreground">
                This member has no collected cards yet.
              </CardContent>
            </Card>
          ) : (
            collection.sets
              .filter((set) => cardsBySet.has(set.series_id))
              .map((set) => {
                const cards = [...(cardsBySet.get(set.series_id) ?? [])].sort(
                  (a, b) =>
                    RARITY_ORDER.indexOf(a.rarity as (typeof RARITY_ORDER)[number]) -
                      RARITY_ORDER.indexOf(b.rarity as (typeof RARITY_ORDER)[number]) ||
                    a.number - b.number,
                );
                return (
                  <section key={set.series_id} className="space-y-4">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <h2 className="text-xl font-bold">{set.display_name}</h2>
                      <span className="text-sm text-muted-foreground">
                        {set.owned_unique}/{set.total_cards} unique · {set.completion_pct}%
                      </span>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {cards.map((card) => (
                        <button
                          key={card.card_id}
                          type="button"
                          className="relative overflow-hidden rounded-xl border bg-card text-left outline-none transition-shadow hover:shadow-lg focus-visible:ring-2 focus-visible:ring-primary"
                          style={{ borderColor: `${RARITY_COLORS[card.rarity] ?? '#9B9B9B'}60` }}
                          onClick={() => setSelectedCardId(card.card_id)}
                          aria-label={`Open ${card.name} fullscreen`}
                        >
                          <CardArtwork card={card} renderVersion={collection.render_version} />
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
              })
          )}

          <CardPreviewDialog
            card={selectedCard ?? null}
            renderVersion={collection.render_version}
            quantity={selectedCard?.quantity}
            open={selectedCard !== undefined}
            onOpenChange={(open) => !open && setSelectedCardId(null)}
          />
        </>
      )}
    </div>
  );
}
