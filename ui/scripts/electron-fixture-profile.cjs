// Isolated profiles for the existing short-lived, hidden Electron fixtures.
module.exports = function configureProfile(app, dir) {
  const path = require('node:path')
  const fs = require('node:fs')
  for (const name of ['userData', 'sessionData', 'crashDumps', 'logs']) {
    const folder = path.join(dir, name)
    fs.mkdirSync(folder, { recursive: true })
    app.setPath(name, folder)
  }
  app.commandLine.appendSwitch('disk-cache-dir', path.join(dir, 'cache'))
  app.commandLine.appendSwitch('disable-background-networking')
  app.disableHardwareAcceleration()
}
