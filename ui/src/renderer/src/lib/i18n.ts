/** Tiny UI translation layer.
 *
 *  - Dictionaries are keyed by the ENGLISH source string, so untranslated
 *    strings simply render in English (partial coverage degrades gracefully
 *    and `t()` calls keep the code readable).
 *  - This installation defaults to Brazilian Portuguese. Settings can
 *    follow the system language or choose another installed dictionary.
 */
import ar from '../locales/ar.json'
import bn from '../locales/bn.json'
import de from '../locales/de.json'
import es from '../locales/es.json'
import fr from '../locales/fr.json'
import hi from '../locales/hi.json'
import id from '../locales/id.json'
import it from '../locales/it.json'
import ja from '../locales/ja.json'
import ko from '../locales/ko.json'
import pt from '../locales/pt.json'
import ru from '../locales/ru.json'
import th from '../locales/th.json'
import tl from '../locales/tl.json'
import tr from '../locales/tr.json'
import ur from '../locales/ur.json'
import vi from '../locales/vi.json'
import zh from '../locales/zh.json'

const LOCALES: Record<string, Record<string, string>> = {
  es, pt, hi, id, ja, ar, ru, de, fr, zh, vi, tl, tr, ur, bn, th, ko, it
}

/** code -> [English name, native name]. Shown as "English (Native)" wherever
 *  a language is picked, so a viewer who reads only one of the two can still
 *  find their language in the list. */
export const LANGUAGE_NAMES: Record<string, [string, string]> = {
  en: ['English', 'English'],
  es: ['Spanish', 'Español'],
  pt: ['Portuguese', 'Português'],
  fr: ['French', 'Français'],
  de: ['German', 'Deutsch'],
  hi: ['Hindi', 'हिन्दी'],
  id: ['Indonesian', 'Bahasa Indonesia'],
  ja: ['Japanese', '日本語'],
  ru: ['Russian', 'Русский'],
  ar: ['Arabic', 'العربية'],
  zh: ['Chinese (Simplified)', '简体中文'],
  vi: ['Vietnamese', 'Tiếng Việt'],
  tl: ['Filipino', 'Filipino'],
  tr: ['Turkish', 'Türkçe'],
  ur: ['Urdu', 'اردو'],
  bn: ['Bengali', 'বাংলা'],
  th: ['Thai', 'ไทย'],
  ko: ['Korean', '한국어'],
  it: ['Italian', 'Italiano']
}

/** "Spanish (Español)" — collapsed to one name when the two are identical. */
export function languageLabel(code: string): string {
  const pair = LANGUAGE_NAMES[code]
  if (!pair) return code
  const [english, native] = pair
  if (activeLocale() === 'pt') return t(code === 'pt' ? 'Portuguese (Brazil)' : english)
  const translated = t(english)
  return translated === native ? translated : translated + ' (' + native + ')'
}

/** Interface languages, named in the language the user is reading. */
export function appLanguages(): [string, string][] {
  return [
    ['system', t('System (Windows) language')],
    ['en', languageLabel('en')],
    ...Object.keys(LOCALES)
      .map((code): [string, string] => [code, languageLabel(code)])
      .sort((a, b) => a[1].localeCompare(b[1], interfaceLocale()))
  ]
}

const STORE_KEY = 'app-language'

export function appLanguageSetting(): string {
  return localStorage.getItem(STORE_KEY) ?? 'pt'
}

/** The locale actually in effect (resolving 'system' to the OS language). */
export function activeLocale(): string {
  const setting = appLanguageSetting()
  if (setting !== 'system') return setting
  const sys = (navigator.language || 'en').slice(0, 2).toLowerCase()
  return sys in LOCALES ? sys : 'en'
}

/** Re-read labels declared in modules and return to Settings. */
export function setAppLanguage(code: string): void {
  if (code === appLanguageSetting()) return
  localStorage.setItem(STORE_KEY, code)
  sessionStorage.setItem('restore-language-settings', 'yes')
  window.location.reload()
}

export const opensLanguageSettings = sessionStorage.getItem('restore-language-settings') === 'yes'
sessionStorage.removeItem('restore-language-settings')

const dict = LOCALES[activeLocale()]

export function interfaceLocale(): string {
  const locale = activeLocale()
  return locale === 'pt' ? 'pt-BR' : locale
}

function applyLocale(): void {
  document.documentElement.lang = interfaceLocale()
  void window.studio?.setInterfaceLanguage?.(activeLocale()).catch(() => undefined)
}

applyLocale()

/** Translate a UI message and substitute its numbered values after lookup. */
export function t(source: string, ...values: unknown[]): string {
  const message = dict && Object.hasOwn(dict, source) ? dict[source] : source
  if (!values.length) return message
  return message.replace(/\{(\d+)\}/g, (token, index: string) =>
    Number(index) < values.length ? String(values[Number(index)]) : token
  )
}

/** Localize server and browser messages that include a varying value. */
export function messageText(source: string): string {
  const exact = t(source)
  if (exact !== source || activeLocale() !== 'pt') return exact
  const text = source.trim()
  const known = t(text)
  if (known !== text) return known

  if (/Failed to fetch|ERR_CONNECTION_REFUSED|NetworkError when attempting to fetch/i.test(text)) {
    return t('Failed to fetch')
  }
  if (text.includes('X-Clips-Kitty-Session')) {
    return t('Open the Clips Kitty desktop app again to renew the local session.')
  }
  const model = text.match(/^(?:model )?(.+?) isn.t downloaded\. Download it on the Models page.*$/i)
  if (model) return t('Model {0} is not downloaded. Open Models to download it.', model[1])
  const preview = text.match(/^preview render failed:\s*(.+)$/i)
  if (preview) return t('Could not render the preview. {0}', messageText(preview[1]))
  return exact
}
