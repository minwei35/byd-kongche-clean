"""Offline regression tests; all derived artifacts stay in this new directory."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / 'rea/apktool'
REQUIRED = ['cloud/BemfaMqtt.smali', 'cloud/BemfaSync.smali',
            'cloud/BemfaState.smali', 'cloud/BemfaSync$Result.smali',
            'cloud/BemfaCards.smali', 'wui/WebBridge.smali']

def module():
    path = HERE / 'bemfa_patch.py'
    if not path.exists():
        raise AssertionError('bemfa_patch.apply is not implemented')
    spec = importlib.util.spec_from_file_location('bemfa_patch', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class BemfaPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bemfa-test-', dir=HERE)
        self.work = Path(self.tmp.name)
        for name in REQUIRED:
            rel = 'smali_classes2/com/qinl/car/pub/' + name
            target = self.work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / rel, target)
        for name in ['index.html', 'app.js']:
            target = self.work / 'assets/ui' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / 'assets/ui' / name, target)
        self.sentinel = self.work / 'smali_classes2/com/qinl/car/pub/CredentialManager.smali'
        self.sentinel.write_text('DO NOT ALTER KEY STORAGE\n', encoding='utf-8')
        self.before = {p.relative_to(self.work).as_posix(): p.read_bytes()
                       for p in self.work.rglob('*') if p.is_file()}
        self.addCleanup(self.tmp.cleanup)

    def text(self, name):
        return (self.work / ('smali_classes2/com/qinl/car/pub/' + name)).read_text(encoding='utf-8')

    def test_three_classes_remove_network_control_and_storage_bodies(self):
        report = module().apply(self.work)
        for name in ['BemfaMqtt', 'BemfaSync', 'BemfaState']:
            text = self.text('cloud/' + name + '.smali')
            for danger in ['Ljava/net/', 'Landroid/net/', 'CarActionRunner;->',
                           'CredentialManager;->', 'SecureStore;->',
                           'getSharedPreferences', 'Landroid/os/Handler;']:
                executable = '\n'.join(body for _, body in module().METHOD.findall(text))
                self.assertNotIn(danger, executable, (name, danger))
        self.assertIn('const/4 v0, 0x0\n    return v0', self.text('cloud/BemfaMqtt.smali'))
        self.assertIn('invoke-direct/range {v0 .. v8}', self.text('cloud/BemfaSync.smali'))
        self.assertEqual('DO NOT ALTER KEY STORAGE\n', self.sentinel.read_text())
        self.assertGreater(len(report['methods']), 75)

    def test_bridge_keeps_javascript_annotation_and_non_null_contract(self):
        module().apply(self.work)
        text = self.text('wui/WebBridge.smali')
        for sig in ['bemfaSyncPull()V', 'exportDiag(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;',
                    'cardsTable()Ljava/lang/String;', 'takeLocalRestore()Ljava/lang/String;']:
            block = re.search(r'(?ms)^\.method [^\n]*' + re.escape(sig) + r'\n(.*?)^\.end method', text).group(1)
            self.assertIn('Landroid/webkit/JavascriptInterface;', block)
            self.assertNotIn('new-instance', block)
        for name in ['saveConfig', 'config']:
            pat = r'(?ms)^\.method [^\n]*\b' + name + r'\([^\n]*\n.*?^\.end method'
            original = self.before['smali_classes2/com/qinl/car/pub/wui/WebBridge.smali'].decode('utf-8').replace('\r\n', '\n')
            self.assertEqual(re.search(pat, original).group(), re.search(pat, text).group())
        self.assertNotIn('openConnection', re.search(r'(?ms)^\.method [^\n]* http\(.*?^\.end method', self.text('cloud/BemfaCards.smali')).group())

    def test_ui_strips_feature_text_preserves_ids_and_disabled_nodes(self):
        report = module().apply(self.work)
        html = (self.work / 'assets/ui/index.html').read_text(encoding='utf-8')
        original = self.before['assets/ui/index.html'].decode('utf-8')
        ids = lambda s: set(re.findall(r'\bid="([^"]+)"', s))
        self.assertEqual(ids(original), ids(html))
        for name in ['cfBemfa', 'btnBemfaPull', 'btnExportDiag', 'cfCustomCmd']:
            self.assertRegex(html, r'<[^>]+id="' + name + r'"[^>]*\bdisabled')
        self.assertNotIn('⤓ 从巴法云同步配置', html)
        self.assertNotIn('>小爱语音<', html)
        self.assertNotIn('Download/qinl-car-conf.json', html)
        self.assertIn('display:none!important', html)
        js = (self.work / 'assets/ui/app.js').read_text(encoding='utf-8')
        self.assertNotIn("$('cfBemfa').value = c.bemfa", js)
        self.assertIn('HARDEN_BEMFA_DISABLED', js)
        self.assertIn('cardsTable', js)
        self.assertEqual(4, len(report['ui_blocks']))

    def test_idempotent_and_exact_change_inventory(self):
        mod = module()
        first = mod.apply(self.work)
        after = {p.relative_to(self.work).as_posix(): p.read_bytes()
                 for p in self.work.rglob('*') if p.is_file()}
        second = mod.apply(self.work)
        again = {p.relative_to(self.work).as_posix(): p.read_bytes()
                 for p in self.work.rglob('*') if p.is_file()}
        self.assertEqual(after, again)
        changed = sorted(k for k in after if after[k] != self.before[k])
        self.assertEqual(changed, sorted(first['files']))
        self.assertEqual([], second['files'])
        self.assertEqual(7, len(changed))

    def test_preflight_rejects_missing_signature_before_any_write(self):
        p = self.work / 'smali_classes2/com/qinl/car/pub/cloud/BemfaMqtt.smali'
        p.write_text(p.read_text(encoding='utf-8').replace('start(Landroid/content/Context;)Z', 'unexpectedStart(Landroid/content/Context;)Z'), encoding='utf-8')
        before = {p.relative_to(self.work).as_posix(): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            module().apply(self.work)
        self.assertEqual(before, {p.relative_to(self.work).as_posix(): p.read_bytes() for p in self.work.rglob('*') if p.is_file()})

    def test_js_removed_feature_sections_are_inert_at_runtime(self):
        module().apply(self.work)
        js = (self.work / 'assets/ui/app.js').read_text(encoding='utf-8')
        self.assertNotIn("addEventListener('click', exportDiag)", js)
        self.assertNotIn("call('bemfaTouch', j)", js)
        self.assertNotIn('localStorage.setItem = function', js)
        self.assertNotIn("$('btnCardsOn').addEventListener", js)
        self.assertNotIn('APP_CHANGELOG = [\n', js)
        self.assertIn('onBemfaSync: function () {}', js)
        self.assertIn('onCards: function () {}', js)
        for ident in ['cardCards', 'cfgMqtt', 'sheetCustomCard', 'btnExportDiag']:
            html = (self.work / 'assets/ui/index.html').read_text(encoding='utf-8')
            parser = module()._Elements(html)
            node = next(n for n in parser.nodes if n['attrs'].get('id') == ident)
            self.assertEqual('1', node['attrs'].get('data-harden-removed'))
            self.assertEqual('display:none!important', node['attrs'].get('style'))

    def test_js_bridge_guard_runs_without_removed_native_calls(self):
        module().apply(self.work)
        js = (self.work / 'assets/ui/app.js').read_text(encoding='utf-8')
        dispatch = re.search(r'(?ms)  function call\(name\) \{.*?^  \}', js).group()
        callbacks = re.search(r'onBemfaSync: function \(\) \{\},\s+onCards: function \(\) \{\}', js).group()
        script = '''const assert = require('assert');
let calls = [];
let B = new Proxy({}, {get: (target, name) => function() {calls.push(name); return 'kept';}});
''' + dispatch + '\nconst callbacks = {' + callbacks + '''};
['cardsEnable','cardsCustomAdd','bemfaSyncPull','bemfaTouch','exportDiag','putLsSnapshot'].forEach(n => call(n, 'test'));
assert.strictEqual(calls.length, 0);
assert.deepStrictEqual(JSON.parse(call('cardsTable')).customs, []);
assert.strictEqual(JSON.parse(call('takeLocalRestore')).ls, '');
callbacks.onBemfaSync('{"ok":true,"lsJson":"test"}');
callbacks.onCards('{"phase":"doneOn","ok":true}');
assert.strictEqual(call('qrAuthorize'), 'kept');
assert.deepStrictEqual(calls, ['qrAuthorize']);
console.log('guard/callback/QR compatibility PASS');
'''
        node = Path.home() / '.dsh/dsh-runtimes/dsh-plugin-desktop-primary-runtime/dependencies/node/bin/node.exe'
        if not node.exists():
            self.skipTest('host Node executable is absent')
        result = subprocess.run([str(node), '-e', script], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('PASS', result.stdout)

    def test_javascript_syntax_with_host_node(self):
        module().apply(self.work)
        node = Path.home() / '.dsh/dsh-runtimes/dsh-plugin-desktop-primary-runtime/dependencies/node/bin/node.exe'
        if not node.exists():
            self.skipTest('host Node executable is absent')
        result = subprocess.run([str(node), '--check', str(self.work / 'assets/ui/app.js')], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

if __name__ == '__main__':
    unittest.main(verbosity=2)
