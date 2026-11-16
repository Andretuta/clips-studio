// Runs only in the development host with --verificar.
document.addEventListener('DOMContentLoaded', async () => {
  const report = {}
  let preview
  const timer = setTimeout(() => finish(false, 'timeout'), 20000)

  function finish(ok, reason) {
    clearTimeout(timer)
    if (reason) report.error = reason
    if (preview) {
      preview.pause()
      preview.removeAttribute('src')
      preview.load()
      preview.remove()
    }
    document.title = `clipador-verificar:${ok ? 'ok' : 'erro'} ${JSON.stringify(report)}`
  }

  try {
    const api = 'http://127.0.0.1:8765'
    const health = await fetch(`${api}/health`)
    report.engine = health.ok && (await health.json()).ok
    const { contagens, cortes } = await (await fetch(`${api}/mesa/cortes`)).json()
    report.pendentes = contagens.pendentes
    report.react = Boolean(document.querySelector('#root')?.children.length)
    const first = cortes[0]
    if (!first) return finish(false, 'mesa_vazia')

    preview = document.createElement('video')
    preview.muted = true
    preview.playsInline = true
    preview.style.position = 'fixed'
    preview.style.width = '240px'
    preview.style.bottom = '0'
    preview.style.right = '0'
    document.body.appendChild(preview)
    preview.src = `${api}/mesa/cortes/${encodeURIComponent(first.nome)}/video`
    await preview.play()
    preview.requestVideoFrameCallback(() => {
      report.react = Boolean(document.querySelector('#root')?.children.length)
      report.width = preview.videoWidth
      report.muted = preview.muted
      finish(Boolean(report.engine && report.react && report.width > 0 && report.muted))
    })
  } catch (error) {
    finish(false, error.name)
  }
}, { once: true })
