  /*T-BEGIN*/
  /* 4.1：阈值精确设定 —— 长按拖动只能凑个大概，这里填准确值。
     原生 setRssiEnter / setRssiExit 自带夹取：进入 [-90,-30]、离开 [-100,-40]；
     这里先按同一区间校验，并额外要求 进入 ≥ 离开+3（迟滞太小会在边界来回跳）。 */
  var THR_EN_MIN = -90, THR_EN_MAX = -30, THR_EX_MIN = -100, THR_EX_MAX = -40, THR_GAP = 3;
  function thrCur() {
    var st = lastBleSt || {};
    return {
      en: Math.round(Number(st.rssiEnter != null ? st.rssiEnter : -70)),
      ex: Math.round(Number(st.rssiExit != null ? st.rssiExit : -80))
    };
  }
  function thrFill() {
    var c = thrCur(), a = $('thrEnter'), b = $('thrExit'), tip = $('thrTip'), msg = $('thrMsg');
    if (a) a.value = c.en;
    if (b) b.value = c.ex;
    if (tip) tip.textContent = '当前生效：进入 ' + c.en + ' / 离开 ' + c.ex + ' dBm';
    if (msg) msg.textContent = '';
  }
  function thrOpen() {
    thrFill();
    var s = $('sheetThr');
    if (s) { s.hidden = false; try { haptic('light'); } catch (e) {} }
  }
  function thrClose() { var s = $('sheetThr'); if (s) s.hidden = true; }
  function thrSave() {
    var a = $('thrEnter'), b = $('thrExit'), msg = $('thrMsg');
    var en = parseInt(String((a && a.value) || '').trim(), 10);
    var ex = parseInt(String((b && b.value) || '').trim(), 10);
    function bad(t) { if (msg) msg.textContent = t; return false; }
    if (!isFinite(en) || !isFinite(ex)) return bad('两个阈值都要填数字');
    if (en < THR_EN_MIN || en > THR_EN_MAX) return bad('进入阈值要在 ' + THR_EN_MIN + ' ~ ' + THR_EN_MAX + ' dBm');
    if (ex < THR_EX_MIN || ex > THR_EX_MAX) return bad('离开阈值要在 ' + THR_EX_MIN + ' ~ ' + THR_EX_MAX + ' dBm');
    if (en < ex + THR_GAP) return bad('进入阈值要比离开阈值高至少 ' + THR_GAP + ' dB（当前差 ' + (en - ex) + '）');
    try { call('setRssiEnter', String(en)); } catch (e) { warn('thrEnter', e); }
    try { call('setRssiExit', String(ex)); } catch (e) { warn('thrExit', e); }
    try { haptic('light'); } catch (e) {}
    toast('阈值已保存：进入 ' + en + ' / 离开 ' + ex + ' dBm', 'ok');
    thrClose();
    /* 立刻回画：不等原生下一次 state 推送，点保存就能看见线动了。 */
    try { if (lastBleSt) { lastBleSt.rssiEnter = en; lastBleSt.rssiExit = ex; renderScope(lastBleSt); } } catch (e) {}
  }
  (function bindThr() {
    var g = $('btnScopeThr'), s = $('sheetThr');
    if (!g || !s) return;
    g.addEventListener('click', thrOpen);
    var c = $('btnThrCancel'); if (c) c.addEventListener('click', thrClose);
    var v = $('btnThrSave'); if (v) v.addEventListener('click', thrSave);
    s.addEventListener('click', function (e) { if (e.target === s) thrClose(); });
    var ps = s.querySelectorAll('[data-thr-preset]');
    for (var i = 0; i < ps.length; i++) {
      ps[i].addEventListener('click', function () {
        var a = $('thrEnter'), b = $('thrExit');
        if (a) a.value = this.getAttribute('data-en');
        if (b) b.value = this.getAttribute('data-ex');
      });
    }
  })();
  /*T-END*/
