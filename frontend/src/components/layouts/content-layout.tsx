import * as React from 'react';

import { SidebarTrigger } from '../ui/sidebar';
import { ThemeToggle } from '../theme/theme-toggle';

type ContentLayoutProps = {
  children: React.ReactNode;
  fullHeight?: boolean;
};

export const ContentLayout = ({
  children,
  fullHeight = false,
}: ContentLayoutProps) => {
  return (
    <div className="flex flex-1 flex-col h-screen overflow-hidden bg-sidebar">
      <header className="bg-transparent flex shrink-0 items-center justify-between gap-2 px-4 pt-1.5">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
        </div>
        <ThemeToggle />
      </header>
      <main className="flex-1 min-h-0 overflow-hidden pr-2 pb-2">
        <div className="h-full w-full bg-background rounded-xl border shadow-sm overflow-auto">
          {fullHeight ? (
            children
          ) : (
            <div className="mx-auto max-w-7xl px-4 pb-6 pt-2 sm:px-6 md:px-8 md:pt-4">
              {children}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
