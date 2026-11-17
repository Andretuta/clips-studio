import { useEffect, useState } from 'react'
import { mesa, type Autonomy, type PublicationHistory } from '../lib/mesa'

const states: Record<string, string> = {
  queued: 'Na fila', running: 'Enviando', done: 'Upload concluído', failed: 'Falhou',
  interrupted: 'Interrompido · confira o canal', uncertain: 'Resultado incerto · confira o canal',
  awaiting_operator: 'Aceito · finalize no TikTok', cancelled: 'Cancelado'
}

export default function AutonomyCard(): JSX.Element {
  const [policy, setPolicy] = useState<Autonomy | null>(null)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<PublicationHistory[]>([])
  const [note, setNote] = useState('')
  useEffect(() => { mesa.autonomy().then(setPolicy).catch(() => setNotice('Autonomia indisponível: confira a sessão e recarregue o motor.')) }, [])
  useEffect(() => {
    const refresh = (): void => { mesa.history().then(setHistory).catch(() => {}) }
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [])
  const reconcile = async (id: number, outcome: 'found' | 'absent'): Promise<void> => {
    setBusy(true)
    try { await mesa.reconcile(id, outcome, note); setHistory(await mesa.history()); setNote(''); setNotice('Conferência registrada.') }
    catch (e) { setNotice(String(e)) }
    finally { setBusy(false) }
  }
  const save = async (): Promise<void> => {
    if (!policy) return
    setBusy(true)
    try { setPolicy(await mesa.saveAutonomy(policy)); setNotice('Opções salvas para os próximos cortes entregues pela Cola.') }
    catch (e) { setNotice(String(e)) }
    finally { setBusy(false) }
  }
  return <details className="mx-5 mt-2 text-sm">
    <summary className="cursor-pointer">Autonomia da IA e postagem automática</summary>
    {policy && <form className="flex flex-wrap items-center gap-3 py-3" onSubmit={(e) => { e.preventDefault(); void save() }}>
      <label><input type="checkbox" checked={policy.edit_enabled} onChange={(e) => setPolicy({ ...policy, edit_enabled: e.target.checked })} /> IA revisa texto e bordas (até 2 s)</label>
      <label><input type="checkbox" checked={policy.post_enabled} onChange={(e) => setPolicy({ ...policy, post_enabled: e.target.checked })} /> Autoaprovar e enviar</label>
      <label>Limiar (0–1) <input className="input !w-20" type="number" min="0" max="1" step="0.01" required value={policy.threshold} onChange={(e) => setPolicy({ ...policy, threshold: Number(e.target.value) })} /></label>
      <label>Máximo/h <input className="input !w-20" type="number" min="1" max="20" required value={policy.max_per_hour} onChange={(e) => setPolicy({ ...policy, max_per_hour: Number(e.target.value) })} /></label>
      <label>Destino <select className="input" value={policy.target} onChange={(e) => setPolicy({ ...policy, target: e.target.value as Autonomy['target'] })}>
        <option value="youtube">YouTube direto</option><option value="tiktok">TikTok · rascunho Composio</option>
      </select></label>
      {policy.target === 'youtube' && <label>Visibilidade <select className="input" value={policy.youtube_privacy} onChange={(e) => setPolicy({ ...policy, youtube_privacy: e.target.value as Autonomy['youtube_privacy'] })}>
        <option value="public">Público</option><option value="private">Privado</option>
      </select></label>}
      <button className="btn-ghost" type="submit" disabled={busy}>Salvar autonomia</button>
      <p className="w-full text-xs text-muted">Começa desligada. Sem momento-chave válido não há postagem automática. TikTok requer finalizar na caixa de entrada. A edição usa a IA configurada e precisa da autorização de automação do plano.</p>
    </form>}
    {notice && <p role="status" className="py-2">{notice}</p>}
    <p className="mt-2 font-semibold">Últimos envios</p>
    {history.slice(0, 8).map((job) => <div key={job.id} className="text-xs py-1">
      #{job.id} · {job.platform} · {states[job.status] || job.status} · {job.receipt?.remote_id || job.youtube_id || 'sem ID remoto'}
      {job.error && <span> · {job.error}</span>}
      {(job.status === 'uncertain' || job.status === 'interrupted') && job.platform === 'tiktok' && <span className="ml-2">
        <button type="button" className="btn-ghost" disabled={busy || note.trim().length < 10} onClick={() => void reconcile(job.id, 'found')}>Conferi: chegou</button>
        <button type="button" className="btn-ghost" disabled={busy || note.trim().length < 10 || !!job.receipt?.remote_id} onClick={() => void reconcile(job.id, 'absent')}>Conferi: não chegou</button>
      </span>}
    </div>)}
    <label className="block py-2 text-xs">Conferência na plataforma (para envios incertos)
      <input className="input" value={note} maxLength={400} placeholder="Descreva a conferência feita na caixa de entrada/painel" onChange={(e) => setNote(e.target.value)} />
    </label>
  </details>
}
