  /*R-BEGIN*/
  /* 4.3：车辆控制标题行
     ① 通道标签说人话：原生只写「云端」/「蓝牙优先」，看不出是"走哪条路"——
        这里改写成「云端通道」/「蓝牙直连」，并用 MutationObserver 跟住原生每次刷新。
     ② 二次确认从"裸开关"变成带说明的整行（开关本体还在原位，只是文案由我们补）。 */
  (function bindCtlHead() {
    var tag = $('chanTag');
    if (tag) {
      var label = function (t) {
        if (t === '云端') return '云端通道';
        if (t === '蓝牙优先') return '蓝牙直连';
        return t;
      };
      var kind = function (t) {
        if (t === '蓝牙优先' || t === '蓝牙直连') return 'ble';
        if (t === '云端通道' || t === '云端') return 'cloud';
        return '';
      };
      var sync = function () {
        var raw = String(tag.textContent || '').trim();
        var want = label(raw);
        if (want !== raw) tag.textContent = want;
        var k = kind(want);
        if (k) tag.setAttribute('data-chan', k);
        else tag.removeAttribute('data-chan');
      };
      sync();
      if (window.MutationObserver) {
        try { new MutationObserver(sync).observe(tag, { childList: true, characterData: true, subtree: true }); } catch (e) {}
      }
    }

    var sw = $('swConfirmCmd'), state = $('ctlCfmState');
    if (sw && state) {
      var paint = function () {
        var on = sw.classList.contains('on');
        state.textContent = on ? '开 · 点按钮先弹确认' : '关 · 点一下直接执行';
        state.setAttribute('data-on', on ? '1' : '0');
      };
      paint();
      sw.addEventListener('click', function () { setTimeout(paint, 0); });
    }
  })();
  /*R-END*/

  /*N-BEGIN*/
  /* 4.12：顶栏那颗 🔊 挪进设置后，用一枚标准开关接管；
     真值仍以原生 bleState.sound 为准（setSoundEnabled 落盘），localStorage 只做前端镜像。 */
  (function initSoundCard() {
    var sw = $('swSound'), now = $('sndNow');
    if (!sw) return;
    function paint(on) {
      sw.classList.toggle('on', on);
      if (now) now.textContent = on ? '开' : '已静音';
      sw.title = on ? '点一下全部静音' : '点一下恢复音效';
    }
    function cur() { return !!(lastBleSt && lastBleSt.sound !== false); }
    paint(cur());
    sw.addEventListener('click', function () {
      var next = !sw.classList.contains('on');
      try { call('setSoundEnabled', next ? '1' : '0'); } catch (e) { warn('setSoundEnabled', e); }
      try { localStorage.setItem('qinl_mute_all', next ? '0' : '1'); } catch (e) {}
      paint(next);
      try { haptic('light'); } catch (e) {}
      try { toast(next ? '音效已恢复（App 内所有提示音）' : '已全部静音（App 内所有提示音都不响）', 'ok'); } catch (e) {}
    });
    setInterval(function () {
      var pg = $('page-settings');
      if (pg && pg.classList.contains('active')) paint(cur());
    }, 3000);
  })();
  /*N-END*/

/* ── 1.0.3 诊断心跳 + 保活自愈 ───────────────────────────────────────
   状态变化/启停事件持久化进 AppLog（随每日文件保留 7 天，可按时间段导出）；
   8 秒周期心跳仅打到 logcat（tag=KC），不刷爆日志文件。 */
(function kcDiag() {
  var T = '[KC]';
  function txt(id) { var e = $(id); return e ? String(e.textContent || '').trim() : '?'; }
  function page() {
    var p = document.querySelector('.page.active');
    return p ? String(p.id || '?') : '?';
  }
  function pts() { try { return (typeof scopeBuf !== 'undefined' && scopeBuf) ? scopeBuf.length : -1; } catch (e) { return -2; } }
  function snap() {
    return 'page=' + page() + ' hidden=' + (document.hidden ? 1 : 0)
      + ' conn=' + txt('scopeConn') + ' rssi=' + txt('scopeRssi')
      + ' judge=' + txt('scopeState') + ' pts=' + pts();
  }
  function log(s, persist) {
    var line = T + ' ' + s;
    try { console.log(line); } catch (e) {}
    if (window.KCLog && window.KCLog.note) {
      try { window.KCLog.note(line, !!persist); return; } catch (e) {}
    }
    try { call('diagNote', line); } catch (e) {}
  }

  var lastUserStop = 0;
  document.addEventListener('click', function (ev) {
    var t = ev && ev.target ? String((ev.target.textContent || '') + '') : '';
    if (t.indexOf('断开') >= 0) { lastUserStop = Date.now(); log('user-stop ' + snap(), true); }
    else if (t.indexOf('立即连接') >= 0 || t.indexOf('已直连') >= 0) { log('user-connect ' + snap(), true); }
  }, true);

  log('boot v1.0.6 diag', true);
  var last = '';
  setInterval(function () {
    var s = snap();
    if (s !== last) { log('chg ' + s, true); last = s; } else { log('hb ' + s, false); }
  }, 8000);

  var lastStart = 0;
  function ensure(why) {
    if (Date.now() - lastStart < 20000) return;
    if (Date.now() - lastUserStop < 60000) return;
    var conn = txt('scopeConn');
    if (conn === '已直连' || conn.indexOf('停扫') >= 0) return;
    lastStart = Date.now();
    log('keeperStart why=' + why + ' ' + snap(), true);
    try { call('keeperStart'); } catch (e) { log('keeperStart err ' + e, true); }
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) setTimeout(function () { ensure('visible'); }, 900);
  });
  setTimeout(function () { ensure('boot'); }, 3000);
})();
