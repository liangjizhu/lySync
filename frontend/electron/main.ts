import { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } from "electron";
import { join } from "path";
import { spawn, ChildProcess } from "child_process";

const IS_DEV = process.env.NODE_ENV === "development";
const WAYLAND = !!process.env.WAYLAND_DISPLAY;

let win: BrowserWindow | null = null;
let tray: Tray | null = null;
let backend: ChildProcess | null = null;

// Pass Wayland flags before app ready
if (WAYLAND) {
  app.commandLine.appendSwitch("enable-features", "UseOzonePlatform");
  app.commandLine.appendSwitch("ozone-platform", "wayland");
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 700,
    height: 220,
    x: 0,
    y: 0,
    transparent: !IS_DEV,
    backgroundColor: IS_DEV ? "#1a1a1a" : undefined,
    frame: IS_DEV,
    alwaysOnTop: true,
    skipTaskbar: false,
    hasShadow: false,
    resizable: true,
    movable: true,
    focusable: IS_DEV,
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!IS_DEV) {
    win.setIgnoreMouseEvents(true, { forward: true });
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    win.setAlwaysOnTop(true, "screen-saver");
  }

  if (IS_DEV) {
    win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

// Allow renderer to toggle click-through (hover to show settings)
ipcMain.on("set-ignore-mouse", (_event, ignore: boolean) => {
  win?.setIgnoreMouseEvents(ignore, { forward: true });
  if (!ignore) {
    win?.setFocusable(true);
    win?.focus();
  } else {
    win?.setFocusable(false);
  }
});

ipcMain.on("quit", () => app.quit());

function startBackend(): void {
  const python = process.platform === "win32" ? "python" : "python3";
  const cwd = IS_DEV
    ? join(__dirname, "../../..")  // repo root during dev
    : process.resourcesPath;

  backend = spawn(python, ["-m", "uvicorn", "backend.main:app", "--port", "7314", "--no-access-log"], {
    cwd,
    stdio: "pipe",
  });

  backend.stderr?.on("data", (d) => {
    if (IS_DEV) process.stderr.write(d);
  });
}

function createTray(): void {
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip("lySync");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show", click: () => win?.show() },
      { label: "Quit", click: () => app.quit() },
    ])
  );
}

app.whenReady().then(() => {
  if (!IS_DEV) startBackend();  // dev: run uvicorn manually in a separate terminal
  createWindow();
  createTray();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("will-quit", () => {
  backend?.kill();
});
