import { t as tr } from "../lib/i18n"
import { useEffect, useState } from 'react'
import { api, errorText } from '../lib/api'
import type { ComposioJob, ComposioPlatform, ComposioStatus } from '../lib/composio'
import type { Clip } from '../lib/types'

const labels = { youtube: 'YouTube', tiktok: 'TikTok' }
const statuses = {
  queued: tr("Na fila"), running: tr("Enviando"), done: tr("Envio aceito"), failed: tr("O envio falhou"),
  cancelled: tr("Envio cancelado"), interrupted: tr("Envio interrompido")
}

export default function ComposioPanel({ clip, onlyYouTube, onOpenAccounts }: {
  clip: Clip
  onlyYouTube: boolean
  onOpenAccounts: () => void
}): JSX.Element {
  const [platform, setPlatform] = useState<ComposioPlatform>('youtube')
  const [title, setTitle] = useState((clip.title || clip.hook || '').slice(0, 100))
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<ComposioStatus | null>(null)
  const [jobs, setJobs] = useState<ComposioJob[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [requestId, setRequestId] = useState(0)
  const [error, setError] = useState('')
  const active = jobs?.some((job) => job.status === 'queued' || job.status === 'running')

  useEffect(() => {
    api.composioStatus().then(setStatus).catch((e) => setError(errorText(e)))
  }, [])

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    const refresh = async (): Promise<void> => {
      try {
        const next = await api.composioJobs(clip.id)
        if (stopped) return
        setJobs(next)
        if (!next.some((job) => job.status === 'queued' || job.status === 'running')) return
      } catch (e) {
        if (!stopped) setError(errorText(e))
      }
      if (!stopped) timer = setTimeout(refresh, 1800)
    }
    void refresh()
    return () => { stopped = true; clearTimeout(timer) }
  }, [clip.id, requestId])

  const send = async (): Promise<void> => {
    setBusy(true)
    setError('')
    try {
      const next = await api.composioSend(clip.id, platform, title.trim(), description)
      setJobs((before) => [next, ...(before ?? []).filter((job) => job.platform !== platform)])
      setRequestId(next.id)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const channel = status?.channels[platform]
  return (
    <section className="space-y-3 rounded-lg border border-white/10 p-3" aria-label="Enviar pelo Composio">
      <h3 className="font-semibold">Enviar pelo Composio</h3>
      <p className="text-sm text-muted truncate">{clip.title || clip.hook}</p>
      {!onlyYouTube && (
        <label className="block text-sm">
          {tr("Destino")}
          <select className="input mt-1" value={platform} disabled={busy || active}
            onChange={(event) => setPlatform(event.target.value === 'tiktok' ? 'tiktok' : 'youtube')}>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
          </select>
        </label>
      )}
      {platform === 'youtube' ? (
        <>
          <p className="text-sm text-muted">Vídeo privado. Revise o público infantil e a visibilidade no YouTube Studio.</p>
          <label className="block text-sm">
            Título
            <input className="input mt-1" value={title} maxLength={100}
              onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="block text-sm">
            Descrição
            <textarea className="input mt-1" value={description} maxLength={5000}
              onChange={(event) => setDescription(event.target.value)} />
          </label>
        </>
      ) : <p className="text-sm text-muted">{tr("Abra a notificação na Caixa de entrada do TikTok para finalizar o post.")}</p>}
      {channel?.connected ? (
        <button type="button" className="btn-accent" disabled={!jobs || busy || active || (platform === 'youtube' && !title.trim())}
          onClick={() => void send()}>
          {platform === 'youtube' ? 'Enviar vídeo privado' : 'Enviar rascunho para o TikTok'}
        </button>
      ) : (
        <button type="button" className="btn-ghost" onClick={onOpenAccounts}>{tr("Abrir canais de postagem")}</button>
      )}
      {channel?.error && <p role="alert" className="text-sm text-error">{channel.error}</p>}
      {channel?.name && <p className="text-sm text-muted">Conta conectada: {channel.name}</p>}
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
      {jobs?.map((job) => (
        <div key={job.id} aria-live="polite" className="text-sm text-muted">
          {labels[job.platform]} · {statuses[job.status]}{job.error && ` · ${job.error}`}
          {job.url && <button type="button" className="ml-2 text-accent underline"
            onClick={() => void window.studio.openExternal(job.url)}>{tr("Abrir no YouTube Studio")}</button>}
        </div>
      ))}
    </section>
  )
}
