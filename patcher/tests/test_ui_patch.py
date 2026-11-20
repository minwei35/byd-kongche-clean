"""secure5 presentation contracts: calibration removed, manual upload only, 停扫 cell."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_UI = ROOT.parent.parent / 'rea/apktool/assets/ui'
sys.path.insert(0, str(ROOT))
import ui_patch  # noqa: E402


def _apply(tmp):
    ui = Path(tmp) / 'assets/ui'
    ui.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC_UI / 'index.html', ui / 'index.html')
    shutil.copy(SRC_UI / 'app.js', ui / 'app.js')
    ui_patch.apply(tmp)
    return ui


class Secure5UiTest(unittest.TestCase):
    def test_calibration_feature_files_are_gone(self):
        for name in ('calibration.js', 'calibration.css'):
            self.assertFalse((ROOT / 'assets' / name).exists(), name)
        for name in ('calibration_ui.py', 'calibration_patch.py'):
            self.assertFalse((ROOT / name).exists(), name)
        for name in ('Calibration.java', 'CalibrationPolicy.java'):
            self.assertFalse((ROOT / 'src/com/qinl/car/pub/trial' / name).exists(), name)
        build = (ROOT / 'build_secure.py').read_text(encoding='utf-8')
        self.assertNotIn('apply_calibration', build)
        self.assertNotIn('calibration_patch', build)
        self.assertNotIn('calibration_ui', build)

    def test_settings_only_keeps_manual_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
        for gone in ('btnAboutAuthor', '制作者', '联系方式', '关于作者', 'abDouyin', 'sheetAbout',
                     'sheetDouyin', 'calibration', '校准'):
            self.assertNotIn(gone, html, gone)
        self.assertIn('id="btnExportAbout"', html)   # 1.0.0：上传按钮换成导出压缩包
        self.assertNotIn('btnTrialUpload', html)
        self.assertIn('导出日志压缩包', html)
        self.assertIn('Content-Security-Policy', html)

    def test_pause_merged_into_connection_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        # 不再单独加一格：停扫直接改写「连接」那格（守护未开 → WiFi停扫 / 定时停扫）。
        self.assertNotIn('id="scopePause"', html)
        self.assertEqual(html.count('id="scopeConn"'), 1)
        self.assertIn('_cn.textContent = pauseLabelOf(scopePause)', js)
        self.assertIn("var _cn = $('scopeConn');", js)
        self.assertNotIn("scopeSetTxt('scopePause'", js)

    def test_manual_upload_only(self):
        # 1.0.0：上传组件已删除，公开版没有任何上报出口
        self.assertFalse((ROOT / 'src/com/qinl/car/pub/trial/SecureUpload.java').exists())
        self.assertNotIn('AndroidBridge.logUploadNow',
                         (ROOT / 'ui_patch.py').read_text(encoding='utf-8'))

    def test_app_js_parses_and_drops_removed_nodes(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node runtime required')
        with tempfile.TemporaryDirectory() as tmp:
            js_path = _apply(tmp) / 'app.js'
            r = subprocess.run([node, '--check', str(js_path)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(r.returncode, 0, r.stderr)
            js = js_path.read_text(encoding='utf-8')
        self.assertNotIn('btnAboutAuthor', js)
        self.assertNotIn('aboutLongFired', js)
        self.assertNotIn('aboutClose', js)
        self.assertIn('$(\'updLog\').textContent', js)

    def test_pause_labels(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node runtime required')
        with tempfile.TemporaryDirectory() as tmp:
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        block = js[js.index('/*P-BEGIN*/'):js.index('/*P-END*/') + len('/*P-END*/')]
        cases = [(dict(paused=1, on=1), 'WiFi停扫'),
                 (dict(paused=1, sched=1), '定时停扫'),
                 (dict(paused=1, on=1, sched=1), '定时+WiFi停扫'),
                 (dict(paused=1), '后台停扫'),
                 (dict(paused=0, on=1), ''),
                 (dict(error='stat failed'), '')]
        script = block + '''
const cases=%s;
for (const [r, want] of cases) { const got = pauseLabelOf(r); if (got !== want) { console.error(JSON.stringify(r), got, want); process.exit(1); } }
if (pauseLabelOf(null) !== '') process.exit(2);
console.log('PASS pause labels');
''' % json.dumps(cases, ensure_ascii=False)
        r = subprocess.run([node, '-e', script], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_threshold_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        # 波形卡表头长了「阈值」按钮，弹层带两个数字输入 + 三个预设
        self.assertIn('id="btnScopeThr"', html)
        self.assertIn('id="sheetThr"', html)
        for el in ('thrEnter', 'thrExit', 'thrTip', 'thrMsg', 'btnThrSave', 'btnThrCancel'):
            self.assertIn('id="%s"' % el, html)
        self.assertEqual(html.count('data-thr-preset'), 3)
        # 原生夹取区间 + 迟滞校验都在，桥调用必须用 setRssiEnter/setRssiExit
        self.assertIn('THR_EN_MIN = -90', js)
        self.assertIn('THR_EX_MAX = -40', js)
        self.assertIn('THR_GAP = 3', js)
        self.assertIn("call('setRssiEnter'", js)
        self.assertIn("call('setRssiExit'", js)
        self.assertIn("lastBleSt.rssiEnter = en", js)

    def test_trip_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        for el in ('cardTripStat', 'tripSeg', 'tripBars', 'tkKm', 'tkCnt',
                   'tkAvg', 'tkDelta', 'tripStatHint'):
            self.assertIn('id="%s"' % el, html)
        # 三个周期按钮 + 卡片插在「行程记录」标题之前
        self.assertEqual(html.count('data-span='), 3)
        self.assertLess(html.index('id="cardTripStat"'), html.index('>行程记录<'))
        # 只读本机行程表，自己算周期；不得写回或调用新桥
        self.assertIn('initTripStat', js)
        self.assertIn("'qinl_trips'", js)
        self.assertIn('864e5', js)

    def test_trip_kpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        for el in ('cardTripKpi', 'kpiLongest', 'kpiLatest', 'kpiBusiest', 'kpiDays',
                   'kpiAvgTrip', 'kpiPerDay', 'chgTitle', 'chgFrom', 'chgTo',
                   'chgGain', 'chgKm', 'chgHint'):
            self.assertIn('id="%s"' % el, html)
        # 关键指标卡必须排在统计卡之后、行程记录之前
        self.assertLess(html.index('id="cardTripStat"'), html.index('id="cardTripKpi"'))
        self.assertLess(html.index('id="cardTripKpi"'), html.index('>行程记录<'))
        # 充电：本次/上次两条记录，靠电量+总里程现算"充完开了多远"
        self.assertIn("'qinl_charge_cur'", js)
        self.assertIn("'qinl_charge_last'", js)
        self.assertIn('initTripKpi', js)
        self.assertIn('chgBoot', js)
        self.assertIn('chgTick', js)
        self.assertIn('b.battery', js)
        self.assertIn('b.mileage', js)
        # 官方通知时刻：原生 KCCharge 优先，拿不到就退回轮询
        self.assertIn('nativeWindow', js)
        self.assertIn('KCCharge', js)
        self.assertIn('id="chgAccess"', html)
        self.assertIn('id="chgSrc"', html)
        # 旧的"在车/充电"比例条已撤掉
        self.assertNotIn('barDrive', html)
        self.assertNotIn('id="barCharge"', html)

    def test_chan_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        for el in ('sheetChan', 'chanState', 'chanWhy', 'chanEta', 'btnChanGo',
                   'btnCarPick', 'btnCarReset', 'chanClose'):
            self.assertIn('id="%s"' % el, html)
        # 点通道牌开弹层；换图 / 还原复用原生已有的 pickCarImage / resetCarImage
        self.assertIn('bindChanSheet', js)
        self.assertIn('pickCarImage()', js)
        self.assertIn('resetCarImage()', js)
        # 不提供"强制通道"——原生没有覆盖接口，别假装有
        self.assertNotIn('forceChannel', js)
        self.assertNotIn('setChannel', js)

    def test_control_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (_apply(tmp) / 'index.html').read_text(encoding='utf-8')
            js = (_apply(tmp) / 'app.js').read_text(encoding='utf-8')
        # 二次确认从裸开关变成"名字 + 含义 + 开关"的整行
        self.assertIn('id="ctlCfm"', html)
        self.assertIn('id="ctlCfmState"', html)
        self.assertIn('控车二次确认', html)
        # 开关本体 id 不变（app.js 的 initCfm 按 id 绑），且只出现一次
        self.assertEqual(html.count('id="swConfirmCmd"'), 1)
        # 通道标签：原生写「云端」/「蓝牙优先」，我们改写成说人话的版本
        self.assertIn('data-chan', html)
        self.assertIn("'云端'", js)
        self.assertIn('云端通道', js)
        self.assertIn('蓝牙直连', js)
        self.assertIn('MutationObserver', js)

    def test_skin_switcher(self):
        import ui_v4_patch
        with tempfile.TemporaryDirectory() as tmp:
            ui = Path(tmp) / 'assets/ui'
            ui.mkdir(parents=True, exist_ok=True)
            shutil.copy(SRC_UI / 'index.html', ui / 'index.html')
            shutil.copy(SRC_UI / 'app.js', ui / 'app.js')
            ui_patch.apply(tmp)
            ui_v4_patch.apply(tmp)
            html = (ui / 'index.html').read_text(encoding='utf-8')
            boot = (ui / 'skin.js').read_text(encoding='utf-8')
            plat = (ui / 'v4-platinum.css').read_text(encoding='utf-8')
        # 三份资源都要进包，且顺序必须是 styles -> v4 -> platinum -> skin.js
        for name in ('v4.css', 'v4-platinum.css', 'skin.js'):
            self.assertIn(name, html)
        self.assertLess(html.index('href="v4.css"'), html.index('href="v4-platinum.css"'))
        self.assertLess(html.index('href="v4-platinum.css"'), html.index('src="skin.js"'))
        # 外观卡 + 三个选项 + 落盘 key
        self.assertIn('id="cardSkin"', html)
        self.assertEqual(html.count('data-skin="'), 3)
        self.assertIn("localStorage", boot)
        self.assertIn("'kc_skin'", boot)
        # 4.4.1：必须同步 app.js 的 qinl_theme，并挂 MutationObserver 兜底
        self.assertIn('qinl_theme', boot)
        self.assertIn('MutationObserver', boot)
        self.assertIn('wantTheme', boot)
        self.assertIn("setAttribute('data-skin'", boot)
        # 白金皮：只许配色，不许几何；不许裸 :root
        for bad in ('margin', 'padding:', 'width:', 'height:', 'display:', 'float:',
                    'flex', 'grid', 'gap:', 'position:', 'transform'):
            self.assertNotIn(bad, plat, bad)
        # 方位属性只允许出现在 border-top/border-left 这类复合属性里
        self.assertIsNone(re.search(r'(?<![-\w])(top|left|right|bottom)\s*:', plat))
        self.assertNotIn(chr(10) + ':root', plat)
        self.assertNotIn('url(', plat)
        self.assertNotIn('@import', plat)
        self.assertIn('#D8C29A', plat)

    def test_second_apply_is_refused_without_partial_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            ui = _apply(tmp)
            before = {p.name: p.read_bytes() for p in ui.iterdir()}
            with self.assertRaises(AssertionError):
                ui_patch.apply(tmp)
            self.assertEqual(before, {p.name: p.read_bytes() for p in ui.iterdir()})


if __name__ == '__main__':
    unittest.main()
