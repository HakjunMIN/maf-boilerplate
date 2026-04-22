import { useEffect, useState } from 'react'

const STORAGE_KEY = 'maf-lab-config'

export interface AppConfig {
  baseUrl: string
  token: string
}

const defaultConfig: AppConfig = {
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
  token: import.meta.env.VITE_API_TOKEN ?? '',
}

function readConfig(): AppConfig {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (!stored) {
    return defaultConfig
  }

  try {
    const parsed = JSON.parse(stored) as Partial<AppConfig>
    return {
      baseUrl: parsed.baseUrl ?? defaultConfig.baseUrl,
      token: parsed.token ?? defaultConfig.token,
    }
  } catch {
    return defaultConfig
  }
}

export function useConfig(): {
  config: AppConfig
  setConfig: (updater: AppConfig | ((current: AppConfig) => AppConfig)) => void
} {
  const [config, setConfig] = useState<AppConfig>(() => readConfig())

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  }, [config])

  return { config, setConfig }
}