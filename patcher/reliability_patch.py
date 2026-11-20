"""Drop Watch API payloads at the log source, before any logcat sink."""
from pathlib import Path
import re

def apply(work):
    p=Path(work)/'smali_classes2/com/qinl/car/pub/cloud/WatchApiClient.smali'
    text=p.read_text(encoding='utf-8')
    pattern=r'(?ms)^\.method private final log\(Ljava/lang/String;\)V\n.*?^\.end method'
    body='''.method private final log(Ljava/lang/String;)V
    .locals 1
    const-string v0, "WatchApiClient"
    const-string p1, "[WatchApi] event [payload-omitted]"
    invoke-static {v0, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method'''
    text,count=re.subn(pattern,lambda _:body,text)
    if count!=1:raise ValueError('WatchApiClient log signature changed')
    p.write_text(text,encoding='utf-8')
