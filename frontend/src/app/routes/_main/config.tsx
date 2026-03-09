import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { MarkdownRenderer } from '@/components/markdown/markdown';
import { useConfig } from '@/hooks/use-config';
import { Spinner } from '@/components/ui/spinner';
import { GuildSelector } from '@/components/guild-selector';

export const Route = createFileRoute('/_main/config')({
  component: ConfigComponent,
});

function ConfigComponent() {
  const { data, isLoading } = useConfig();
  const [configDataString, setConfigDataString] = useState('');

  useEffect(() => {
    setConfigDataString(
      '```json\n' + JSON.stringify(data?.config, null, '\t') + '\n```',
    );
  }, [data]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <GuildSelector />
        <div className="flex items-center gap-2">
          <Spinner />
          Loading Configuration Data...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <GuildSelector />
        <div className="text-sm text-muted-foreground">
          Config Version: {data?.version}
        </div>
      </div>
      <MarkdownRenderer content={configDataString} />
    </div>
  );
}
