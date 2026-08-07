import { createFileRoute } from '@tanstack/react-router';
import { ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layouts/page-header';
import { Badge } from '@/components/ui/badge';
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
import { useReputation, useUpdateReputation } from '@/hooks/use-config';
import { useGuildMembers } from '@/hooks/use-economy';

export const Route = createFileRoute('/_main/config/reputation')({
  component: ReputationComponent,
});

function ReputationComponent() {
  const [userId, setUserId] = useState('');
  const [score, setScore] = useState('');
  const [status, setStatus] = useState<
    'active' | 'warning' | 'blocked' | 'manual_blocked'
  >('active');
  const [reason, setReason] = useState('Manual dashboard adjustment');
  const { data, isLoading } = useReputation(userId);
  const { data: membersData, isLoading: membersLoading } = useGuildMembers();
  const update = useUpdateReputation();

  const profile = data?.profile;

  useEffect(() => {
    if (profile) setStatus(profile.status);
  }, [profile]);

  const save = async () => {
    if (!userId) return;
    try {
      await update.mutateAsync({
        userId,
        data: {
          score: score === '' ? undefined : Number(score),
          status,
          reason,
        },
      });
      toast.success('Reputation updated');
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to update reputation',
      );
    }
  };

  return (
    <div className="space-y-8 pb-20" data-page="reputation">
      <PageHeader
        icon={<ShieldAlert />}
        title="Reputation"
        description="Review audit history and manage a user's ability to interact with bruh.bot."
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <CardIcon>
              <ShieldAlert />
            </CardIcon>
            <div>
              <CardTitle>Select User</CardTitle>
              <CardDescription>
                Choose a member of the selected guild to inspect their
                reputation profile.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Select value={userId} onValueChange={setUserId}>
            <SelectTrigger className="w-full">
              <SelectValue
                placeholder={
                  membersLoading
                    ? 'Loading guild members...'
                    : 'Select a guild member...'
                }
              />
            </SelectTrigger>
            <SelectContent>
              {(membersData?.members ?? []).map((member) => (
                <SelectItem key={member.user_id} value={member.user_id}>
                  <span className="flex items-center gap-2">
                    {member.avatar_url && (
                      <img
                        src={member.avatar_url}
                        alt=""
                        className="size-5 rounded-full"
                      />
                    )}
                    {member.display_name || member.username}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner className="size-8" />
        </div>
      )}

      {profile && !isLoading && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Score</p>
                <p className="text-3xl font-semibold">{profile.score}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Status</p>
                <Badge variant="outline" className="mt-2 capitalize">
                  {profile.status.replace('_', ' ')}
                </Badge>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Blocked Until</p>
                <p className="mt-2 text-sm">
                  {profile.blocked_until
                    ? new Date(profile.blocked_until).toLocaleString()
                    : 'Not blocked'}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Manual Adjustment</CardTitle>
              <CardDescription>
                Every change creates an administrative audit entry.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Score</Label>
                <Input
                  type="number"
                  placeholder={String(profile.score)}
                  value={score}
                  onChange={(event) => setScore(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={status}
                  onValueChange={(value) => setStatus(value as typeof status)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="blocked">Temporary block</SelectItem>
                    <SelectItem value="manual_blocked">Manual block</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Reason</Label>
                <Input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
              </div>
              <Button
                className="md:col-span-3 md:w-fit"
                onClick={save}
                disabled={update.isPending}
              >
                Save Reputation
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Audit History</CardTitle>
              <CardDescription>
                Recent automated and administrator changes.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.events.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No audit entries.
                </p>
              ) : (
                data.events.map((event) => (
                  <div
                    key={event.id}
                    className="flex items-start justify-between gap-4 rounded-lg border border-border/40 p-4"
                  >
                    <div>
                      <p className="text-sm">{event.summary}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {event.reason_code.replaceAll('_', ' ')} ·{' '}
                        {event.source} ·{' '}
                        {event.created_at
                          ? new Date(event.created_at).toLocaleString()
                          : 'Unknown date'}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        event.score_delta < 0
                          ? 'border-destructive/30 text-destructive'
                          : ''
                      }
                    >
                      {event.score_delta >= 0 ? '+' : ''}
                      {event.score_delta}
                    </Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
