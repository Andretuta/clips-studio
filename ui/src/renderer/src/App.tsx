import { t as tr } from "./lib/i18n"
import { useEffect, useState } from 'react'
import Dashboard from './pages/Dashboard'
import ClipStudio from './pages/ClipStudio'
import Controle from './pages/Controle'
import Creators from './pages/Creators'
import Marketplace from './pages/Marketplace'
import Mesa from './pages/Mesa'
import Models from './pages/Models'
import Publication from './pages/Publication'
import Queue from './pages/Queue'
import Settings from './pages/Settings'
import Watch from './pages/Watch'
import FeedbackHub from './components/FeedbackHub'
import ModelSwitcher from './components/ModelSwitcher'
import SetupWizard, { setupDone } from './components/SetupWizard'
import UpdateBanner from './components/UpdateBanner'
import { opensLanguageSettings, t } from './lib/i18n'
import { api } from './lib/api'
import { mesa } from './lib/mesa'
import type { StudioEvent } from './lib/types'
import { useEvents } from './lib/useEvents'
import { useQueueNotifications } from './lib/queueNotifications'
import { ApprovalCards, ClipUpdatesProvider } from './components/ApprovalCard'
import { OPEN_MARKETPLACE, checkOnlineListAtStart } from './lib/plugins'
import mascot from './assets/mascot.png'

type Page = 'mesa' | 'controle' | 'dashboard' | 'queue' | 'watch' | 'studio' | 'publication' | 'creators' | 'marketplace' | 'models' | 'settings'

const GITHUB_URL = 'https://github.com/ColinGPT9/clips-studio'

const NAV: { id: Page; label: string; icon: string }[] = [
  // The approval desk and control room (settings.yaml `mesa:`), shown only when on.
  { id: 'mesa', label: tr("Approval desk"), icon: '✓' },
  { id: 'controle', label: tr("Control room"), icon: '◈' },
  { id: 'dashboard', label: tr("Dashboard"), icon: '◧' },
  { id: 'queue', label: tr("Queue"), icon: '≡' },
  { id: 'watch', label: tr("Watched channels"), icon: '◎' },
  // Renamed in 1.1.3. The previous label matched an existing product closely
  // enough to block the Microsoft Store listing, so do not change it back —
  // "Clip Editor" is also just what the page is.
  { id: 'studio', label: tr("Clip Editor"), icon: '✂' },
  { id: 'publication', label: 'Publicação', icon: '↗' },
  { id: 'creators', label: tr("Creators"), icon: '◉' },
  // Community pipelines: browse the registry, install, manage (plugins/).
  { id: 'marketplace', label: tr("Marketplace"), icon: '⊞' },
  { id: 'models', label: tr("Models"), icon: '⬢' },
  { id: 'settings', label: tr("Settings"), icon: '⚙' }
]

export interface StudioTarget {
  videoId: string
  clipId?: number
}

export default function App(): JSX.Element {
  const [page, setPage] = useState<Page>(opensLanguageSettings ? 'settings' : 'dashboard')
  const [studioTarget, setStudioTarget] = useState<StudioTarget | null>(null)
  const [creatorTarget, setCreatorTarget] = useState<number | null>(null)
  const [mesaTarget, setMesaTarget] = useState<string | null>(null)
  // Whether the approval desk is on: then it is the first screen. Asked until
  // the engine answers, since it may still be starting with the window.
  const [mesaOn, setMesaOn] = useState(false)
  useEffect(() => {
    let id: ReturnType<typeof setTimeout>
    const ask = (): void => {
      mesa
        .cortes()
        .then((s) => {
          if (!s.enabled) return
          setMesaOn(true)
          setPage((p) => (p === 'dashboard' ? 'mesa' : p))
        })
        .catch(() => {
          id = setTimeout(ask, 5000)
        })
    }
    ask()
    return () => clearTimeout(id)
  }, [])
  // First run: walk the creator through what the installer can't bundle
  // (Ollama, a model) before they hit a video that fails for want of it.
  // Settings can re-open it, so this is not a one-shot.
  const [wizard, setWizard] = useState(!setupDone())
  useEffect(() => {
    const open = (): void => setWizard(true)
    window.addEventListener('open-setup-wizard', open)
    return () => window.removeEventListener('open-setup-wizard', open)
  }, [])
  // Jump to the queue from anywhere (the Generate bar links here after
  // queueing). Same window-event mechanism as the setup wizard above —
  // this app navigates by state, not a router.
  useEffect(() => {
    const open = (): void => setPage('queue')
    window.addEventListener('open-queue', open)
    return () => window.removeEventListener('open-queue', open)
  }, [])
  // Same door for Settings: the editor's YouTube panel sends people here to
  // connect an account, rather than duplicating the setup flow inside a tab.
  useEffect(() => {
    const open = (): void => setPage('settings')
    window.addEventListener('open-settings', open)
    return () => window.removeEventListener('open-settings', open)
  }, [])
  // And Models: Settings → AI links here to manage local models.
  useEffect(() => {
    const open = (): void => setPage('models')
    window.addEventListener('open-models', open)
    return () => window.removeEventListener('open-models', open)
  }, [])
  // And the Marketplace: the Generate bar's Pipeline switch links here.
  useEffect(() => {
    const open = (): void => setPage('marketplace')
    window.addEventListener(OPEN_MARKETPLACE, open)
    return () => window.removeEventListener(OPEN_MARKETPLACE, open)
  }, [])
  // Installed pipelines hear about a blocked version without the Marketplace being opened.
  useEffect(() => checkOnlineListAtStart(), [])
  // Whether any AI runs in the cloud on the user's own key, so the sidebar's
  // "100% local" line is only ever shown when it is true.
  const [cloudAI, setCloudAI] = useState('')
  useEffect(() => {
    const read = (): void => {
      api
        .ai()
        .then((s) => {
          const label = (id: string): string => s.providers.find((p) => p.id === id)?.label ?? id
          const parts: string[] = []
          if (!s.active.local) parts.push(`${t('AI')}: ${label(s.active.provider)}`)
          if (s.transcription.backend !== 'local') {
            parts.push(`${t('transcription')}: ${label(s.transcription.backend)}`)
          }
          setCloudAI(parts.join(', '))
        })
        .catch(() => setCloudAI(''))
    }
    read()
    const id = setInterval(read, 30000)
    return () => clearInterval(id)
  }, [])
  // Mounted at the shell, not on the queue page: the point of a notification
  // is to reach someone who is NOT looking at the queue.
  useQueueNotifications()
  // How many channels are being watched, for the live dot beside "Watched
  // channels", so it shows from every page that the PC is on the job.
  const [watching, setWatching] = useState(0)
  useEffect(() => {
    const load = (): void => {
      api
        .automation()
        .then((s) => setWatching(s.enabled ? s.watching : 0))
        .catch(() => setWatching(0))
    }
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [])
  useEvents((e: StudioEvent) => {
    if (e.type === 'automation' && !('activity' in e) && !('doing' in e)) {
      api
        .automation()
        .then((s) => setWatching(s.enabled ? s.watching : 0))
        .catch(() => {})
    }
  })
  // Language switches re-render the tree IN PLACE (no reload): the page
  // state lives here, so the user stays wherever they were (e.g. Settings).

  const openInStudio = (videoId: string, clipId?: number): void => {
    setStudioTarget({ videoId, clipId })
    setPage('studio')
  }

  // A watched channel's card opens its creator profile, already selected.
  const openCreator = (creatorId: number): void => {
    setCreatorTarget(creatorId)
    setPage('creators')
  }

  return (
    <ClipUpdatesProvider><div className="flex h-screen">
      <ApprovalCards onOpen={videoId => { setStudioTarget({videoId}); setPage('studio') }} />
      <aside className="w-52 shrink-0 bg-surface border-r border-raised/60 flex flex-col">
        {/* Same lockup as the website header: Clippy, then the name and
            tagline stacked beside him. `min-w-0` on the text column so a
            longer translated tagline wraps instead of pushing Clippy out of
            the sidebar — several of the 19 locales are wordier than English. */}
        <div className="px-5 py-5 flex items-center gap-2.5">
          <img
            src={mascot}
            alt=""
            width={34}
            height={34}
            className="shrink-0 w-[34px] h-[34px]"
          />
          <div className="min-w-0">
            <h1 className="text-lg font-bold leading-tight">
              Clips <span className="text-accent">Kitty</span>
            </h1>
            <p className="text-xs text-muted mt-px">{t('local-first AI clipping')}</p>
          </div>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {NAV.filter((item) => mesaOn || (item.id !== 'mesa' && item.id !== 'controle')).map((item) => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-3 transition-colors ${
                page === item.id
                  ? 'bg-accent/15 text-accent font-medium'
                  : 'text-muted hover:bg-raised hover:text-ink'
              }`}
            >
              <span aria-hidden>{item.icon}</span>
              {t(item.label)}
              {item.id === 'watch' && watching > 0 && (
                <span
                  className="ml-auto relative flex size-2.5"
                  title={`${t('Watching')} ${watching}`}
                  aria-label={t('Watching')}
                >
                  <span className="absolute inline-flex size-full rounded-full bg-success opacity-60 animate-ping" />
                  <span className="relative inline-flex size-2.5 rounded-full bg-success" />
                </span>
              )}
            </button>
          ))}
        </nav>
        {/* Pinned below the nav: reachable from every page — bugs don't
            only happen on the Dashboard. */}
        <div className="px-3 pb-1">
          <FeedbackHub />
        </div>
        <ModelSwitcher />
        <div className="px-5 py-4 border-t border-raised/60">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted hover:text-accent transition-colors"
          >
            <span className="font-semibold">{t('Open source')}</span> — {t('view & modify on GitHub')} ↗
          </a>
          {/* The AGPL expects anyone running the program to be able to find
              its source. The link above is that offer, so it names the
              licence rather than leaving "open source" to mean anything. */}
          <p className="text-[10px] text-muted/60 mt-1.5">
            {cloudAI
              ? tr("AGPL-3.0 · {0} ({1})", t('cloud AI on your key'), cloudAI)
              : t('AGPL-3.0 · 100% local · no cloud AI')}
          </p>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto flex flex-col">
        <UpdateBanner />
        {page === 'mesa' && (
          <Mesa target={mesaTarget} onTargetConsumed={() => setMesaTarget(null)} onOpenInStudio={openInStudio} />
        )}
        {page === 'controle' && (
          <Controle
            onOpenMesa={(nome) => {
              setMesaTarget(nome ?? null)
              setPage('mesa')
            }}
            onOpenQueue={() => setPage('queue')}
          />
        )}
        {page === 'dashboard' && <Dashboard onOpenInStudio={openInStudio} />}
        {page === 'queue' && <Queue onOpenInStudio={(videoId) => openInStudio(videoId)} />}
        {page === 'watch' && (
          <Watch onOpenInStudio={(videoId) => openInStudio(videoId)} onOpenCreator={openCreator} />
        )}
        {page === 'studio' && (
          <ClipStudio target={studioTarget} onTargetConsumed={() => setStudioTarget(null)} />
        )}
        {page === 'creators' && (
          <Creators initialSelected={creatorTarget} onTargetConsumed={() => setCreatorTarget(null)} />
        )}
        {page === 'marketplace' && <Marketplace />}
        {page === 'models' && <Models />}
        {page === 'publication' && <Publication onOpenInStudio={openInStudio} />}
        {page === 'settings' && <Settings />}
      </main>
      {wizard && (
        <SetupWizard
          onClose={() => {
            setWizard(false)
            setPage('studio')
          }}
        />
      )}
    </div></ClipUpdatesProvider>
  )
}
