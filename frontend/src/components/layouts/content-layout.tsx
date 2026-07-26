import * as React from 'react';

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
      <main className="flex-1 min-h-0 overflow-hidden pr-4 py-4">
        <div
          data-slot="content-layout-main"
          className="h-full w-full bg-background rounded-xl border shadow-sm overflow-auto"
        >
          {fullHeight ? (
            children
          ) : (
            <div className="mx-auto max-w-7xl pb-16 pt-6 sm:px-8 md:px-10">
              {children}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};