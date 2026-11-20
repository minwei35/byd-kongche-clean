"""Baseline migration, credential preservation and native defaults for the hardened build.

secure5 removed the calibration sampling feature; only the parts that are independent of it
stay here: encrypted credential init, the one-shot recommended-settings migration and the
observation-baseline defaults that the migration seeds.
"""
from pathlib import Path
import re


def apply(work):
    work = Path(work)
    base = work / 'smali_classes2/com/qinl/car/pub'
    from credential_patch import apply as preserve_credentials
    preserve_credentials(work)
    p = base / 'MainActivity.smali'
    s = p.read_text(encoding='utf-8')
    anchor = '    invoke-super {p0, p1}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(Landroid/os/Bundle;)V'
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor + '\n    invoke-static {p0}, Lcom/qinl/car/pub/trial/Baseline;->apply(Landroid/content/Context;)V')
    p.write_text(s, encoding='utf-8')
    # Native defaults used by "reset" also agree with the observation baseline.
    p = base / 'wui/BleRuntime.smali'
    s = p.read_text(encoding='utf-8')
    for method in ['autoNear', 'autoFar']:
        pat = re.compile(r'(?ms)^\.method public final ' + method + r'\(Landroid/content/Context;\)Z\n.*?^\.end method')
        m = pat.search(s)
        assert m, method
        body = m.group()
        body, n = re.subn(r'const/4 (v\d+), 0x1', r'const/4 \1, 0x0', body)
        assert n == 1, (method, n)
        s = s[:m.start()] + body + s[m.end():]
    p.write_text(s, encoding='utf-8')
    # Keep threshold defaults consistent with the migrated -70/-83 pair.
    p = base / 'BleScanService.smali'
    s = p.read_text(encoding='utf-8')
    pat = re.compile(r'(const-string v6, "rssi_exit"\s+const/16 v7, )-0x50')
    s, n = pat.subn(r'\g<1>-0x53', s)
    assert n == 1, n
    p.write_text(s, encoding='utf-8')
