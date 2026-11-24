'use strict';

const { WebContentsView } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function studioWorkspace(app) {
  return path.resolve(process.env.SHANZIGEO_VIDEO_WORKFLOW_DIR || (app.isPackaged
    ? path.join(path.dirname(app.getPath('exe')), '..', '..', 'video-workflow')
    : path.join(__dirname, '..', '..', 'video-workflow')));
}

function createStudio(app, window, webPreferences) {
  const workspace = studioWorkspace(app);
  let child;
  let origin;
  let view;
  let bounds;
  let pending;
  let stopping;

  function startServer() {
    const configPath = path.join(workspace, 'config.json');
    if (!fs.existsSync(path.join(workspace, 'studio_server.py')) || !fs.existsSync(configPath)) {
      throw new Error('找不到 VideoFlow 工程目录。请将已有 video-workflow 放在 GEO 项目目录。');
    }
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''));
    const python = process.env.SHANZIGEO_VIDEO_PYTHON || config.python || 'python';
    if (path.isAbsolute(python) && !fs.existsSync(python)) {
      throw new Error('VideoFlow 配置的 Python 已找不到，请检查 video-workflow/config.json。');
    }
    const proc = spawn(python, ['-u', path.join(__dirname, 'studio_host.py'), workspace], {
      cwd: workspace, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUNBUFFERED: '1',
        VIDEOFLOW_THREEJS_NODE: app.getPath('exe'),
        ELECTRON_RUN_AS_NODE: '1',
      },
    });
    child = proc;
    proc.stdin.on('error', () => {});
    proc.stderr.resume();
    return new Promise((resolve, reject) => {
      let line = '';
      const timeout = setTimeout(() => reject(new Error('视频工作台启动超时。')), 30_000);
      const fail = () => {
        clearTimeout(timeout);
        reject(new Error('视频工作台未能启动，请检查工程中的 Python 和依赖。'));
      };
      proc.on('error', fail);
      proc.once('close', () => {
        fail();
        if (child !== proc) return;
        child = undefined;
        origin = undefined;
        releaseView();
        if (!window.isDestroyed()) window.webContents.send('geo:studio-closed');
      });
      proc.stdout.on('data', data => {
        line = (line + data.toString('utf8')).slice(-4096);
        const ready = line.match(/(?:^|\n)VIDEOFLOW_READY (http:\/\/127\.0\.0\.1:\d+)\s/);
        if (ready) {
          clearTimeout(timeout);
          resolve(ready[1]);
        }
      });
    });
  }

  function setBounds(rect) {
    bounds = rect;
    if (!view || window.isDestroyed()) return;
    view.setVisible(Boolean(rect));
    if (!rect) return;
    const [width, height] = window.getContentSize();
    const x = Math.max(0, Math.min(rect.x, width));
    const y = Math.max(0, Math.min(rect.y, height));
    const next = { x, y, width: Math.max(0, Math.min(width - x, rect.width)), height: Math.max(0, Math.min(height - y, rect.height)) };
    const last = view.getBounds();
    if (Object.keys(next).some(key => next[key] !== last[key])) view.setBounds(next);
  }

  function releaseView() {
    const active = view;
    view = undefined;
    if (!active) return;
    if (!window.isDestroyed()) window.contentView.removeChildView(active);
    if (!active.webContents.isDestroyed()) active.webContents.close();
  }

  async function open() {
    if (stopping) await stopping;
    if (pending) return pending;
    if (view) return;
    pending = (async () => {
      try {
        const url = origin || await startServer();
        let ready = false;
        for (let attempt = 0; attempt < 30 && !ready; attempt++) {
          try {
            ready = (await fetch(`${url}/_geo/status`, { signal: AbortSignal.timeout(1000) })).ok;
          } catch (_) { /* Wait for Uvicorn to begin accepting connections. */ }
          if (!ready) await new Promise(resolve => setTimeout(resolve, 120));
        }
        if (!ready || window.isDestroyed() || !child) throw new Error('无法连接视频工作台。');
        origin = url;
        const studio = new WebContentsView({ webPreferences: { ...webPreferences, partition: 'shanzigeo-video-studio' } });
        view = studio;
        const checkNavigation = (event, target) => {
          if (!(event.url || target || '').startsWith(`${url}/`)) event.preventDefault();
        };
        studio.webContents.on('will-navigate', checkNavigation);
        studio.webContents.on('will-redirect', checkNavigation);
        studio.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
        studio.webContents.on('content-bounds-updated', event => event.preventDefault());
        window.contentView.addChildView(studio);
        setBounds(bounds);
        await studio.webContents.loadURL(`${url}/`);
      } catch (error) {
        releaseView();
        if (origin) shutdown();
        else child?.kill();
        throw error;
      }
    })();
    try { await pending; } finally { pending = undefined; }
  }

  async function takeDraft(draft) {
    await open();
    return view.webContents.executeJavaScript(`(() => {
      const field = document.querySelector('#pmArticle');
      const tab = document.querySelector('[data-tab="prompt"]');
      if (!field || !tab) return false;
      tab.click();
      if (field.value.trim() && field.value !== ${JSON.stringify(draft)}) return false;
      field.value = ${JSON.stringify(draft)};
      field.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    })()`);
  }

  function shutdown() {
    const proc = child;
    if (!proc || stopping) return stopping;
    stopping = new Promise(resolve => {
      proc.once('close', resolve);
      proc.stdin.end();
    }).finally(() => { stopping = undefined; });
    return stopping;
  }

  async function stop() {
    if (pending) await pending;
    if (!child || !origin) return;
    const response = await fetch(`${origin}/_geo/status`, { signal: AbortSignal.timeout(3000) });
    if (!response.ok) throw new Error('无法确认视频任务状态，请稍后再试。');
    if ((await response.json()).running_jobs) throw new Error('有视频任务正在运行，完成后才能关闭。');
    if (view && await view.webContents.executeJavaScript(`(() => {
      const dirty = document.querySelector('#dirtyDot');
      const fields = ['#pmArticle', '#importJsonBox'];
      return Boolean(dirty && !dirty.classList.contains('hidden')) ||
        fields.some(selector => Boolean(document.querySelector(selector)?.value.trim()));
    })()`)) throw new Error('视频工作台还有未保存的改动或素材，请先保存工程并清空已使用的输入框。');
    releaseView();
    await shutdown();
  }

  return { open, setBounds, takeDraft, stop, shutdown };
}

module.exports = { createStudio };
