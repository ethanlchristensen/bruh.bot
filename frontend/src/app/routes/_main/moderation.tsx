import { createFileRoute } from '@tanstack/react-router'
import { ModerationSection } from './moderation-section'
import { defaultConfig } from '@/lib/default-config'
import { useState } from 'react'

export const Route = createFileRoute('/_main/moderation')({
  component: ModerationPage,
})

function ModerationPage() {
  const [config, setConfig] = useState(defaultConfig)

  const updateConfig = (updates: Partial<typeof defaultConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return <ModerationSection config={config} onUpdate={updateConfig} />
}
