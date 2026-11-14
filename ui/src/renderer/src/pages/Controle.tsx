import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { t } from '../lib/i18n'
import { BLOCO_S, FAIXA_CHIP, FAIXA_PONTO, faixa, mesa, type ControleState } from '../lib/mesa'
import { formatQueueEta } from '../lib/queue'
import type { QueueSnapshot } from '../lib/types'

/** The control room: what is recording, the Clips Kitty queue, today's lives
 *  with each cut where it came from, and the best cuts still on the desk. */

interface Props {
  onOpenMesa: (nome?: string) => void
  onOpenQueue: () => void
}

const minutos = (hhmm: string): number => {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}
const hora = (min: number): string =>
  `${String(Math.floor(min / 60) % 24).padStart(2, '0')}:${String(Math.round(min) % 60).padStart(2, '0')}`

interface Aviso {
  tom: 'ok' | 'warn' | 'erro'
  titulo: string
  texto: string
  abrir?: () => void
}

const TOM = {
  ok: { bg: 'bg-success/10', dot: 'bg-success' },
  warn: { bg: 'bg-warn/10', dot: 'bg-warn' },
  erro: { bg: 'bg-error/10', dot: 'bg-error' }
}

export default function Controle({ onOpenMesa, onOpenQueue }: Props): JSX.Element {
  const [estado, setEstado] = useState<ControleState | null>(null)
  const [fila, setFila] = useState<QueueSnapshot | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    const ler = (): void => {
      mesa
        .controle()
        .then((s) => {
          setEstado(s)
          setErro('')
        })
        .catch((e: Error) => setErro(e.message))
      api
        .queue()
        .then(setFila)
        .catch(() => setFila(null))
    }
    ler()
    const id = setInterval(ler, 15000)
    return () => clearInterval(id)
  }, [])

  if (!estado) return <div className="p-8 text-muted">{erro || t('Loading…')}</div>
  if (!estado.enabled) {
    return (
      <div className="p-8 max-w-xl text-muted">
        {t('The approval desk is off. Set mesa.dir in settings.yaml to the folder with the cuts.')}
      </div>
    )
  }

  const { canais, lives, melhores, contagens } = estado
  const gravando = canais.filter((c) => c.gravando)
  const processando = fila?.processing ?? []
  const filaSeg = fila
    ? fila.estimate.queued_seconds + (processando.length ? fila.estimate.per_video_seconds : 0)
    : 0

  const etapas = [
    {
      nome: t('Recording'),
      grande: gravando.length,
      pequeno: gravando.map((c) => c.canal).join(', ') || t('no channel recording'),
      dot: 'bg-error animate-pulse'
    },
    { nome: t('Waiting'), grande: fila?.queued.length ?? 0, pequeno: t('in the Clips Kitty queue'), dot: 'bg-muted' },
    {
      nome: t('Processing'),
      grande: processando.length,
      pequeno: processando[0]?.display_title || '—',
      dot: 'bg-accent'
    },
    { nome: t('On the desk'), grande: contagens.pendentes, pequeno: t('waiting for you'), dot: 'bg-accent' },
    {
      nome: t('Approved cuts'),
      grande: contagens.aprovados,
      pequeno: `+${contagens.aprovados_hoje} ${t('today')}`,
      dot: 'bg-success'
    }
  ]

  // One time axis for every lane: from the first block to the last one, or now while recording.
  const agora = new Date()
  const agoraMin = agora.getHours() * 60 + agora.getMinutes()
  const inicios = lives.flatMap((lv) => lv.blocos.map((b) => minutos(b.inicio)))
  let eixoIni = 0
  let eixoFim = 0
  if (inicios.length) {
    eixoIni = Math.floor(Math.min(...inicios) / 15) * 15
    eixoFim = Math.max(...inicios) + BLOCO_S / 60
    if (gravando.length) eixoFim = Math.max(eixoFim, agoraMin)
    eixoFim = Math.ceil(eixoFim / 15) * 15
  }
  const span = Math.max(eixoFim - eixoIni, 15)
  const passo = span > 360 ? 60 : span > 180 ? 30 : 15
  const marcas: number[] = []
  for (let m = eixoIni; m <= eixoFim; m += passo) marcas.push(m)
  const pos = (min: number): string => `${(100 * (min - eixoIni)) / span}%`

  const avisos: Aviso[] = []
  for (const c of canais) {
    if (!c.gravando && c.ultimo_s !== null && c.ultimo_s < 3 * 3600) {
      avisos.push({
        tom: 'warn',
        titulo: `${c.canal} ${t('stopped recording')}`,
        texto: `${t('no new segment for')} ${Math.round(c.ultimo_s / 60)} min`
      })
    }
  }
  if (fila?.failed.length) {
    avisos.push({
      tom: 'erro',
      titulo: `${fila.failed.length} ${t('videos failed in Clips Kitty')}`,
      texto: t('see the Queue'),
      abrir: onOpenQueue
    })
  }
  if (filaSeg > 30 * 60) {
    avisos.push({ tom: 'warn', titulo: t('The queue is over 30 min behind'), texto: t('Pause one of the lives.') })
  }
  if (!avisos.length) {
    avisos.push({ tom: 'ok', titulo: t('All working'), texto: `${gravando.length} ${t('channels recording')}` })
  }

  return (
    <div className="flex-1 flex flex-col gap-5 p-5 min-h-0">
      <header className="flex items-baseline gap-4">
        <h2 className="text-lg font-bold">{t('Control room')}</h2>
        {erro && <span className="text-error text-sm">{erro}</span>}
      </header>

      <section className="grid gap-2.5 grid-cols-[repeat(auto-fit,minmax(170px,1fr))]">
        {etapas.map((e) => (
          <div key={e.nome} className="flex flex-col gap-1.5 px-4 py-3.5 rounded-xl bg-surface border border-raised">
            <span className="flex items-center gap-2 text-xs font-semibold text-muted">
              <span className={`size-2 rounded-full ${e.dot}`} />
              {e.nome}
            </span>
            <span className="text-2xl font-bold leading-tight">{e.grande}</span>
            <span className="text-xs text-muted truncate">{e.pequeno}</span>
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-3.5 px-5 py-4 rounded-2xl bg-surface border border-raised">
        <div className="flex flex-wrap items-baseline gap-4">
          <h3 className="text-base font-bold">{t("Today's lives")}</h3>
          <span className="text-xs text-muted">{t('each dot is a cut, where it came from in the live')}</span>
          <span className="flex-1" />
          <span className="flex gap-3.5 text-xs text-muted">
            {(
              [
                ['alta', t('score 70+')],
                ['media', '60–69'],
                ['baixa', t('below 60')]
              ] as const
            ).map(([f, rotulo]) => (
              <span key={f} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: FAIXA_PONTO[f] }} />
                {rotulo}
              </span>
            ))}
          </span>
        </div>

        {!lives.length ? (
          <p className="text-muted py-4">{t('No live recorded today yet.')}</p>
        ) : (
          <>
            <div className="flex">
              <div className="w-36 shrink-0" />
              <div className="flex-1 relative h-4 text-[11px] text-muted">
                {marcas.map((m) => (
                  <span key={m} className="absolute -translate-x-1/2 tabular-nums" style={{ left: pos(m) }}>
                    {hora(m)}
                  </span>
                ))}
              </div>
            </div>
            {lives.map((lv) => {
              const aoVivo = gravando.some((c) => c.canal.toLowerCase() === lv.streamer.toLowerCase())
              return (
                <div key={lv.streamer} className="flex items-center">
                  <div className="w-36 shrink-0 flex flex-col gap-0.5">
                    <span className="font-semibold">{lv.streamer}</span>
                    <span className="text-[11px] text-muted font-semibold">
                      {lv.plataforma}
                      {aoVivo && <span className="ml-1.5 text-error">● {t('recording now')}</span>}
                    </span>
                  </div>
                  <div className="flex-1 relative h-[68px]">
                    {aoVivo && eixoFim > eixoIni && (
                      <span className="absolute inset-y-0 w-px bg-error/60" style={{ left: pos(agoraMin) }} />
                    )}
                    {lv.blocos.map((b) => {
                      const ini = minutos(b.inicio)
                      return (
                        <div key={b.inicio}>
                          <div
                            className="absolute inset-y-0 rounded-lg border border-raised bg-raised/50 px-2 py-1 text-[11px] font-semibold text-muted overflow-hidden whitespace-nowrap"
                            style={{ left: pos(ini), width: `calc(${(100 * (BLOCO_S / 60)) / span}% - 4px)` }}
                          >
                            {b.inicio} · {b.cortes.length}
                          </div>
                          {b.cortes.map((c) => {
                            const f = faixa(c.nota)
                            const tam = f === 'alta' ? 13 : 9
                            return (
                              <button
                                key={c.nome}
                                type="button"
                                title={`${c.nota ?? '–'} · ${c.estado}`}
                                disabled={c.estado !== 'pendente'}
                                onClick={() => onOpenMesa(c.nome)}
                                className={`absolute top-[42px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface ${
                                  c.estado === 'aprovado' ? 'ring-2 ring-accent' : ''
                                } ${c.estado === 'descartado' ? 'opacity-30' : ''}`}
                                style={{
                                  left: pos(ini + (c.inicio_s + c.fim_s) / 120),
                                  width: tam,
                                  height: tam,
                                  background: FAIXA_PONTO[f]
                                }}
                              />
                            )
                          })}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </>
        )}
      </section>

      <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(300px,1fr))]">
        <section className="flex flex-col gap-3 px-5 py-4 rounded-2xl bg-surface border border-raised">
          <h3 className="text-base font-bold">{t('Queue breath')}</h3>
          <span className={`text-3xl font-bold ${filaSeg > 30 * 60 ? 'text-warn' : ''}`}>
            {filaSeg > 0 ? formatQueueEta(filaSeg) : '0'}
          </span>
          <p className="text-muted">
            {t('to clear the Clips Kitty queue')} · {fila?.queued.length ?? 0} {t('waiting')} · {processando.length}{' '}
            {t('processing')}
          </p>
          <p className="text-xs text-muted">{t('Over 30 min behind? Pause one of the lives.')}</p>
        </section>

        <section className="flex flex-col gap-2.5 px-5 py-4 rounded-2xl bg-surface border border-raised">
          <h3 className="text-base font-bold">{t('Alerts')}</h3>
          {avisos.map((a) => (
            <button
              key={a.titulo}
              type="button"
              disabled={!a.abrir}
              onClick={a.abrir}
              className={`flex gap-2.5 items-start px-3 py-2.5 rounded-lg text-left ${TOM[a.tom].bg} disabled:cursor-default`}
            >
              <span className={`shrink-0 mt-1.5 size-2 rounded-full ${TOM[a.tom].dot}`} />
              <span className="flex flex-col gap-0.5">
                <span className="font-semibold">{a.titulo}</span>
                <span className="text-xs text-muted">{a.texto}</span>
              </span>
            </button>
          ))}
        </section>

        <section className="flex flex-col gap-2.5 px-5 py-4 rounded-2xl bg-surface border border-raised">
          <div className="flex items-baseline justify-between">
            <h3 className="text-base font-bold">{t('Best of the lives')}</h3>
            <button type="button" className="text-xs font-semibold text-accent" onClick={() => onOpenMesa()}>
              {t('Open the desk')}
            </button>
          </div>
          {melhores.map((c) => (
            <button
              key={c.nome}
              type="button"
              onClick={() => onOpenMesa(c.nome)}
              className="flex items-center gap-3 py-2 border-b border-raised text-left hover:bg-raised/40"
            >
              <span className={`shrink-0 w-9 h-7 rounded-md grid place-items-center font-bold ${FAIXA_CHIP[faixa(c.nota)]}`}>
                {c.nota ?? '–'}
              </span>
              <span className="min-w-0 flex flex-col">
                <span className="font-semibold truncate">{c.titulo || c.nome}</span>
                <span className="text-[11px] text-muted">{c.streamer}</span>
              </span>
            </button>
          ))}
        </section>
      </div>
    </div>
  )
}
