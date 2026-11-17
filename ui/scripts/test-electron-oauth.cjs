// Real YouTubeCard in Electron, with HTTP and the system-browser bridge doubled.
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
if (!process.versions.electron) {
  ;(async () => {
    const root = path.resolve(__dirname, '..')
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'clipador-oauth-'))
    await require('esbuild').build({
      stdin: { contents: `import React from 'react';import {createRoot} from 'react-dom/client';import Card from './src/renderer/src/components/YouTubeCard';createRoot(document.getElementById('root')).render(<Card/>);`, resolveDir: root, loader: 'tsx' },
      bundle: true, outfile: path.join(dir, 'fixture.js'), jsx: 'automatic', platform: 'browser'
    })
    fs.writeFileSync(path.join(dir, 'fixture.html'), `<!doctype html><div id="root"></div><script>
      localStorage.setItem('app-language','en');window.opened=[];window.polls=0;
      const connected={enabled:true,connected:true,has_client:true,accounts:[{id:'test-channel',title:'Canal de ensaio',default:true}],settings:{}};
      window.studio={openExternal:async(url)=>{window.opened.push(url);return true}};
      window.fetch=async(url,init={})=>{
        const route=new URL(url).pathname;let body;
        if(route==='/youtube/status') body={enabled:true,has_client:true,connected:false,settings:{}};
        else if(route==='/youtube/connect'&&init.method==='POST') body={state:'waiting'};
        else if(route==='/youtube/connect') body=++window.polls<=2?{state:'waiting',authorization_url:'https://accounts.google.com/o/oauth2/auth?state=fixture'}:{state:'done',status:connected};
        else throw Error('Rota inesperada');
        return {ok:true,status:200,json:async()=>body};
      };</script><script src="fixture.js"></script>`)
    const env = { ...process.env }
    delete env.ELECTRON_RUN_AS_NODE
    const report = path.join(dir, 'report.json')
    const result = require('node:child_process').spawnSync(require('electron'), [__filename, dir, report], { env, windowsHide: true, timeout: 90000, encoding: 'utf8' })
    if (result.error) throw result.error
    if (result.status !== 0) throw Error(result.stderr || (fs.existsSync(report) ? fs.readFileSync(report, 'utf8') : 'OAuth fixture falhou'))
    console.log('OAuth Electron: navegador aberto uma vez, polling e conta conectada passaram.')
  })().catch((error) => { console.error(error); process.exitCode = 1 })
} else {
  const { app, BrowserWindow } = require('electron')
  const [dir, report] = process.argv.slice(-2)
  fs.writeFileSync(report, JSON.stringify({ stage: 'starting' }))
  require('./electron-fixture-profile.cjs')(app, dir)
  app.disableHardwareAcceleration()
  app.whenReady().then(async () => {
    fs.writeFileSync(report, JSON.stringify({ stage: 'ready' }))
    const win = new BrowserWindow({ show: false, webPreferences: { sandbox: true, contextIsolation: true, offscreen: true } })
    try {
      await win.loadFile(path.join(dir, 'fixture.html'))
      await new Promise((r) => setTimeout(r, 500))
      await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Connect your YouTube channel').click()`)
      await new Promise((r) => setTimeout(r, 5200))
      const result = await win.webContents.executeJavaScript(`({opened:window.opened.length,connected:document.body.innerText.includes('Canal de ensaio')})`)
      if (result.opened !== 1 || !result.connected) throw Error('Não abriu uma vez ou não conectou: ' + JSON.stringify(result))
      fs.writeFileSync(report, JSON.stringify({ ok: true }))
      app.exit(0)
    } catch (error) { fs.writeFileSync(report, JSON.stringify({ ok: false, error: String(error) })); app.exit(1) }
  })
}
