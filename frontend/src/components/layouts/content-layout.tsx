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
        <div className="h-full w-full bg-background rounded-xl border shadow-sm overflow-auto">
          {fullHeight ? (
            children
          ) : (
            <div className="mx-auto max-w-7xl pb-6 pt-4 sm:px-6 md:px-8">
              {children}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};