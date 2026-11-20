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

  /*E-BEGIN*/
  /* 1.0.0：关于卡里的「导出日志压缩包」= 复用既有的导出诊断包流程（不重复实现） */
  (function bindExportAbout() {
    var b = $('btnExportAbout'), t = $('btnExportDiag');
    if (!b) return;
    b.addEventListener('click', function () {
      if (!t) { toast('导出入口缺失', 'err'); return; }
      try { t.click(); } catch (e) { warn('exportAbout', e); }
    });
  })();
  /*E-END*/
