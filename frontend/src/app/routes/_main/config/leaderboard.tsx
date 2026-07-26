import { createFileRoute } from '@tanstack/react-router';
import { Coins, Heart, ImageIcon, MessageSquare, Trophy, Zap } from 'lucide-react';

import { useEconomyLeaderboard } from '@/hooks/use-economy';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { PageHeader } from '@/components/layouts/page-header';

export const Route = createFileRoute('/_main/config/leaderboard')({
  component: LeaderboardComponent,
});

function LeaderboardComponent() {
  const { data, isLoading } = useEconomyLeaderboard('xp', 25);

  if (isLoading) {
    return (
      <div className="space-y-8 pb-20">
        <PageHeader icon={<Trophy />} title="Leaderboard" description="Top users by XP, messages, and coins." />
        <div className="flex h-[40vh] flex-col items-center justify-center gap-4">
          <Spinner className="h-8 w-8 text-primary" />
          <p className="text-sm text-muted-foreground animate-pulse">Loading leaderboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20" data-page="leaderboard">
      <PageHeader icon={<Trophy />} title="Leaderboard" description="Top users by XP, messages, and coins." />

      {!data || !data.leaderboard.length ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            <Trophy className="h-10 w-10 mx-auto mb-3 opacity-20" />
            <p>No data yet. Start chatting!</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Top 25 by XP</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-3.5 px-5 font-medium text-muted-foreground w-12">#</th>
                    <th className="text-left py-3.5 px-5 font-medium text-muted-foreground">User</th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Zap className="h-3.5 w-3.5" /> Total XP</span>
                    </th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Trophy className="h-3.5 w-3.5" /> Level</span>
                    </th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><MessageSquare className="h-3.5 w-3.5" /> Msgs</span>
                    </th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Heart className="h-3.5 w-3.5" /> Rxns</span>
                    </th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><ImageIcon className="h-3.5 w-3.5" /> Imgs</span>
                    </th>
                    <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Coins className="h-3.5 w-3.5" /> Coins</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.leaderboard.map((entry, idx) => (
                    <tr key={entry.user_id} className="border-b border-border/20 hover:bg-muted/30 transition-colors">
                      <td className="py-3.5 px-5 font-bold text-muted-foreground">{idx + 1}</td>
                      <td className="py-3.5 px-5 font-medium">
                        <div className="flex items-center gap-3">
                          {entry.avatar_url && (
                            <img src={entry.avatar_url} alt="" className="size-7 rounded-full shrink-0" />
                          )}
                          <span>{entry.username}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.xp.toLocaleString()}</td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.level}</td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.total_messages.toLocaleString()}</td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.total_reactions_given.toLocaleString()}</td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.total_images.toLocaleString()}</td>
                      <td className="py-3.5 px-5 text-right font-mono text-xs">{entry.bruh_coins.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}