import * as React from 'react';

import { ErrorBoundary } from 'react-error-boundary';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from '@/components/theme/theme-provider';
import { SidebarProvider } from '@/components/ui/sidebar';

import { MainErrorFallback } from '@/components/errors/main';
import { Spinner } from '@/components/ui/spinner';
import { queryConfig } from '@/lib/react-query';
import { AuthProvider } from '@/contexts/auth-context';
import { ConfigChangesProvider } from '@/contexts/config-changes-context';
import { GuildProvider } from '@/contexts/guild-context';
import { MusicProvider } from '@/contexts/music-context';

type AppProviderProps = {
  children: React.ReactNode;
};

export const AppProvider = ({ children }: AppProviderProps) => {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: queryConfig,
      }),
  );

  const [open, setOpen] = React.useState(() => {
    const saved = localStorage.getItem('sidebar-open');
    return saved ? JSON.parse(saved) : true;
  });

  const handleOpenChange = (value: boolean) => {
    setOpen(value);
    localStorage.setItem('sidebar-open', JSON.stringify(value));
  };

  return (
    <ThemeProvider defaultTheme="dark" storageKey="bruh-ui-theme">
      <React.Suspense
        fallback={
          <div className="flex h-screen w-screen items-center justify-center">
            <Spinner />
          </div>
        }
      >
        <ErrorBoundary FallbackComponent={MainErrorFallback}>
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              <GuildProvider>
                <MusicProvider>
                  <SidebarProvider
                    style={
                      {
                        '--sidebar-width': '350px',
                      } as React.CSSProperties
                    }
                    open={open}
                    onOpenChange={handleOpenChange}
                  >
                    <ConfigChangesProvider>{children}</ConfigChangesProvider>
                  </SidebarProvider>
                </MusicProvider>
                <ReactQueryDevtools />
              </GuildProvider>
            </AuthProvider>
          </QueryClientProvider>
        </ErrorBoundary>
      </React.Suspense>
    </ThemeProvider>
  );
};
