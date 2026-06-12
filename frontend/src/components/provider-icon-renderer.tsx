import React from 'react'
import { HugeiconsIcon } from '@hugeicons/react'
import { AiChatIcon } from '@hugeicons/core-free-icons'
import {
  OpenAI,
  Gemini,
  Anthropic,
  Ollama,
  Meta,
  Mistral,
  Perplexity,
  DeepSeek,
  Groq,
  XAI,
  Cohere,
  Together,
  Microsoft,
  OpenRouter,
  Qwen,
  Moonshot,
  ZeroOne,
  Baichuan,
  Minimax,
  Stepfun,
  Upstage,
  Spark,
  Hunyuan,
  Baidu,
  ByteDance,
  Doubao,
  Ai360,
  HuggingFace,
  ModelScope,
  Ai21,
  Bedrock,
  Fireworks,
  Replicate,
  SambaNova,
  Stability,
  Zhipu,
  SenseNova,
  Nvidia,
  Fal,
  Novita,
  SiliconCloud,
  Midjourney,
  Adobe,
  Voyage,
  Phind,
  AionLabs,
  Arcee,
  DeepCogito,
  EssentialAI,
  IBM,
  Inception,
  Inflection,
  Kwaipilot,
  Liquid,
  Morph,
  NousResearch,
  Relace,
  Tencent,
  ZAI,
} from '@lobehub/icons'

export interface ProviderIconRendererProps {
  provider: string
  size?: number
  className?: string
}

/**
 * Safely renders a LobeHub icon with fallback
 */
const SafeIcon = React.memo(
  ({
    Component,
    size,
    className,
  }: {
    Component: any
    size: number
    className?: string
  }) => {
    if (!Component) {
      return (
        <HugeiconsIcon icon={AiChatIcon} size={size} className={className} />
      )
    }

    // Prefer .Color if available, otherwise use the base component
    const Target = Component.Color || Component

    // Final safety check in case the export exists but isn't a component
    if (typeof Target !== 'function' && typeof Target !== 'object') {
      return (
        <HugeiconsIcon icon={AiChatIcon} size={size} className={className} />
      )
    }

    return <Target size={size} className={className} />
  },
)

SafeIcon.displayName = 'SafeIcon'

export const ProviderIconRenderer = React.memo(
  ({ provider, size = 18, className }: ProviderIconRendererProps) => {
    const p = provider.toLowerCase()

    switch (p) {
      case 'openai':
      case '~openai':
        return <SafeIcon Component={OpenAI} size={size} className={className} />
      case 'anthropic':
      case '~anthropic':
        return (
          <SafeIcon Component={Anthropic} size={size} className={className} />
        )
      case 'google':
      case '~google':
      case 'gemini':
        return <SafeIcon Component={Gemini} size={size} className={className} />
      case 'ollama':
        return <SafeIcon Component={Ollama} size={size} className={className} />
      case 'meta':
      case 'meta-llama':
      case 'llama':
        return <SafeIcon Component={Meta} size={size} className={className} />
      case 'mistral':
      case 'mistralai':
        return (
          <SafeIcon Component={Mistral} size={size} className={className} />
        )
      case 'perplexity':
        return (
          <SafeIcon Component={Perplexity} size={size} className={className} />
        )
      case 'deepseek':
        return (
          <SafeIcon Component={DeepSeek} size={size} className={className} />
        )
      case 'groq':
        return <SafeIcon Component={Groq} size={size} className={className} />
      case 'xai':
      case 'x-ai':
      case 'grok':
        return <SafeIcon Component={XAI} size={size} className={className} />
      case 'cohere':
        return <SafeIcon Component={Cohere} size={size} className={className} />
      case 'together':
      case 'together-ai':
        return (
          <SafeIcon Component={Together} size={size} className={className} />
        )
      case 'microsoft':
      case 'azure':
        return (
          <SafeIcon Component={Microsoft} size={size} className={className} />
        )
      case 'qwen':
        return <SafeIcon Component={Qwen} size={size} className={className} />
      case 'moonshot':
      case '~moonshotai':
      case 'moonshotai':
        return (
          <SafeIcon Component={Moonshot} size={size} className={className} />
        )
      case 'zeroone':
      case '01-ai':
      case 'yi':
        return (
          <SafeIcon Component={ZeroOne} size={size} className={className} />
        )
      case 'baichuan':
        return (
          <SafeIcon Component={Baichuan} size={size} className={className} />
        )
      case 'minimax':
        return (
          <SafeIcon Component={Minimax} size={size} className={className} />
        )
      case 'stepfun':
        return (
          <SafeIcon Component={Stepfun} size={size} className={className} />
        )
      case 'upstage':
        return (
          <SafeIcon Component={Upstage} size={size} className={className} />
        )
      case 'spark':
        return <SafeIcon Component={Spark} size={size} className={className} />
      case 'hunyuan':
        return (
          <SafeIcon Component={Hunyuan} size={size} className={className} />
        )
      case 'baidu':
      case 'wenxin':
        return <SafeIcon Component={Baidu} size={size} className={className} />
      case 'bytedance':
      case 'volcengine':
        return (
          <SafeIcon Component={ByteDance} size={size} className={className} />
        )
      case 'doubao':
        return <SafeIcon Component={Doubao} size={size} className={className} />
      case 'ai360':
      case '360':
        return <SafeIcon Component={Ai360} size={size} className={className} />
      case 'huggingface':
        return (
          <SafeIcon Component={HuggingFace} size={size} className={className} />
        )
      case 'modelscope':
        return (
          <SafeIcon Component={ModelScope} size={size} className={className} />
        )
      case 'ai21':
        return <SafeIcon Component={Ai21} size={size} className={className} />
      case 'amazon':
      case 'aws':
        return (
          <SafeIcon Component={Bedrock} size={size} className={className} />
        )
      case 'fireworks':
      case 'fireworks-ai':
        return (
          <SafeIcon Component={Fireworks} size={size} className={className} />
        )
      case 'replicate':
        return (
          <SafeIcon Component={Replicate} size={size} className={className} />
        )
      case 'sambanova':
        return (
          <SafeIcon Component={SambaNova} size={size} className={className} />
        )
      case 'stability':
      case 'stabilityai':
        return (
          <SafeIcon Component={Stability} size={size} className={className} />
        )
      case 'zhipu':
      case 'zhipuai':
        return <SafeIcon Component={Zhipu} size={size} className={className} />
      case 'sensetime':
        return (
          <SafeIcon Component={SenseNova} size={size} className={className} />
        )
      case 'nvidia':
        return <SafeIcon Component={Nvidia} size={size} className={className} />
      case 'fal':
      case 'fal-ai':
        return <SafeIcon Component={Fal} size={size} className={className} />
      case 'novita':
      case 'novita-ai':
        return <SafeIcon Component={Novita} size={size} className={className} />
      case 'siliconflow':
        return (
          <SafeIcon
            Component={SiliconCloud}
            size={size}
            className={className}
          />
        )
      case 'midjourney':
        return (
          <SafeIcon Component={Midjourney} size={size} className={className} />
        )
      case 'adobe':
        return <SafeIcon Component={Adobe} size={size} className={className} />
      case 'voyage':
      case 'voyageai':
        return <SafeIcon Component={Voyage} size={size} className={className} />
      case 'phind':
        return <SafeIcon Component={Phind} size={size} className={className} />
      case 'aion-labs':
        return (
          <SafeIcon Component={AionLabs} size={size} className={className} />
        )
      case 'arcee-ai':
        return <SafeIcon Component={Arcee} size={size} className={className} />
      case 'bytedance-seed':
        return (
          <SafeIcon Component={ByteDance} size={size} className={className} />
        )
      case 'deepcogito':
        return (
          <SafeIcon Component={DeepCogito} size={size} className={className} />
        )
      case 'essentialai':
        return (
          <SafeIcon Component={EssentialAI} size={size} className={className} />
        )
      case 'ibm':
      case 'ibm-granite':
        return <SafeIcon Component={IBM} size={size} className={className} />
      case 'inception':
        return (
          <SafeIcon Component={Inception} size={size} className={className} />
        )
      case 'inflection':
        return (
          <SafeIcon Component={Inflection} size={size} className={className} />
        )
      case 'kwaipilot':
        return (
          <SafeIcon Component={Kwaipilot} size={size} className={className} />
        )
      case 'liquid':
        return <SafeIcon Component={Liquid} size={size} className={className} />
      case 'morph':
        return <SafeIcon Component={Morph} size={size} className={className} />
      case 'nousresearch':
        return (
          <SafeIcon
            Component={NousResearch}
            size={size}
            className={className}
          />
        )
      case 'relace':
        return <SafeIcon Component={Relace} size={size} className={className} />
      case 'tencent':
        return (
          <SafeIcon Component={Tencent} size={size} className={className} />
        )
      case 'z-ai':
        return <SafeIcon Component={ZAI} size={size} className={className} />
      case 'openrouter':
      case 'mesh_router':
        return (
          <SafeIcon Component={OpenRouter} size={size} className={className} />
        )
      default:
        return (
          <HugeiconsIcon icon={AiChatIcon} size={size} className={className} />
        )
    }
  },
)

ProviderIconRenderer.displayName = 'ProviderIconRenderer'