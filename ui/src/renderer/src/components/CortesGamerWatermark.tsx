import { useEffect, useState, type RefObject } from 'react'
import { API_BASE } from '../lib/api'
import type { CortesGamerStyle } from '../lib/types'

export const DEFAULT_CORTES_GAMER_STYLE: CortesGamerStyle = { size: 22.5, opacity: 90 }
const DWELL = 3.4
// Matches video_editor/cortes_gamer.py. Positions are relative to the picture, not the player.
const ROUTE = [[0.14, 0.16], [0.78, 0.77], [0.60, 0.29], [0.33, 0.67]] as const
const PORTRAIT_Y = [0.41, 0.58, 0.45, 0.54] as const
const ACTIVE_Y = [0.20, 0.86, 0.37, 0.94] as const

export function CortesGamerSliders({ value, onChange, disabled }: {
  value: CortesGamerStyle
  onChange: (value: CortesGamerStyle) => void
  disabled?: boolean
}): JSX.Element {
  return (
    <div className="grid gap-2 w-full max-w-sm">
      <label className="grid grid-cols-[5rem_1fr_3.5rem] items-center gap-2 text-xs">
        Tamanho
        <input type="range" min={10} max={40} step={0.5} value={value.size} disabled={disabled}
          className="min-w-0 accent-[#38BDF8]"
          onChange={(e) => onChange({ ...value, size: e.currentTarget.valueAsNumber })} />
        <span className="text-right tabular-nums">{value.size.toLocaleString('pt-BR')}%</span>
      </label>
      <label className="grid grid-cols-[5rem_1fr_3.5rem] items-center gap-2 text-xs">
        Opacidade
        <input type="range" min={0} max={100} value={value.opacity} disabled={disabled}
          className="min-w-0 accent-[#38BDF8]"
          onChange={(e) => onChange({ ...value, opacity: e.currentTarget.valueAsNumber })} />
        <span className="text-right tabular-nums">{value.opacity}%</span>
      </label>
    </div>
  )
}

export function CortesGamerToggle({ checked, onChange, disabled }: {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}): JSX.Element {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" className="size-4 accent-[#38BDF8]" checked={checked}
        disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      Marca d’água Cortes Gamer
    </label>
  )
}

export function CortesGamerOverlay({ videoRef, style }: {
  videoRef: RefObject<HTMLVideoElement>
  style: CortesGamerStyle
}): JSX.Element | null {
  const [frame, setFrame] = useState({ w: 0, h: 0, x: 0, y: 0 })
  const [point, setPoint] = useState(0)
  const [band, setBand] = useState<[number, number] | null>(null)
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const size = (): void => {
      if (!video.videoWidth || !video.videoHeight) {
        setFrame({ w: 0, h: 0, x: 0, y: 0 })
        return
      }
      const scale = Math.min(video.clientWidth / video.videoWidth, video.clientHeight / video.videoHeight)
      const w = video.videoWidth * scale
      const h = video.videoHeight * scale
      setFrame({ w, h, x: (video.clientWidth - w) / 2, y: (video.clientHeight - h) / 2 })
    }
    const update = (): void => setPoint(Math.floor(video.currentTime / DWELL) % ROUTE.length)
    const observer = new ResizeObserver(size)
    observer.observe(video)
    const request = new AbortController()
    if (video.src) {
      fetch(video.src + '/picture', { signal: request.signal })
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          const bounds = data?.band
          if (Array.isArray(bounds) && bounds.length === 2) setBand([bounds[0], bounds[1]])
        })
        .catch(() => { /* The centre strip is safe when the picture can't be measured. */ })
    }
    video.addEventListener('loadedmetadata', size)
    video.addEventListener('emptied', size)
    video.addEventListener('timeupdate', update)
    video.addEventListener('seeked', update)
    size()
    update()
    return () => {
      request.abort()
      observer.disconnect()
      video.removeEventListener('loadedmetadata', size)
      video.removeEventListener('emptied', size)
      video.removeEventListener('timeupdate', update)
      video.removeEventListener('seeked', update)
    }
  }, [videoRef])

  if (!frame.w || !frame.h || !style.opacity) return null
  const width = Math.min(frame.w, frame.h) * style.size / 100
  const height = width * 227 / 440
  const [x, landscapeY] = ROUTE[point]
  const y = band
    ? band[0] * frame.h + ((band[1] - band[0]) * frame.h - height) * ACTIVE_Y[point]
    : (frame.h - height) * (frame.h > frame.w ? PORTRAIT_Y[point] : landscapeY)
  return (
    <div className="absolute z-10 pointer-events-none overflow-hidden"
      style={{ left: frame.x, top: frame.y, width: frame.w, height: frame.h }}>
      <img
        src={API_BASE + '/branding/cortes-gamer.png'}
        alt="@CortesGameroffc"
        draggable={false}
        className="absolute"
        style={{ width, opacity: style.opacity / 100, left: (frame.w - width) * x, top: y }}
      />
    </div>
  )
}
