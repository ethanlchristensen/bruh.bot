import * as React from 'react';
import { Shield, Code } from 'lucide-react';
import { Link, useLocation } from '@tanstack/react-router';
import { useAuth } from '@/hooks/use-auth';

import { NavUser } from '@/components/sidebar/nav-user';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';

const data = {
  navMain: [
    {
      title: 'View Config',
      url: '/config',
      icon: Code,
      isActive: true,
    },
    {
      title: 'User Management',
      url: '/user-management',
      icon: Shield,
      isActive: false
    }
  ],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation();
  const { user } = useAuth();

  const activeItem = React.useMemo(() => {
    const firstSegment = location.pathname.split('/')[1];
    const matchPath = firstSegment ? `/${firstSegment}` : '/';

    return (
      data.navMain.find((item) => item.url === matchPath)
    );
  }, [location.pathname]);

  return (
    <>
      <Sidebar
        collapsible="icon"
        className="overflow-hidden *:data-[sidebar=sidebar]:flex-row"
        {...props}
      >
        <Sidebar
          collapsible="none"
          className="w-[calc(var(--sidebar-width-icon)+1px)]! border-r"
        >
          <SidebarHeader>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton size="lg" asChild className="md:h-8 md:p-0">
                  <Link to="/" search={{}} className="relative overflow-hidden">
                    <img
                      src="/bruh.chat.png"
                      alt="Company Logo"
                      className="h-8 w-full object-cover rounded-lg"
                    />
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupContent className="px-1.5 md:px-0">
                <SidebarMenu>
                  {data.navMain.map((item) => (
                    <SidebarMenuItem key={item.title}>
                      <SidebarMenuButton
                        tooltip={{
                          children: item.title,
                          hidden: false,
                        }}
                        asChild
                        isActive={activeItem?.title === item.title}
                        className="px-2.5 md:px-2"
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
          </SidebarContent>
          <SidebarFooter>{user && <NavUser />}</SidebarFooter>
        </Sidebar>
      </Sidebar>
    </>
  );
}
