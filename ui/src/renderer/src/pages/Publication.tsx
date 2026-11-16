import { t as tr } from "../lib/i18n"
import { useEffect, useRef, useState } from 'react'
import ComposioCard from '../components/ComposioCard'
import { CortesGamerOverlay, CortesGamerSliders, CortesGamerToggle, DEFAULT_CORTES_GAMER_STYLE } from '../components/CortesGamerWatermark'
import ComposioPanel from '../components/ComposioPanel'
import UploadPostCard from '../components/UploadPostCard'
import UploadPostPanel from '../components/UploadPostPanel'
import YouTubeCard from '../components/YouTubeCard'
import YouTubePanel from '../components/YouTubePanel'
import { api, errorText } from '../lib/api'
import { getExportFolder } from '../lib/exportFolder'
import type { Clip, CompilationJob, CompilationSource, CortesGamerStyle, Job } from '../lib/types'
import type { UploadPostStatus } from '../lib/uploadpost'
import type { YouTubeStatus } from '../lib/youtube'

const DRAFT_KEY = 'compilation-draft'

interface Draft {
  title: string
  order: string[]
  job: CompilationJob | null
  cortesGamer: boolean
  cortesGamerStyle: CortesGamerStyle
}

function loadDraft(): Draft {
  try {
    const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}')
    return {
      title: typeof draft.title === 'string' ? draft.title : '',
      order: Array.isArray(draft.order) ? draft.order.filter((id: unknown) => typeof id === 'string') : [],
      cortesGamer: draft.cortesGamer === true,
      cortesGamerStyle: { ...DEFAULT_CORTES_GAMER_STYLE, ...draft.cortesGamerStyle },
      job: Number.isSafeInteger(draft.job?.job_id) && typeof draft.job?.video_id === 'string' ? draft.job : null
    }
  } catch {
    return { title: '', order: [], job: null, cortesGamer: false, cortesGamerStyle: DEFAULT_CORTES_GAMER_STYLE }
  }
}

function duration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return [Math.floor(total / 60), String(total % 60).padStart(2, '0')].join(':')
}

const statusLabel = {
  queued: tr("Na fila"),
  running: 'Montando o vídeo',
  done: 'Compilado pronto',
  failed: tr("Falha na exportação"),
  cancelled: tr("Exportação cancelada")
}

export default function Publication({ onOpenInStudio }: {
  onOpenInStudio: (videoId: string, clipId: number) => void
}): JSX.Element {
  const [tab, setTab] = useState<'compilation' | 'accounts'>('compilation')
  const [draft, setDraft] = useState(loadDraft)
  const [sources, setSources] = useState<CompilationSource[] | null>(null)
  const [search, setSearch] = useState('')
  const [preview, setPreview] = useState<CompilationSource | null>(null)
  const previewVideo = useRef<HTMLVideoElement>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [result, setResult] = useState<Clip | null>(null)
  const [busy, setBusy] = useState(false)
  const [preparing, setPreparing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [youtube, setYouTube] = useState<YouTubeStatus | null>(null)
  const [uploadPost, setUploadPost] = useState<UploadPostStatus | null>(null)
  const [posting, setPosting] = useState(false)
  const [composioCut, setComposioCut] = useState<{ source: string; clip: Clip } | null>(null)
  const [composioCompilation, setComposioCompilation] = useState(false)
  const selected = draft.order.map((id) => sources?.find((source) => source.id === id))
  const picking = !busy && (!draft.job || (job !== null && !['queued', 'running'].includes(job.status)))

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
    } catch {
      // The draft remains usable in this page if browser storage is full.
    }
  }, [draft])
  useEffect(() => {
    if (tab !== 'compilation') return
    api.compilationSources().then(setSources).catch((e) => setError(errorText(e)))
  }, [tab])
  useEffect(() => {
    if (!draft.job) return
    const { job_id: jobId, video_id: videoId } = draft.job
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const check = async (): Promise<void> => {
      try {
        const next = await api.job(jobId)
        if (cancelled) return
        setJob(next)
        if (next.status === 'done') {
          const [clip] = await api.clips(videoId)
          if (!cancelled && clip) setResult(clip)
          if (clip) return
          if (!cancelled) setError('O arquivo do compilado não está mais na biblioteca.')
          return
        }
        if (next.status === 'failed' || next.status === 'cancelled') return
      } catch (e) {
        if (!cancelled) setError(errorText(e))
      }
      if (!cancelled) timer = setTimeout(check, 1500)
    }
    void check()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [draft.job])

  const changeOrder = (order: string[]): void => setDraft((before) => ({ ...before, order }))
  const move = (index: number, direction: -1 | 1): void => {
    const order = [...draft.order]
    const [cut] = order.splice(index, 1)
    order.splice(index + direction, 0, cut)
    changeOrder(order)
  }
  const compile = async (): Promise<void> => {
    if (!picking) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const next = await api.makeCompilation(draft.title.trim(), draft.order, draft.cortesGamer, draft.cortesGamerStyle)
      setJob(null)
      setResult(null)
      setPosting(false)
      setComposioCompilation(false)
      setDraft((before) => ({ ...before, job: next }))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const prepare = async (cut: CompilationSource, target: 'editor' | 'composio'): Promise<void> => {
    setPreparing(true)
    setError('')
    try {
      const ready = await api.preparePublication(cut.id)
      if (target === 'editor') {
        onOpenInStudio(ready.video_id, ready.clip_id)
      } else {
        const clip = (await api.clips(ready.video_id)).find((item) => item.id === ready.clip_id)
        if (!clip) throw new Error('O corte preparado não está na biblioteca.')
        setComposioCut({ source: cut.id, clip })
      }
    } catch (e) {
      setError(errorText(e))
    } finally {
      setPreparing(false)
    }
  }
  const saveFile = async (clip: Clip): Promise<void> => {
    try {
      const saved = await api.exportClip(clip.id, await getExportFolder())
      setNotice(saved.exported[0] ? tr("MP4 salvo em {0}", saved.exported[0]) : tr("MP4 salvo."))
    } catch (e) {
      setError(errorText(e))
    }
  }
  const openYouTube = async (): Promise<void> => {
    setError('')
    try {
      const direct = await api.youtubeStatus()
      if (direct.connected) {
        setYouTube(direct)
        setUploadPost(null)
      } else {
        const profile = await api.uploadPostStatus()
        if (!profile.enabled || !profile.has_key ||
            !(await api.uploadPostConnections()).connected.includes('youtube')) {
          setTab('accounts')
          return
        }
        setYouTube(null)
        setUploadPost(profile)
      }
      setPosting(true)
    } catch (e) {
      setError(errorText(e))
    }
  }

  const query = search.trim().toLocaleLowerCase()
  const found = sources?.filter((item) => `${item.title} ${item.channel} ${item.state}`.toLocaleLowerCase().includes(query))
  const total = selected.every((item) => item?.duration != null)
    ? duration(selected.reduce((sum, item) => sum + (item?.duration ?? 0), 0))
    : null

  return (
    <div className="p-4 sm:p-6 space-y-4 w-full max-w-[1400px] mx-auto">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">{tr("Publicação")}</h2>
        <nav aria-label={tr("Publicação")} className="flex gap-1 rounded-lg bg-surface p-1 text-sm">
          <button type="button" aria-pressed={tab === 'compilation'}
            className={tab === 'compilation' ? 'btn-accent' : 'btn-ghost'} onClick={() => setTab('compilation')}>
            Compilado para YouTube
          </button>
          <button type="button" aria-pressed={tab === 'accounts'}
            className={tab === 'accounts' ? 'btn-accent' : 'btn-ghost'} onClick={() => setTab('accounts')}>
            {tr("Canais de postagem")}
          </button>
        </nav>
      </header>

      {tab === 'accounts' ? (
        <div className="grid gap-4 xl:grid-cols-2 items-start">
          <ComposioCard />
          <div className="space-y-2">
            <p className="text-sm text-muted">{tr("TikTok e YouTube pelo mesmo perfil do Upload-Post.")}</p>
            <UploadPostCard />
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted">YouTube direto para Shorts e vídeos horizontais.</p>
            <YouTubeCard />
          </div>
        </div>
      ) : (
        <>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] items-start">
            <section className="card space-y-3" aria-labelledby="compilation-cuts">
              <h3 id="compilation-cuts" className="font-semibold">Cortes disponíveis</h3>
              <input className="input" type="search" value={search}
                placeholder="Buscar corte ou canal" aria-label="Buscar corte ou canal"
                onChange={(event) => setSearch(event.target.value)} />
              <div className="space-y-1 max-h-[31rem] overflow-y-auto pr-1">
                {found?.map((cut) => (
                  <div key={cut.id} className="flex items-center gap-2 rounded-lg bg-base/60 p-2.5">
                    <button type="button" className="min-w-0 flex-1 text-left hover:text-accent"
                      aria-pressed={preview?.id === cut.id} onClick={() => setPreview(cut)}>
                      <span className="block text-sm truncate" title={cut.title}>{cut.title}</span>
                      <span className="block text-xs text-muted truncate">
                        {[cut.channel, cut.state, cut.duration != null ? duration(cut.duration) : ''].filter(Boolean).join(' · ')}
                      </span>
                    </button>
                    <button type="button" className="btn-ghost !py-1.5 text-xs shrink-0"
                      aria-label={tr("Adicionar {0}", cut.title)}
                      disabled={draft.order.includes(cut.id)}
                      onClick={() => changeOrder([...draft.order, cut.id])}>
                      {draft.order.includes(cut.id) ? tr("Adicionado") : tr("+ Adicionar")}
                    </button>
                  </div>
                ))}
                {!found?.length && <p className="text-sm text-muted p-2">
                  {sources ? 'Nenhum corte encontrado.' : error ? 'A lista de cortes está indisponível.' : 'Carregando cortes…'}
                </p>}
              </div>
            </section>

            <section className="card space-y-3" aria-labelledby="compilation-sequence">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 id="compilation-sequence" className="font-semibold">Ordem do vídeo</h3>
                <p className="text-xs font-mono text-muted">{tr("16:9 · 1080p ·")} {draft.order.length} cortes{total ? ` · ≈ ${total}` : ''}</p>
              </div>
              <div className="relative rounded-lg bg-black aspect-video max-h-60 grid place-items-center overflow-hidden">
                {preview ? (
                  <>
                    <video key={preview.id} ref={previewVideo} className="absolute inset-0 size-full object-contain"
                      controls muted preload="metadata" aria-label={preview.title} src={api.compilationMedia(preview.id)} />
                    {draft.cortesGamer && !preview.cortes_gamer_baked && (
                      <CortesGamerOverlay key={preview.id} videoRef={previewVideo} style={draft.cortesGamerStyle} />
                    )}
                  </>
                ) : <p className="text-sm text-muted px-3">Selecione um corte para ver a prévia.</p>}
              </div>
              {preview && <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-ghost text-sm" disabled={preparing}
                  onClick={() => void prepare(preview, 'editor')}>
                  {preparing ? 'Preparando corte…' : 'Abrir corte no editor para postar'}
                </button>
                <button type="button" className="btn-ghost text-sm" disabled={preparing}
                  onClick={() => void prepare(preview, 'composio')}>Enviar corte pelo Composio</button>
              </div>}
              {composioCut && preview?.id === composioCut.source &&
                <ComposioPanel key={composioCut.clip.id} clip={composioCut.clip} onlyYouTube={false}
                  onOpenAccounts={() => setTab('accounts')} />}
              <ol className="space-y-1 max-h-56 overflow-y-auto pr-1">
                {draft.order.map((id, index) => (
                  <li key={id} className="grid grid-cols-[2rem_1fr_auto] items-center gap-2 bg-raised/70 rounded-md p-1.5">
                    <span className="font-mono text-center text-sm text-accent">{String(index + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 text-sm truncate">{selected[index]?.title ?? 'Corte indisponível'}</span>
                    <span className="flex gap-1">
                      <button type="button" className="btn-ghost !px-2 !py-1"
                        aria-label={`Subir corte ${index + 1}`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
                      <button type="button" className="btn-ghost !px-2 !py-1"
                        aria-label={`Descer corte ${index + 1}`} disabled={index === draft.order.length - 1}
                        onClick={() => move(index, 1)}>↓</button>
                      <button type="button" className="btn-ghost !px-2 !py-1"
                        aria-label={`Remover corte ${index + 1}`}
                        onClick={() => changeOrder(draft.order.filter((value) => value !== id))}>×</button>
                    </span>
                  </li>
                ))}
              </ol>
              {!draft.order.length && <p className="text-sm text-muted">Adicione pelo menos dois cortes à sequência.</p>}
              <label className="block text-sm">
                Título do compilado
                <input className="input mt-1" maxLength={100} value={draft.title}
                  placeholder="Título do vídeo no YouTube"
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
              </label>
              <CortesGamerToggle checked={draft.cortesGamer} disabled={!picking}
                onChange={(on) => setDraft((before) => ({ ...before, cortesGamer: on }))} />
              {draft.cortesGamer && <CortesGamerSliders value={draft.cortesGamerStyle} disabled={!picking}
                onChange={(style) => setDraft((before) => ({ ...before, cortesGamerStyle: style }))} />}
              <button type="button" className="btn-accent" onClick={() => void compile()}
                disabled={!picking || !draft.title.trim() || draft.order.length < 2 || selected.some((item) => !item)}>
                {busy ? tr("Adicionando à fila…") : 'Gerar compilado'}
              </button>
            </section>
          </div>
          {(job || error || notice) && (
            <section className="card space-y-3">
              {job && <p role="status" className="font-semibold">{statusLabel[job.status]}</p>}
              {job?.status === 'queued' && <button type="button" className="btn-ghost text-sm"
                onClick={() => window.dispatchEvent(new Event('open-queue'))}>{tr("Abrir fila")}</button>}
              {job?.error && <p className="text-sm text-error">{job.error}</p>}
              {error && <p role="alert" className="text-sm text-error">{error}</p>}
              {notice && <p role="status" className="text-sm text-success break-all">{notice}</p>}
              {result && (
                <div className="space-y-3">
                  <p className="text-sm">{result.title} · {duration(result.end_s - result.start_s)}</p>
                  <video className="block w-full max-w-lg rounded bg-black" controls muted preload="metadata"
                    aria-label="Prévia do compilado" src={api.mediaUrl(result.id)} />
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="btn-ghost" onClick={() => void saveFile(result)}>Salvar MP4</button>
                    <button type="button" className="btn-ghost" onClick={() => void openYouTube()}>
                      {tr("Preparar upload no YouTube")}
                    </button>
                    <button type="button" className="btn-ghost" aria-expanded={composioCompilation}
                      onClick={() => setComposioCompilation(!composioCompilation)}>Enviar compilado pelo Composio</button>
                  </div>
                  {composioCompilation && <ComposioPanel key={result.id} clip={result} onlyYouTube
                    onOpenAccounts={() => setTab('accounts')} />}
                  {posting && youtube && <YouTubePanel key={result.id} clip={result} status={youtube}
                    pendingRender={null} duration={result.end_s - result.start_s} currentTime={0}
                    onOpenSettings={() => setTab('accounts')} />}
                  {posting && uploadPost && <UploadPostPanel key={result.id} clip={result} status={uploadPost}
                    provider="uploadpost" onlyPlatform="youtube" otherAvailable={false} onSwitchProvider={() => {}} />}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  )
}
