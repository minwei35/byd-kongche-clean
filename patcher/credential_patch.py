"""Non-destructive encrypted credential initialization for the derived APK."""
from pathlib import Path
import re

INIT = '''.method public final init(Landroid/content/Context;)V
    .locals 4

    const-string v0, "context"
    invoke-static {p1, v0}, Lkotlin/jvm/internal/Intrinsics;->checkNotNullParameter(Ljava/lang/Object;Ljava/lang/String;)V
    sget-object v0, Lcom/qinl/car/pub/CredentialManager;->prefs:Landroid/content/SharedPreferences;
    if-eqz v0, :init_begin
    sget-object v0, Lcom/qinl/car/pub/CredentialManager;->initError:Ljava/lang/String;
    if-nez v0, :init_begin
    return-void

    :init_begin
    const/4 v0, 0x0
    :try_start_init
    invoke-direct {p0, p1}, Lcom/qinl/car/pub/CredentialManager;->create(Landroid/content/Context;)Landroid/content/SharedPreferences;
    move-result-object v1
    sput-object v1, Lcom/qinl/car/pub/CredentialManager;->prefs:Landroid/content/SharedPreferences;
    sput-object v0, Lcom/qinl/car/pub/CredentialManager;->initError:Ljava/lang/String;
    :try_end_init
    .catchall {:try_start_init .. :try_end_init} :init_failed
    return-void

    :init_failed
    move-exception v2
    sput-object v0, Lcom/qinl/car/pub/CredentialManager;->prefs:Landroid/content/SharedPreferences;
    const-string v1, "storage_unavailable"
    sput-object v1, Lcom/qinl/car/pub/CredentialManager;->initError:Ljava/lang/String;
    return-void
.end method'''


def apply(work):
    target = Path(work) / 'smali_classes2/com/qinl/car/pub/CredentialManager.smali'
    original = target.read_text(encoding='utf-8')
    pattern = r'(?ms)^\.method public final init\(Landroid/content/Context;\)V\n.*?^\.end method'
    updated, count = re.subn(pattern, lambda match: INIT, original)
    if count != 1:
        raise ValueError('Expected unique CredentialManager.init(Context)')
    if updated != original:
        target.write_text(updated, encoding='utf-8')
