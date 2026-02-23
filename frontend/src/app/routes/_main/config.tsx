import { createFileRoute } from '@tanstack/react-router'
import { MarkdownRenderer } from '@/components/markdown/markdown'
import { useConfig } from '@/hooks/use-config'
import { Spinner } from '@/components/ui/spinner';
import { useState, useEffect } from 'react';

export const Route = createFileRoute('/_main/config')({
  component: ConfigComponent,
})

function ConfigComponent() {
  const { data, isLoading } = useConfig();
  const [configDataString, setConfigDataString] = useState('');

  useEffect(() => {
    setConfigDataString("```json\n" + JSON.stringify(data?.config, null, '\t') + "\n```")
  }, [data]);

;  if (isLoading) {
    return (
      <div className='flex items-center gap-2'>
        <Spinner />
        Loading Configuration Data...
      </div>
    )
  }

  return (
    <MarkdownRenderer content={configDataString}/>
  )
}
