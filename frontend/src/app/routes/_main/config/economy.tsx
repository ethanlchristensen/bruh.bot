import { useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createFileRoute } from '@tanstack/react-router';
import { Coins, TrendingUp, Trophy, Zap } from 'lucide-react';
import { toast } from 'sonner';

import { useConfig, useUpdateConfig } from '@/hooks/use-config';
import { useEconomyLeaderboard } from '@/hooks/use-economy';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardIcon } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { PageHeader } from '@/components/layouts/page-header';
import { StickySaveBar } from '@/components/layouts/sticky-save-bar';

export const Route = createFileRoute('/_main/config/economy')({
  component: EconomyConfigComponent,
});

function EconomyConfigComponent() {
  const { data, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();
  const queryClient = useQueryClient();
  const { data: leaderboardData } = useEconomyLeaderboard('xp', 10);

  const [isSaving, setIsSaving] = useState(false);

  const [xpEnabled, setXpEnabled] = useState(true);
  const [coinsEnabled, setCoinsEnabled] = useState(true);
  const [levelUpAnnounce, setLevelUpAnnounce] = useState(true);
  const [baseXpMin, setBaseXpMin] = useState(15);
  const [baseXpMax, setBaseXpMax] = useState(25);
  const [imageXpBonus, setImageXpBonus] = useState(10);
  const [reactionXp, setReactionXp] = useState(5);
  const [mentionXpMin, setMentionXpMin] = useState(10);
  const [mentionXpMax, setMentionXpMax] = useState(15);
  const [messageCoinMin, setMessageCoinMin] = useState(1.0);
  const [messageCoinMax, setMessageCoinMax] = useState(3.0);
  const [imageCoinBonus, setImageCoinBonus] = useState(3.0);
  const [reactionCoin, setReactionCoin] = useState(1.0);
  const [mentionCoinMin, setMentionCoinMin] = useState(2.0);
  const [mentionCoinMax, setMentionCoinMax] = useState(5.0);
  const [dailyCoinMin, setDailyCoinMin] = useState(50.0);
  const [dailyCoinMax, setDailyCoinMax] = useState(100.0);

  const initialValuesRef = useRef<{
    xpEnabled: boolean;
    coinsEnabled: boolean;
    levelUpAnnounce: boolean;
    baseXpMin: number;
    baseXpMax: number;
    imageXpBonus: number;
    reactionXp: number;
    mentionXpMin: number;
    mentionXpMax: number;
    messageCoinMin: number;
    messageCoinMax: number;
    imageCoinBonus: number;
    reactionCoin: number;
    mentionCoinMin: number;
    mentionCoinMax: number;
    dailyCoinMin: number;
    dailyCoinMax: number;
  } | null>(null);

  useEffect(() => {
    if (data?.config && !isSaving) {
      const econ = data.config.economyConfig;
      if (econ) {
        const vals = {
          xpEnabled: econ.xpEnabled,
          coinsEnabled: econ.coinsEnabled,
          levelUpAnnounce: econ.levelUpAnnounceInChannel,
          baseXpMin: econ.baseXpRange[0],
          baseXpMax: econ.baseXpRange[1],
          imageXpBonus: econ.imageXpBonus,
          reactionXp: econ.reactionXp,
          mentionXpMin: econ.mentionXpRange[0],
          mentionXpMax: econ.mentionXpRange[1],
          messageCoinMin: econ.messageCoinRange[0],
          messageCoinMax: econ.messageCoinRange[1],
          imageCoinBonus: econ.imageCoinBonus,
          reactionCoin: econ.reactionCoin,
          mentionCoinMin: econ.mentionCoinRange[0],
          mentionCoinMax: econ.mentionCoinRange[1],
          dailyCoinMin: econ.dailyCoinMin,
          dailyCoinMax: econ.dailyCoinMax,
        };
        if (!initialValuesRef.current) {
          initialValuesRef.current = vals;
        }
        setXpEnabled(vals.xpEnabled);
        setCoinsEnabled(vals.coinsEnabled);
        setLevelUpAnnounce(vals.levelUpAnnounce);
        setBaseXpMin(vals.baseXpMin);
        setBaseXpMax(vals.baseXpMax);
        setImageXpBonus(vals.imageXpBonus);
        setReactionXp(vals.reactionXp);
        setMentionXpMin(vals.mentionXpMin);
        setMentionXpMax(vals.mentionXpMax);
        setMessageCoinMin(vals.messageCoinMin);
        setMessageCoinMax(vals.messageCoinMax);
        setImageCoinBonus(vals.imageCoinBonus);
        setReactionCoin(vals.reactionCoin);
        setMentionCoinMin(vals.mentionCoinMin);
        setMentionCoinMax(vals.mentionCoinMax);
        setDailyCoinMin(vals.dailyCoinMin);
        setDailyCoinMax(vals.dailyCoinMax);
      }
    }
  }, [data, isSaving]);

  const hasChanges = useMemo(() => {
    const iv = initialValuesRef.current;
    if (!iv) return false;
    return (
      xpEnabled !== iv.xpEnabled ||
      coinsEnabled !== iv.coinsEnabled ||
      levelUpAnnounce !== iv.levelUpAnnounce ||
      baseXpMin !== iv.baseXpMin ||
      baseXpMax !== iv.baseXpMax ||
      imageXpBonus !== iv.imageXpBonus ||
      reactionXp !== iv.reactionXp ||
      mentionXpMin !== iv.mentionXpMin ||
      mentionXpMax !== iv.mentionXpMax ||
      messageCoinMin !== iv.messageCoinMin ||
      messageCoinMax !== iv.messageCoinMax ||
      imageCoinBonus !== iv.imageCoinBonus ||
      reactionCoin !== iv.reactionCoin ||
      mentionCoinMin !== iv.mentionCoinMin ||
      mentionCoinMax !== iv.mentionCoinMax ||
      dailyCoinMin !== iv.dailyCoinMin ||
      dailyCoinMax !== iv.dailyCoinMax
    );
  }, [
    xpEnabled, coinsEnabled, levelUpAnnounce,
    baseXpMin, baseXpMax, imageXpBonus, reactionXp,
    mentionXpMin, mentionXpMax,
    messageCoinMin, messageCoinMax, imageCoinBonus, reactionCoin,
    mentionCoinMin, mentionCoinMax, dailyCoinMin, dailyCoinMax,
  ]);

  const handleSave = () => {
    setIsSaving(true);
    toast.promise(
      updateConfig.mutateAsync({
        economyConfig: {
          xpEnabled,
          coinsEnabled,
          levelUpAnnounceInChannel: levelUpAnnounce,
          baseXpRange: [baseXpMin, baseXpMax],
          imageXpBonus,
          reactionXp,
          mentionXpRange: [mentionXpMin, mentionXpMax],
          messageCoinRange: [messageCoinMin, messageCoinMax],
          imageCoinBonus,
          reactionCoin,
          mentionCoinRange: [mentionCoinMin, mentionCoinMax],
          dailyCoinMin,
          dailyCoinMax,
        },
      }).then(() => {
        initialValuesRef.current = {
          xpEnabled, coinsEnabled, levelUpAnnounce,
          baseXpMin, baseXpMax, imageXpBonus, reactionXp,
          mentionXpMin, mentionXpMax,
          messageCoinMin, messageCoinMax, imageCoinBonus, reactionCoin,
          mentionCoinMin, mentionCoinMax, dailyCoinMin, dailyCoinMax,
        };
        return queryClient.invalidateQueries({ queryKey: ['config'] });
      }).finally(() => {
        setIsSaving(false);
      }),
      {
        loading: 'Saving economy configuration...',
        success: 'Economy configuration saved!',
        error: (err) => `Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`,
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center gap-4">
        <Spinner className="h-8 w-8 text-primary" />
        <p className="text-sm text-muted-foreground animate-pulse">Loading economy configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20" data-page="economy">
      <PageHeader
        icon={<Coins />}
        title="Economy Settings"
        description="Configure XP, leveling, and bruh.coin economy."
      />

      <StickySaveBar onSave={handleSave} isSaving={isSaving} hasChanges={hasChanges} />

      <div className="grid gap-8 xl:grid-cols-3">
        {/* XP & Leveling */}
        <Card variant="hero">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Zap /></CardIcon>
              <div>
                <CardTitle>XP & Leveling</CardTitle>
                <CardDescription>Experience gain rates and level-up behavior.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
              <div className="space-y-1">
                <Label className="font-semibold cursor-pointer">Enable XP</Label>
                <p className="text-xs text-muted-foreground">Users earn XP from messages</p>
              </div>
              <Switch checked={xpEnabled} onCheckedChange={setXpEnabled} />
            </div>

            <Separator label="Base Messages" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">XP Min</Label>
                <Input type="number" value={baseXpMin} onChange={(e) => setBaseXpMin(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">XP Max</Label>
                <Input type="number" value={baseXpMax} onChange={(e) => setBaseXpMax(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <Separator label="Bonuses" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Image Bonus</Label>
                <Input type="number" value={imageXpBonus} onChange={(e) => setImageXpBonus(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Reaction XP</Label>
                <Input type="number" value={reactionXp} onChange={(e) => setReactionXp(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <Separator label="@Mentions" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Mention XP Min</Label>
                <Input type="number" value={mentionXpMin} onChange={(e) => setMentionXpMin(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Mention XP Max</Label>
                <Input type="number" value={mentionXpMax} onChange={(e) => setMentionXpMax(parseInt(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
              <div className="space-y-1">
                <Label className="font-semibold cursor-pointer">Level-Up Announcements</Label>
                <p className="text-xs text-muted-foreground">Public embed when a user levels up</p>
              </div>
              <Switch checked={levelUpAnnounce} onCheckedChange={setLevelUpAnnounce} />
            </div>
          </CardContent>
        </Card>

        {/* bruh.coin Economy */}
        <Card variant="hero">
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Coins /></CardIcon>
              <div>
                <CardTitle>bruh.coin Economy</CardTitle>
                <CardDescription>Coin earning rates per interaction type.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between p-4 rounded-xl bg-muted/30">
              <div className="space-y-1">
                <Label className="font-semibold cursor-pointer">Enable Coins</Label>
                <p className="text-xs text-muted-foreground">Users earn coins from interactions</p>
              </div>
              <Switch checked={coinsEnabled} onCheckedChange={setCoinsEnabled} />
            </div>

            <Separator label="Base Messages" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Coin Min</Label>
                <Input type="number" step="0.1" value={messageCoinMin} onChange={(e) => setMessageCoinMin(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Coin Max</Label>
                <Input type="number" step="0.1" value={messageCoinMax} onChange={(e) => setMessageCoinMax(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <Separator label="Bonuses" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Image Bonus</Label>
                <Input type="number" step="0.1" value={imageCoinBonus} onChange={(e) => setImageCoinBonus(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Reaction Coin</Label>
                <Input type="number" step="0.1" value={reactionCoin} onChange={(e) => setReactionCoin(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <Separator label="@Mentions" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Mention Coin Min</Label>
                <Input type="number" step="0.1" value={mentionCoinMin} onChange={(e) => setMentionCoinMin(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Mention Coin Max</Label>
                <Input type="number" step="0.1" value={mentionCoinMax} onChange={(e) => setMentionCoinMax(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
            </div>

            <Separator label="Daily Rewards" />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-sm">Daily Min</Label>
                <Input type="number" step="0.1" value={dailyCoinMin} onChange={(e) => setDailyCoinMin(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Daily Max</Label>
                <Input type="number" step="0.1" value={dailyCoinMax} onChange={(e) => setDailyCoinMax(parseFloat(e.target.value) || 0)} className="h-10" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Leaderboard */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <CardIcon><Trophy /></CardIcon>
              <div>
                <CardTitle>Leaderboard</CardTitle>
                <CardDescription>Top 10 by XP.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {leaderboardData?.leaderboard && leaderboardData.leaderboard.length > 0 ? (
              <div className="space-y-1.5">
                {leaderboardData.leaderboard.slice(0, 10).map((entry, idx) => (
                  <div key={entry.user_id} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 text-sm">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-muted-foreground w-5">{idx + 1}.</span>
                      {entry.avatar_url && (
                        <img src={entry.avatar_url} alt="" className="size-6 rounded-full" />
                      )}
                      <span className="truncate max-w-[140px]">{entry.username}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        Lv{entry.level}
                      </span>
                      <span className="flex items-center gap-1">
                        <Coins className="h-3 w-3" />
                        {entry.bruh_coins.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-12">No data yet. Start chatting!</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Separator({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-px flex-1 bg-gradient-to-r from-border/60 to-transparent" />
      {label && <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground shrink-0">{label}</span>}
      {label && <div className="h-px flex-1 bg-gradient-to-l from-border/60 to-transparent" />}
    </div>
  );
}