  /*K-BEGIN*/
  /* 4.7：关键指标（跟着上面的周/月/年一起变）
       六格离散指标全部从 `qinl_trips`（[{t0,t1,km}]）现算，不新增任何请求。

       充电块（本版重点）：回答"上次充电从多少充到多少、之后开了多远"。
       数据来源是车况里的 battery(%) 与 mileage(总里程)，云端不存历史，所以在本地自己攒：
         qinl_charge_cur  = {socS, socNow, odoS, t0}         充电中
         qinl_charge_last = {socS, socE, odoS, odoE, t0, t1, approx}  上一次充完
       20 秒看一眼充电相位：变 charging 就开一条，变回 off/gun 就收尾。
       App 没运行的时间观察不到；收尾时若没看到结束瞬间，用"最后一次读数"补并标 approx
       （界面写"估"），不假装精确。 */
  (function initTripKpi() {
    var KEY = 'qinl_trips';
    var CUR = 'qinl_charge_cur';
    var LAST = 'qinl_charge_last';
    var kindEl = $('kpiSpan');

    function trips() {
      try { var a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a : []; }
      catch (e) { return []; }
    }
    function load(k) {
      try { var o = JSON.parse(localStorage.getItem(k) || 'null'); return (o && typeof o === 'object') ? o : null; }
      catch (e) { return null; }
    }
    function save(k, v) {
      try { if (v) localStorage.setItem(k, JSON.stringify(v)); else localStorage.removeItem(k); }
      catch (e) {}
    }
    function num(v) { var n = Number(v); return isFinite(n) ? n : null; }
    function nowS() { return Math.floor(Date.now() / 1000); }
    function brief() { return (typeof lastBrief !== 'undefined' && lastBrief) ? lastBrief : null; }
    function phaseOf(b) {
      if (!b) return 'unknown';
      return b.charge_phase || (b.charging === true ? 'charging' : (b.charging === false ? 'off' : 'unknown'));
    }

    /* ── 充电会话记录器 ── */
    function chgBoot() {
      var cur = load(CUR);
      if (!cur) return;
      var b = brief(), ph = phaseOf(b);
      if (ph === 'charging') return;
      var socNow = (cur.socNow != null) ? cur.socNow : cur.socS;
      var odo = b ? num(b.mileage) : null;
      save(LAST, {
        socS: cur.socS, socE: socNow, odoS: cur.odoS, odoE: odo,
        t0: cur.t0, t1: nowS(), approx: true
      });
      save(CUR, null);
    }
    function chgTick() {
      var b = brief(), ph = phaseOf(b);
      if (ph === 'unknown') return;
      var cur = load(CUR);
      var soc = b ? num(b.battery) : null;
      var odo = b ? num(b.mileage) : null;
      if (ph === 'charging') {
        if (!cur) cur = { socS: soc, socNow: soc, odoS: odo, t0: nowS() };
        else if (soc != null) cur.socNow = soc;
        save(CUR, cur);
        return;
      }
      if (cur) {
        save(LAST, {
          socS: cur.socS,
          socE: (soc != null ? soc : cur.socNow),
          odoS: cur.odoS,
          odoE: odo,
          t0: cur.t0,
          t1: nowS(),
          approx: false
        });
        save(CUR, null);
        renderCharge();
      }
    }

    function nativeMarks() {
      try {
        if (typeof KCCharge === 'undefined' || !KCCharge) return null;
        var a = JSON.parse(KCCharge.marks() || '[]');
        return Array.isArray(a) ? a : null;
      } catch (e) { return null; }
    }
    function nativeStatus() {
      try {
        if (typeof KCCharge === 'undefined' || !KCCharge) return null;
        return JSON.parse(KCCharge.status() || 'null');
      } catch (e) { return null; }
    }
    /* 从官方通知里取"最近一次完整的充电窗口"：最后一个 start，后面跟 stop/done */
    function nativeWindow() {
      var a = nativeMarks();
      if (!a || !a.length) return null;
      var start = null, lastStart = null, lastEnd = null;
      for (var i = 0; i < a.length; i++) {
        var k = a[i] && a[i].kind, ts = a[i] ? Number(a[i].ts) : 0;
        if (!ts) continue;
        if (k === 'start') { start = ts; }
        else if ((k === 'stop' || k === 'done') && start) { lastStart = start; lastEnd = ts; start = null; }
      }
      if (lastStart && lastEnd && lastEnd > lastStart) {
        return { t0: lastStart, t1: lastEnd, open: false };
      }
      if (start) return { t0: start, t1: 0, open: true };
      return null;
    }

    function md(sec) {
      var d = new Date(sec * 1000);
      var p = function (n) { return n < 10 ? '0' + n : '' + n; };
      return (d.getMonth() + 1) + '-' + p(d.getDate());
    }
    function hhmm(sec) {
      var d = new Date(sec * 1000);
      var p = function (n) { return n < 10 ? '0' + n : '' + n; };
      return p(d.getHours()) + ':' + p(d.getMinutes());
    }
    function ymd(d) {
      var p = function (n) { return n < 10 ? '0' + n : '' + n; };
      return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + p(d.getDate());
    }
    function periodOf(kind, base) {
      var s, e;
      if (kind === 'week') {
        var wd = (base.getDay() + 6) % 7;
        s = new Date(base); s.setHours(0, 0, 0, 0); s.setDate(s.getDate() - wd);
        e = new Date(s); e.setDate(e.getDate() + 7);
      } else if (kind === 'month') {
        s = new Date(base); s.setHours(0, 0, 0, 0); s.setDate(1);
        e = new Date(s); e.setMonth(e.getMonth() + 1);
      } else {
        s = new Date(base); s.setHours(0, 0, 0, 0); s.setMonth(0, 1);
        e = new Date(s); e.setFullYear(e.getFullYear() + 1);
      }
      return { s: s, e: e, sec: Math.max(1, Math.floor((e - s) / 1000)) };
    }

    /* ── 充电块（与周期无关：始终讲"这次/上次"）── */
    function renderCharge() {
      var set = function (id, v) { var el = $(id); if (el) el.textContent = v; };
      var cur = load(CUR), last = load(LAST), b = brief();
      var odoNow = b ? num(b.mileage) : null;
      var title = $('chgTitle');
      var nw = nativeWindow(), nstat = nativeStatus();

      /* 授权入口：只有原生接口在、且没授权时才露出来 */
      var acc = $('chgAccess');
      if (acc) {
        var need = !!(nstat && !nstat.granted);
        acc.hidden = !need;
        if (need) acc.textContent = '开启通知读取，拿到精确的起止时刻';
      }
      var src = $('chgSrc');
      var priv = $('chgPriv');
      if (priv) {
        var cnt = (nstat && typeof nstat.count === 'number') ? nstat.count : null;
        priv.textContent = '只读取「比亚迪官方 App」的通知，且只记充电事件；其它 App 与其他车辆消息一律丢弃，不上传'
          + (cnt != null ? '（已抓 ' + cnt + ' 条）' : '');
      }
      function srcText(native) {
        if (!src) return;
        src.textContent = native
          ? '时刻来自官方 App 的充电通知（系统通知监听）'
          : '时刻来自本机每 20 秒的观察，可能有几分钟误差';
      }

      /* 原生通知窗口优先：它给的是精确到秒的起止，比轮询准 */
      if (nw) {
        if (nw.open) {
          if (title) title.textContent = '正在充电';
          set('chgFrom', (cur && cur.socS != null ? cur.socS : '--') + '%');
          set('chgTo', (cur && cur.socNow != null ? cur.socNow : '--') + '%');
          var gn = (cur && cur.socS != null && cur.socNow != null) ? (cur.socNow - cur.socS) : null;
          set('chgGain', gn != null ? '+' + gn + '%' : '');
          set('chgAt', '开始 ' + md(nw.t0) + ' ' + hhmm(nw.t0));
          if (last && last.odoE != null && odoNow != null && odoNow >= last.odoE) {
            set('chgKm', (odoNow - last.odoE).toFixed(1) + ' km');
            set('chgKmSub', '上次充完到现在');
          } else { set('chgKm', '--'); set('chgKmSub', '还没有上次充电记录'); }
          srcText(true);
          set('chgHint', '官方通知已经报"开始充电"，拔枪后会再收到一次结束通知，届时自动结算。');
          return;
        }
        if (title) title.textContent = '上次充电';
        set('chgFrom', (last && last.socS != null ? last.socS : (cur && cur.socS != null ? cur.socS : '--')) + '%');
        set('chgTo', (last && last.socE != null ? last.socE : '--') + '%');
        var g2n = (last && last.socS != null && last.socE != null) ? (last.socE - last.socS) : null;
        set('chgGain', g2n != null ? '+' + g2n + '%' : '');
        set('chgAt', md(nw.t0) + ' ' + hhmm(nw.t0) + ' → ' + hhmm(nw.t1));
        if (last && last.odoE != null && odoNow != null && odoNow >= last.odoE) {
          set('chgKm', (odoNow - last.odoE).toFixed(1) + ' km');
          set('chgKmSub', '· ' + Math.max(0, Math.round((nowS() - nw.t1) / 86400)) + ' 天');
        } else {
          set('chgKm', '--');
          set('chgKmSub', '缺里程读数');
        }
        srcText(true);
        set('chgHint', last ? '下次插枪时会自动开一条新记录。'
          : '这次充电的电量没有观测到（要在充电时开着 App 才有），时刻是准的。');
        return;
      }

      if (cur) {
        if (title) title.textContent = '正在充电';
        set('chgFrom', ((cur.socS != null ? cur.socS : '--') + '%'));
        set('chgTo', ((cur.socNow != null ? cur.socNow : '--') + '%'));
        var g1 = (cur.socS != null && cur.socNow != null) ? (cur.socNow - cur.socS) : null;
        set('chgGain', g1 != null ? '+' + g1 + '%' : '');
        set('chgAt', '开始 ' + md(cur.t0) + ' ' + hhmm(cur.t0));
        if (last && last.odoE != null && odoNow != null && odoNow >= last.odoE) {
          set('chgKm', (odoNow - last.odoE).toFixed(1) + ' km');
          set('chgKmSub', '上次充完到现在');
        } else {
          set('chgKm', '--');
          set('chgKmSub', '还没有上次充电记录');
        }
        set('chgHint', '拔枪时会记下结束电量与当时总里程，之后每开一段都能算出"充完开了多远"。');
        return;
      }

      if (last) {
        if (title) title.textContent = '上次充电';
        set('chgFrom', ((last.socS != null ? last.socS : '--') + '%'));
        set('chgTo', ((last.socE != null ? last.socE : '--') + '%'));
        var g2 = (last.socS != null && last.socE != null) ? (last.socE - last.socS) : null;
        set('chgGain', g2 != null ? '+' + g2 + '%' : '');
        set('chgAt', md(last.t1) + ' ' + hhmm(last.t1) + (last.approx ? ' · 估' : ''));
        if (last.odoE != null && odoNow != null && odoNow >= last.odoE) {
          set('chgKm', (odoNow - last.odoE).toFixed(1) + ' km');
          set('chgKmSub', '· ' + Math.max(0, Math.round((nowS() - last.t1) / 86400)) + ' 天');
        } else {
          set('chgKm', '--');
          set('chgKmSub', '缺里程读数');
        }
        set('chgHint', last.approx
          ? '这次充电的结束时刻没被观测到（App 当时没在运行），按最后一次读数估算。'
          : '下次插枪充电时自动开一条新记录。');
        return;
      }

      /* 还没有任何记录：至少把"当前电量"放出来，别让整块全是横杠 */
      var socNow = b ? num(b.battery) : null;
      if (title) title.textContent = '上次充电';
      set('chgFrom', socNow != null ? socNow + '%' : '--');
      set('chgTo', '--'); set('chgGain', '');
      set('chgAt', socNow != null ? '当前电量' : '还没有记录');
      set('chgKm', '--');
      set('chgKmSub', '等第一次充电');
      set('chgHint', '本版起开始记录：插枪充电时记起始电量，拔枪时记结束电量与总里程。');
    }

    function render(kind) {
      var all = trips(), p = periodOf(kind, new Date());
      var s = Math.floor(p.s.getTime() / 1000), e = Math.floor(p.e.getTime() / 1000);
      var inP = [], i;
      for (i = 0; i < all.length; i++) {
        var t0 = Number(all[i].t0), t1 = Number(all[i].t1), km = Number(all[i].km);
        if (!isFinite(t0) || t0 < s || t0 >= e) continue;
        if (!isFinite(km) || km <= 0) continue;
        if (!isFinite(t1) || t1 < t0) t1 = t0;
        inP.push({ t0: t0, t1: t1, km: km });
      }

      var longest = null, latest = null, busiest = null, days = {}, kmSum = 0;
      for (i = 0; i < inP.length; i++) {
        var x = inP[i];
        kmSum += x.km;
        if (!longest || x.km > longest.km) longest = x;
        var eod = x.t1 % 86400;
        if (!latest || eod > latest.eod) latest = { eod: eod, t1: x.t1 };
        var dk = ymd(new Date(x.t0 * 1000));
        days[dk] = (days[dk] || 0) + x.km;
      }
      for (var d in days) if (!busiest || days[d] > busiest.km) busiest = { d: d, km: days[d] };
      var dayCount = 0;
      for (var d2 in days) dayCount++;

      var set = function (id, v) { var el = $(id); if (el) el.textContent = v; };
      set('kpiLongest', longest ? longest.km.toFixed(1) + ' km' : '--');
      set('kpiLongestAt', longest ? md(longest.t0) + ' ' + hhmm(longest.t0) : '本期无行程');
      set('kpiLatest', latest ? hhmm(latest.t1) : '--');
      set('kpiLatestAt', latest ? md(latest.t1) : '本期无行程');
      set('kpiBusiest', busiest ? busiest.km.toFixed(1) + ' km' : '--');
      set('kpiBusiestAt', busiest ? busiest.d : '本期无行程');
      set('kpiDays', dayCount ? dayCount + ' 天' : '--');
      set('kpiDaysSub', '占 ' + Math.round(p.sec / 86400) + ' 天');
      set('kpiAvgTrip', inP.length ? (kmSum / inP.length).toFixed(1) + ' km' : '--');
      set('kpiAvgTripSub', '共 ' + inP.length + ' 段');
      set('kpiPerDay', inP.length ? (kmSum / (p.sec / 86400)).toFixed(1) + ' km' : '--');
      if (kindEl) kindEl.textContent = ({ week: '本周', month: '本月', year: '今年' })[kind] || '';

      renderCharge();
    }

    function curSpan() {
      var on = document.querySelector('#tripSeg [data-span].on');
      return on ? on.getAttribute('data-span') : 'week';
    }

    chgBoot();
    setInterval(chgTick, 20000);
    chgTick();

    var clearBtn = $('chgClear');
    if (clearBtn) clearBtn.addEventListener('click', function () {
      try {
        if (typeof KCCharge !== 'undefined' && KCCharge) { KCCharge.clear(); toast('充电记录已清空', 'ok'); }
        else { localStorage.removeItem(LAST); localStorage.removeItem(CUR); toast('充电记录已清空', 'ok'); }
      } catch (e) { warn('chgClear', e); }
      renderCharge();
    });

    var accBtn = $('chgAccess');
    if (accBtn) accBtn.addEventListener('click', function () {
      try {
        if (typeof KCCharge !== 'undefined' && KCCharge) KCCharge.openAccess();
        else toast('这台机器不支持通知读取', '');
      } catch (e) { warn('openAccess', e); }
    });

    var seg = $('tripSeg');
    if (seg) {
      seg.addEventListener('click', function (ev) {
        var t = ev.target;
        while (t && t !== seg && !t.getAttribute('data-span')) t = t.parentNode;
        if (!t || t === seg) return;
        var v = t.getAttribute('data-span');
        if (v) setTimeout(function () { render(v); }, 0);
      });
    }
    document.addEventListener('click', function (ev) {
      var t = ev.target, hit = false;
      while (t && t !== document) {
        if (t.getAttribute && t.getAttribute('data-page') === 'trips') hit = true;
        t = t.parentNode;
      }
      if (hit) setTimeout(function () { render(curSpan()); }, 80);
    }, true);
    setInterval(function () {
      var pg = $('page-trips');
      if (pg && pg.classList.contains('active')) render(curSpan());
      else renderCharge();
    }, 12000);

    render(curSpan());
  })();
  /*K-END*/
