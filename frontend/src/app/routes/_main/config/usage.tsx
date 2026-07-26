import { useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Gauge } from 'lucide-react';

import { useUsageLeaderboard } from '@/hooks/use-config';
import { Card, CardContent, CardHeader, CardTitle, CardIcon } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { PageHeader } from '@/components/layouts/page-header';

export const Route = createFileRoute('/_main/config/usage')({
  component: UsageLeaderboardComponent,
});

function UsageLeaderboardComponent() {
  const [days, setDays] = useState<string>('');
  const daysParam = days ? parseInt(days) : undefined;
  const { data, isLoading } = useUsageLeaderboard(daysParam);

  const formatCost = (cost: number) => {
    if (cost >= 0.01) return `$${cost.toFixed(4)}`;
    if (cost > 0) return `$${cost.toFixed(6)}`;
    return '$0.00';
  };

  const formatTokens = (n: number) => n.toLocaleString();

  if (isLoading) {
    return (
      <div className="space-y-8 pb-20">
        <PageHeader icon={<Gauge />} title="AI Usage Leaderboard" description="Top users by AI token consumption and cost." />
        <div className="flex h-[40vh] flex-col items-center justify-center gap-4">
          <Spinner className="h-8 w-8 text-primary" />
          <p className="text-sm text-muted-foreground animate-pulse">Loading leaderboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20" data-page="usage">
      <PageHeader
        icon={<Gauge />}
        title="AI Usage Leaderboard"
        description="Top users by AI token consumption and cost."
      >
        <div className="flex items-center gap-2">
          <Label htmlFor="days" className="text-sm whitespace-nowrap">Last N days (blank = all time):</Label>
          <Input
            id="days"
            type="number"
            placeholder="e.g. 7"
            value={days}
            onChange={(e) => setDays(e.target.value)}
            className="h-10 w-24"
            min={1}
          />
        </div>
      </PageHeader>

      {!data || !data.leaderboard.length ? (
        <Card>
          <CardContent className="py-16 text-center text-muted-foreground">
            <Gauge className="h-10 w-10 mx-auto mb-3 opacity-20" />
            <p>No usage data available yet. Start chatting with the AI to generate data.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <Card variant="hero" className="max-w-lg">
            <CardHeader>
              <div className="flex items-center gap-4">
                <CardIcon><Gauge /></CardIcon>
                <CardTitle>Summary</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6 text-sm">
                <div>
                  <span className="text-muted-foreground">Total Requests: </span>
                  <span className="font-semibold">{data.summary.total_requests.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Cost: </span>
                  <span className="font-semibold">{formatCost(data.summary.total_cost)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Leaderboard</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/40">
                      <th className="text-left py-3.5 px-5 font-medium text-muted-foreground w-12">#</th>
                      <th className="text-left py-3.5 px-5 font-medium text-muted-foreground">User</th>
                      <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">Requests</th>
                      <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">Input Tokens</th>
                      <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">Output Tokens</th>
                      <th className="text-right py-3.5 px-5 font-medium text-muted-foreground">Cost</th>
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
                        <td className="py-3.5 px-5 text-right">{entry.total_requests.toLocaleString()}</td>
                        <td className="py-3.5 px-5 text-right font-mono text-xs">{formatTokens(entry.total_input_tokens)}</td>
                        <td className="py-3.5 px-5 text-right font-mono text-xs">{formatTokens(entry.total_output_tokens)}</td>
                        <td className="py-3.5 px-5 text-right font-mono text-xs">{formatCost(entry.total_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}