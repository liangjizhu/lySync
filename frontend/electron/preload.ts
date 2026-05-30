import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  setIgnoreMouse: (ignore: boolean) => ipcRenderer.send("set-ignore-mouse", ignore),
  quit: () => ipcRenderer.send("quit"),
});
