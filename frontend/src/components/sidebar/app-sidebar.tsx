import * as React from 'react';
import { BrainCircuit, Coins, Gauge, Music, PanelLeft, Server, Settings, Sparkles, Trophy, Users } from 'lucide-react';
import { Link, useLocation } from '@tanstack/react-router';
import { useAuth } from '@/hooks/use-auth';

import { NavUser } from '@/components/sidebar/nav-user';
import { GuildSelector } from '@/components/guild-selector';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';

const data = {
  navMain: [
    {
      title: 'Config',
      icon: Settings,
      items: [
        { title: 'AI & Models', url: '/config/ai', icon: Sparkles },
        { title: 'Memory', url: '/config/memory', icon: BrainCircuit },
        { title: 'Server', url: '/config/server', icon: Server },
        { title: 'Memories', url: '/config/memories', icon: Users },
        { title: 'Usage', url: '/config/usage', icon: Gauge },
        { title: 'Economy', url: '/config/economy', icon: Coins },
        { title: 'Leaderboard', url: '/config/leaderboard', icon: Trophy },
      ],
    },
    {
      title: 'Music Queue',
      url: '/music',
      icon: Music,
    },
  ],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();
  const { user } = useAuth();
  const { state, toggleSidebar } = useSidebar();
  const isCollapsed = state === 'collapsed';

  const activeItem = React.useMemo(() => {
    const segments = location.pathname.split('/').filter(Boolean);
    const matchPath = '/' + segments.slice(0, 2).join('/');

    return data.navMain.find((item) => {
      if (item.items) {
        return item.items.some((sub) => sub.url === matchPath);
      }
      return item.url === '/' + segments[0];
    });
  }, [location.pathname]);

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center justify-between w-full">
              {isCollapsed ? (
                <button
                  onClick={toggleSidebar}
                  className="flex items-center justify-center size-8 rounded-md hover:bg-sidebar-accent"
                >
                  <img src="/bruh.chat.png" alt="Logo" className="size-6 rounded-sm" />
                </button>
              ) : (
                <div className="flex items-center gap-2 h-8 px-2">
                  <img src="/bruh.chat.png" alt="Logo" className="size-6 rounded-sm shrink-0" />
                  <span className="font-semibold text-sm">bruh.bot</span>
                </div>
              )}
              {!isCollapsed && (
                <button
                  onClick={toggleSidebar}
                  className="flex items-center justify-center size-8 rounded-md hover:bg-sidebar-accent hover:text-sidebar-accent-foreground shrink-0"
                >
                  <PanelLeft className="size-4" />
                </button>
              )}
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarMenu>
          <SidebarMenuItem>
            <GuildSelector />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {data.navMain.map((group) => {
          if (group.items) {
            return (
              <SidebarGroup key={group.title} className="py-0">
                <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {group.items.map((item) => (
                      <SidebarMenuItem key={item.title}>
                        <SidebarMenuButton
                          tooltip={{
                            children: item.title,
                            hidden: false,
                          }}
                          asChild
                          isActive={location.pathname.startsWith(item.url)}
                        >
                          <Link to={item.url} search={{}}>
                            <item.icon />
                            <span>{item.title}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            );
          }

          return (
            <SidebarGroup key={group.title} className="py-0">
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      tooltip={{
                        children: group.title,
                        hidden: false,
                      }}
                      asChild
                      isActive={activeItem?.title === group.title}
                    >
                      <Link to={group.url} search={{}}>
                        <group.icon />
                        <span>{group.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          );
        })}
      </SidebarContent>
      <SidebarFooter>
        {user && <NavUser />}
      </SidebarFooter>
    </Sidebar>
  );
}