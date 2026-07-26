import * as React from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ icon, title, description, children, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between border-b border-border/50 pb-6', className)}>
      <div className="flex items-start gap-4 min-w-0">
        {icon && (
          <div className="shrink-0 p-3 rounded-xl bg-primary/10 text-primary hidden sm:flex">
            {React.isValidElement(icon)
              ? React.cloneElement(icon as React.ReactElement<{ className?: string }>, {
                  className: cn('h-6 w-6', (icon as React.ReactElement<{ className?: string }>).props.className),
                })
              : icon}
          </div>
        )}
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight truncate">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground mt-1.5">{description}</p>
          )}
        </div>
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </div>
  );
}