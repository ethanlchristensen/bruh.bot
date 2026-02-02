import { createFileRoute } from '@tanstack/react-router'
import { UsersSection } from './users-section'
import { defaultConfig } from '@/lib/default-config'
import { useState } from 'react'

export const Route = createFileRoute('/_main/users')({
  component: UsersPage,
})

function UsersPage() {
  const [config, setConfig] = useState(defaultConfig)

  const updateConfig = (updates: Partial<typeof defaultConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return <UsersSection config={config} onUpdate={updateConfig} />
}
