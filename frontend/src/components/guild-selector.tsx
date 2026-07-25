import { useQueryClient } from '@tanstack/react-query';
import { configKeys, useGuilds } from '@/hooks/use-config';
import { useGuild } from '@/contexts/guild-context';
import { useSidebar } from '@/components/ui/sidebar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

function GuildIcon({ icon, name, size = 16 }: { icon: string; name: string; size?: number }) {
  if (!icon) {
    return (
      <div
        className="rounded-sm bg-sidebar-accent flex items-center justify-center shrink-0 text-xs font-bold text-sidebar-accent-foreground"
        style={{ width: size, height: size }}
      >
        {name.charAt(0).toUpperCase()}
      </div>
    );
  }
  return (
    <img
      src={`${icon}?size=64`}
      alt={name}
      className="rounded-sm shrink-0"
      style={{ width: size, height: size }}
    />
  );
}

export function GuildSelector() {
  const { data, isLoading } = useGuilds();
  const { selectedGuildId, setSelectedGuildId } = useGuild();
  const queryClient = useQueryClient();
  const { state: sidebarState } = useSidebar();
  const isCollapsed = sidebarState === 'collapsed';

  const handleGuildChange = (guildId: string) => {
    setSelectedGuildId(guildId);
    queryClient.invalidateQueries({ queryKey: configKeys.all });
  };

  const selectedGuild = data?.guilds?.find((g) => g.id === selectedGuildId);

  if (isLoading) {
    return isCollapsed ? (
      <div className="flex items-center justify-center size-8">
        <Spinner className="size-4" />
      </div>
    ) : (
      <div className="flex items-center gap-2 px-2">
        <Spinner className="size-3" />
        <span className="text-sm text-muted-foreground">Loading...</span>
      </div>
    );
  }

  if (!data?.guilds || data.guilds.length === 0) {
    return null;
  }

  if (isCollapsed) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className={cn(
              'flex items-center justify-center size-8 rounded-md w-full',
              'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
              'data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground',
            )}
          >
            {selectedGuild ? (
              <GuildIcon icon={selectedGuild.icon} name={selectedGuild.name} size={24} />
            ) : (
              <div className="size-6 rounded-sm bg-sidebar-accent" />
            )}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="right" align="start" className="w-52">
          {data.guilds.map((guild) => (
            <DropdownMenuItem
              key={guild.id}
              onClick={() => handleGuildChange(guild.id)}
              className={cn(
                'gap-3 cursor-pointer',
                guild.id === selectedGuildId && 'bg-accent font-medium',
              )}
            >
              <GuildIcon icon={guild.icon} name={guild.name} size={24} />
              <span className="truncate">{guild.name}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  return (
    <Select value={selectedGuildId} onValueChange={handleGuildChange}>
      <SelectTrigger className="w-full justify-start gap-2">
        <SelectValue placeholder="Select a guild" />
      </SelectTrigger>
      <SelectContent>
        {data.guilds.map((guild) => (
          <SelectItem key={guild.id} value={guild.id}>
            <span className="flex items-center gap-2">
              <GuildIcon icon={guild.icon} name={guild.name} size={20} />
              {guild.name}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}