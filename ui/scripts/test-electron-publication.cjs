const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function compile(file, require, globals = {}) {
  const module = { exports: {} }
  const source = fs.readFileSync(path.join(__dirname, file), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022
  } }).outputText
  vm.runInNewContext(code, { exports: module.exports, require, URL, ...globals })
  return module.exports
}

const { safeHttps } = compile('../src/main/externalUrl.ts', () => {})
for (const url of ['https://accounts.google.com/o/oauth2/auth?state=fake', 'https://app.composio.dev/link/test']) {
  assert.equal(safeHttps(url), true)
}
for (const url of ['file:///D:/evil.exe', 'javascript:alert(1)', 'ms-settings:privacy',
  'http://127.0.0.1/', 'https://user:password@example.org/', 'https://example.org:8443/', null]) {
  assert.equal(safeHttps(url), false)
}

async function main() {
  const calls = []
  let session = 'test-session'
  let status = 200
  const { mesa } = compile('../src/renderer/src/lib/mesa.ts', (name) => {
    if (name === './i18n') return { t: (s) => s }
    if (name === './api') return { API_BASE: 'http://127.0.0.1:8765', responseErrorText: (s) => s }
    if (name === './plugins') return { sessionSecret: async () => session }
    throw new Error(name)
  }, { fetch: async (url, init) => {
    calls.push({ url, init })
    return { ok: status === 200, status, json: async () => ({ status: 'queued', job_id: 7 }), text: async () => 'Envio anterior incerto' }
  } })
  await mesa.privateTest('corte teste', 'youtube')
  assert.equal(calls[0].url, 'http://127.0.0.1:8765/publication/mesa/corte%20teste/private-test')
  assert.equal(calls[0].init.headers['X-Clips-Kitty-Session'], 'test-session')
  assert.deepEqual(JSON.parse(calls[0].init.body), { target: 'youtube' })
  await mesa.privateTest('corte', 'tiktok')
  assert.equal(JSON.parse(calls[1].init.body).target, 'tiktok')
  status = 409
  await assert.rejects(mesa.privateTest('corte', 'youtube'), /Envio anterior incerto/)
  session = ''
  const before = calls.length
  await assert.rejects(mesa.privateTest('corte', 'youtube'), /desktop app/)
  assert.equal(calls.length, before)
  console.log('Publicação Electron: URLs, sessão, destinos e resposta incerta passaram.')
}
main().catch((error) => { console.error(error); process.exitCode = 1 })
