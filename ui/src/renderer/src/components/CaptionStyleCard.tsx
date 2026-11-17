import { useEffect, useState } from 'react'
import { api, errorText } from '../lib/api'
import type { CaptionStyle } from '../lib/types'
import CaptionStyleControls, { DEFAULT_CAPTION_STYLE } from './CaptionStyleControls'

/** The caption every new clip gets, adjusted on the Mesa like the CG watermark.
 *  The picture is the engine's own burn (libass), so what you see is what posts.
 *  Saving applies to the next clip the engine makes, with no restart. */
export default function CaptionStyleCard(): JSX.Element {
  const [style, setStyle] = useState<Required<CaptionStyle> | null>(null)
  const [saved, setSaved] = useState('')
  const [shown, setShown] = useState<Required<CaptionStyle> | null>(null)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.captionStyle()
      .then((s) => { const full = { ...DEFAULT_CAPTION_STYLE, ...s }; setStyle(full); setSaved(JSON.stringify(full)) })
      .catch(() => setNotice('Estilo da legenda indisponível: recarregue o motor.'))
  }, [])

  useEffect(() => {
    if (!style) return
    // Waits for the slider to settle: one render per pause, not per pixel.
    const timer = setTimeout(() => setShown(style), 250)
    return () => clearTimeout(timer)
  }, [style])

  const save = async (): Promise<void> => {
    if (!style) return
    setBusy(true)
    try {
      const s = { ...DEFAULT_CAPTION_STYLE, ...(await api.saveCaptionStyle(style)) }
      setStyle(s)
      setSaved(JSON.stringify(s))
      setNotice('Salvo. Os próximos cortes já saem com esta legenda.')
    } catch (e) {
      setNotice(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const changed = style !== null && JSON.stringify(style) !== saved
  return (
    <details className="mx-5 mt-2 text-sm">
      <summary className="cursor-pointer">Legenda dos próximos cortes</summary>
      {style && (
        <form className="flex flex-wrap items-start gap-5 py-3" onSubmit={(e) => { e.preventDefault(); void save() }}>
          <div className="grid gap-3 w-full max-w-sm">
            <CaptionStyleControls
              idPrefix="mesa-caption"
              style={style}
              onChange={(key, value) => { setNotice(''); setStyle({ ...style, [key]: value }) }}
              hideSecondSpeaker
              hideExample
            />
            <div className="flex items-center gap-3">
              <button type="submit" className="btn-accent" disabled={busy || !changed}>Salvar legenda</button>
              {changed && (
                <button type="button" className="btn-ghost" disabled={busy}
                  onClick={() => setStyle(JSON.parse(saved) as Required<CaptionStyle>)}>Desfazer</button>
              )}
            </div>
          </div>
          <figure className="grid gap-1">
            {shown
              ? <img src={api.captionPreviewUrl(shown)} alt="Prévia da legenda gravada pelo motor"
                  onError={() => setNotice('Prévia indisponível: recarregue o motor.')}
                  className="w-[360px] max-w-full rounded-lg ring-1 ring-raised" />
              : <div className="w-[360px] aspect-[9/8] rounded-lg bg-raised" />}
            <figcaption className="grid grid-cols-2 text-xs text-muted text-center">
              <span>Tela dividida: na linha</span>
              <span>Sem divisão: posição escolhida</span>
            </figcaption>
          </figure>
        </form>
      )}
      {notice && <p role="status" className="pb-2 text-xs text-muted">{notice}</p>}
    </details>
  )
}
