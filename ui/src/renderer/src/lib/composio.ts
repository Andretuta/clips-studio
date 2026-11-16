export type ComposioPlatform = 'youtube' | 'tiktok'

export interface ComposioStatus {
  configured: boolean
  tiktok_auth_config: string
  channels: Record<ComposioPlatform, { connected: boolean; name: string; error: string }>
}

export interface ComposioJob {
  id: number
  platform: ComposioPlatform
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrupted'
  error: string
  url: string
}
