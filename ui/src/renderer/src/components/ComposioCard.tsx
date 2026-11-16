import { t as tr } from "../lib/i18n"
import { useCallback, useEffect, useState } from 'react'
import { api, errorText } from '../lib/api'
import type { ComposioPlatform, ComposioStatus } from '../lib/composio'

const labels = { youtube: 'YouTube', tiktok: 'TikTok' }
const platforms = ['youtube', 'tiktok'] as const
const guide = 'https://docs.composio.dev/kb/guide/toolkits-tiktok'

export default function ComposioCard(): JSX.Element {
  const [status, setStatus] = useState<ComposioStatus | null>(null)
  const [key, setKey] = useState('')
  const [config, setConfig] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [auth, setAuth] = useState<{ platform: ComposioPlatform; url: string } | null>(null)

  const refresh = useCallback(async (): Promise<void> => {
    try {
      setStatus(await api.composioStatus())
      setError('')
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    const onFocus = (): void => { void refresh() }
    void refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refresh])

  const save = async (): Promise<void> => {
    setBusy(true)
    setMessage('')
    setError('')
    try {
      await api.composioSettings({
        api_key: key.trim() || undefined,
        tiktok_auth_config: config?.trim() ?? status?.tiktok_auth_config ?? ''
      })
      setKey('')
      setConfig(null)
      setAuth(null)
      await refresh()
      setMessage(tr("Configuração salva."))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const connect = async (platform: ComposioPlatform): Promise<void> => {
    setBusy(true)
    setMessage('')
    setError('')
    try {
      const { url } = await api.composioConnect(platform)
      setAuth({ platform, url })
      setMessage(tr("Conclua a autorização no navegador e atualize o status."))
      await window.studio.openExternal(url)
      await refresh()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card space-y-4" aria-labelledby="composio-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="composio-heading" className="font-semibold">Composio</h3>
        <button type="button" className="btn-ghost text-sm" disabled={busy}
          onClick={() => void refresh()}>{tr("Atualizar status")}</button>
      </div>
      <div className="space-y-2">
        {platforms.map((platform) => {
          const channel = status?.channels[platform]
          const ready = status?.configured && (platform === 'youtube' || !!status.tiktok_auth_config)
          return (
            <div key={platform} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-base p-2.5">
              <div className="min-w-0">
                <p className="text-sm font-semibold">{labels[platform]}</p>
                <p className="text-xs text-muted break-words">{channel?.error || (channel?.connected
                  ? channel.name || tr("Conectado")
                  : status ? 'Aguardando autorização' : tr("Verificando…"))}</p>
              </div>
              <button type="button" className="btn-ghost text-sm" disabled={!ready || busy}
                onClick={() => void connect(platform)}>{channel?.connected ? tr("Reconectar") : tr("Conectar")} {labels[platform]}</button>
            </div>
          )
        })}
      </div>
      {auth && !status?.channels[auth.platform].connected && (
        <button type="button" className="text-sm text-accent underline"
          onClick={() => void window.studio.openExternal(auth.url)}>{tr("Abrir autorização de")} {labels[auth.platform]}</button>
      )}
      <details open={status ? !status.configured || undefined : undefined}>
        <summary className="cursor-pointer text-sm">{tr("Configuração do Composio")}</summary>
        <form className="mt-3 space-y-3" onSubmit={(event) => { event.preventDefault(); void save() }}>
          <label className="block text-sm">
            {tr("Chave de API")}
            <input className="input mt-1" type="password" value={key} autoComplete="off"
              placeholder={status?.configured ? tr("Chave configurada") : tr("Chave do projeto no Composio")}
              onChange={(event) => setKey(event.target.value)} />
          </label>
          <label className="block text-sm">
            {tr("Auth Config do TikTok")}
            <input className="input mt-1" value={config ?? status?.tiktok_auth_config ?? ''}
              placeholder={tr("ac_…")} onChange={(event) => setConfig(event.target.value)} />
          </label>
          <p className="text-xs text-muted">
            O TikTok precisa de um app com permissão para enviar rascunhos.{' '}
            <button type="button" className="text-accent underline"
              onClick={() => void window.studio.openExternal(guide)}>{tr("Ver configuração do TikTok")}</button>
          </p>
          <button type="submit" className="btn-accent text-sm"
            disabled={!status || busy || (!key.trim() && config === null)}>Salvar configuração</button>
        </form>
      </details>
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      {message && <p role="status" className="text-sm text-muted">{message}</p>}
    </section>
  )
}
