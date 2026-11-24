(() => {
  const native = window.geoDesktop;
  if (!native) {
    window.workbenchBrowser = {
      async open(target = {}) {
        try {
          const result = await apiFetch('/api/browser/open', { method: 'POST', body: target });
          if (!result.ok) showToast(result.message || '无法打开登录浏览器', true);
        } catch (error) {
          showToast(error.message, true);
        }
      },
    };
    return;
  }

  const panel = document.getElementById('browserPanel');
  const shell = panel.parentElement;
  const viewport = document.getElementById('browserViewport');
  const divider = document.getElementById('browserDivider');
  const sidebar = shell.querySelector('.sidebar');
  const address = document.getElementById('browserAddress');
  const platform = document.getElementById('browserPlatform');
  const status = document.getElementById('browserStatus');
  const tabs = document.getElementById('browserTabs');
  const launchers = [document.getElementById('topBrowserButton'), document.getElementById('sidebarBrowserButton')];
  const controls = Object.fromEntries([...panel.querySelectorAll('[data-browser-action]')]
    .map(button => [button.dataset.browserAction, button]));
  const examBox = document.getElementById('examResults');
  const examStart = document.getElementById('openExamTabs');
  const studioViewport = document.getElementById('videoStudioViewport');
  const studioStatus = document.getElementById('videoStudioStatus');
  const studioStop = document.getElementById('stopVideoStudio');
  const studioRetry = document.getElementById('retryVideoStudio');
  const studioDraft = document.getElementById('sendVideoDraft');
  const engines = { doubao: '豆包', deepseek: 'DeepSeek' };
  let examState = {};
  let running = false;
  let question = '';
  let currentTab = null;
  let renderedTabs = '';
  let fullscreen = false;
  let preferredWidth = null;
  let receivedWidth = false;
  let layoutFrame = 0;
  let drag = null;
  let studioActive = false;
  let studioLoaded = false;
  let studioOpening = false;

  document.documentElement.classList.add('native-browser');
  setExternalAction('ledger_only');

  function widthLimits() {
    const style = getComputedStyle(shell);
    const padding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
    const sidebarWidth = sidebar.getBoundingClientRect().width;
    const gaps = parseFloat(style.columnGap) * (sidebarWidth ? 3 : 2);
    const mainWidth = parseFloat(style.getPropertyValue('--main-min-width'));
    const available = shell.clientWidth - padding - sidebarWidth - gaps - divider.offsetWidth - mainWidth;
    return { min: 300, max: Math.max(300, Math.min(3000, Math.floor(available))) };
  }

  function fitWidth(width) {
    const { min, max } = widthLimits();
    return Math.round(Math.max(min, Math.min(max, width)));
  }

  function syncLayout() {
    layoutFrame = 0;
    if (panel.hidden || studioActive) return;
    if (!fullscreen) {
      const layoutWidth = fitWidth(preferredWidth ?? Math.max(330, Math.min(440, innerWidth * 0.34)));
      const width = `${layoutWidth}px`;
      if (shell.style.getPropertyValue('--side-browser-width') !== width) shell.style.setProperty('--side-browser-width', width);
      const { min, max } = widthLimits();
      divider.setAttribute('aria-valuemin', String(min));
      divider.setAttribute('aria-valuemax', String(max));
      divider.setAttribute('aria-valuenow', String(layoutWidth));
      divider.setAttribute('aria-valuetext', `${layoutWidth} 像素`);
    }
    const { left, top, width, height } = viewport.getBoundingClientRect();
    native.setBounds({ x: left, y: top, width, height });
  }

  function scheduleLayout() {
    if (!layoutFrame) layoutFrame = requestAnimationFrame(syncLayout);
  }

  function updateFullscreen(enabled) {
    if (fullscreen === enabled) return;
    const active = document.activeElement;
    fullscreen = enabled;
    shell.classList.toggle('browser-fullscreen', enabled);
    divider.hidden = panel.hidden || enabled;
    controls.fullscreen.setAttribute('aria-pressed', String(enabled));
    controls.fullscreen.textContent = enabled ? '还原分栏' : '全屏';
    controls.fullscreen.title = enabled ? '还原分栏（Esc）' : '全屏浏览器（F11）';
    if (active === divider) controls.fullscreen.focus();
    scheduleLayout();
  }

  new ResizeObserver(scheduleLayout).observe(viewport);
  window.addEventListener('resize', scheduleLayout);

  function setPreferredWidth(width, save) {
    preferredWidth = width === null ? null : fitWidth(width);
    scheduleLayout();
    if (save) action('split-width', preferredWidth);
  }

  divider.addEventListener('pointerdown', event => {
    if (event.button !== 0 || drag) return;
    divider.focus({ preventScroll: true });
    divider.setPointerCapture(event.pointerId);
    drag = { id: event.pointerId, startX: event.clientX, startWidth: panel.offsetWidth };
    shell.classList.add('browser-dragging');
  });
  divider.addEventListener('pointermove', event => {
    if (drag?.id === event.pointerId) setPreferredWidth(drag.startWidth + drag.startX - event.clientX, false);
  });
  function finishDrag(event) {
    if (drag?.id !== event.pointerId) return;
    drag = null;
    shell.classList.remove('browser-dragging');
    action('split-width', preferredWidth);
  }
  divider.addEventListener('pointerup', finishDrag);
  divider.addEventListener('lostpointercapture', finishDrag);
  divider.addEventListener('dblclick', () => setPreferredWidth(null, true));
  divider.addEventListener('keydown', event => {
    const step = event.shiftKey ? 80 : 24;
    const width = panel.offsetWidth;
    const { min, max } = widthLimits();
    const choices = { ArrowLeft: width + step, ArrowRight: width - step, Home: min, End: max };
    if (!Object.hasOwn(choices, event.key)) return;
    event.preventDefault();
    setPreferredWidth(choices[event.key], true);
  });

  function setOpen(enabled) {
    panel.hidden = !enabled;
    divider.hidden = !enabled || fullscreen;
    shell.classList.toggle('browser-open', enabled);
    launchers.forEach(button => button.setAttribute('aria-expanded', String(enabled)));
    if (enabled) scheduleLayout();
    else {
      updateFullscreen(false);
      native.setBounds(null);
    }
  }

  function fitStudio() {
    if (!studioActive || !studioLoaded) {
      native.setStudioBounds(null);
      return;
    }
    const { left, top, width, height } = studioViewport.getBoundingClientRect();
    native.setStudioBounds({ x: left, y: top, width, height });
  }

  new ResizeObserver(fitStudio).observe(studioViewport);
  window.addEventListener('resize', fitStudio);

  function resetStudio(message) {
    studioLoaded = false;
    studioStop.hidden = true;
    studioRetry.hidden = false;
    studioStatus.textContent = message;
    fitStudio();
  }

  async function openStudio() {
    if (studioOpening || studioLoaded) return;
    studioOpening = true;
    studioRetry.hidden = true;
    studioStatus.textContent = '正在启动短视频工作台…';
    try {
      const result = await native.studio('open');
      if (!result.ok) {
        resetStudio(result.message);
        return;
      }
      studioLoaded = true;
      studioStop.hidden = false;
      studioStatus.textContent = '';
      requestAnimationFrame(fitStudio);
    } catch (error) {
      resetStudio(error.message);
    } finally {
      studioOpening = false;
    }
  }

  function setSection(section) {
    const active = section === 'video';
    if (active === studioActive) return;
    studioActive = active;
    shell.classList.toggle('video-active', active);
    if (active) {
      native.setBounds(null);
      openStudio();
      requestAnimationFrame(fitStudio);
    } else {
      fitStudio();
      scheduleLayout();
    }
  }

  async function open(target = {}) {
    setOpen(true);
    if (target.platform || target.url) {
      try {
        const result = await native.navigate(target);
        if (!result.ok) showToast(result.message, true);
      } catch (error) {
        showToast(error.message, true);
      }
    }
  }

  async function action(name, tabId) {
    try {
      const result = await native.action(name, tabId);
      if (result?.ok === false) showToast(result.message, true);
    } catch (error) {
      showToast(error.message, true);
    }
  }

  function renderTabs(state) {
    const next = JSON.stringify([state.activeTab, state.tabs]);
    if (next === renderedTabs) return;
    renderedTabs = next;
    tabs.replaceChildren(...state.tabs.map(item => {
      const tab = document.createElement('div');
      tab.className = 'browser-tab';
      tab.dataset.active = String(item.id === state.activeTab);
      const openTab = document.createElement('button');
      openTab.type = 'button';
      openTab.setAttribute('role', 'tab');
      openTab.setAttribute('aria-selected', tab.dataset.active);
      openTab.textContent = item.title;
      openTab.title = item.title;
      openTab.addEventListener('click', () => action('select', item.id));
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'browser-tab-close';
      remove.setAttribute('aria-label', '关闭 ' + item.title);
      remove.textContent = '×';
      remove.addEventListener('click', () => action('remove', item.id));
      tab.append(openTab, remove);
      return tab;
    }));
    tabs.hidden = !state.tabs.length;
  }

  function renderExamResults() {
    const title = question || '当前考试';
    examBox.hidden = false;
    examBox.innerHTML = `
      <div class="exam-results-heading">
        <strong>${esc(title)}</strong>
        <button type="button" class="btn btn-glass btn-xs" id="collectExamResult" ${running ? 'disabled' : ''}>回收当前答案</button>
      </div>
      ${Object.entries(engines).map(([key, name]) => {
        const result = examState[key] || {};
        const links = (result.sources || []).filter(item => httpLink(item.url));
        const otherLinks = (result.answerLinks || []).filter(item =>
          httpLink(item.url) && !links.some(link => link.url === item.url));
        const list = items => items.map(item => {
          const url = httpLink(item.url);
          return `<li><button type="button" class="source-link line-ellipsis" data-source-url="${esc(url)}" title="${esc(url)}">${esc(item.title || url)}</button></li>`;
        }).join('');
        return `
          <section class="exam-engine-result">
            <div class="exam-engine-heading">
              <strong>${name}</strong>
              ${links.length ? `<button type="button" class="btn btn-glass btn-xs" data-copy-exam="${key}">复制 ${links.length} 条来源</button>` : ''}
            </div>
            <p class="field-hint">${esc(result.message || '等待处理…')}</p>
            ${links.length ? `<ol>${list(links)}</ol>` : ''}
            ${otherLinks.length ? `<details><summary>回答内的其他链接（待核对）</summary><ul>${list(otherLinks)}</ul></details>` : ''}
            ${result.text ? `<details><summary>查看完整回答</summary><p class="exam-answer">${esc(result.text)}</p></details>` : ''}
          </section>`;
      }).join('')}
    `;
  }

  function setExamRunning(enabled) {
    running = enabled;
    examStart.disabled = enabled;
    document.querySelectorAll('[data-exam-run]').forEach(button => { button.disabled = enabled; });
  }

  async function conductExam(mode, index) {
    if (running) return;
    const item = normalizeExamQuestions().questions[index];
    if (mode === 'run' && !item?.text) return;
    if (mode === 'run') question = item.text;
    setOpen(true);
    setExamRunning(true);
    if (mode !== 'open') {
      examState = Object.fromEntries(Object.keys(engines).map(engine => [engine,
        { message: mode === 'run' ? '正在打开新对话…' : '正在回收当前页面…' }]));
      renderExamResults();
    }
    try {
      const response = await native.exam({ mode, question });
      if (!response.ok) {
        if (mode !== 'open') {
          for (const key of Object.keys(engines)) examState[key] = { message: response.message };
        }
        showToast(response.message, true);
      } else {
        Object.assign(examState, response.results);
        if (mode === 'open') showToast('请切换到豆包和 DeepSeek 标签，分别确认登录。');
      }
    } catch (error) {
      if (mode !== 'open') {
        for (const key of Object.keys(engines)) examState[key] = { message: error.message };
      }
      showToast(error.message, true);
    } finally {
      setExamRunning(false);
      if (mode !== 'open') renderExamResults();
    }
  }

  window.workbenchBrowser = { open, setSection, runExam: index => conductExam('run', index) };

  studioRetry.addEventListener('click', openStudio);
  studioStop.addEventListener('click', async () => {
    studioStop.disabled = true;
    try {
      const result = await native.studio('stop');
      if (result.ok) resetStudio('视频工作台已关闭。');
      else showToast(result.message, true);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      studioStop.disabled = false;
    }
  });
  studioDraft.addEventListener('click', async () => {
    const draft = ['composeTitle', 'composeContent']
      .map(id => document.getElementById(id).value.trim()).filter(Boolean).join('\n\n');
    if (!draft) return showToast('请先填写文章标题或正文。', true);
    studioDraft.disabled = true;
    switchView('video');
    try {
      const result = await native.studio('draft', draft);
      showToast(result.ok ? '已将稿件带入视频提示词的素材栏。' : result.message, !result.ok);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      studioDraft.disabled = false;
    }
  });
  native.onStudioClosed(() => {
    if (studioLoaded) resetStudio('视频工作台已退出。');
  });

  controls.close.addEventListener('click', () => setOpen(false));
  for (const name of ['new', 'back', 'forward', 'reload', 'fullscreen']) {
    controls[name].addEventListener('click', () => action(name));
  }
  controls.new.addEventListener('click', () => address.focus());

  controls.fill.addEventListener('click', async () => {
    controls.fill.disabled = true;
    try {
      const result = await native.fillDraft({
        title: document.getElementById('composeTitle').value,
        content: document.getElementById('composeContent').value,
      });
      showToast(result.message, !result.ok);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      controls.fill.disabled = false;
    }
  });

  platform.addEventListener('change', () => {
    const selected = platform.value;
    platform.value = '';
    if (selected) open({ platform: selected });
  });
  document.getElementById('browserAddressForm').addEventListener('submit', event => {
    event.preventDefault();
    const url = address.value.trim();
    if (!url) return;
    address.blur();
    open({ url: /^[a-z]+:\/\//i.test(url) ? url : 'https://' + url });
  });

  native.onState(state => {
    if (!receivedWidth) {
      preferredWidth = state.splitWidth;
      receivedWidth = true;
      scheduleLayout();
    }
    updateFullscreen(state.browserFullscreen);
    if (document.activeElement !== address || currentTab !== state.activeTab) address.value = state.url;
    currentTab = state.activeTab;
    renderTabs(state);
    controls.back.disabled = !state.back;
    controls.forward.disabled = !state.forward;
    controls.reload.disabled = !state.url;
    status.textContent = state.loading ? '正在载入…' : '选择平台或输入网址。';
    if (state.message) showToast(state.message, true);
  });
  action('state');
  native.onExamProgress(({ engine, message, result }) => {
    examState[engine] = result || { message };
    renderExamResults();
  });

  examStart.addEventListener('click', () => conductExam('open'));
  examBox.addEventListener('click', async event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.id === 'collectExamResult') conductExam('collect');
    if (button.dataset.sourceUrl) open({ url: button.dataset.sourceUrl, newTab: true });
    if (button.dataset.copyExam) {
      const urls = (examState[button.dataset.copyExam]?.sources || []).map(item => item.url);
      try {
        await navigator.clipboard.writeText(urls.join('\n'));
        showToast('来源链接已复制');
      } catch (error) {
        showToast('无法访问剪贴板', true);
      }
    }
  });
})();
