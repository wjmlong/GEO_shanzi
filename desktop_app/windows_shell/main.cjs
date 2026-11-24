const { app, BrowserWindow, WebContentsView, ipcMain, dialog } = require('electron');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { runExam, collectExam } = require('./exam-browser.cjs');
const { createStudio } = require('./video-studio.cjs');

const PLATFORM_URLS = {
  sohu: 'https://mp.sohu.com/',
  toutiao: 'https://mp.toutiao.com/',
  netease: 'https://mp.163.com/',
  wechat: 'https://mp.weixin.qq.com/',
  douyin: 'https://creator.douyin.com/',
  xiaohongshu: 'https://creator.xiaohongshu.com/',
  eastmoney: 'https://guba.eastmoney.com/list,000981.html',
  ths: 'https://basic.10jqka.com.cn/000981/',
  official: 'https://www.sensteed.com/insights/',
  doubao: 'https://www.doubao.com/chat/',
  deepseek: 'https://chat.deepseek.com/',
};
const PLATFORM_PARTITION = 'persist:shanzigeo-platforms';
const PLATFORM_LABELS = {
  sohu: '搜狐号', toutiao: '今日头条', netease: '网易号', wechat: '微信公众号',
  douyin: '抖音', xiaohongshu: '小红书', eastmoney: '东方财富', ths: '同花顺',
  official: '官网', doubao: '豆包', deepseek: 'DeepSeek',
};
const EXAM_ENGINES = ['doubao', 'deepseek'];
const TAB_LIMIT = 10;
const WEB_PREFERENCES = {
  nodeIntegration: false, sandbox: true, contextIsolation: true, webSecurity: true,
  backgroundThrottling: process.env.SHANZIGEO_SHELL_QA !== '1' && process.env.SHANZIGEO_SHELL_HIDDEN !== '1',
};

const userData = process.env.SHANZIGEO_SHELL_DATA_DIR || path.join(app.getPath('appData'), 'ShanziGEO-Electron');
fs.mkdirSync(userData, { recursive: true });
app.setPath('userData', userData);
app.setName('山子高科 GEO 工作台');
app.setAppUserModelId('Shanzi.GEO.Workbench');

const appIcon = app.isPackaged
  ? path.join(process.resourcesPath, 'app', 'app_icon.ico')
  : path.join(__dirname, '..', 'assets', 'app_icon.ico');

const splitWidthPath = path.join(userData, 'browser-width.txt');
const storedSplitWidth = (() => {
  try { return Number(fs.readFileSync(splitWidthPath, 'utf8')); }
  catch (_) { return 0; }
})();
let window;
let backend;
let videoStudio;
let backendOrigin;
let panelBounds;
let splitWidth = Number.isInteger(storedSplitWidth) && storedSplitWidth >= 300 && storedSplitWidth <= 3000
  ? storedSplitWidth : null;
let browserFullscreen = false;
const pages = [];
let selectedView;
let examRunning = false;
const nativeToken = randomBytes(32).toString('hex');
const startupTime = Date.now();
let cdpPort;
app.commandLine.appendSwitch('remote-debugging-address', '127.0.0.1');
app.commandLine.appendSwitch('remote-debugging-port', '0');

function readCdpPort() {
  const activePort = path.join(userData, 'DevToolsActivePort');
  return new Promise((resolve, reject) => {
    const interval = setInterval(() => {
      try {
        const fresh = fs.statSync(activePort).mtimeMs >= startupTime - 1000;
        const port = Number(fs.readFileSync(activePort, 'utf8').split(/\r?\n/)[0]);
        if (fresh && Number.isInteger(port) && port > 0 && port < 65536) {
          clearInterval(interval);
          resolve(port);
          return;
        }
      } catch (_) {
        // The renderer process writes the port file during startup.
      }
      if (Date.now() - startupTime > 12_000) {
        clearInterval(interval);
        reject(new Error('桌面浏览器的本地连接没有就绪。'));
      }
    }, 100);
  });
}

function startBackend() {
  const packed = path.join(process.resourcesPath, 'backend', 'ShanziGEO.exe');
  const devRoot = path.resolve(__dirname, '../..');
  const exe = fs.existsSync(packed) ? packed : (process.env.SHANZIGEO_PYTHON || 'python');
  const args = exe === packed ? ['--serve-only'] : [path.join(devRoot, 'desktop_app', 'main.py'), '--serve-only'];
  const previousData = exe === packed
    ? path.resolve(path.dirname(app.getPath('exe')), '../ShanziGEO/data')
    : path.join(devRoot, 'dist', 'ShanziGEO', 'data');
  const dataDir = process.env.SHANZIGEO_DATA_DIR || (fs.existsSync(previousData) ? previousData : path.join(userData, 'workbench'));
  backend = spawn(exe, args, {
    cwd: exe === packed ? path.dirname(packed) : devRoot,
    windowsHide: true,
    env: {
      ...process.env, PYTHONUNBUFFERED: '1', SHANZIGEO_DATA_DIR: dataDir,
      SHANZIGEO_NATIVE_TOKEN: nativeToken, SHANZIGEO_NATIVE_CDP_PORT: String(cdpPort),
      PLAYWRIGHT_NODEJS_PATH: app.getPath('exe'), ELECTRON_RUN_AS_NODE: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return new Promise((resolve, reject) => {
    let output = '';
    const timeout = setTimeout(() => reject(new Error('工作台后端启动超时。')), 25_000);
    const fail = () => { clearTimeout(timeout); reject(new Error('工作台后端未启动，请检查本地应用日志。')); };
    backend.on('error', fail);
    backend.on('exit', fail);
    backend.stderr.resume();
    backend.stdout.on('data', data => {
      output = (output + data.toString('utf8')).slice(-8192);
      const match = output.match(/(?:^|\n)READY (http:\/\/127\.0\.0\.1:\d+)\s/);
      if (match) { clearTimeout(timeout); resolve(match[1]); }
    });
  });
}

function webUrl(input) {
  if (typeof input !== 'string' || input.length > 4096) return null;
  try {
    const url = new URL(input);
    if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && url.origin !== backendOrigin) {
      return url.href;
    }
  } catch (_) { /* A typed address may be incomplete. */ }
  return null;
}

function activeView() {
  return selectedView;
}

function sendState(message = '') {
  if (!window || window.isDestroyed()) return;
  const current = activeView()?.webContents;
  const history = current?.navigationHistory;
  window.webContents.send('geo:state', {
    url: current?.getURL() || '', loading: current?.isLoadingMainFrame() || false,
    back: Boolean(history?.canGoBack()), forward: Boolean(history?.canGoForward()),
    splitWidth, browserFullscreen,
    activeTab: current?.id ?? null,
    tabs: pages.filter(view => !view.webContents.isDestroyed()).map(view => {
      const contents = view.webContents;
      return { id: contents.id, title: view.tabLabel || contents.getTitle() || '新标签' };
    }),
    message,
  });
}

function placeActiveView() {
  const active = activeView();
  if (!window || window.isDestroyed()) return;
  for (const view of pages) view.setVisible(view === active && Boolean(panelBounds));
  if (!active || !panelBounds) return;
  const [width, height] = window.getContentSize();
  const x = Math.min(width, Math.max(0, panelBounds.x));
  const y = Math.min(height, Math.max(0, panelBounds.y));
  const bounds = { x, y, width: Math.max(0, Math.min(width - x, panelBounds.width)), height: Math.max(0, Math.min(height - y, panelBounds.height)) };
  const previous = active.getBounds();
  if (Object.keys(bounds).some(key => bounds[key] !== previous[key])) active.setBounds(bounds);
}

function selectView(view) {
  selectedView = view;
  placeActiveView();
  sendState();
}

function toggleBrowserFullscreen(enabled) {
  if (!window || window.isDestroyed() || enabled === browserFullscreen) return;
  if (enabled && !panelBounds) return;
  browserFullscreen = enabled;
  window.setFullScreen(enabled);
  sendState();
}

function browserFullscreenShortcut(event, input) {
  if (input.type !== 'keyDown' || input.isAutoRepeat || input.alt || input.control || input.meta || input.shift) return;
  if ((input.key === 'F11' && (panelBounds || browserFullscreen)) || (input.key === 'Escape' && browserFullscreen)) {
    event.preventDefault();
    toggleBrowserFullscreen(!browserFullscreen);
  }
}

function createPlatformView(options = {}, { key, label, activate = true, exam = false } = {}) {
  const view = new WebContentsView({
    ...(options.webContents ? { webContents: options.webContents } : {}),
    webPreferences: {
      ...options.webPreferences, ...WEB_PREFERENCES, partition: PLATFORM_PARTITION, preload: undefined,
      ...(exam ? { backgroundThrottling: false } : {}),
    },
  });
  const contents = view.webContents;
  contents.on('before-input-event', browserFullscreenShortcut);
  view.tabKey = key;
  view.tabLabel = label;
  contents.setWindowOpenHandler(({ url }) => {
    if (pages.length >= TAB_LIMIT || (url !== 'about:blank' && !webUrl(url))) return { action: 'deny' };
    return {
      action: 'allow',
      overrideBrowserWindowOptions: { webPreferences: WEB_PREFERENCES },
      createWindow: popup => createPlatformView(popup).webContents,
    };
  });
  const allowNavigation = (event, url) => {
    const target = event.url || url;
    if (target !== 'about:blank' && !webUrl(target)) event.preventDefault();
  };
  contents.on('will-navigate', allowNavigation);
  contents.on('will-redirect', allowNavigation);
  contents.on('content-bounds-updated', event => event.preventDefault());
  for (const name of ['did-start-loading', 'did-stop-loading', 'did-navigate', 'did-navigate-in-page', 'page-title-updated']) {
    contents.on(name, () => { if (activeView() === view) sendState(); });
  }
  contents.on('did-fail-load', (_event, code, _message, _url, isMainFrame) => {
    if (isMainFrame && code !== -3 && activeView() === view) sendState('页面加载失败，请检查网址或网络。');
  });
  contents.on('destroyed', () => {
    const index = pages.indexOf(view);
    if (index !== -1) pages.splice(index, 1);
    if (window && !window.isDestroyed()) window.contentView.removeChildView(view);
    if (selectedView === view) selectView(pages[Math.min(index, pages.length - 1)]);
    else sendState();
  });
  const mount = () => {
    if (!window || window.isDestroyed() || contents.isDestroyed()) return;
    window.contentView.addChildView(view);
    pages.push(view);
    if (activate || !selectedView) selectView(view);
    else {
      view.setVisible(false);
      sendState();
    }
  };
  // Let Chromium finish creating a renderer-initiated popup before mounting its view.
  if (options.webContents) setImmediate(mount);
  else mount();
  return view;
}

function trusted(event) {
  return window && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame
    && event.senderFrame.url.startsWith(`${backendOrigin}/`);
}

function safeBounds(bounds) {
  const keys = ['x', 'y', 'width', 'height'];
  if (!bounds || !keys.every(key => Number.isFinite(bounds[key]))) return null;
  return Object.fromEntries(keys.map(key => [key, Math.round(bounds[key])]));
}

ipcMain.on('geo:bounds', (event, bounds) => {
  if (!trusted(event)) return;
  if (bounds === null) {
    panelBounds = null;
    if (browserFullscreen) toggleBrowserFullscreen(false);
  }
  else panelBounds = safeBounds(bounds) ?? panelBounds;
  placeActiveView();
});

ipcMain.on('geo:studio-bounds', (event, bounds) => {
  if (trusted(event)) videoStudio?.setBounds(safeBounds(bounds));
});

ipcMain.handle('geo:studio', async (event, action, draft) => {
  if (!trusted(event) || !videoStudio) return { ok: false, message: '视频工作台不可用。' };
  try {
    if (action === 'open') await videoStudio.open();
    else if (action === 'stop') await videoStudio.stop();
    else if (action === 'draft') {
      if (typeof draft !== 'string' || !draft.trim() || draft.length > 100_000) {
        return { ok: false, message: '请先填写稿件，视频素材最多 10 万字。' };
      }
      if (!await videoStudio.takeDraft(draft)) {
        return { ok: false, message: '视频工作台已有素材，请先清空原素材，再试一次。' };
      }
    } else return { ok: false, message: '不支持此视频工作台操作。' };
    return { ok: true };
  } catch (error) {
    return { ok: false, message: error.message };
  }
});

ipcMain.handle('geo:navigate', async (event, target) => {
  if (!trusted(event)) throw new Error('无法打开地址。');
  const platform = Object.hasOwn(PLATFORM_URLS, target?.platform) ? target.platform : '';
  const url = webUrl(PLATFORM_URLS[platform] || target?.url);
  if (!url) return { ok: false, message: '请输入有效网址或选择平台。' };
  const key = platform || (target.newTab ? url : undefined);
  let view = key ? pages.find(item => item.tabKey === key) : activeView();
  if (!view) {
    if (pages.length >= TAB_LIMIT) return { ok: false, message: '请先关闭一个标签页。' };
    view = createPlatformView({}, { key, label: PLATFORM_LABELS[platform] });
  } else {
    selectView(view);
    if (key && view.webContents.getURL()) return { ok: true };
  }
  try {
    if (view.webContents.getURL() !== url) await view.webContents.loadURL(url);
    return { ok: true };
  } catch (_) {
    return { ok: false, message: '页面暂未载入，可以在右栏重试。' };
  }
});

ipcMain.handle('geo:action', (event, action, value) => {
  if (!trusted(event)) return;
  if (action === 'state') {
    sendState();
    return;
  }
  if (action === 'fullscreen') {
    toggleBrowserFullscreen(!browserFullscreen);
    return;
  }
  if (action === 'split-width') {
    if (value !== null && (!Number.isInteger(value) || value < 300 || value > 3000)) return;
    splitWidth = value;
    try {
      fs.writeFileSync(splitWidthPath, splitWidth === null ? '' : String(splitWidth), 'utf8');
    } catch (_) {
      return { ok: false, message: '本次宽度已应用，暂时无法保存到下次。' };
    }
    return;
  }
  if (action === 'new') {
    if (pages.length >= TAB_LIMIT) return { ok: false, message: '请先关闭一个标签页。' };
    createPlatformView();
    return;
  }
  if (action === 'select' || action === 'remove') {
    const view = pages.find(item => item.webContents.id === value);
    if (view && action === 'select') selectView(view);
    if (view && action === 'remove') view.webContents.close({ waitForBeforeUnload: true });
    return;
  }
  const current = activeView()?.webContents;
  if (!current) return;
  const history = current.navigationHistory;
  if (action === 'back' && history.canGoBack()) history.goBack();
  if (action === 'forward' && history.canGoForward()) history.goForward();
  if (action === 'reload') current.reload();
});

function examUrl(engine) {
  const fixture = process.env.SHANZIGEO_SHELL_QA === '1' && webUrl(process.env.SHANZIGEO_EXAM_FIXTURE_ORIGIN);
  return fixture && new URL(fixture).hostname === '127.0.0.1'
    ? new URL(`/${engine}`, fixture).href : PLATFORM_URLS[engine];
}

function examView(engine) {
  return pages.find(view => view.tabKey === `exam-${engine}`);
}

ipcMain.handle('geo:exam', async (event, request) => {
  if (!trusted(event)) return { ok: false, message: '考试入口不可用。' };
  const mode = request?.mode;
  const question = typeof request?.question === 'string' ? request.question.trim() : '';
  if (!['open', 'run', 'collect'].includes(mode) || (mode === 'run' && (!question || question.length > 3000))) {
    return { ok: false, message: '请选择一题再开始考试。' };
  }
  if (examRunning) return { ok: false, message: '本题仍在运行。' };
  if (mode !== 'collect' && pages.length + EXAM_ENGINES.filter(engine => !examView(engine)).length > TAB_LIMIT) {
    return { ok: false, message: '请关闭几个标签，为两个考场留位置。' };
  }
  examRunning = true;
  try {
    const targets = EXAM_ENGINES.map(engine => {
      let view = examView(engine);
      if (!view && mode !== 'collect') {
        view = createPlatformView({}, { key: `exam-${engine}`, label: PLATFORM_LABELS[engine] + ' · 考试', activate: false, exam: true });
      }
      return { engine, view, startUrl: examUrl(engine) };
    });
    const results = {};
    await Promise.all(targets.map(async ({ engine, view, startUrl }) => {
      try {
        if (!view) throw new Error('对应考试标签已关闭');
        const contents = view.webContents;
        if (mode === 'run' || (mode === 'open' && !contents.getURL())) await contents.loadURL(startUrl);
        if (mode === 'run') {
          results[engine] = await runExam(contents, engine, startUrl, question, message => {
            if (!window?.isDestroyed()) window?.webContents.send('geo:exam-progress', { engine, message });
          });
        }
        if (mode === 'collect') results[engine] = await collectExam(contents, engine, startUrl);
      } catch (error) {
        results[engine] = { status: 'review', message: error.message, sources: [], answerLinks: [], text: '' };
      }
      if (results[engine] && !window?.isDestroyed()) window?.webContents.send('geo:exam-progress', { engine, result: results[engine] });
    }));
    return { ok: true, results };
  } finally {
    examRunning = false;
  }
});

ipcMain.handle('geo:fill', async (event, draft) => {
  if (!trusted(event)) return { ok: false, message: '填稿入口不可用。' };
  const current = activeView()?.webContents;
  const url = current && webUrl(current.getURL());
  if (!url || current.isLoadingMainFrame()) return { ok: false, message: '请先打开右栏发稿编辑页。' };
  const hostname = new URL(url).hostname;
  const approved = Object.values(PLATFORM_URLS).some(known => new URL(known).hostname === hostname);
  if (!approved && !(process.env.SHANZIGEO_SHELL_QA === '1' && hostname === '127.0.0.1')) {
    return { ok: false, message: '当前页面没有可用的发稿平台配置。' };
  }
  const { title, content } = draft || {};
  if (typeof title !== 'string' || typeof content !== 'string' || !title.trim() || !content.trim()) {
    return { ok: false, message: '请在左边先填好标题和正文。' };
  }
  let attached = false;
  let targetId;
  try {
    if (!current.debugger.isAttached()) { current.debugger.attach('1.3'); attached = true; }
    const { targetInfo } = await current.debugger.sendCommand('Target.getTargetInfo');
    targetId = targetInfo.targetId;
  } catch (_) {
    return { ok: false, message: '暂时无法接管当前页面，请重试。' };
  } finally {
    if (attached && !current.isDestroyed() && current.debugger.isAttached()) current.debugger.detach();
  }
  if (current !== activeView()?.webContents || current.getURL() !== url) {
    return { ok: false, message: '右栏页面已经切换，请重新点填稿。' };
  }
  try {
    const response = await fetch(`${backendOrigin}/api/desktop/draft`, {
      method: 'POST', signal: AbortSignal.timeout(18_000),
      headers: { 'content-type': 'application/json', 'x-shanzigeo-native': nativeToken },
      body: JSON.stringify({ target_id: targetId, url, title: title.trim(), content: content.trim() }),
    });
    const result = await response.json();
    return response.ok ? result : { ok: false, message: '填稿失败，请检查右栏是否还在发稿页。' };
  } catch (_) {
    return { ok: false, message: '无法连接本地填稿服务。' };
  }
});

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => {
    if (!window || window.isDestroyed()) return;
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
  });
  app.whenReady().then(async () => {
    window = new BrowserWindow({
      width: 1210, height: 935, minWidth: 760, minHeight: 620,
      backgroundColor: '#f6f5f3', autoHideMenuBar: true, show: false,
      icon: appIcon,
      webPreferences: { ...WEB_PREFERENCES, preload: path.join(__dirname, 'preload.cjs') },
    });
    videoStudio = createStudio(app, window, WEB_PREFERENCES);
    window.removeMenu();
    window.on('leave-full-screen', () => {
      if (!browserFullscreen) return;
      browserFullscreen = false;
      sendState();
    });
    window.on('closed', () => {
      window = null;
      for (const view of [...pages]) if (!view.webContents.isDestroyed()) view.webContents.close();
    });
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    window.webContents.on('before-input-event', browserFullscreenShortcut);
    window.webContents.on('will-navigate', (event, url) => {
      if (!(event.url || url || '').startsWith(`${backendOrigin}/`)) event.preventDefault();
    });
    cdpPort = await readCdpPort();
    backendOrigin = await startBackend();
    await window.loadURL(`${backendOrigin}/`);
    if (process.env.SHANZIGEO_SHELL_HIDDEN !== '1') {
      if (process.env.SHANZIGEO_SHELL_QA === '1') window.showInactive();
      else window.show();
    }
  }).catch(error => {
    if (process.env.SHANZIGEO_SHELL_HIDDEN === '1') console.error(error.message);
    else dialog.showErrorBox('山子 GEO 启动失败', error.message);
    app.quit();
  });
}

app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => {
  videoStudio?.shutdown();
  if (backend && backend.exitCode === null) backend.kill();
});
