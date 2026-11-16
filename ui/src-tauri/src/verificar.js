// Injetado apenas quando a janela recebe --verificar (debug ou release).
document.addEventListener('DOMContentLoaded', async () => {
  const report = { origin: window.location.origin }
  let preview
  let finished = false
  const timer = setTimeout(() => finish(false, 'timeout'), 20000)

  function finish(ok, reason) {
    if (finished) return
    finished = true
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
    // A chave de sessão chega pelo comando do Tauri e o motor a aceita numa rota protegida.
    const sessao = await window.__TAURI__.core.invoke('sessao_motor')
    report.sessao = (await fetch(`${api}/diagnostics/errors`, { headers: { 'X-Clips-Kitty-Session': sessao } })).status
    while (!document.querySelector('#root')?.children.length && !finished) {
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    if (finished) return
    report.react = true
    const first = cortes[0]
    if (!first) {
      report.preview = 'sem_cortes'
      return finish(Boolean(report.engine && report.react && report.sessao === 200))
    }

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
      report.preview = 'quadro_decodificado'
      finish(Boolean(report.engine && report.react && report.width > 0 && report.muted && report.sessao === 200))
    })
  } catch (error) {
    finish(false, `${error.name}: ${error.message}`.slice(0, 300))
  }
}, { once: true })
