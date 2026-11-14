import { useCallback, useEffect, useRef, useState } from 'react'
import { t } from '../lib/i18n'
import {
  BLOCO_S,
  DESTINOS,
  FAIXA_CHIP,
  FAIXA_PONTO,
  faixa,
  mesa,
  somaHora,
  type Corte,
  type MesaState
} from '../lib/mesa'

/** The approval desk: one cut at a time, best score first. Approving or
 *  discarding moves its files (server/mesa_api.py); A, X, E and the arrows
 *  do the same from the keyboard, except while typing. */

interface Props {
  target: string | null
  onTargetConsumed: () => void
  onOpenInStudio: (videoId: string, clipId?: number) => void
}

interface Rascunho {
  titulo: string
  descricao: string
  hashtags: string[]
  destinos: string[]
}

const rascunhoDe = (c: Corte): Rascunho => ({
  titulo: c.titulo ?? '',
  descricao: c.descricao ?? '',
  hashtags: c.hashtags ?? [],
  destinos: c.destinos ?? DESTINOS.map((d) => d.id)
})

const mmss = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

function digitando(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null
  return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))
}

/** A cut's thumbnail that is only asked for while it is in (or near) the visible
 *  part of the list, and dropped from the page once it scrolls away. The image
 *  stays in the browser's cache (and the engine's), so coming back is instant. */
function Capa({ nome, lista }: { nome: string; lista: HTMLElement | null }): JSX.Element {
  const caixa = useRef<HTMLSpanElement>(null)
  const [visivel, setVisivel] = useState(false)
  const [falhou, setFalhou] = useState(false)
  useEffect(() => {
    const el = caixa.current
    if (!el || !lista) return
    const io = new IntersectionObserver(([e]) => setVisivel(e.isIntersecting), {
      root: lista,
      rootMargin: '300px 0px'
    })
    io.observe(el)
    return () => io.disconnect()
  }, [lista])
  return (
    <span ref={caixa} className="shrink-0 w-[34px] h-[60px] rounded-md bg-raised overflow-hidden">
      {visivel && !falhou && (
        <img
          src={mesa.capaUrl(nome)}
          alt=""
          decoding="async"
          className="size-full object-cover"
          onError={() => setFalhou(true)}
        />
      )}
    </span>
  )
}

function Kbd({ k, escuro }: { k: string; escuro?: boolean }): JSX.Element {
  return (
    <kbd className={`px-1.5 rounded text-[11px] font-normal ${escuro ? 'bg-black/20' : 'bg-raised text-muted'}`}>{k}</kbd>
  )
}

export default function Mesa({ target, onTargetConsumed, onOpenInStudio }: Props): JSX.Element {
  const [estado, setEstado] = useState<MesaState | null>(null)
  const [erro, setErro] = useState('')
  const [nome, setNome] = useState<string | null>(null)
  const [rascunho, setRascunho] = useState<Rascunho | null>(null)
  const [sujo, setSujo] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [novaTag, setNovaTag] = useState('')
  const video = useRef<HTMLVideoElement>(null)
  const [lista, setLista] = useState<HTMLDivElement | null>(null)

  const carregar = useCallback(() => {
    mesa
      .cortes()
      .then((s) => setEstado(s))
      .catch((e: Error) => setErro(e.message))
  }, [])
  useEffect(() => {
    carregar()
    const id = setInterval(carregar, 30000)
    return () => clearInterval(id)
  }, [carregar])

  const cortes = estado?.enabled ? estado.cortes : []
  const idx = Math.max(0, cortes.findIndex((c) => c.nome === nome))
  const atual: Corte | undefined = cortes[idx]

  // The control room opens the desk on one cut.
  useEffect(() => {
    if (!target || !estado) return
    if (cortes.some((c) => c.nome === target)) setNome(target)
    onTargetConsumed()
  }, [target, estado]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setRascunho(atual ? rascunhoDe(atual) : null)
    setSujo(false)
    setNovaTag('')
    // Keep the chosen cut in view, and the keyboard focus with it when it was in the list.
    const item = atual ? document.querySelector<HTMLElement>(`[data-corte="${CSS.escape(atual.nome)}"]`) : null
    item?.scrollIntoView({ block: 'nearest' })
    if (document.activeElement?.hasAttribute('data-corte')) item?.focus()
  }, [atual?.nome]) // eslint-disable-line react-hooks/exhaustive-deps

  const salvar = async (r: Rascunho | null = rascunho, forcar = false): Promise<void> => {
    if (!atual || !r || (!sujo && !forcar)) return
    try {
      await mesa.editar(atual.nome, r)
      setSujo(false)
    } catch (e) {
      setErro((e as Error).message)
    }
  }

  const mudar = (patch: Partial<Rascunho>, agora = false): void => {
    if (!rascunho) return
    const r = { ...rascunho, ...patch }
    setRascunho(r)
    setSujo(true)
    if (agora) void salvar(r, true)
  }

  const decidir = async (como: 'aprovar' | 'descartar'): Promise<void> => {
    if (!atual || !rascunho || ocupado) return
    setOcupado(true)
    setErro('')
    // Windows can't move a file the player is still reading.
    const v = video.current
    if (v) {
      v.pause()
      v.removeAttribute('src')
      v.load()
    }
    try {
      if (como === 'aprovar') await mesa.aprovar(atual.nome, rascunho)
      else await mesa.descartar(atual.nome)
      setNome((cortes[idx + 1] ?? cortes[idx - 1])?.nome ?? null)
      setEstado((s) => (s?.enabled ? { ...s, cortes: s.cortes.filter((c) => c.nome !== atual.nome) } : s))
      carregar()
    } catch (e) {
      setErro((e as Error).message)
      if (v) v.src = mesa.videoUrl(atual.nome)
    } finally {
      setOcupado(false)
    }
  }

  const abrirEditor = (): void => {
    if (atual?.no_editor && atual.video_id) onOpenInStudio(atual.video_id, atual.clip_id ?? undefined)
  }

  // Bound on every render so the keys always act on the cut on screen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (digitando(e) || e.ctrlKey || e.metaKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (k === 'a') void decidir('aprovar')
      else if (k === 'x') void decidir('descartar')
      else if (k === 'e') abrirEditor()
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const prox = cortes[idx + (e.key === 'ArrowDown' ? 1 : -1)]
        if (prox) {
          e.preventDefault()
          setNome(prox.nome)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const addTag = (): void => {
    const tag = novaTag.trim().replace(/\s+/g, '')
    if (!tag || !rascunho) return
    const comHash = tag.startsWith('#') ? tag : `#${tag}`
    if (!rascunho.hashtags.includes(comHash)) mudar({ hashtags: [...rascunho.hashtags, comHash] }, true)
    setNovaTag('')
  }

  if (!estado) {
    return <div className="p-8 text-muted">{erro || t('Loading…')}</div>
  }
  if (!estado.enabled) {
    return (
      <div className="p-8 max-w-xl text-muted">
        {t('The approval desk is off. Set mesa.dir in settings.yaml to the folder with the cuts.')}
      </div>
    )
  }

  const { contagens } = estado
  const revisados = contagens.aprovados_hoje + contagens.descartados_hoje
  const total = revisados + contagens.pendentes
  const marcas = atual?.live
    ? cortes.filter((c) => c.streamer === atual.streamer && c.live?.bloco === atual.live?.bloco)
    : []

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <header className="flex flex-wrap items-center gap-5 px-5 py-3 border-b border-raised">
        <h2 className="text-lg font-bold">{t('Approval desk')}</h2>
        <div className="flex flex-1 items-center justify-end gap-3 min-w-[260px]">
          <span className="text-muted whitespace-nowrap">
            <span className="text-ink font-semibold">{revisados}</span> / {total} {t('reviewed today')}
          </span>
          <span className="relative h-1.5 w-44 rounded bg-raised overflow-hidden">
            <span
              className="absolute inset-y-0 left-0 bg-accent"
              style={{ width: `${total ? (100 * revisados) / total : 0}%` }}
            />
          </span>
          <span className="px-2.5 py-1 rounded-full bg-raised text-xs whitespace-nowrap">
            <span className="text-success font-semibold">{contagens.aprovados_hoje}</span> {t('approved today')} ·{' '}
            <span className="text-error font-semibold">{contagens.descartados_hoje}</span> {t('discarded today')}
          </span>
        </div>
      </header>

      {erro && <p className="mx-5 mt-3 px-3 py-2 rounded-lg bg-error/15 text-error text-sm">{erro}</p>}

      {!atual ? (
        <div className="flex-1 grid place-items-center text-muted text-lg">{t('Clean desk: no cut waiting.')}</div>
      ) : (
        <>
          <div className="flex flex-1 min-h-0">
            <section aria-label={t('On the desk')} className="w-80 shrink-0 flex flex-col border-r border-raised min-h-0">
              <div className="flex items-baseline justify-between px-5 pt-4 pb-2">
                <h3 className="font-bold">{t('On the desk')}</h3>
                <span className="text-xs text-muted">{t('best score first')}</span>
              </div>
              <div ref={setLista} className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
                {cortes.map((c) => {
                  const sel = c.nome === atual.nome
                  return (
                    <button
                      key={c.nome}
                      data-corte={c.nome}
                      type="button"
                      onClick={() => setNome(c.nome)}
                      aria-current={sel}
                      className={`w-full flex gap-3 items-center p-2 rounded-lg border text-left transition-colors ${
                        sel ? 'border-accent bg-raised' : 'border-transparent hover:bg-raised/60'
                      }`}
                    >
                      <Capa nome={c.nome} lista={lista} />
                      <span className="min-w-0 flex flex-col gap-1">
                        <span className="text-xs font-semibold leading-snug line-clamp-2">{c.titulo || c.nome}</span>
                        <span className="flex items-center gap-1.5 text-[11px] text-muted">
                          <span className={`rounded px-1 font-bold ${FAIXA_CHIP[faixa(c.nota)]}`}>{c.nota ?? '–'}</span>
                          {c.streamer}
                          {c.live && ` · ${c.live.fim_s - c.live.inicio_s} s`}
                        </span>
                      </span>
                    </button>
                  )
                })}
              </div>
            </section>

            <section className="flex-1 min-w-0 flex flex-col items-center gap-3 p-5 overflow-y-auto">
              <p className="text-muted text-center">
                <span className="text-ink font-semibold">{atual.streamer}</span> · {atual.plataforma}
                {atual.live &&
                  ` · ${mmss(atual.live.inicio_s)}–${mmss(atual.live.fim_s)} ${t('of the block at')} ${atual.live.bloco}`}
              </p>
              <video
                key={atual.nome}
                ref={video}
                src={mesa.videoUrl(atual.nome)}
                poster={mesa.capaUrl(atual.nome)}
                controls
                autoPlay
                loop
                playsInline
                className="h-[min(560px,calc(100vh-290px))] min-h-[320px] aspect-[9/16] rounded-2xl bg-black border border-raised"
              />
              {atual.live && (
                <div className="w-full max-w-xl flex flex-col gap-1.5">
                  <div className="flex justify-between text-[11px] text-muted">
                    <span>{atual.live.bloco}</span>
                    <span>{t('Where it came from in the live')}</span>
                    <span>{somaHora(atual.live.bloco, BLOCO_S)}</span>
                  </div>
                  <div className="relative h-[18px] rounded-md bg-raised">
                    {marcas.map((c) => (
                      <button
                        key={c.nome}
                        type="button"
                        aria-label={c.titulo ?? c.nome}
                        onClick={() => setNome(c.nome)}
                        className="absolute top-1 bottom-1 min-w-[3px] rounded-sm"
                        style={{
                          left: `${(100 * (c.live?.inicio_s ?? 0)) / BLOCO_S}%`,
                          width: `${(100 * ((c.live?.fim_s ?? 0) - (c.live?.inicio_s ?? 0))) / BLOCO_S}%`,
                          background: c.nome === atual.nome ? 'var(--color-accent)' : FAIXA_PONTO[faixa(c.nota)],
                          opacity: c.nome === atual.nome ? 1 : 0.55
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </section>

            {rascunho && (
              <aside className="w-96 shrink-0 flex flex-col gap-4 p-5 border-l border-raised overflow-y-auto">
                <div className="flex items-center gap-3.5 p-3.5 rounded-xl bg-surface border border-raised">
                  <span
                    className="text-4xl font-bold leading-none"
                    style={{ color: FAIXA_PONTO[faixa(atual.nota)] }}
                  >
                    {atual.nota ?? '–'}
                  </span>
                  <span className="flex flex-col gap-0.5">
                    <span className="font-semibold">{t('AI score')}</span>
                    <span className="text-xs text-muted">{t('0 to 100 · the higher, the more viral')}</span>
                  </span>
                </div>
                <label className="flex flex-col gap-1.5">
                  <span className="label">{t('Title')}</span>
                  <input
                    className="input"
                    value={rascunho.titulo}
                    onChange={(e) => mudar({ titulo: e.target.value })}
                    onBlur={() => void salvar()}
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="label">{t('Description')}</span>
                  <textarea
                    className="input resize-y"
                    rows={4}
                    value={rascunho.descricao}
                    onChange={(e) => mudar({ descricao: e.target.value })}
                    onBlur={() => void salvar()}
                  />
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {rascunho.hashtags.map((h) => (
                    <span key={h} className="flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-full bg-raised text-xs">
                      {h}
                      <button
                        type="button"
                        aria-label={`${t('Remove')} ${h}`}
                        className="text-muted hover:text-ink"
                        onClick={() => mudar({ hashtags: rascunho.hashtags.filter((x) => x !== h) }, true)}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <input
                    className="w-28 px-2.5 py-1 rounded-full border border-dashed border-muted/50 bg-transparent text-xs outline-none focus:border-accent"
                    placeholder="+ hashtag"
                    value={novaTag}
                    onChange={(e) => setNovaTag(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') addTag()
                    }}
                    onBlur={addTag}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <span className="label">{t('Where to post')}</span>
                  {DESTINOS.map((d) => {
                    const on = rascunho.destinos.includes(d.id)
                    return (
                      <div
                        key={d.id}
                        className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface border border-raised"
                      >
                        <span className="font-medium">{d.label}</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={on}
                          aria-label={d.label}
                          onClick={() =>
                            mudar(
                              {
                                destinos: on
                                  ? rascunho.destinos.filter((x) => x !== d.id)
                                  : [...rascunho.destinos, d.id]
                              },
                              true
                            )
                          }
                          className={`relative w-[38px] h-[22px] rounded-full transition-colors ${on ? 'bg-accent' : 'bg-raised'}`}
                        >
                          <span
                            className="absolute top-[3px] size-4 rounded-full bg-ink transition-all"
                            style={{ left: on ? 19 : 3 }}
                          />
                        </button>
                      </div>
                    )
                  })}
                </div>
              </aside>
            )}
          </div>

          <footer className="flex flex-wrap justify-center items-center gap-3 px-5 py-3.5 border-t border-raised bg-surface">
            <button
              type="button"
              disabled={ocupado}
              onClick={() => void decidir('descartar')}
              className="h-12 px-5 rounded-xl border border-error text-[#fca5a5] font-semibold flex items-center gap-2.5 hover:bg-error/10 disabled:opacity-40"
            >
              {t('Discard')} <Kbd k="X" />
            </button>
            <button
              type="button"
              disabled={!atual.no_editor}
              title={atual.no_editor ? undefined : t('This cut is no longer in Clips Kitty')}
              onClick={abrirEditor}
              className="h-12 px-5 rounded-xl border border-muted/40 font-semibold flex items-center gap-2.5 hover:bg-raised disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {t('Adjust in the editor')} <Kbd k="E" />
            </button>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => void decidir('aprovar')}
              className="h-12 px-7 rounded-xl bg-accent text-on-accent font-bold flex items-center gap-2.5 hover:bg-accent-strong disabled:opacity-40"
            >
              {t('Approve')} <Kbd k="A" escuro />
            </button>
          </footer>
        </>
      )}
    </div>
  )
}
