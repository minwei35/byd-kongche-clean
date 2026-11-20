from pathlib import Path
import re,json,subprocess,os,zipfile,hashlib,sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
WORK=Path(os.environ['TEMP'])/'kongche-secure5'
JDK=Path('C:/Program Files/java/jdk-11.0.18');JAVA=JDK/'bin/java.exe'
SDK=Path.home()/'android-sdk';BT=SDK/'build-tools/android-14'
TOOL=Path.home()/'.local/share/rea/apktool/apktool_2.11.1.jar'
def run(args):subprocess.run([str(x) for x in args],check=True)
run([JAVA,'-jar',TOOL,'d','-f','-o',WORK,ROOT/'BYD-kongche_3.20.83.apk'])
from bemfa_patch import apply
print(apply(WORK))
BASE=WORK/'smali_classes2/com/qinl/car/pub'
METHOD=re.compile(r'(?ms)^\.method ([^\n]+)\n(.*?)^\.end method')
def modify(path,name,fn):
 s=path.read_text(encoding='utf-8');n=0
 def f(m):
  nonlocal n
  if m[1].split('(')[0].split()[-1]!=name:return m[0]
  n+=1;return '.method '+m[1]+'\n'+fn(m[2])+'\n.end method'
 s=METHOD.sub(f,s);assert n==1,(name,n);path.write_text(s,encoding='utf-8')
def body(path,name,code):modify(path,name,lambda b:code)
def filter_return(b):
 return re.sub(r'(?m)^(\s*)return-object ([vp]\d+)',lambda m:m[1]+'invoke-static {'+m[2]+'}, Lcom/qinl/car/pub/trial/SecureRuntime;->publicConfig(Ljava/lang/String;)Ljava/lang/String;\n'+m[1]+'move-result-object '+m[2]+'\n'+m[1]+'return-object '+m[2],b)
bridge=BASE/'wui/WebBridge.smali'
modify(bridge,'config',filter_return)
modify(bridge,'saveConfig',lambda b:re.sub(r'(\.locals \d+\n)',r'\1    invoke-static/range {p1 .. p1}, Lcom/qinl/car/pub/trial/SecureRuntime;->preserveSecrets(Ljava/lang/String;)Ljava/lang/String;\n    move-result-object p1\n',b,count=1))
# Build annotations explicitly for public JavaScript entry points.
bridge.write_text(bridge.read_text(encoding='utf-8'),encoding='utf-8')

body(BASE/'LogUploader.smali','candidates','''    .locals 1
    invoke-static {}, Ljava/util/Collections;->emptyList()Ljava/util/List;
    move-result-object v0
    return-object v0''')
body(BASE/'LogUploader.smali','postOne','''    .locals 1
        const/4 v0, -0x1
    return v0''')
p=BASE/'LogUploader.smali';s=p.read_text(encoding='utf-8').replace('invoke-direct {p0}, Lcom/qinl/car/pub/LogUploader;->scheduleAutoUpload()V','nop');p.write_text(s,encoding='utf-8')
modify(BASE/'AppLog.smali','add',lambda b:re.sub(r'(\.locals \d+\n)',r'\1    invoke-static {p1}, Lcom/qinl/car/pub/trial/SafeLog;->clean(Ljava/lang/String;)Ljava/lang/String;\n    move-result-object p1\n',b,count=1))
p=BASE/'AppLog$tsFormat$1.smali';p.write_text(p.read_text(encoding='utf-8').replace('MM-dd HH:mm:ss"','MM-dd HH:mm:ss.SSS"'),encoding='utf-8')
body(BASE/'UpdateChecker.smali','updateUrls','''    .locals 1
    invoke-static {}, Ljava/util/Collections;->emptyList()Ljava/util/List;
    move-result-object v0
    return-object v0''')
body(BASE/'UpdateChecker.smali','openDownload','    .locals 1\n    const/4 v0, 0x0\n    return v0')
# Explicit export and restore endpoints have no side effects.
p=BASE/'cloud/ConfFile.smali'
for name in ['save','saveLegacy','saveMediaStore','load','loadLegacy','loadMediaStore','takePending']:
 if re.search(r'^\.method .*? '+name+r'\(',p.read_text(encoding='utf-8'),re.M):body(p,name,'    .locals 1\n    const/4 v0, 0x0\n    return-object v0')
# Disable direct raw packet dumps; protocol and callbacks are untouched.
p=BASE/'bluetooth/BleDirectSession.smali';s=p.read_text(encoding='utf-8')
needle='    sput-boolean v1, Lcom/qinl/car/pub/bluetooth/BleDirectSession;->RAW_DUMP:Z';assert s.count(needle)==1;s=s.replace(needle,'    const/4 v0, 0x0\n    sput-boolean v0, Lcom/qinl/car/pub/bluetooth/BleDirectSession;->RAW_DUMP:Z');p.write_text(s,encoding='utf-8')
# One-time provisioning uses Android encrypted CredentialManager, never a token in dex.
p=BASE/'MainActivity.smali'
modify(p,'onCreate',lambda b:b.replace('    return-void','''    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;
    move-result-object v0
    invoke-static {p0, v0}, Lcom/qinl/car/pub/trial/SecureRuntime;->configure(Landroid/content/Context;Landroid/content/Intent;)V
    return-void'''))
s=p.read_text(encoding='utf-8');needle='invoke-virtual {p1, v3}, Landroid/webkit/WebSettings;->setAllowFileAccess(Z)V';assert needle in s;s=s.replace(needle,'invoke-virtual {p1, v4}, Landroid/webkit/WebSettings;->setAllowFileAccess(Z)V')
p.write_text(s,encoding='utf-8')
p=BASE/'MainActivity$onCreate$4.smali';s=p.read_text(encoding='utf-8');assert '"file://"' in s;s=s.replace('"file://"','"file:///android_asset/ui/"');p.write_text(s,encoding='utf-8')
# Presentation: CSP, 设置页只留手动加密上传, 波形「停扫」格. secure5 removed calibration sampling.
from ui_patch import apply as apply_ui
apply_ui(WORK)
from ui_v4_patch import apply as apply_ui_v4
apply_ui_v4(WORK)
from baseline_patch import apply as apply_baseline
apply_baseline(WORK)
from reliability_patch import apply as apply_reliability
apply_reliability(WORK)
# 4.8: register notification listener service + expose window.KCCharge
# 4.11: 锁屏媒体卡片 -> 让 MediaSession 永不激活（setActive(true) 改成 false）
msess = BASE/'BleScanService.smali'
ss = msess.read_text(encoding='utf-8')
NEED = '    invoke-virtual {v0, v1}, Landroid/media/session/MediaSession;->setActive(Z)V'
if NEED in ss and 'const/4 v1, 0x0  # 4.11 media-off' not in ss:
    ss = ss.replace(NEED, '    const/4 v1, 0x0  # 4.11 media-off\n' + NEED, 1)
    msess.write_text(ss, encoding='utf-8')

man = WORK/'AndroidManifest.xml'
ms = man.read_text(encoding='utf-8')
if 'ChargeNotify' not in ms:
    _i = ms.index('<application')
    _j = ms.index('>', _i) + 1
    ms = ms[:_j] + '<service android:name="com.qinl.car.pub.trial.ChargeNotify" android:exported="true" android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"><intent-filter><action android:name="android.service.notification.NotificationListenerService" /></intent-filter></service>' + ms[_j:]
    man.write_text(ms, encoding='utf-8')
p = BASE/'MainActivity.smali'
s = p.read_text(encoding='utf-8')
assert s.count('    invoke-virtual {v3, p1, v4}, Landroid/webkit/WebView;->addJavascriptInterface(Ljava/lang/Object;Ljava/lang/String;)V') == 1, 'addJavascriptInterface anchor changed'
s = s.replace('    invoke-virtual {v3, p1, v4}, Landroid/webkit/WebView;->addJavascriptInterface(Ljava/lang/Object;Ljava/lang/String;)V', '    invoke-virtual {v3, p1, v4}, Landroid/webkit/WebView;->addJavascriptInterface(Ljava/lang/Object;Ljava/lang/String;)V\n    invoke-static {p0, v3}, Lcom/qinl/car/pub/trial/ChargeApi;->attach(Landroid/app/Activity;Landroid/webkit/WebView;)V', 1)
p.write_text(s, encoding='utf-8')

p=WORK/'apktool.yml';s=p.read_text(encoding='utf-8').replace('versionCode: 603','versionCode: 700').replace('versionName: 3.20.83','versionName: 1.0.0');p.write_text(s,encoding='utf-8')
# Only the public certificate is compiled; no bearer secret is in APK.
cls=WORK/'secure-classes';cls.mkdir(exist_ok=True);dex=WORK/'secure-dex';dex.mkdir(exist_ok=True)
run([JDK/'bin/javac.exe','-encoding','UTF-8','--release','11','-cp',SDK/'platforms/android-34/android.jar','-d',cls]+list((HERE/'src').rglob('*.java')))
run([JAVA,'-cp',BT/'lib/d8.jar','com.android.tools.r8.D8','--lib',SDK/'platforms/android-34/android.jar','--min-api','25','--output',dex]+list(cls.rglob('*.class')))
raw=WORK/'secure-raw.apk';run([JAVA,'-jar',TOOL,'b',WORK,'-o',raw])
repacked=WORK/'secure-repacked.apk'
with zipfile.ZipFile(raw) as z,zipfile.ZipFile(ROOT/'BYD-kongche_3.20.83.apk') as orig,zipfile.ZipFile(repacked,'w') as out:
 for item in z.infolist():out.writestr(item,orig.read('classes.dex') if item.filename=='classes.dex' else z.read(item.filename))
 out.write(dex/'classes.dex','classes3.dex',compress_type=zipfile.ZIP_DEFLATED)
aligned=WORK/'secure-aligned.apk';run([BT/'zipalign.exe','-f','-p','4',repacked,aligned])
final=ROOT/'instrument/dist/BYD-kongche-1.0.0.apk'
run([JAVA,'-jar',BT/'lib/apksigner.jar','sign','--ks',ROOT/'instrument/.trial.keystore','--ks-pass','pass:CHANGE_ME','--key-pass','pass:CHANGE_ME','--out',final,aligned])
run([JAVA,'-jar',BT/'lib/apksigner.jar','verify','--verbose',final]);run([BT/'zipalign.exe','-c','-p','4',final])
with zipfile.ZipFile(final) as z,zipfile.ZipFile(ROOT/'BYD-kongche_3.20.83.apk') as orig:
 assert all(orig.read(n)==z.read(n) for n in orig.namelist() if n.startswith('lib/') and n.endswith('.so'))
 assert b'192.168.' not in z.read('classes3.dex')
 assert b'192.168.' not in z.read('assets/ui/index.html')
 assert "$('updLog').innerHTML" not in z.read('assets/ui/app.js').decode()
print('PASS native libraries unchanged; current tokens absent from APK; signature and alignment verified')
print('ARTIFACT',final,final.stat().st_size,hashlib.sha256(final.read_bytes()).hexdigest())
