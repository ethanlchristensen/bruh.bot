'use client';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Save } from 'lucide-react';

interface StickySaveBarProps {
  onSave: () => void;
  isSaving?: boolean;
  hasChanges: boolean;
  className?: string;
  saveLabel?: string;
}

export function StickySaveBar({
  onSave,
  isSaving = false,
  hasChanges,
  className,
  saveLabel = 'Save Changes',
}: StickySaveBarProps) {
  return (
    <div
      className={cn(
        'sticky top-0 z-40 -mx-2 px-2',
        'transition-all duration-200',
        className,
      )}
    >
      <div
        className={cn(
          'flex items-center justify-between rounded-xl border px-5 py-3',
          'bg-background/90 backdrop-blur-md shadow-sm',
          hasChanges
            ? 'border-amber-500/30'
            : 'border-border/40',
        )}
      >
        <div className="flex items-center gap-3">
          {hasChanges ? (
            <div className="flex items-center gap-2 text-sm font-medium text-amber-600 dark:text-amber-500">
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
              Unsaved changes
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              All changes saved
            </div>
          )}
        </div>
        <Button
          onClick={onSave}
          disabled={isSaving || !hasChanges}
          className="gap-2"
          size="sm"
        >
          <Save className="h-4 w-4" />
          {isSaving ? 'Saving...' : saveLabel}
        </Button>
      </div>
    </div>
  );
}