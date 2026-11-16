import { t as tr } from "./i18n"
import { API_BASE, responseErrorText } from './api'
import type { CortesGamerStyle } from './types'
import { sessionSecret } from './plugins'

/** The approval desk and control room: the engine's /mesa routes
 *  (server/mesa_api.py) over the folder another program leaves cuts in.
 *  Approving or discarding moves files, so those calls take the desktop
 *  app's session secret, like the campaign routes. */

export interface PosicaoLive {
  /** "18:25": when the block of the live this cut came from started. */
  bloco: string
  inicio_s: number
  fim_s: number
}

export interface Corte {
  nome: string
  streamer: string | null
  plataforma: string | null
  fonte: string | null
  titulo: string | null
  descricao: string | null
  hashtags: string[] | null
  nota: number | null
  clip_id: number | null
  video_id: string | null
  criado_em: string | null
  destinos: string[] | null
  cortes_gamer_watermark: boolean | null
  cortes_gamer_baked: boolean | null
  cortes_gamer_style: CortesGamerStyle | null
  /** Whether the clip is still in Clips Kitty, so the editor can open it. */
  no_editor: boolean
  /** Null for cuts that didn't come from a recorded live. */
  live: PosicaoLive | null
}

export interface Contagens {
  pendentes: number
  aprovados_hoje: number
  descartados_hoje: number
  aprovados: number
}

export type MesaState = { enabled: false } | { enabled: true; cortes: Corte[]; contagens: Contagens }

export interface Canal {
  nome: string
  plataforma: string
  canal: string
  gravando: boolean
  /** Seconds since the newest segment; null when there is none. */
  ultimo_s: number | null
}

export interface CorteNaLive {
  nome: string
  inicio_s: number
  fim_s: number
  nota: number | null
  estado: 'pendente' | 'aprovado' | 'descartado'
}

export interface Live {
  streamer: string
  plataforma: string | null
  blocos: { inicio: string; cortes: CorteNaLive[] }[]
}

export type ControleState =
  | { enabled: false }
  | { enabled: true; canais: Canal[]; lives: Live[]; melhores: Corte[]; contagens: Contagens }

export interface Edicao {
  titulo?: string
  descricao?: string
  hashtags?: string[]
  destinos?: string[]
  cortes_gamer_watermark?: boolean
  cortes_gamer_style?: CortesGamerStyle
}

// ponytail: the recorder's block length (16 min); read it from the engine if it ever changes.
export const BLOCO_S = 960

export const DESTINOS = [
  { id: 'tiktok', label: 'TikTok' },
  { id: 'shorts', label: 'YouTube Shorts' },
  { id: 'reels', label: 'Instagram Reels' }
]

/** The score's colour band: 70+ green, 60–69 yellow, below grey. */
export function faixa(nota: number | null): 'alta' | 'media' | 'baixa' {
  return (nota ?? 0) >= 70 ? 'alta' : (nota ?? 0) >= 60 ? 'media' : 'baixa'
}

export const FAIXA_CHIP = {
  alta: 'bg-[#14361f] text-[#6ee7a0]',
  media: 'bg-[#3a2c05] text-[#fcd34d]',
  baixa: 'bg-raised text-muted'
}

export const FAIXA_PONTO = { alta: '#6ee7a0', media: '#fcd34d', baixa: '#8e8c86' }

/** "18:25" plus seconds, as "18:41". */
export function somaHora(hhmm: string, segundos: number): string {
  const [h, m] = hhmm.split(':').map(Number)
  const total = Math.floor((h * 3600 + m * 60 + segundos) / 60) % (24 * 60)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

async function call<T>(path: string, init: RequestInit = {}, guarded = false): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (guarded) {
    const s = await sessionSecret()
    if (!s) throw new Error(tr("Approving and discarding cuts needs the Clips Kitty desktop app."))
    headers['X-Clips-Kitty-Session'] = s
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(responseErrorText(text, res.status))
  }
  return res.json() as Promise<T>
}

const corte = (nome: string): string => `/mesa/cortes/${encodeURIComponent(nome)}`
const send = (method: string, body?: unknown): RequestInit =>
  body === undefined ? { method } : { method, body: JSON.stringify(body) }

export const mesa = {
  cortes: () => call<MesaState>('/mesa/cortes'),
  controle: () => call<ControleState>('/mesa/controle'),
  videoUrl: (nome: string) => `${API_BASE}${corte(nome)}/video`,
  /** A small JPEG of the cut (made once by the engine, cached a week by the browser). */
  capaUrl: (nome: string) => `${API_BASE}${corte(nome)}/capa`,
  editar: (nome: string, e: Edicao) => call<Corte>(corte(nome), send('PATCH', e), true),
  aprovar: (nome: string, e: Edicao) => call<{ nome: string }>(`${corte(nome)}/aprovar`, send('POST', e), true),
  descartar: (nome: string) => call<{ nome: string }>(`${corte(nome)}/descartar`, send('POST'), true)
}
