import { Package } from 'lucide-react';

import type { TradingCardPackCard } from '@/lib/api-client';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export const RARITY_ORDER = [
  'basic',
  'common',
  'rare',
  'epic',
  'legendary',
  'diamond',
  'platinum',
] as const;

export const RARITY_COLORS: Record<string, string> = {
  basic: '#9B9B9B',
  common: '#1EFF00',
  rare: '#0070DD',
  epic: '#A335EE',
  legendary: '#FF8000',
  diamond: '#00F0FF',
  platinum: '#E5CC80',
};

export function cardImageUrl(
  cardId: string,
  assetSha256: string,
  renderVersion?: string,
): string {
  const version = [assetSha256 || '0', renderVersion || '0'].join('-');
  return `/api/trading-cards/card/${encodeURIComponent(cardId)}/image?v=${encodeURIComponent(version)}`;
}

export function CardArtwork({
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
        onError={(event) => {
          const target = event.currentTarget;
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

export function CardPreviewDialog({
  card,
  renderVersion,
  open,
  onOpenChange,
  quantity,
}: {
  card: TradingCardPackCard | null;
  renderVersion?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quantity?: number;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[95vh] w-[min(96vw,1100px)] max-w-none overflow-y-auto p-0 sm:rounded-2xl">
        {card && (
          <div className="grid gap-0 md:grid-cols-[minmax(280px,0.9fr)_1.1fr]">
            <CardArtwork
              card={card}
              renderVersion={renderVersion}
              className="h-full min-h-[360px] w-full object-cover md:min-h-[620px]"
            />
            <DialogHeader className="justify-center gap-4 p-6 sm:p-10">
              <div className="flex items-center gap-2 text-sm font-medium capitalize text-muted-foreground">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: RARITY_COLORS[card.rarity] ?? '#9B9B9B' }}
                />
                {card.rarity} · #{card.number}
              </div>
              <DialogTitle className="text-3xl">{card.name}</DialogTitle>
              <DialogDescription className="text-base leading-7">
                {card.description || 'No description available.'}
              </DialogDescription>
              {quantity !== undefined && (
                <p className="text-sm font-semibold">Owned: x{quantity}</p>
              )}
              <p className="text-xs text-muted-foreground">Card ID: {card.card_id}</p>
            </DialogHeader>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
