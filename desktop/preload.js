const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kitchenDesktop', {
  pickDwg: () => ipcRenderer.invoke('dwg:pick'),
  importDwg: (filePath) => ipcRenderer.invoke('dwg:import', filePath),
  revealFolder: (folderPath) => ipcRenderer.invoke('folder:reveal', folderPath)
});
