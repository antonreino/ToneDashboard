/* Orbit Zero v3: rewrite root-relative URLs created dynamically by its SPA.
   Without this, catalogue JSON loads but thumbnails point at /artwork instead
   of /orbit-bridge/zero/artwork and Safari shows blank covers. */
(function () {
  'use strict';
  const script = document.currentScript;
  const BASE = new URL('.', script.src).pathname;
  const bridgeUrl = function(value) {
    if (value == null || typeof value !== 'string') return value;
    if (/^(?:data:|blob:|about:|javascript:|#)/i.test(value)) return value;
    try {
      const url = new URL(value, document.baseURI);
      const orbitLocal = (url.protocol === 'http:' || url.protocol === 'ws:') &&
        url.port === '34179';
      if (url.origin !== location.origin && !orbitLocal) return value; // Don't proxy third-party images.
      if (url.origin === location.origin && (url.pathname.startsWith(BASE) || url.pathname.startsWith('/orbit-bridge/'))) return value;
      if (!value.startsWith('/') && !orbitLocal && !/^(?:https?:|wss?:)/i.test(value)) return value; // Relative paths already use <base>.
      url.pathname = BASE + url.pathname.replace(/^\//, '');
      url.host = location.host;
      url.protocol = (url.protocol === 'ws:' || url.protocol === 'wss:')
        ? (location.protocol === 'https:' ? 'wss:' : 'ws:') : location.protocol;
      return url.href;
    } catch (_) { return value; }
  };
  const bridgeSrcset = function(v) {
    if (typeof v !== 'string' || v.includes('data:')) return v;
    return v.split(',').map(part => {
      const m = part.match(/^(\s*)(\S+)([\s\S]*)$/);
      return m ? m[1] + bridgeUrl(m[2]) + m[3] : part;
    }).join(',');
  };
  const bridgeCss = function(v) {
    return typeof v === 'string' ? v.replace(/url\(\s*(["']?)(\/[^/)"']+)(\1)\s*\)/gi,
      (_, quote, url) => 'url(' + quote + bridgeUrl(url) + quote + ')') : v;
  };
  const nativeFetch = window.fetch;
  window.fetch = function(input, ...args) {
    if (input instanceof Request) {
      try { input = new Request(bridgeUrl(input.url), input); } catch (_) {}
    } else { input = bridgeUrl(input); }
    return nativeFetch.call(this, input, ...args);
  };
  const nativeOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) { return nativeOpen.call(this, method, bridgeUrl(url), ...rest); };
  const NativeWS = window.WebSocket;
  if (NativeWS) window.WebSocket = class extends NativeWS {
    constructor(url, protocols) { if (protocols === undefined) super(bridgeUrl(url)); else super(bridgeUrl(url), protocols); }
  };
  const NativeES = window.EventSource;
  if (NativeES) window.EventSource = class extends NativeES {
    constructor(url, opt) { super(bridgeUrl(url), opt); }
  };
  // img.src assigned from JavaScript does not use Element.setAttribute in Safari.
  function patchProperty(cls, prop, translator) {
    if (!cls) return;
    const d = Object.getOwnPropertyDescriptor(cls.prototype, prop);
    if (!d || !d.set || !d.get || !d.configurable) return;
    Object.defineProperty(cls.prototype, prop, {
      configurable: true, enumerable: d.enumerable,
      get() { return d.get.call(this); },
      set(v) { return d.set.call(this, translator(v)); }
    });
  }
  patchProperty(window.HTMLImageElement, 'src', bridgeUrl);
  patchProperty(window.HTMLImageElement, 'srcset', bridgeSrcset);
  patchProperty(window.HTMLSourceElement, 'src', bridgeUrl);
  patchProperty(window.HTMLSourceElement, 'srcset', bridgeSrcset);
  patchProperty(window.HTMLVideoElement, 'poster', bridgeUrl);
  const nativeSet = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function(name, value) {
    const n = String(name).toLowerCase();
    const tag = this.tagName;
    if (['IMG','SOURCE','VIDEO','SCRIPT','LINK','A','IFRAME'].includes(tag)) {
      if (n === 'src' || n === 'href' || n === 'poster') value = bridgeUrl(String(value));
      else if (n === 'srcset') value = bridgeSrcset(String(value));
    }
    if (n === 'style') value = bridgeCss(String(value));
    return nativeSet.call(this, name, value);
  };
  // Handle images inserted via innerHTML, template cloning and CSS background styles.
  function repair(node) {
    if (!node || node.nodeType !== 1) return;
    const tags = node.matches && node.matches('img,source,video') ? [node] : [];
    if (node.querySelectorAll) tags.push(...node.querySelectorAll('img,source,video'));
    for (const el of tags) {
      const attrs = el.tagName === 'VIDEO' ? ['poster'] : ['src', 'srcset'];
      for (const attr of attrs) {
        const original = el.getAttribute(attr);
        if (!original) continue;
        const fixed = attr === 'srcset' ? bridgeSrcset(original) : bridgeUrl(original);
        if (fixed !== original) nativeSet.call(el, attr, fixed);
      }
    }
    const sty = node.matches && node.matches('[style]') ? [node] : [];
    if (node.querySelectorAll) sty.push(...node.querySelectorAll('[style]'));
    for (const el of sty) {
      const old = el.getAttribute('style');
      const fixed = bridgeCss(old);
      if (fixed !== old) nativeSet.call(el, 'style', fixed);
    }
  }
  const observer = new MutationObserver(changes => {
    for (const change of changes) {
      if (change.type === 'attributes') repair(change.target);
      else for (const node of change.addedNodes) repair(node);
    }
  });
  observer.observe(document.documentElement || document, {subtree:true, childList:true,
    attributes:true, attributeFilter:['src','srcset','poster','style']});
  repair(document.documentElement);
})();
