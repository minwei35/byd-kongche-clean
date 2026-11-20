  /*S-BEGIN*/
  /* 4.5：行程统计（周 / 月 / 年）
     数据源就是本机行程表 `qinl_trips`（[{t0,t1,mi0,mi1,km}]，app.js 每段行程结束时落盘），
     不改任何记录逻辑，只在本地按自然周期聚合：
       周 = 本周一 00:00 起，7 根柱（周一~周日）
       月 = 本月 1 日起，5 根柱（1-7 / 8-14 / 15-21 / 22-28 / 29+）
       年 = 今年 1 月起，12 根柱（1~12 月）
     对比上期用同长度上一周期（上周 / 上月 / 去年），只做展示。 */
  (function initTripStat() {
    var KEY = 'qinl_trips';
    var seg = $('tripSeg'), bars = $('tripBars'), hint = $('tripStatHint'), kindEl = $('tripStatKind');
    if (!seg || !bars) return;
    var span = 'week';
    var NAME = { week: '本周', month: '本月', year: '今年' };

    function trips() {
      try {
        var a = JSON.parse(localStorage.getItem(KEY) || '[]');
        return Array.isArray(a) ? a : [];
      } catch (e) { return []; }
    }
    function dayStart(d) { var x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
    function ms2s(d) { return Math.floor(d.getTime() / 1000); }

    function period(kind, base) {
      var s, e, labels = [], n;
      if (kind === 'week') {
        var wd = (base.getDay() + 6) % 7;            // 周一 = 0
        s = dayStart(base); s.setDate(s.getDate() - wd);
        e = new Date(s); e.setDate(s.getDate() + 7);
        labels = ['一', '二', '三', '四', '五', '六', '日']; n = 7;
      } else if (kind === 'month') {
        s = dayStart(base); s.setDate(1);
        e = new Date(s); e.setMonth(e.getMonth() + 1);
        labels = ['1-7', '8-14', '15-21', '22-28', '29+']; n = 5;
      } else {
        s = dayStart(base); s.setMonth(0, 1);
        e = new Date(s); e.setFullYear(e.getFullYear() + 1);
        for (var i = 1; i <= 12; i++) labels.push(i + '月');
        n = 12;
      }
      return { s: s, e: e, labels: labels, n: n };
    }
    function prevOf(kind, p) {
      var s = new Date(p.s), e = new Date(p.e);
      if (kind === 'week') { s.setDate(s.getDate() - 7); e.setDate(e.getDate() - 7); }
      else if (kind === 'month') { s.setMonth(s.getMonth() - 1); e.setMonth(e.getMonth() - 1); }
      else { s.setFullYear(s.getFullYear() - 1); e.setFullYear(e.getFullYear() - 1); }
      return { s: s, e: e };
    }
    function idxOf(kind, t, p) {
      if (kind === 'week') return Math.floor((dayStart(t) - p.s) / 864e5);
      if (kind === 'month') return Math.min(4, Math.floor((t.getDate() - 1) / 7));
      return t.getMonth();
    }
    function sumIn(list, p) {
      var s = ms2s(p.s), e = ms2s(p.e), km = 0, c = 0;
      for (var i = 0; i < list.length; i++) {
        var t = Number(list[i].t0);
        if (!isFinite(t) || t < s || t >= e) continue;
        var v = Number(list[i].km);
        if (isFinite(v) && v > 0) km += v;
        c++;
      }
      return { km: km, c: c };
    }
    function fmtSpan(p) {
      var f = function (d) { return (d.getMonth() + 1) + '-' + d.getDate(); };
      var last = new Date(p.e); last.setDate(last.getDate() - 1);
      if (span === 'year') return p.s.getFullYear() + ' 年';
      return f(p.s) + ' ~ ' + f(last);
    }

    function render() {
      var all = trips(), p = period(span, new Date()), pv = prevOf(span, p);
      var buckets = [];
      for (var i = 0; i < p.n; i++) buckets.push(0);
      var s = ms2s(p.s), e = ms2s(p.e), km = 0, cnt = 0;
      for (var j = 0; j < all.length; j++) {
        var t = Number(all[j].t0);
        if (!isFinite(t) || t < s || t >= e) continue;
        var v = Number(all[j].km);
        if (isFinite(v) && v > 0) { km += v; }
        cnt++;
        var bi = idxOf(span, new Date(t * 1000), p);
        if (bi >= 0 && bi < p.n && isFinite(v) && v > 0) buckets[bi] += v;
      }
      var prev = sumIn(all, pv);
      var set = function (id, txt) { var el = $(id); if (el) el.textContent = txt; };
      set('tkKm', cnt ? km.toFixed(1) : '0');
      set('tkCnt', String(cnt));
      set('tkAvg', cnt ? (km / cnt).toFixed(1) : '--');
      if (prev.km > 0) {
        var d = (km - prev.km) / prev.km * 100;
        set('tkDelta', (d >= 0 ? '▲ ' : '▼ ') + Math.abs(d).toFixed(0) + '%');
        var de = $('tkDelta');
        if (de) de.setAttribute('data-dir', d >= 0 ? 'up' : 'down');
      } else {
        set('tkDelta', km > 0 ? '新增' : '--');
        var de2 = $('tkDelta');
        if (de2) de2.setAttribute('data-dir', km > 0 ? 'up' : 'none');
      }
      if (kindEl) kindEl.textContent = NAME[span];

      var mx = 0;
      for (var k = 0; k < buckets.length; k++) if (buckets[k] > mx) mx = buckets[k];
      var html = '';
      for (var b = 0; b < buckets.length; b++) {
        var h = mx > 0 ? Math.round(buckets[b] / mx * 100) : 0;
        if (h < 3 && buckets[b] > 0) h = 3;
        html += '<div class="tb' + (buckets[b] > 0 ? ' has' : '') + '">'
          + '<i style="height:' + h + '%"></i>'
          + '<b>' + p.labels[b] + '</b></div>';
      }
      bars.innerHTML = html;

      if (hint) {
        hint.textContent = fmtSpan(p) + ' · 本机共保存 ' + all.length + ' 段完整行程'
          + (all.length ? '（清空记录会一并清掉统计）' : '');
      }
    }

    seg.addEventListener('click', function (ev) {
      var t = ev.target;
      while (t && t !== seg && !t.getAttribute('data-span')) t = t.parentNode;
      if (!t || t === seg) return;
      var v = t.getAttribute('data-span');
      if (!v || v === span) return;
      span = v;
      var bs = seg.querySelectorAll('[data-span]');
      for (var i = 0; i < bs.length; i++) bs[i].classList.toggle('on', bs[i].getAttribute('data-span') === span);
      render();
      try { haptic('light'); } catch (e) {}
    });

    /* 切到行程页就刷一次；清空记录后也刷。 */
    document.addEventListener('click', function (ev) {
      var t = ev.target, hitPage = false, hitClear = false;
      while (t && t !== document) {
        if (t.id === 'btnTripClear') hitClear = true;
        if (t.getAttribute && t.getAttribute('data-page') === 'trips') hitPage = true;
        t = t.parentNode;
      }
      if (hitPage) setTimeout(render, 60);
      if (hitClear) setTimeout(render, 400);
    }, true);
    setInterval(function () {
      var pg = $('page-trips');
      if (pg && pg.classList.contains('active')) render();
    }, 8000);

    render();
  })();
  /*S-END*/
