import { t as tr } from "./i18n"
import type { JobOptions, QueueJob, QueueSnapshot } from './types'
import type { JobProgress } from './jobProgress'
import { etaSeconds } from './jobProgress'
import { describeSport } from './sports'

/** Pure queue helpers — no React, no fetch.
 *
 *  Everything here is a function of the snapshot the server sent, so the
 *  queue's rules can be reasoned about (and changed) without touching a
 *  component, and no component grows its own private copy of them. */

/** What to call a queue row.
 *
 *  `display_title` comes from the videos table and is empty until the
 *  download names the video — and for jobs queued before this feature
 *  existed. The URL is the honest fallback; inventing a name would be worse
 *  than showing the thing the user actually pasted. */
export function jobLabel(job: QueueJob): string {
  if (job.display_title) return job.display_title
  if (job.type === 'render') return tr("Re-rendering a clip")
  if (job.type === 'translate') return tr("Subtitles & dubbing")
  if (!job.url) return tr("Job {0}", job.id)
  if (job.url.startsWith('local:')) return tr("Local video file")
  try {
    const u = new URL(job.url)
    return `${u.hostname.replace(/^www\./, '')}${u.pathname}`
  } catch {
    return job.url
  }
}

/** Which site a job's video came from, for a small chip on the row.
 *
 *  Matched against the parsed hostname rather than the whole URL. Testing
 *  /twitch\.tv/ against the raw string also matches
 *  `example.com/watch?ref=twitch.tv` and `twitch.tv.phishing.example`, which
 *  puts a Twitch chip on a row that has nothing to do with Twitch. */
export function sourceOf(url: string): string {
  if (!url) return ''
  if (url.startsWith('local:')) return tr("Local file")

  let host: string
  try {
    host = new URL(url).hostname.replace(/^www\./, '').toLowerCase()
  } catch {
    return tr("Link")
  }

  // Exact host, or a subdomain of it — never a substring.
  const from = (domain: string): boolean => host === domain || host.endsWith(`.${domain}`)
  if (from('youtube.com') || from('youtu.be')) return 'YouTube'
  if (from('twitch.tv')) return 'Twitch'
  if (from('kick.com')) return 'Kick'
  return tr("Link")
}

/** The settings that actually differ from the defaults, as short chips.
 *  Only what was chosen is listed — a row of "off" badges is noise. */
export function describeOptions(o: JobOptions | undefined): string[] {
  if (!o) return []
  const chips: string[] = []
  if (o.captions === false) chips.push(tr('No captions'))
  if (o.long_clips) chips.push('60s+')
  if (o.podcast) chips.push('Podcast')
  if (o.vertical_live) chips.push(tr('Vertical Live'))
  if (o.gaming) chips.push(tr('Gaming / Reaction'))
  if (o.sport) chips.push(describeSport(o.sport))
  if (o.longform)
    chips.push(
      tr('Longform · {0}{1}', tr(o.longform.mode ?? ''), o.longform.shorts ? tr(' + 9:16 Shorts') : '')
    )
  if (o.watermark_profile_id) chips.push(tr('Watermark'))
  if (o.cortes_gamer_watermark) chips.push('Cortes Gamer')
  if (o.filter && o.filter !== 'none') chips.push(tr('Filter · {0}', tr(o.filter)))
  if (typeof o.max_clips === 'number') chips.push(tr('Max {0} clips', o.max_clips))
  if (typeof o.min_score === 'number') chips.push(tr('Score ≥ {0}', o.min_score))
  if (o.focus) chips.push(tr('Direction · {0}', o.focus.length > 40 ? o.focus.slice(0, 40) + '…' : o.focus))
  if (o.force) chips.push(tr('Reprocess'))
  return chips
}

/** Seconds until the whole queue is done.
 *
 *  Two halves from two sources, deliberately. The waiting videos are the
 *  server's call — it has the processing history. The running video is the
 *  UI's, because the live progress fraction is already here and extrapolating
 *  from it beats any historical average once a video is underway. Falls back
 *  to the server's per-video figure while progress is too young to trust. */
export function queueEta(
  snapshot: QueueSnapshot | null,
  live: JobProgress,
  now: number
): number | null {
  if (!snapshot) return null
  const waiting = snapshot.estimate.queued_seconds
  const running = snapshot.processing.length > 0
  if (!running) return waiting > 0 ? waiting : null
  const fromProgress = etaSeconds(live, now)
  const current = fromProgress ?? snapshot.estimate.per_video_seconds
  return waiting + current
}

/** "2h 47m" / "18m" / "45s". Coarser than the per-clip timer on purpose:
 *  to the second is false precision on an hour-long estimate. */
export function formatQueueEta(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`
  return `${m}m`
}

/** How long a finished job took, from its own timestamps. */
export function ranFor(job: QueueJob): string | null {
  if (!job.started_at || !job.finished_at) return null
  const ms = new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
  if (!Number.isFinite(ms) || ms <= 0) return null
  return formatQueueEta(ms / 1000)
}

/** Total videos still to process, including the one running. */
export function remainingCount(snapshot: QueueSnapshot | null): number {
  if (!snapshot) return 0
  return snapshot.processing.length + snapshot.queued.length
}
