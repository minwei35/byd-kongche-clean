"""Offline, idempotent Bemfa removal for the clean 3.20.83 apktool tree.

Only apply(work) writes derived input-tree files. Import has no side effects.
Preflight validates all expected methods/UI blocks before any write. Existing
credential stores and BLE/QR methods are outside this patch's write set.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re

BASE = 'smali_classes2/com/qinl/car/pub/'
METHOD = re.compile(r'(?ms)^\.method ([^\n]+)\n(.*?)^\.end method')
RESULT = 'Lcom/qinl/car/pub/cloud/BemfaSync$Result;'
MARKER = 'HARDEN_BEMFA_DISABLED'
BRIDGE_NAMES = {
    'bemfaArchive', 'bemfaSyncPull', 'bemfaTouch', 'setBemfaSync',
    'cardsRun', 'cardsRefresh', 'cardsCustomAdd', 'cardsCustomDel',
    'cardsCustomRename', 'cardsDisable', 'cardsEnable', 'cardsSaveSel',
    'cardsTable', 'putLsSnapshot', 'takeLocalRestore', 'exportDiag',
}
REQUIRED_METHODS = {
    'cloud/BemfaMqtt.smali': ['start(Landroid/content/Context;)Z',
        'restart(Landroid/content/Context;)V', 'publish(Ljava/lang/String;Ljava/lang/String;)Z',
        'loop(Ljava/lang/String;)V', 'registerNetwork()V'],
    'cloud/BemfaSync.smali': ['push(Landroid/content/Context;Ljava/lang/String;)Z',
        'pull(Landroid/content/Context;Ljava/lang/String;)' + RESULT,
        'restoreFromFile(Landroid/content/Context;Ljava/lang/String;)' + RESULT,
        'snapshotJson(Landroid/content/Context;)Ljava/lang/String;',
        'http(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'],
    'cloud/BemfaState.smali': ['push(Landroid/content/Context;Ljava/util/Map;)V'],
    'cloud/BemfaCards.smali': ['http(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'],
    'wui/WebBridge.smali': ['bemfaArchive(Z)V', 'bemfaSyncPull()V',
        'bemfaTouch(Ljava/lang/String;)V', 'cardsTable()Ljava/lang/String;',
        'takeLocalRestore()Ljava/lang/String;',
        'exportDiag(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'],
}


def _string(value):
    return '    .locals 1\n    const-string v0, ' + json.dumps(value, ensure_ascii=True) + '\n    return-object v0'


def _result():
    # invoke-direct/range is required: constructor consumes 9 registers.
    return '''    .locals 9
    new-instance v0, Lcom/qinl/car/pub/cloud/BemfaSync$Result;
    const/4 v1, 0x0
    const-string v2, "Feature removed"
    const/4 v3, 0x0
    const/4 v4, 0x0
    const/4 v5, 0x0
    const/4 v6, 0x0
    const-string v7, ""
    invoke-static {}, Ljava/util/Collections;->emptyList()Ljava/util/List;
    move-result-object v8
    invoke-direct/range {v0 .. v8}, Lcom/qinl/car/pub/cloud/BemfaSync$Result;-><init>(ZLjava/lang/String;ZIIILjava/lang/String;Ljava/util/List;)V
    return-object v0'''


def _body(signature, owner):
    name = signature.split('(')[0].split()[-1]
    ret = signature.rsplit(')', 1)[1]
    if name == '<clinit>':
        return ('    .locals 1\n    new-instance v0, ' + owner + '\n'
                '    invoke-direct {v0}, ' + owner + '-><init>()V\n'
                '    sput-object v0, ' + owner + '->INSTANCE:' + owner + '\n    return-void')
    if ret == 'V':
        return '    .locals 0\n    return-void'
    if ret == RESULT:
        return _result()
    if ret == 'Ljava/lang/String;':
        values = {'cardsTable': '{"uid":"","table":[],"customs":[],"cmds":[]}',
                  'takeLocalRestore': '{"report":"","ls":""}',
                  'exportDiag': '{"ok":0,"err":"Feature removed"}',
                  'setBemfaSync': '{"ok":false,"msg":"Feature removed"}',
                  'cardsCustomAdd': '{"ok":false,"msg":"Feature removed"}',
                  'cardsCustomDel': '{"ok":false,"msg":"Feature removed"}',
                  'cardsCustomRename': '{"ok":false,"msg":"Feature removed"}',
                  'snapshotJson': '{}'}
        return _string(values.get(name, ''))
    containers = {'Ljava/util/List;': ('Ljava/util/Collections;', 'emptyList'),
                  'Ljava/util/Map;': ('Ljava/util/Collections;', 'emptyMap')}
    if ret in containers:
        cls, method = containers[ret]
        return ('    .locals 1\n    invoke-static {}, ' + cls + '->' + method + '()' + ret +
                '\n    move-result-object v0\n    return-object v0')
    if ret == 'Lorg/json/JSONObject;':
        return ('    .locals 1\n    new-instance v0, Lorg/json/JSONObject;\n'
                '    invoke-direct {v0}, Lorg/json/JSONObject;-><init>()V\n    return-object v0')
    if ret == '[B':
        return '    .locals 1\n    const/4 v0, 0x0\n    new-array v0, v0, [B\n    return-object v0'
    if ret.startswith(('L', '[')):
        return '    .locals 1\n    const/4 v0, 0x0\n    return-object v0'
    if ret in ('Z', 'I', 'B', 'S', 'C', 'F'):
        return '    .locals 1\n    const/4 v0, 0x0\n    return v0'
    if ret in ('J', 'D'):
        return '    .locals 2\n    const-wide/16 v0, 0x0\n    return-wide v0'
    raise ValueError('Unsupported return type: ' + signature)


def _patch_smali(text, relative, methods):
    owner = re.search(r'(?m)^\.class .* (L[^;]+;)$', text).group(1)
    all_methods = relative in ('cloud/BemfaMqtt.smali', 'cloud/BemfaSync.smali', 'cloud/BemfaState.smali')
    def replace(match):
        signature, old = match.groups()
        name = signature.split('(')[0].split()[-1]
        chosen = all_methods and name != '<init>'
        if relative == 'cloud/BemfaCards.smali':
            chosen = name == 'http'
        if relative == 'wui/WebBridge.smali':
            chosen = name.split('$', 1)[0] in BRIDGE_NAMES
        if not chosen:
            return match.group()
        # Preserve JavascriptInterface and other declaration annotations. Executable
        # code, try/catch, debug locals, labels and parameter annotations are removed.
        annotations = re.findall(r'(?ms)^    \.annotation .*?^    \.end annotation\n?', old)
        body = _body(signature, owner)
        lines = body.split('\n', 1)
        body = lines[0] + '\n' + ''.join(annotations) + (lines[1] if len(lines) > 1 else '')
        replacement = '.method ' + signature + '\n' + body + '\n.end method'
        methods.append({'file': BASE + relative, 'signature': signature,
                        'changed': replacement != match.group()})
        return replacement
    return METHOD.sub(replace, text)


class _Elements(HTMLParser):
    VOID = {'input', 'br', 'hr', 'img', 'meta', 'link', 'source', 'area', 'base', 'wbr', 'embed', 'param', 'col'}
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.starts = [0]
        for match in re.finditer('\n', text):
            self.starts.append(match.end())
        self.stack = []
        self.nodes = []
        self.feed(text)
    def position(self):
        row, col = self.getpos()
        return self.starts[row - 1] + col
    def handle_starttag(self, tag, attrs):
        start = self.position()
        node = {'tag': tag, 'attrs': dict(attrs), 'start': start,
                'end': start + len(self.get_starttag_text()),
                'parent': self.stack[-1] if self.stack else None}
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()
    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                self.stack[i]['end'] = self.text.index('>', self.position()) + 1
                del self.stack[i:]
                return


def _empty_node(node):
    tag = node['tag']
    ident = node['attrs']['id']
    attrs = (' id="' + ident + '" disabled hidden aria-hidden="true" tabindex="-1"'
             ' data-harden-removed="1" style="display:none!important"')
    if tag == 'input':
        return '<input' + attrs + ' type="hidden" value="">'
    if tag in _Elements.VOID:
        return '<' + tag + attrs + '>'
    # setKV() queries these classes; keep empty children for its compatibility.
    children = '<span class="kv-k"></span><span class="kv-v"></span>' if ident == 'cfgMqtt' else ''
    return '<' + tag + attrs + '>' + children + '</' + tag + '>'


def _patch_html(text, blocks):
    if MARKER in text:
        return text
    parser = _Elements(text)
    byid = {n['attrs'].get('id'): n for n in parser.nodes if n['attrs'].get('id')}
    for ident in ['cardCards', 'cfgMqtt', 'sheetCustomCard', 'btnExportDiag']:
        if ident not in byid:
            raise ValueError('Missing UI anchor: ' + ident)
    export = byid['btnExportDiag']
    while export and 'card' not in export['attrs'].get('class', '').split():
        export = export['parent']
    if not export:
        raise ValueError('Export card ancestor absent')
    targets = [byid['cardCards'], byid['cfgMqtt'], byid['sheetCustomCard'], export]
    edits = []
    for target in targets:
        children = [n for n in parser.nodes if target['start'] <= n['start'] < target['end'] and n['attrs'].get('id')]
        content = '<div hidden aria-hidden="true" style="display:none!important" data-harden-removed="1">'
        content += ''.join(_empty_node(n) for n in children) + '</div>'
        edits.append((target['start'], target['end'], content))
        blocks.append({'anchor': target['attrs'].get('id', 'exportDiagCard'),
                       'retained_ids': [n['attrs']['id'] for n in children]})
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    # Comments are not UI and may retain references to historical removed features.
    return '<!-- ' + MARKER + ' -->\n' + text


def _section(text, start, end, replacement):
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < a:
        raise ValueError('JS binding section not found: ' + start)
    return text[:a] + replacement + '\n\n  ' + text[b:]


def _patch_js(text):
    if MARKER in text:
        return text
    # Strip implementation and event bindings, not merely DOM visibility.
    text = _section(text, '  function exportDiag() {',
                    '  // ★★★ 3.15.40：预约时间滑条已删',
                    '  function exportDiag() {}')
    text = _section(text, '/* ═══════════ 小爱卡片', '/* ══ 界面设置快照',
        '''/* HARDEN_BEMFA_DISABLED: inert legacy callbacks */
  var CARDS = [], CUSTOMS = [], CMDOPTS = [];
  var customEditing = null, cloudCards = null, cardsBusy = false;
  function cardsSel() { return []; }
  function cardsFold() {}
  function cardsTag() {}
  function cardsRender() {}
  function customRender() {}
  function customOpen() {}
  function customClose() {}
  function customDel() {}
  function cardsInit() {}
  function cardsMarkRows() {}''')
    text = _section(text, '/* ══ 界面设置快照', '/* ★★★ 客户需求（2026-10-29，用户）',
                    'var lsLastSent = "";\n  function lsCollect() { return {}; }\n  function lsReport() {}\n  function lsApply() { return 0; }')
    text = _section(text, '/* ★★★ 客户需求（2026-10-29，用户）', '/* ★★★ 3.16.92（用户：「同一个界面，两种折叠方式」）', '')
    text, count = re.subn(r"(?ms)  if \(\$\('cfBemfa'\)\) \{\n    \$\('cfBemfa'\)\.addEventListener.*?^    \}\);\n  \}", '', text, count=1)
    if count != 1:
        raise ValueError('cfBemfa change binding absent')
    text = text.replace("$('cfBemfa').value = c.bemfa || '';", "$('cfBemfa').value = '';")
    text = text.replace("$('cfBemfa').dataset.saved = c.bemfa || '';", "$('cfBemfa').dataset.saved = '';")
    text = text.replace("bemfa: $('cfBemfa').value.trim(),", '')
    # Ensure legacy callers cannot reach removed bridge methods, even future callbacks.
    guard = '''    if (/^(?:bemfa|cards|setBemfaSync|putLsSnapshot|takeLocalRestore|exportDiag)/i.test(name)) {
      if (name === 'cardsTable') return '{"uid":"","table":[],"customs":[],"cmds":[]}';
      if (name === 'takeLocalRestore') return '{"report":"","ls":""}';
      return '{"ok":false,"msg":"Feature removed"}';
    }
'''
    if '  function call(name) {\n' not in text:
        raise ValueError('JS bridge dispatch missing')
    text = text.replace('  function call(name) {\n', '  function call(name) {\n' + guard, 1)
    # Historical release notes advertised the removed features; suppress that
    # stale public catalogue while keeping the array contract intact.
    text, count = re.subn(r'(?ms)  var APP_CHANGELOG = \[.*?^  \];', '  var APP_CHANGELOG = [];', text, count=1)
    if count != 1:
        raise ValueError('APP_CHANGELOG array absent')
    text = _section(text, '    /* ★★★ 客户需求（2026-10-29）：从巴法云同步配置',
                    '\n  };\n', '    onBemfaSync: function () {},\n    onCards: function () {}')
    text = text.replace('蓝牙 / 云端 / 小爱语音三条通道都照这份设置执行', '蓝牙通道按这份设置执行')
    return text


def apply(work):
    """Patch a decoded tree; return exact changed files/methods and retained IDs.

    This patch targets 3.20.83 signatures. Missing or renamed anchors fail before
    writing, rather than silently producing a partially disabled application.
    It does not decode, build, install, contact a network, or invoke BLE.
    """
    work = Path(work).resolve()
    originals = {}
    methods, blocks = [], []
    for relative, signatures in REQUIRED_METHODS.items():
        path = work / (BASE + relative)
        text = path.read_text(encoding='utf-8')
        for signature in signatures:
            count = sum(s.endswith(' ' + signature) for s, _ in METHOD.findall(text))
            if count != 1:
                raise ValueError('Expected exactly one method: ' + relative + ': ' + signature)
        originals[BASE + relative] = text
    # Validate the Result contract against actual smali before generating a caller.
    result = (work / (BASE + 'cloud/BemfaSync$Result.smali')).read_text(encoding='utf-8')
    if '.method public constructor <init>(ZLjava/lang/String;ZIIILjava/lang/String;Ljava/util/List;)V' not in result:
        raise ValueError('BemfaSync.Result constructor differs')
    for name in ['assets/ui/index.html', 'assets/ui/app.js']:
        originals[name] = (work / name).read_text(encoding='utf-8')
    derived = {BASE + relative: _patch_smali(originals[BASE + relative], relative, methods)
               for relative in REQUIRED_METHODS}
    derived['assets/ui/index.html'] = _patch_html(originals['assets/ui/index.html'], blocks)
    derived['assets/ui/app.js'] = _patch_js(originals['assets/ui/app.js'])
    changed = []
    for name, text in derived.items():
        if text != originals[name]:
            (work / name).write_text(text, encoding='utf-8', newline='\n')
            changed.append(name)
    return {'files': changed, 'methods': methods, 'ui_blocks': blocks}
