  /*L-BEGIN*/
  /* 1.0.4：① 指定时间段导出本地日志 ZIP（下拉精准选日期/时/分，避开 WebView 原生 time 控件不可选问题）；
            ② 蓝牙页停扫「临时恢复 30 分钟」横幅 */
  (function initLogExportAndPauseBar() {
    function pad2(n) { return (n < 10 ? '0' : '') + n; }
    function fmtDate(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
    function fillRange(sel, from, to, suffix) {
      if (!sel) return;
      var html = '';
      for (var i = from; i <= to; i++) {
        var v = pad2(i);
        html += '<option value="' + v + '">' + v + suffix + '</option>';
      }
      sel.innerHTML = html;
    }
    function setDates(sel, dates, fallback) {
      if (!sel) return;
      var list = (dates && dates.length) ? dates.slice() : [fallback];
      if (fallback && list.indexOf(fallback) < 0) list.push(fallback);
      list.sort().reverse();
      var html = '';
      for (var i = 0; i < list.length; i++) {
        var d = list[i];
        html += '<option value="' + d + '">' + d.slice(5) + '</option>';
      }
      sel.innerHTML = html;
    }
    function pickVal(sel, val) {
      if (!sel) return;
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === val) { sel.selectedIndex = i; return; }
      }
      if (val && sel.classList.contains('logexp-date')) {
        var opt = document.createElement('option');
        opt.value = val; opt.textContent = val.slice(5);
        sel.insertBefore(opt, sel.firstChild);
        sel.value = val;
      }
    }
    function parseSel(ds, hs, ms, endOfMin) {
      if (!ds || !hs || !ms) return 0;
      var dp = String(ds.value || '').split('-');
      if (dp.length !== 3) return 0;
      var d = new Date(Number(dp[0]), Number(dp[1]) - 1, Number(dp[2]),
        Number(hs.value || 0), Number(ms.value || 0), endOfMin ? 59 : 0, endOfMin ? 999 : 0);
      return isNaN(d.getTime()) ? 0 : d.getTime();
    }

    var sheet = $('sheetLogExport');
    var btnOpen = $('btnExportAbout');
    var hintAbout = $('diagExportHintAbout');
    var invEl = $('logExpInv');
    var dsEl = $('logDateStart'), hsEl = $('logHourStart'), msEl = $('logMinStart');
    var deEl = $('logDateEnd'), heEl = $('logHourEnd'), meEl = $('logMinEnd');
    var rangeBox = $('logExpRange');
    var msgEl = $('logExpMsg');
    var btnGo = $('btnLogExpGo'), btnCancel = $('btnLogExpCancel');
    var presetsBox = $('logExpPresets');
    var modeAll = false, curLabel = '最近 3 小时', busy = false;
    var availDates = [];

    fillRange(hsEl, 0, 23, '时');
    fillRange(heEl, 0, 23, '时');
    fillRange(msEl, 0, 59, '分');
    fillRange(meEl, 0, 59, '分');

    function markPreset(key) {
      if (!presetsBox) return;
      var bs = presetsBox.querySelectorAll('button[data-log-preset]');
      for (var i = 0; i < bs.length; i++) {
        bs[i].classList.toggle('on', bs[i].getAttribute('data-log-preset') === key);
      }
    }

    function setStartEnd(d0, d1) {
      pickVal(dsEl, fmtDate(d0)); pickVal(hsEl, pad2(d0.getHours())); pickVal(msEl, pad2(d0.getMinutes()));
      pickVal(deEl, fmtDate(d1)); pickVal(heEl, pad2(d1.getHours())); pickVal(meEl, pad2(d1.getMinutes()));
    }

    function applyPreset(key) {
      var now = new Date();
      modeAll = (key === 'all');
      if (rangeBox) rangeBox.classList.toggle('dim', modeAll);
      markPreset(key);
      if (key === '1h') {
        setStartEnd(new Date(now.getTime() - 3600 * 1000), now);
        curLabel = '最近 1 小时';
      } else if (key === '3h') {
        setStartEnd(new Date(now.getTime() - 3 * 3600 * 1000), now);
        curLabel = '最近 3 小时';
      } else if (key === 'today') {
        var t0 = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        setStartEnd(t0, now);
        curLabel = '今天';
      } else if (key === 'yesterday') {
        var y = new Date(now.getTime() - 86400 * 1000);
        var y0 = new Date(y.getFullYear(), y.getMonth(), y.getDate(), 0, 0, 0);
        var y1 = new Date(y.getFullYear(), y.getMonth(), y.getDate(), 23, 59, 0);
        setStartEnd(y0, y1);
        curLabel = '昨天';
      } else {
        curLabel = '全部留存';
      }
      if (msgEl) { msgEl.textContent = ''; msgEl.className = 'logexp-msg'; }
    }

    function refreshInv() {
      var today = fmtDate(new Date());
      availDates = [today];
      if (window.KCLog && window.KCLog.info) {
        try {
          var r = json(window.KCLog.info(), null);
          if (r && Number(r.ok) === 1) {
            var days = r.days || [];
            if (days.length > 0) {
              availDates = [];
              for (var i = 0; i < days.length; i++) if (days[i] && days[i].date) availDates.push(days[i].date);
              if (invEl) {
                invEl.textContent = '本机已留存：' + r.minDate + ' ~ ' + r.maxDate +
                  '（' + days.length + ' 天 · 共 ' + r.totalLines + ' 行，保留 ' + (r.keepDays || 7) + ' 天）';
              }
            } else if (Number(r.memLines || 0) > 0) {
              if (invEl) invEl.textContent = '本机内存当前有 ' + r.memLines + ' 行日志（导出时会自动写入）';
            } else if (invEl) {
              invEl.textContent = '当前暂无留存日志';
            }
          } else if (invEl) {
            invEl.textContent = '读取日志留存失败';
          }
        } catch (e) {
          if (invEl) invEl.textContent = '读取失败：' + e;
        }
      } else if (invEl) {
        invEl.textContent = '原生导出接口未就绪';
      }
      setDates(dsEl, availDates, today);
      setDates(deEl, availDates, today);
    }

    function openSheet() {
      if (!sheet) return;
      sheet.hidden = false;
      refreshInv();
      applyPreset('3h');
    }
    function closeSheet() { if (sheet) sheet.hidden = true; }

    if (btnOpen) {
      btnOpen.addEventListener('click', function () {
        try { haptic('light'); } catch (e) {}
        openSheet();
      });
    }
    if (btnCancel) btnCancel.addEventListener('click', closeSheet);
    if (sheet) {
      sheet.addEventListener('click', function (ev) {
        if (ev.target === sheet) closeSheet();
      });
    }
    if (presetsBox) {
      presetsBox.addEventListener('click', function (ev) {
        var b = ev.target && ev.target.closest ? ev.target.closest('button[data-log-preset]') : null;
        if (!b) return;
        applyPreset(b.getAttribute('data-log-preset'));
      });
    }
    [dsEl, hsEl, msEl, deEl, heEl, meEl].forEach(function (el) {
      if (!el) return;
      el.addEventListener('change', function () {
        modeAll = false;
        if (rangeBox) rangeBox.classList.remove('dim');
        markPreset('');
        curLabel = '自定义时段';
      });
    });

    if (btnGo) {
      btnGo.addEventListener('click', function () {
        if (busy) return;
        if (!window.KCLog || !window.KCLog.exportRange) {
          if (msgEl) { msgEl.textContent = '原生导出接口不可用'; msgEl.className = 'logexp-msg err'; }
          return;
        }
        var sMs = 0, eMs = 0;
        if (!modeAll) {
          sMs = parseSel(dsEl, hsEl, msEl, false);
          eMs = parseSel(deEl, heEl, meEl, true);
          if (!sMs || !eMs) {
            if (msgEl) { msgEl.textContent = '请选择有效的开始与结束时间'; msgEl.className = 'logexp-msg err'; }
            return;
          }
          if (eMs < sMs) {
            if (msgEl) { msgEl.textContent = '结束时间不能早于开始时间'; msgEl.className = 'logexp-msg err'; }
            return;
          }
        }
        var png = '';
        try {
          var cv = $('scopeCanvas');
          if (cv && cv.width > 400 && cv.height > 150 && typeof scopeBuf !== 'undefined' && scopeBuf && scopeBuf.length > 0) {
            png = cv.toDataURL('image/png');
            if (png && png.length > 3500000) png = cv.toDataURL('image/jpeg', 0.9);
          }
        } catch (e) { png = ''; }

        busy = true;
        btnGo.disabled = true;
        btnGo.textContent = '打包中…';
        if (msgEl) { msgEl.textContent = '正在筛选并压缩日志…'; msgEl.className = 'logexp-msg'; }

        setTimeout(function () {
          try {
            var r = json(window.KCLog.exportRange(sMs, eMs, png, curLabel), null);
            if (r && Number(r.ok) === 1) {
              var txt = '已导出 ' + r.lines + ' 行（' + r.kb + ' KB）→ ' + r.dir + r.file;
              if (msgEl) { msgEl.textContent = txt; msgEl.className = 'logexp-msg ok'; }
              if (hintAbout) hintAbout.textContent = '最近导出：' + txt;
              try { toast('日志已保存：' + r.file, 'ok'); } catch (e) {}
            } else {
              var why = (r && r.err) ? r.err : '未知错误';
              if (msgEl) { msgEl.textContent = '导出失败：' + why; msgEl.className = 'logexp-msg err'; }
            }
          } catch (e) {
            if (msgEl) { msgEl.textContent = '导出异常：' + e; msgEl.className = 'logexp-msg err'; }
          } finally {
            busy = false;
            btnGo.disabled = false;
            btnGo.textContent = '导出 ZIP';
          }
        }, 40);
      });
    }

    /* ── 蓝牙页：停扫临时恢复横幅 ── */
    var bar = $('blePauseBar'), barTxt = $('blePauseTxt'), barSub = $('blePauseSub'), barBtn = $('btnBleTempResume');
    var barMode = '';
    function refreshPauseBar() {
      if (!bar || !barTxt || !barBtn) return;
      var remain = 0;
      if (window.KCLog && window.KCLog.pauseStatus) {
        try {
          var ps = json(window.KCLog.pauseStatus(), null);
          if (ps && Number(ps.ok) === 1) remain = Number(ps.tempRemainSec || 0);
        } catch (e) {}
      }
      var pOn = !!(typeof scopePause !== 'undefined' && scopePause && Number(scopePause.paused || 0) === 1);
      if (remain > 0) {
        barMode = 'resumed';
        bar.hidden = false;
        bar.setAttribute('data-mode', 'resumed');
        var mins = Math.max(1, Math.ceil(remain / 60));
        barTxt.textContent = '已临时恢复扫描 · 剩余约 ' + mins + ' 分钟';
        if (barSub) barSub.textContent = '到期后按 WiFi/定时策略自动恢复停扫';
        barBtn.textContent = '恢复停扫';
      } else if (pOn) {
        barMode = 'paused';
        bar.hidden = false;
        bar.setAttribute('data-mode', 'paused');
        barTxt.textContent = (typeof pauseLabelOf === 'function' ? pauseLabelOf(scopePause) : '后台停扫') + '生效中';
        if (barSub) barSub.textContent = (typeof pauseDetailOf === 'function' ? pauseDetailOf(scopePause) : '') || '省电策略暂停了蓝牙扫描，离开后 1~2 分钟内自动恢复';
        barBtn.textContent = '临时恢复 30 分';
      } else {
        barMode = '';
        bar.hidden = true;
      }
    }
    if (barBtn) {
      barBtn.addEventListener('click', function () {
        if (!window.KCLog) return;
        try { haptic('light'); } catch (e) {}
        if (barMode === 'resumed') {
          try { window.KCLog.cancelTempResume(); } catch (e) {}
          try { toast('已交回停扫策略判定', 'ok'); } catch (e) {}
        } else {
          try { window.KCLog.tempResume(30); } catch (e) {}
          try { toast('已临时恢复蓝牙扫描 30 分钟', 'ok'); } catch (e) {}
        }
        try { scopePauseAt = 0; if (typeof scopePauseRefresh === 'function') scopePauseRefresh(); } catch (e) {}
        setTimeout(refreshPauseBar, 250);
      });
    }
    setInterval(function () {
      var pg = $('page-ble');
      if (pg && pg.classList.contains('active')) refreshPauseBar();
    }, 2500);
    setTimeout(refreshPauseBar, 1200);

    /* 1.0.5：点「立即连接 / 重新连接 / 待命」时，若当前未直连且未停扫，顺手销毁僵尸 GATT 重建 */
    var btnConn = $('btnBleConn');
    if (btnConn) {
      btnConn.addEventListener('click', function () {
        var cn = $('scopeConn') ? String($('scopeConn').textContent || '').trim() : '';
        if (cn === '已直连' || cn.indexOf('停扫') >= 0) return;
        if (window.KCLog && window.KCLog.rebuildBle) {
          try { window.KCLog.rebuildBle(); } catch (e) {}
        }
      });
    }
  })();
  /*L-END*/
