"""secure5 presentation patch.

Three changes on top of the hardened work tree, all presentation-level:
  * the settings "关于" card keeps only the manual encrypted-upload control
    (author / douyin / contact / about-author entry and their sheets are removed);
  * the BLE waveform live row gains a 停扫 cell fed by the native bgStopStat(), so a
    frozen waveform can be told apart from "WiFi/定时 停扫" at a glance;
  * upload is manual only: the button calls logUploadNow, nothing schedules uploads.

Import is read/write-free; call apply(work) explicitly.
"""
from pathlib import Path
import re

CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; '
       "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'>")

UPLOAD_BLOCK = '''<div class="ble-actions" style="margin-top:10px">
          <button class="btn btn-primary" id="btnExportAbout">\U0001F4E6 导出日志压缩包</button>
        </div>
        <div class="hint" id="diagExportHintAbout">支持按时间段筛选（如今天 13:00~14:00），打包成 zip 存到 <b>Download/BYD-Kongche-Logs/</b>，不上传任何服务器。</div>'''

HERE_DIR = Path(__file__).resolve().parent
THR_JS = (HERE_DIR / 'assets/thr.js').read_text(encoding='utf-8')
CTLHEAD_JS = (HERE_DIR / 'assets/ctlhead.js').read_text(encoding='utf-8')
CHAN_JS = (HERE_DIR / 'assets/chan.js').read_text(encoding='utf-8')
TRIPSTAT_JS = (HERE_DIR / 'assets/tripstat.js').read_text(encoding='utf-8')
TRIPSTAT_CARD = (HERE_DIR / 'assets/tripstat_card.html').read_text(encoding='utf-8')
TRIPKPI_JS = (HERE_DIR / 'assets/tripkpi.js').read_text(encoding='utf-8')
TRIPKPI_CARD = (HERE_DIR / 'assets/tripkpi_card.html').read_text(encoding='utf-8')
CHAN_SHEET = (HERE_DIR / 'assets/chan_sheet.html').read_text(encoding='utf-8')
THR_SHEET = (HERE_DIR / 'assets/thr_sheet.html').read_text(encoding='utf-8')
LOGEXPORT_SHEET = (HERE_DIR / 'assets/logexport_sheet.html').read_text(encoding='utf-8')
LOGEXPORT_JS = (HERE_DIR / 'assets/logexport.js').read_text(encoding='utf-8')
BLE_PAUSE_BAR = (
    '<div class="ble-pause-bar" id="blePauseBar" hidden>\n'
    '  <div class="ble-pause-info">\n'
    '    <div class="ble-pause-txt" id="blePauseTxt">后台停扫生效中</div>\n'
    '    <div class="ble-pause-sub" id="blePauseSub"></div>\n'
    '  </div>\n'
    '  <button class="ble-pause-btn" id="btnBleTempResume" type="button">临时恢复 30 分</button>\n'
    '</div>\n'
)

CTL_HEAD_OLD = (
    '<div class="sec-title has-sw">车辆控制<span class="chan-tag" id="chanTag">通道检测中</span>'
    '<span class="sw-mini" id="swConfirmCmd" role="switch" aria-checked="false" '
    'title="控车二次确认：开=点按钮先弹确认框，关=点一下直接执行"><i></i></span></div>')
CTL_HEAD_NEW = (
    '<div class="sec-title has-sw">车辆控制<span class="chan-tag" id="chanTag" data-chan="">通道检测中</span></div>')
CTL_CFM_ROW = (
    '<div class="ctl-cfm" id="ctlCfm">'
    '<span class="ctl-cfm-k">控车二次确认</span>'
    '<span class="ctl-cfm-state" id="ctlCfmState">关 · 点一下直接执行</span>'
    '<span class="sw-mini" id="swConfirmCmd" role="switch" aria-checked="false" aria-label="控车二次确认"><i></i></span>'
    '</div>')

PAUSE_JS = '''  /*P-BEGIN*/
  /* secure6：停扫状态直接并进「连接」格 —— 读原生 bgStopStat 的 paused/on/sched。
     理由：后台自动停扫生效后服务真的会停，波形随之停住；以前界面没有任何提示，
     只能靠猜（日志里 2026-11-20 08:04:01 WiFi 停扫后 靠近诊断 整段消失）。 */
  var scopePause = null, scopePauseAt = 0;
  function pauseLabelOf(r) {
    if (!r || r.error) return '';
    if (Number(r.paused || 0) !== 1) return '';
    var parts = [];
    if (Number(r.sched || 0) === 1) parts.push('定时');
    if (Number(r.on || 0) === 1) parts.push('WiFi');
    return (parts.length ? parts.join('+') : '后台') + '停扫';
  }
  function pauseDetailOf(r) {
    if (!r || r.error || Number(r.paused || 0) !== 1) return '';
    var out = [];
    if (Number(r.sched || 0) === 1) out.push('定时时段内');
    if (Number(r.on || 0) === 1) {
      out.push('WiFi ' + String(r.ssid || '-') + ' ' +
        (Number(r.known || 0) === 1 ? (Number(r.rssi) + ' dBm') : '信号不可读') +
        ' · 门槛 ' + Number(r.thr));
    }
    return out.join('｜');
  }
  function scopePauseRefresh() {
    var now = Date.now();
    if (now - scopePauseAt < 3000) return;   // 渲染循环 200ms 一次，别每次都打桥
    scopePauseAt = now;
    try { var r = json(call('bgStopStat'), null); if (r) scopePause = r; } catch (e) { warn('scopePause', e); }
  }
  /*P-END*/
'''

def _cut_div(text, marker):
    """Remove the <div ...> block that contains marker, matching nested divs."""
    at = text.index(marker)
    start = text.rindex('<div', 0, at)
    i, depth = start, 0
    for m in re.finditer(r'<div\b|</div>', text[start:]):
        depth += 1 if m.group().startswith('<div') else -1
        if depth == 0:
            i = start + m.end()
            break
    else:
        raise ValueError('unbalanced div for ' + marker)
    return text[:start] + text[i:]


def _patch_html(html):
    assert 'Content-Security-Policy' not in html
    html = html.replace('<head>', '<head>\n' + CSP, 1)
    # 4.3：车辆控制标题行 —— 通道标签加语义、二次确认从裸开关变成带说明的整行。
    if CTL_HEAD_OLD in html:
        html = html.replace(CTL_HEAD_OLD, CTL_HEAD_NEW + chr(10) + CTL_CFM_ROW, 1)
    elif 'id="ctlCfm"' not in html:
        raise ValueError('车辆控制标题行变了')
    # 4.5：行程页加「行程统计」卡（周/月/年），插在「行程记录」标题之前。
    trip_anchor = '<div class="sec-title">行程记录</div>'
    if 'id="cardTripStat"' not in html and trip_anchor in html:
        html = html.replace(trip_anchor, TRIPSTAT_CARD + TRIPKPI_CARD + trip_anchor, 1)
    # 4.1：波形卡标题右侧加「阈值」按钮（长按拖动只能凑个大概，给个精确入口）。
    head_old = '<div class="sec-inline">蓝牙信号波形<span class="sec-now" id="scopeMac">--</span></div>'
    head_new = ('<div class="sec-inline">蓝牙信号波形<span class="sec-tools">'
                '<span class="sec-now" id="scopeMac">--</span>'
                '<button class="scope-gear" id="btnScopeThr" type="button">阈值</button></span></div>')
    if head_old in html:
        html = html.replace(head_old, head_new, 1)
    elif 'id="btnScopeThr"' not in html:
        raise ValueError('波形卡表头变了')
    if 'id="sheetChan"' not in html:
        _ta = '<div class="toast" id="toast"></div>'
        if _ta not in html:
            raise ValueError('toast 锚点变了')
        html = html.replace(_ta, CHAN_SHEET + _ta, 1)
    if 'id="sheetThr"' not in html:
        toast_anchor = '<div class="toast" id="toast"></div>'
        if toast_anchor not in html:
            raise ValueError('toast 锚点变了')
        html = html.replace(toast_anchor, THR_SHEET + toast_anchor, 1)
    if 'id="sheetLogExport"' not in html:
        toast_anchor = '<div class="toast" id="toast"></div>'
        if toast_anchor not in html:
            raise ValueError('toast 锚点变了')
        html = html.replace(toast_anchor, LOGEXPORT_SHEET + toast_anchor, 1)
    if 'id="blePauseBar"' not in html and '<div class="scope-live">' in html:
        html = html.replace('<div class="scope-live">', BLE_PAUSE_BAR + '<div class="scope-live">', 1)
    # 停扫并进「连接」格，不再新增格子；这里只确认原有状态行还在。
    for live_id in ('scopeConn', 'scopeRssi', 'scopeState'):
        assert 'id="' + live_id + '"' in html, live_id
    # 设置页「关于」卡片：只留手动加密上传。
    for pat in (r'\s*<div class="kv"><span class="kv-k">制作者</span>.*?</div>',
                r'\s*<div class="kv kv-cp" data-copy="XXD_D".*?</div>',
                r'\s*<div class="kv"><span class="kv-k">联系方式</span>.*?</div>'):
        html, n = re.subn(pat, '', html, count=1, flags=re.S)
        if n != 1:
            raise ValueError('settings row not found: ' + pat)
    about_btn = re.compile(r'<div class="ble-actions" style="margin-top:10px">\s*'
                           r'<button class="btn btn-primary" id="btnAboutAuthor">关于作者</button>\s*</div>')
    html, n = about_btn.subn(UPLOAD_BLOCK, html, count=1)
    if n != 1:
        raise ValueError('about-author button anchor changed')
    for marker in ('id="sheetAbout"', 'id="sheetDouyin"'):
        if marker in html:
            html = _cut_div(html, marker)
    # 注释里还留着「关于作者 / 抖音」的历史说明 —— 一起清掉，别在源码里继续指路。
    html = re.sub(r'(?s)<!--.*?-->',
                  lambda m: '' if ('关于作者' in m.group() or '抖音' in m.group()) else m.group(), html)
    if 'id="btnCheckUpdate"' in html:
        html = html.replace('id="btnCheckUpdate"', 'hidden disabled style="display:none!important" id="btnCheckUpdate"')
    for gone in ('btnAboutAuthor', 'abDouyin', 'sheetAbout', 'sheetDouyin', '制作者', '联系方式', '关于作者'):
        if gone in html:
            raise ValueError('still present: ' + gone)
    return html


def _patch_js(js):
    js = js.replace("$('updLog').innerHTML =", "$('updLog').textContent =")
    js = js.replace("toast('日志已上传（作者端可查）', 'ok');", "toast('加密日志上传已开始');")
    # 「关于作者」长按 3 秒的隐藏上传入口随按钮一起退役 —— 上传只剩设置页那颗明面按钮。
    hold_start = js.index('  var aboutLongFired = false;')
    hold_end = js.index('\n  })();\n', hold_start) + len('\n  })();\n')
    js = js[:hold_start] + js[hold_end:]
    click_start = js.index("  $('btnAboutAuthor').addEventListener('click', function () {")
    click_end = js.index('\n  });\n', click_start) + len('\n  });\n')
    js = js[:click_start] + js[click_end:]
    js = js.replace("  $('aboutClose').addEventListener('click', function () { $('sheetAbout').hidden = true; });\n", '')
    assert 'btnAboutAuthor' not in js and 'aboutLongFired' not in js and 'aboutClose' not in js
    anchor = '  function renderScope(st) {'
    assert js.count(anchor) == 1 and '/*P-BEGIN*/' not in js
    js = js.replace(anchor, PAUSE_JS + chr(10) + THR_JS + chr(10) + CTLHEAD_JS + chr(10) + CHAN_JS + chr(10) + TRIPSTAT_JS + chr(10) + TRIPKPI_JS + chr(10) + LOGEXPORT_JS + anchor, 1)
    state = "    scopeSetTxt('scopeState', st.state || '--');"
    assert js.count(state) == 1
    js = js.replace(state, state + '''
    /* secure6：停扫直接并进「连接」格 —— 停扫时服务本来就没跑，只写「守护未开」等于不说原因。 */
    scopePauseRefresh();
    var _pauseOn = !!(scopePause && Number(scopePause.paused || 0) === 1);
    var _cn = $('scopeConn');
    if (_cn) {
      if (_pauseOn) {
        _cn.textContent = pauseLabelOf(scopePause);
        _cn.classList.remove('link-live');
        _cn.classList.add('link-standby');
        _cn.style.color = '#D9615A';
        _cn.title = pauseDetailOf(scopePause) || '后台停扫中';
      } else {
        _cn.style.color = '';
        _cn.title = st.linkDetail || '';
      }
    }''', 1)
    js += '''
'''

    # ── 4.10 补：把摘掉巴法云卡片后所有没守卫的 JS 引用统一兜住（正则版，幂等）──
    js = re.sub(r"(?m)^(\s*)\$\(('cardsHint')\)\.(innerHTML|textContent)\s*=",
                r"\1if ($('cardsHint')) $('cardsHint').\3 =", js)
    js = re.sub(r"(?m)^(\s*)\$\(('cfBemfa')\)\.value\s*=",
                r"\1if ($('cfBemfa')) $('cfBemfa').value =", js)
    for _cid in ('btnCardsOn', 'btnCardsOff', 'btnCardsFresh'):
        _a = "  $('%s').addEventListener(" % _cid
        _b = "  if ($('%s')) $('%s').addEventListener(" % (_cid, _cid)
        if _a in js:
            js = js.replace(_a, _b)

    # 4.12：顶栏两颗按钮已移除，老代码里按 id 直接绑定会抛错 —— 统一兜住
    for _sid in ('btnSound', 'btnTheme'):
        _a = "  $('%s').addEventListener(" % _sid
        _b = "  if ($('%s')) $('%s').addEventListener(" % (_sid, _sid)
        if _a in js:
            js = js.replace(_a, _b)
    # 4.12：顶栏副标题改紧凑格式（"刷新于 2026-11-20 14:08:23" -> "14:08:23 刷新"），
    # 少 10 个字符，一行放得下；完整时间仍写进 title，长按/无障碍可读。
    _old_sub = ("    sub.textContent = ((plateHidden || !plate) ? '' : plate + ' · ') + onTxt +" + chr(10) +
                "      '刷新于 ' + fmtTimeSec(stamp) +")
    _new_sub = ("    var _ft = fmtTimeSec(stamp);" + chr(10) +
                "    sub.textContent = ((plateHidden || !plate) ? '' : plate + ' · ') + onTxt +" + chr(10) +
                "      _ft + ' 刷新' +")
    if _old_sub in js:
        js = js.replace(_old_sub, _new_sub, 1)
        _tail = "      (b && b.empty ? '（云端暂未上报）' : (b && b.stale ? '（缓存）' : ''));"
        if _tail in js and 'sub.title = _ft' not in js:
            js = js.replace(_tail, _tail + chr(10) + "    try { sub.title = _ft; } catch (e) {}", 1)
    # 1.0.0：检查更新按钮已摘，顶层绑定要跳过
    if "  $('btnCheckUpdate').addEventListener(" in js:
        js = js.replace("  $('btnCheckUpdate').addEventListener(",
                        "  if ($('btnCheckUpdate')) $('btnCheckUpdate').addEventListener(")
    return js


def apply(work):
    work = Path(work)
    ui = work / 'assets/ui'
    html = (ui / 'index.html').read_text(encoding='utf-8')

    # ── 1.0.0：设置页收尾 ──
    #  · 桌面图标卡摘掉（只保留包内那套白色图标）
    #  · 更新日志卡摘掉（公开版不跟随作者发版节奏）
    #  · 「检查更新」按钮与「启动时自动检查一次」文案摘掉（UpdateChecker.updateUrls 已置空）
    #  · 原独立「导出诊断包」卡并入「关于」，按钮 id 仍是 btnExportDiag（复用既有流程）
    for _gone in ('id="iconCard"', 'id="chgBody"'):
        if _gone in html:
            html = _cut_div(html, _gone)
    if 'id="btnCheckUpdate"' in html:
        html = re.sub(r'\s*<div class="ble-actions">\s*<button class="btn btn-ghost" id="btnCheckUpdate">.*?</button>\s*</div>', '', html, count=1, flags=re.S)
    if 'id="updateHint"' in html:
        html = re.sub(r'\s*<div class="hint" id="updateHint">.*?</div>', '', html, count=1, flags=re.S)
    # ── 4.12：顶栏瘦身 —— 声音挪进设置、皮肤按钮删掉 ──
    # 目的：顶栏右侧只留 ⚙，让「刷新于 2026-11-20 14:0x:xx」能完整显示一行。
    def _cut_btn(text, bid):
        m = re.search(r'\s*<button class="icon-btn" id="%s".*?</button>' % bid, text, re.S)
        if not m:
            return text, None
        return text[:m.start()] + text[m.end():], m.group(0)

    html, _snd_btn = _cut_btn(html, 'btnSound')
    html, _ = _cut_btn(html, 'btnTheme')
    if _snd_btn is not None:
        # 用同一颗按钮的原型（含 svg）重建设置里的「声音」卡，行为由注入脚本接管
        _card = (
            '<div class="card" id="cardSound">\n'
            '  <div class="sec-inline">声音<span class="sec-now" id="sndNow">开</span></div>\n'
            '  <div class="cfg-sound">\n'
            '    <div class="cfg-sound-k">音效总开关</div>\n'
            '    <div class="cfg-sound-tip">关掉后 App 里所有提示音都不响；通知、控车与记录不受影响。</div>\n'
            '    <span class="switch on" id="swSound"><i></i></span>\n'
            '  </div>\n'
            '</div>\n'
        )
        _page = '<section class="page" id="page-settings">'
        if _page in html:
            # 插在设置页开头；ui_v4_patch 稍后会把「外观」卡插到同一个位置的前面，
            # 最终顺序 = 外观 → 声音 → 耗电分析
            html = html.replace(_page, _page + chr(10) + _card, 1)
    # ── 4.10：账户页「小爱卡片（巴法云）」整块摘掉 ──
    # 这条链路在本版是有意 inert 的（Bemfa MQTT 不外连、不订阅），留着只是死 UI；
    # 摘 DOM 时必须同时给 app.js 里没守卫的 $('cfBemfa') / $('btnCards*') 加守卫，
    # 否则 loadConfig 与事件绑定会在启动时抛 ReferenceError（3.15.94 事故同因）。
    # ── 4.11：设置页「卡片中心 · 锁屏媒体卡片」也摘掉（4 个下拉 mcBtn1..4）──
    if 'id="cardCenterCard"' in html:
        html = _cut_div(html, 'id="cardCenterCard"')
    if 'id="cardCards"' in html:
        html = _cut_div(html, 'id="cardCards"')
    # bemfa 加固层把这张卡改成了「隐藏空壳 + 搬家后的子节点」，所以还要按子节点各切一刀，
    # 否则会留下一坨 display:none 的死 DOM（tagCards / cfBemfa / cardsBody 等）。
    for _gone in ('id="tagCards"', 'id="sheetCustomCard"'):
        if _gone in html:
            html = _cut_div(html, _gone)
    if 'id="cfgMqtt"' in html:
        html = re.sub(r'\s*<div class="kv" id="cfgMqtt">.*?</div>', '', html, count=1, flags=re.S)
    (ui / 'index.html').write_text(_patch_html(html), encoding='utf-8')
    js = (ui / 'app.js').read_text(encoding='utf-8')
    (ui / 'app.js').write_text(_patch_js(js), encoding='utf-8')
