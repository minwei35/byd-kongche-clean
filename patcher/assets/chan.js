  /*C-BEGIN*/
  /* 4.4：点「云端通道 / 蓝牙直连」这枚牌 → 说明当前走哪条路、为什么、大概多久；
     顺手把一直藏着的能力（换车辆图片 / 恢复默认）放到明面上。
     ⚠ 不提供「强制走云端」开关：原生 cmd() 的路由只看连接状态，WebBridge 里没有
       任何可以覆盖通道的方法（channelText 只是状态回推）。要加得改原生路由，不在本轮。 */
  (function bindChanSheet() {
    var tag = $('chanTag'), sheet = $('sheetChan');
    if (!tag || !sheet) return;
    tag.setAttribute('role', 'button');
    tag.setAttribute('title', '点这里看当前走哪条路、大概多久');

    function sync() {
      var s = lastBleSt || {};
      var live = (s.link === 'live') || (s.link === undefined && s.connected === true);
      var standby = (s.link === 'standby');
      var box = $('chanState'), why = $('chanWhy'), eta = $('chanEta'), go = $('btnChanGo');
      if (box) {
        box.textContent = live ? '蓝牙直连' : (standby ? '蓝牙认证中' : '云端通道');
        box.setAttribute('data-chan', (live || standby) ? 'ble' : 'cloud');
      }
      if (why) {
        why.textContent = live
          ? '手机和车机已经连上，指令走本地蓝牙：不经过云端、不受风控、不用排队。'
          : standby
            ? '蓝牙已登记，正在和车机握手认证；认证完成会自动切到直连，不用你做别的。'
            : (s.running
              ? '蓝牙守护在跑，但这一刻没连上车机（不在范围、被别的 App 占用，或车机休眠）。所以指令只能走云端。'
              : '蓝牙守护没在跑，指令只能走云端。回蓝牙页点「立即连接」，下一条就能走本地。');
      }
      if (eta) eta.textContent = live ? '约 1 秒内发出' : (standby ? '通常 2~5 秒' : '约 10~30 秒，要过云端排队');
      if (go) go.style.display = live ? 'none' : '';
    }

    tag.addEventListener('click', function () {
      sync();
      sheet.hidden = false;
      try { haptic('light'); } catch (e) {}
    });
    var close = $('chanClose');
    if (close) close.addEventListener('click', function () { sheet.hidden = true; });
    sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.hidden = true; });

    var go = $('btnChanGo');
    if (go) go.addEventListener('click', function () {
      sheet.hidden = true;
      var nav = document.querySelector('.nav-item[data-page="ble"]');
      if (nav) nav.click();
    });

    var pick = $('btnCarPick');
    if (pick) pick.addEventListener('click', function () {
      sheet.hidden = true;
      try { pickCarImage(); } catch (e) { warn('pickCarImage', e); }
    });
    var reset = $('btnCarReset');
    if (reset) reset.addEventListener('click', function () {
      sheet.hidden = true;
      try { resetCarImage(); } catch (e) { warn('resetCarImage', e); }
    });

    sync();
    setInterval(function () { if (!sheet.hidden) sync(); }, 1500);
  })();
  /*C-END*/
