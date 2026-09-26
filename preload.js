const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  selectWorkdir: () => ipcRenderer.invoke('select-workdir'),
  selectMuziekfolder: () => ipcRenderer.invoke('select-muziekfolder'),
  start: (config) => ipcRenderer.invoke('start', config),
  stop: () => ipcRenderer.invoke('stop'),
  isRunning: () => ipcRenderer.invoke('is-running'),
  onLog: (callback) => ipcRenderer.on('log', (event, msg) => callback(msg)),
  onFinished: (callback) => ipcRenderer.on('finished', () => callback())
});
