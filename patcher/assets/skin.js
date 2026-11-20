/* 换肤引导（4.4.1）—— 在 <head> 里同步执行，避免首帧闪旧皮。

   三种外观：night（夜间仪表，默认）/ platinum（白金）/ day（白天浅色搪塑）。

   ⚠ 4.4.0 的坑：白天皮肤借用了 `data-theme="light"`，而这个属性**归 app.js 的
     applyTheme() 管** —— 每次进「账户」页 loadConfig() 都会调它，把 data-theme 按
     老的 qinl_theme 重写，于是刚选的皮肤当场被打回夜间。
   4.4.1 的做法：
     ① 选皮肤时**同时写** qinl_theme（night/platinum → dark，day → light），
        让 app.js 每次读到的都和我们对齐，不再互相对抗；
     ② 再挂一个 MutationObserver 兜底：data-theme 被别处改掉就纠正回来；
     ③ 顶栏 🌙 接管成"皮肤内的明暗切换"（day ↔ 上一个深色皮肤）。
   状态只落 localStorage：不动原生、不动任何功能与阈值设置。 */
(function () {
  var KEY = 'kc_skin';           // 我们的键
  var APP_THEME_KEY = 'qinl_theme';  // app.js 自己的键，必须同步
  var VALID = { night: 1, platinum: 1, day: 1 };
  var NAME = { night: '夜间仪表', platinum: '白金', day: '白天' };

  function readKey(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function writeKey(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function read() {
    var v = readKey(KEY);
    if (VALID[v]) return v;
    /* 老用户：只存过 qinl_theme=light 的，按白天算 */
    if (readKey(APP_THEME_KEY) === 'light') return 'day';
    return 'night';
  }

  var cur = read();
  var lastDark = (cur === 'day') ? 'night' : cur;   // 🌙 来回切时记住"上一个深色皮肤"

  function wantTheme(v) { return v === 'day' ? 'light' : 'dark'; }

  function paint() {
    var h = document.documentElement;
    if (cur === 'platinum') h.setAttribute('data-skin', 'platinum');
    else if (h.hasAttribute('data-skin')) h.removeAttribute('data-skin');
    if (h.getAttribute('data-theme') !== wantTheme(cur)) h.setAttribute('data-theme', wantTheme(cur));
  }

  function persist(v) {
    writeKey(KEY, v);
    writeKey(APP_THEME_KEY, wantTheme(v));   // 让 app.js 的 applyTheme() 与我们同向
  }

  /* ① 首帧前同步落属性 */
  paint();
  persist(cur);

  /* ② 兜底：app.js（或原生回调）改了 data-theme，就纠回来 */
  var h = document.documentElement;
  function guard() {
    if (h.getAttribute('data-theme') !== wantTheme(cur)) paint();
    if (cur === 'platinum' && h.getAttribute('data-skin') !== 'platinum') paint();
  }
  if (window.MutationObserver) {
    try { new MutationObserver(guard).observe(h, { attributes: true, attributeFilter: ['data-theme', 'data-skin'] }); } catch (e) {}
  }

  /* ③ 顶栏 🌙：在皮肤里切明暗（day ↔ 上一个深色皮肤） */
  document.addEventListener('click', function (e) {
    var t = e.target;
    while (t && t !== document) {
      if (t.id === 'btnTheme') {
        if (cur === 'day') cur = lastDark || 'night';
        else { lastDark = cur; cur = 'day'; }
        persist(cur); paint(); mark();
        break;
      }
      t = t.parentNode;
    }
  }, true);

  function mark() {
    var row = document.getElementById('skinRow');
    var now = document.getElementById('skinNow');
    var btns = row ? row.querySelectorAll('[data-skin]') : [];
    for (var i = 0; i < btns.length; i++) {
      var on = btns[i].getAttribute('data-skin') === cur;
      btns[i].classList.toggle('active', on);
      btns[i].setAttribute('aria-checked', on ? 'true' : 'false');
    }
    if (now) now.textContent = NAME[cur] || NAME.night;
  }

  function boot() {
    var row = document.getElementById('skinRow');
    var btns = row ? row.querySelectorAll('[data-skin]') : [];
    mark();
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function () {
        var v = this.getAttribute('data-skin');
        if (!VALID[v]) return;
        cur = v;
        if (v !== 'day') lastDark = v;
        persist(cur); paint(); mark();
        try { AndroidBridge.haptic('light'); } catch (e) {}
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  /* 回到前台再对一次（原生可能在后台上报过主题） */
  document.addEventListener('visibilitychange', function () { if (!document.hidden) paint(); });

  window.__kcSkin = {
    get: function () { return cur; },
    set: function (v) {
      if (!VALID[v]) return;
      cur = v;
      if (v !== 'day') lastDark = v;
      persist(cur); paint(); mark();
    }
  };
})();
