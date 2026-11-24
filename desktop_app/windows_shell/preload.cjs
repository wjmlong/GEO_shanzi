const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('geoDesktop', {
  setBounds: bounds => ipcRenderer.send('geo:bounds', bounds),
  setStudioBounds: bounds => ipcRenderer.send('geo:studio-bounds', bounds),
  studio: (action, draft) => ipcRenderer.invoke('geo:studio', action, draft),
  navigate: target => ipcRenderer.invoke('geo:navigate', target),
  action: (name, tabId) => ipcRenderer.invoke('geo:action', name, tabId),
  exam: request => ipcRenderer.invoke('geo:exam', request),
  fillDraft: draft => ipcRenderer.invoke('geo:fill', draft),
  onState: listener => {
    ipcRenderer.on('geo:state', (_event, state) => listener(state));
  },
  onExamProgress: listener => {
    ipcRenderer.on('geo:exam-progress', (_event, state) => listener(state));
  },
  onStudioClosed: listener => {
    ipcRenderer.on('geo:studio-closed', () => listener());
  },
});
