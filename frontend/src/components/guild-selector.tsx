import { useQueryClient } from '@tanstack/react-query';
import { configKeys, useGuilds } from '@/hooks/use-config';
import { useGuild } from '@/contexts/guild-context';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';

export function GuildSelector() {
  const { data, isLoading } = useGuilds();
  const { selectedGuildId, setSelectedGuildId } = useGuild();
  const queryClient = useQueryClient();

  const handleGuildChange = (guildId: string) => {
    setSelectedGuildId(guildId);
    // Invalidate config queries to refetch for new guild
    queryClient.invalidateQueries({ queryKey: configKeys.all });
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Spinner className="size-3" />
        <span className="text-sm text-muted-foreground">Loading guilds...</span>
      </div>
    );
  }

  if (!data?.guilds || data.guilds.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">No guilds available</div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="guild-select" className="text-sm font-medium">
        Guild:
      </label>
      <Select value={selectedGuildId} onValueChange={handleGuildChange}>
        <SelectTrigger id="guild-select" className="w-[200px]">
          <SelectValue placeholder="Select a guild" />
        </SelectTrigger>
        <SelectContent>
          {data.guilds.map((guildId) => (
            <SelectItem key={guildId} value={guildId}>
              {guildId}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
