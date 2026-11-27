from pathlib import Path
import zipfile,hashlib,subprocess,os,re
root=Path(__file__).resolve().parents[2]
work=Path(os.environ['TEMP'])/'kongche-secure5'
apk=root/'instrument/dist/BYD-kongche-1.0.6.apk'
with zipfile.ZipFile(apk) as z:
 html=z.read('assets/ui/index.html').decode();js=z.read('assets/ui/app.js').decode()
 assert 'Content-Security-Policy' in html
 assert 'script-src \'self\'' in html
 assert "$('updLog').innerHTML" not in js
 # secure5: 校准采样整块移除；设置页只留手动加密上传；波形带「停扫」格。
 assert 'id="scopePause"' not in html and 'pauseLabelOf' in js and 'bgStopStat' in js
 for gone in ('btnAboutAuthor','制作者','联系方式','关于作者','sheetAbout','sheetDouyin','calibration','校准'):
  assert gone not in html, gone
 assert 'Calibration' not in js
 assert 'id="btnScopeThr"' in html and 'id="sheetThr"' in html
 assert "call('setRssiEnter'" in js and "call('setRssiExit'" in js
 assert 'assets/ui/v4.css' in z.namelist()
 assert 'assets/ui/v4-platinum.css' in z.namelist() and 'assets/ui/skin.js' in z.namelist()
 assert 'data-skin="platinum"' in z.read('assets/ui/v4-platinum.css').decode()
 assert 'id="cardSkin"' in html and 'src="skin.js"' in html
 assert 'id="ctlCfm"' in html and 'id="ctlCfmState"' in html
 assert 'data-chan' in html
 assert 'id="sheetChan"' in html and 'id="btnCarPick"' in html
 assert 'bindChanSheet' in js
 assert 'id="cardTripStat"' in html and 'id="tripBars"' in html
 # 4.10：账户页「小爱卡片（巴法云）」整块从界面上摘掉（bemfa 加固层留下的空壳是不可见的
 # disabled 节点，JS 守卫已兼容；这里断言"用户看得见的入口"确实没了）
 assert 'fold-head">小爱卡片' not in html and 'id="tagCards"' not in html  # 卡片本体的入口确实没了
 assert 'id="btnSound"' not in html and 'id="btnTheme"' not in html  # 4.12 顶栏只剩 ⚙
 assert 'id="cardSound"' in html and 'id="swSound"' in html
 assert 'id="iconCard"' not in html and 'id="chgBody"' not in html  # 1.0.0 摘掉图标卡与更新日志
 assert 'id="btnCheckUpdate"' not in html and 'id="updateHint"' not in html
 assert 'id="btnExportAbout"' in html and '导出日志压缩包' in html
 assert 'id="sheetLogExport"' in html and 'id="blePauseBar"' in html
 assert 'KCLog' in js and 'exportRange' in js and 'tempResume' in js
 assert 'btnTrialUpload' not in html
 assert 'id="cardCenterCard"' not in html and 'id="mcBtn1"' not in html  # 4.11 锁屏媒体卡片设置也去掉
 assert 'media-off' in (work/'smali_classes2/com/qinl/car/pub/BleScanService.smali').read_text(encoding='utf-8')
 assert 'id="cardCards"' not in html
 assert 'initTripStat' in js
 assert 'id="cardTripKpi"' in html and 'id="chgKm"' in html
 assert 'initTripKpi' in js and 'qinl_charge_last' in js
 assert 'KCCharge' in js and 'nativeWindow' in js and 'href="v4.css"' in html
 assert '--v4-amber:#E8A13A' in z.read('assets/ui/v4.css').decode()
 assert 'classes3.dex' in z.namelist()
 assert b'Calibration' not in z.read('classes3.dex'), 'calibration classes still packed'
base=work/'smali_classes2/com/qinl/car/pub'
for name in ['BemfaMqtt','BemfaSync','BemfaState']:
 s=(base/'cloud'/f'{name}.smali').read_text(encoding='utf-8')
 bodies=re.findall(r'(?ms)^\.method [^\n]+\n(.*?)^\.end method',s)
 assert not any('Ljava/net/Socket;->' in b or 'Ljava/net/HttpURLConnection;->' in b or 'CloudCmdQueue;->' in b for b in bodies)
s=(base/'wui/WebBridge.smali').read_text(encoding='utf-8')
assert 'invoke-static/range {p1 .. p1}, Lcom/qinl/car/pub/trial/SecureRuntime;->preserveSecrets' in s
s=(base/'MainActivity.smali').read_text(encoding='utf-8')
assert 'invoke-virtual {p1, v4}, Landroid/webkit/WebSettings;->setAllowFileAccess(Z)V' in s
# Every BLE class is identical except the specifically approved RAW_DUMP flag.
orig=root/'rea/apktool/smali_classes2/com/qinl/car/pub/bluetooth'
changed=[]
for p in orig.glob('*.smali'):
 if p.read_bytes()!=(base/'bluetooth'/p.name).read_bytes():changed.append(p.name)
assert changed==['BleDirectSession.smali'],changed
text=(orig/'BleDirectSession.smali').read_text(encoding='utf-8').replace('    sput-boolean v1, Lcom/qinl/car/pub/bluetooth/BleDirectSession;->RAW_DUMP:Z','    const/4 v0, 0x0\n    sput-boolean v0, Lcom/qinl/car/pub/bluetooth/BleDirectSession;->RAW_DUMP:Z')
assert text==(base/'bluetooth/BleDirectSession.smali').read_text(encoding='utf-8')
assert '0x124f80' not in (base/'AutoPause.smali').read_text(encoding='utf-8'), '20m backoff still present'
assert 'PauseOverride' in (base/'AutoPause.smali').read_text(encoding='utf-8')
assert 'PauseOverride' in (base/'wui/BleRuntime.smali').read_text(encoding='utf-8')
assert 'LogExportApi' in (base/'MainActivity.smali').read_text(encoding='utf-8')
assert 'GattWatchdog;->tick' in (base/'BleScanService.smali').read_text(encoding='utf-8')
assert 'GattWatchdog;->onMotion' in (base/'BleScanService.smali').read_text(encoding='utf-8')
sdk=Path.home()/'android-sdk/build-tools/android-14'
r=subprocess.check_output([str(sdk/'aapt2.exe'),'dump','badging',str(apk)],text=True,encoding='utf-8')
assert "versionCode='706'" in r and "versionName='1.0.6'" in r,r[:300]
cert=[]
for p in [root/'instrument/dist/BYD-kongche-3.20.83-logtrial1.apk',apk]:
 out=subprocess.check_output(['C:/Program Files/java/jdk-11.0.18/bin/java.exe','-jar',str(sdk/'lib/apksigner.jar'),'verify','--print-certs',str(p)],text=True)
 cert.append(re.search(r'certificate SHA-256 digest: (\w+)',out)[1])
assert cert[0]==cert[1]
h=hashlib.sha256(apk.read_bytes()).hexdigest();apk.with_suffix('.apk.sha256').write_text(h+'  '+apk.name+'\n',encoding='utf-8')
print('PASS CSP/HTML, no calibration, time-range log export, pause override, gatt watchdog, v4 skin, inert Bemfa, bridge, file access, BLE patch only RAW_DUMP, version706, same signer')
print('SIZE',apk.stat().st_size,'SHA256',h)
