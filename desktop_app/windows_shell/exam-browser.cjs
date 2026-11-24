'use strict';

const METHODS = {
  doubao: {
    input: ['textarea[data-testid="chat_input_input"]', 'textarea[placeholder*="发消息"]', '[contenteditable="true"][data-placeholder*="发消息"]'],
    send: ['[data-testid="send_message_button"]', '[data-testid="chat_input_send_button"]'],
    answer: ['[data-message-role="assistant"]', '[data-testid="receive_message"]', '[data-testid="assistant-message"]', '[data-testid="message_content"]'],
    login: '[data-testid="to_login_button"]',
  },
  deepseek: {
    input: ['textarea#chat-input', 'textarea[placeholder*="DeepSeek"]', 'textarea[placeholder*="发消息"]'],
    send: ['[data-testid="send-message"]', '[role="button"][aria-label="发送"]'],
    answer: ['[data-message-role="assistant"]', '.ds-markdown'],
    login: 'input[placeholder*="手机号"]',
  },
};

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

async function examDOM(contents, selector, operation, previous = []) {
  if (contents.isDestroyed()) throw new Error('考试标签页已关闭');
  return contents.executeJavaScript(`(${inspectExamPage.toString()})(${JSON.stringify({ selector, operation, previous })})`);
}

function inspectExamPage({ selector, operation, previous }) {
  function visible(el) {
    if (!el?.getClientRects().length) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  }

  function firstVisible(selectors, element = document) {
    for (const query of selectors) {
      const item = [...element.querySelectorAll(query)].find(visible);
      if (item) return item;
    }
    return null;
  }

  const input = firstVisible(selector.input);
  const gate = firstVisible([selector.login, '[role="dialog"] input[placeholder*="验证码"]']);
  const searchLabel = /^(联网搜索|联网|搜索网页|联网检索|Search the web|Internet Search|Search)$/i;
  const searchable = [...document.querySelectorAll('button,[role="button"],[role="switch"],[role="checkbox"]')].filter(visible);
  const search = searchable.find(el => searchLabel.test(
    (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || '').trim()));
  const searchState = search?.getAttribute('aria-pressed') ?? search?.getAttribute('aria-checked') ??
    search?.getAttribute('data-state') ?? search?.getAttribute('data-active');

  if (operation === 'prepare') {
    if (gate || /sign[_-]?in|login/.test(location.pathname)) return { state: 'login' };
    if (!input) return { state: 'waiting' };
    if ((input.value ?? input.textContent).trim()) return { state: 'has_draft' };
    if (['false', 'unchecked', 'off'].includes(searchState)) search.click();
    input.focus({ preventScroll: true });
    return { state: 'ready', search: Boolean(search), url: location.href };
  }

  if (operation === 'send') {
    const send = firstVisible([...selector.send, 'button[aria-label="发送"]', 'button[title="发送"]', 'button[aria-label="Send"]']);
    if (send && !send.disabled && send.getAttribute('aria-disabled') !== 'true') {
      send.click();
      return true;
    }
    return false;
  }

  const answers = selector.answer.map(query => [...document.querySelectorAll(query)].filter(node => visible(node) && (node.innerText || '').trim()))
    .find(items => items.length) || [];
  const texts = answers.map(el => (el.innerText || '').trim());
  const answer = answers.at(-1);
  const text = texts.at(-1) || '';
  const sources = [];
  const answerLinks = [];

  function add(list, raw, title) {
    if (!raw) return;
    try {
      let url = new URL(raw, location.href);
      if (url.host === location.host && /^\/(link|redirect|jump)\b/.test(url.pathname)) {
        url = new URL(url.searchParams.get('url') || url.searchParams.get('target') || '');
      }
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password ||
          url.host === location.host || list.some(link => link.url === url.href) || list.length >= 50) return;
      list.push({ url: url.href, title: title.trim().slice(0, 200) });
    } catch (_) { /* Non-web references have no openable URL. */ }
  }

  const referenceZones = [
    '[data-testid*="citation"]', '[data-testid*="reference"]', '[data-testid*="search_source"]',
    '[data-testid*="search_result"]', '[class*="citation"]', '[class*="reference-list"]',
    '[aria-label="参考来源"]', '[aria-label="搜索结果"]', '[aria-label="引用来源"]', '[role="doc-bibliography"]',
  ].join(',');
  const inSources = [...document.querySelectorAll(referenceZones)].filter(visible);
  for (const zone of inSources) {
    const nodes = [zone, ...zone.querySelectorAll('a[href],[data-url],[data-href]')].filter(visible);
    for (const node of nodes) {
      add(sources, node.getAttribute('href') || node.dataset.url || node.dataset.href, node.innerText || node.getAttribute('aria-label') || '');
    }
  }
  if (answer) {
    for (const node of answer.querySelectorAll('a[href]')) {
      if (!visible(node)) continue;
      const label = node.innerText.trim();
      const isReference = node.matches('[role="doc-noteref"], sup a') || /^\[\d{1,3}\]$/.test(label);
      add(isReference ? sources : answerLinks, node.href, label);
    }
  }

  if (operation === 'expand' && answer && !sources.length) {
    const sourceButton = searchable.find(node => {
      const label = (node.getAttribute('aria-label') || node.innerText || '').trim();
      return !node.closest('a[href]') && /^(查看|展开|已参考|已搜索到?|参考了?|搜索到?)?\s*\d+\s*(个|条|篇)?\s*(网页|来源|参考资料|搜索结果)$|^(查看参考来源|参考来源|参考资料|查看引用|引用来源|搜索结果)$/.test(label);
    });
    if (sourceButton) sourceButton.click();
  }

  const busy = searchable.some(el => {
    const label = (el.getAttribute('aria-label') || el.getAttribute('title') || el.dataset.testid || el.innerText || '').trim();
    return /^(停止|停止生成|停止回答|Stop|Stop generating|stop_generating_button|stop_message_button)$/i.test(label);
  }) || Boolean(answer?.closest('[aria-busy="true"],[data-streaming="true"]'));
  return {
    state: gate ? 'login' : 'ok', text: text.slice(0, 16000), sources, answerLinks, busy,
    accepted: input ? !(input.value ?? input.textContent).trim() : true,
    changed: texts.length > previous.length || Boolean(text && text !== previous.at(-1)),
    texts: texts.map(value => value.slice(0, 16000)),
  };
}

function checkTarget(contents, startUrl) {
  if (contents.isDestroyed() || new URL(contents.getURL()).origin !== new URL(startUrl).origin) {
    throw new Error('考试页已经离开对应平台');
  }
}

async function enterQuestion(contents, selector, startUrl, question) {
  checkTarget(contents, startUrl);
  const attached = !contents.debugger.isAttached();
  if (attached) contents.debugger.attach('1.3');
  try {
    const { result } = await contents.debugger.sendCommand('Runtime.evaluate', {
      expression: 'document.activeElement instanceof HTMLTextAreaElement || document.activeElement?.isContentEditable',
      returnByValue: true,
    });
    if (!result.value) throw new Error('考试输入框未获得焦点');
    await contents.debugger.sendCommand('Input.insertText', { text: question });
    checkTarget(contents, startUrl);
    if (!await examDOM(contents, selector, 'send')) {
      await contents.debugger.sendCommand('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      await contents.debugger.sendCommand('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
    }
  } finally {
    if (attached && !contents.isDestroyed() && contents.debugger.isAttached()) contents.debugger.detach();
  }
}

function formatResult(result, status, message, search = false) {
  return {
    status, message, search, text: result?.text || '',
    sources: result?.sources || [], answerLinks: result?.answerLinks || [],
  };
}

async function runExam(contents, engine, startUrl, question, notify) {
  const selector = METHODS[engine];
  let preparation;
  for (let count = 0; count < 24; count++) {
    checkTarget(contents, startUrl);
    preparation = await examDOM(contents, selector, 'prepare');
    if (preparation.state !== 'waiting') break;
    await delay(500);
  }
  if (preparation.state === 'login') return formatResult(null, 'login', '请先在对应标签登录，再重新发起。');
  if (preparation.state !== 'ready') return formatResult(null, 'review', '请在对应标签确认输入框，清空未发送的草稿后再试。');

  const before = await examDOM(contents, selector, 'read');
  if (before.texts.length) return formatResult(null, 'review', '请将考试标签切到新对话，避免上一轮影响本题。');
  await enterQuestion(contents, selector, startUrl, question);
  notify('已送出，等平台回答');

  const started = Date.now();
  let lastText = '';
  let lastChange = started;
  let result;
  while (Date.now() - started < 130_000) {
    await delay(800);
    checkTarget(contents, startUrl);
    result = await examDOM(contents, selector, 'read', before.texts);
    if (result.state === 'login') return formatResult(null, 'login', '平台要求登录或验证。');
    if (result.text !== lastText) {
      lastText = result.text;
      lastChange = Date.now();
    }
    if (result.changed && result.accepted && !result.busy && Date.now() - lastChange >= 4200) {
      return collectExam(contents, engine, startUrl, preparation.search);
    }
    if (!result.accepted && !result.changed && Date.now() - started > 10_000) {
      return formatResult(null, 'review', '平台未确认发送，请到该标签检查，再回收当前答案。');
    }
  }
  return formatResult(result, 'review', '等待超时，可在平台答完后回收当前答案。');
}

async function collectExam(contents, engine, startUrl, search = false) {
  checkTarget(contents, startUrl);
  const selector = METHODS[engine];
  let result = await examDOM(contents, selector, 'read');
  if (result.state === 'login') return formatResult(null, 'login', '请先在对应标签登录。');
  if (result.busy) return formatResult(null, 'review', '平台还在回答，答完后再回收。');
  if (!result.text) return formatResult(null, 'review', '当前标签没有可回收的回答。');
  if (!result.sources.length) {
    await examDOM(contents, selector, 'expand');
    await delay(850);
    checkTarget(contents, startUrl);
    result = await examDOM(contents, selector, 'read');
  }
  return formatResult(result, 'done',
    result.sources.length ? '已回收回答和引用。' : '已回收回答，页面上未读到来源链接。', search);
}

module.exports = { runExam, collectExam };
