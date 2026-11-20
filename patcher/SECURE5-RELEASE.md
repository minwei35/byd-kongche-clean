# secure5 变更与验收记录

日期：2026-11-20。需求：用户已正常日常使用，要求

1. 去掉「校准采样」相关内容；
2. 蓝牙页波形处显示「当前是否因 WiFi / 定时停扫」；
3. 设置页去掉制作者 / 抖音 / 联系方式 / 关于作者，只留加密上传；
4. 日志上传改为**只在手动点按钮时**上传。

## 为什么加「停扫」格（.150 昨晚日志实证）

证据来源：`/mnt/user/appdata/byd-keyless/logs/app-20261119.log`、`app-20261120.log`。

- 2026-11-20 **08:04:01** `后台自动停扫生效（WiFi 信号变化）：服务已停，条件解除后自动恢复`；
- 同一时刻 `停扫判定：min -55dBm ≥ -75（本场景门槛 -70）→ 停扫`；
- 最后一条 `靠近诊断` 时间戳是 **08:04:00.474**，此后**一条都没有** —— 服务真的停了，波形没有任何可画的数据；
- 停扫期间复核一直维持停扫结论：`08:09 仍该停（5 分钟后）`、`08:14 / 08:24 / 08:34 / 08:54 仍该停（10 / 20 分钟后）`；
- 11-19 当天共 **14 次**「后台自动停扫生效」、11-20 到 09:00 已有 **15 次**；另有 109 次「停扫复核」、106 次「检测到运动 → 立即重判」。

结论：波形停住时，界面上没有任何东西区分「信号差 / 车不在」与「被 WiFi / 定时停扫」，只能靠翻 NAS 日志。
这就是用户前几轮反复问「蓝牙没有变化」的直接原因，所以这个格子是必要的，不是装饰。

## 改动

| 项 | 改动 |
|---|---|
| 校准采样 | 删除 `Calibration.java` / `CalibrationPolicy.java` / `calibration_ui.py` / `calibration_patch.py` / `assets/calibration.*` 及其测试与计划文档；WebBridge 不再挂 `calibrationMark` / `calibrationStatus`，`MainActivity` 不再 `Calibration.init`，`SecureUpload` 不再拼采样日志 |
| 波形停扫格 | （secure6 已改为并进「连接」格，见 SECURE6-RELEASE.md）初版在「判定」后新增「停扫」，读原生 `bgStopStat()`：`paused` + `on`(WiFi) + `sched`(定时) → `未停扫` / `WiFi停扫` / `定时停扫` / `定时+WiFi停扫` / `后台停扫`；停扫时数字变红，长按显示 SSID / dBm / 门槛；3 秒一次取数，避免 200ms 渲染循环打桥 |
| 设置页 | 「关于」卡只剩版本、性质与「加密上传日志到 NAS」；制作者 / 抖音 / 联系方式 / 关于作者按钮、`sheetAbout`、`sheetDouyin` 及其历史注释、`关于作者` 长按 3 秒隐藏上传入口一并删除 |
| 上传 | `SecureUpload.init` 不再起 60 秒调度；`LogUploader.scheduleAutoUpload` 的调用点仍被替换为 `init`，因此**没有任何自动上传路径**；唯一入口是设置页按钮 → `logUploadNow` → `SecureUpload.post`。默认状态文案改为「点按钮才会加密上传（还没传过）」 |

新增 `baseline_patch.py`（凭据初始化 + 一次性推荐设置迁移 + 原生默认值），把与采样无关的部分从原 `calibration_patch.py` 里留下。
新增 `ui_patch.py` 统一做 CSP、设置页精简、停扫格与手动上传接线，`build_secure.py` 只调用两个 patch。

## 验证

- `python -B -m unittest discover -s instrument/harden/tests -p 'test_*.py'`：**40/40 通过**（新增 `test_ui_patch.py` 7 项：文件已删、设置页只剩上传、停扫格位置、手动上传唯一入口、`node --check` 通过、`pauseLabelOf` 五种标签、重复 apply 拒绝且不半写）。
- Bemfa 独立回归：**8/8 通过**。
- `build_secure.py`：javac / D8 / apktool / zipalign / apksigner v2+v3 全过；native 库逐字节不变；当前 token 不在包内。
- `verify_artifact.py`：CSP、无 calibration、无作者/抖音/联系方式、有 `scopePause`、`classes3.dex` 无 `Calibration`、版本 608、同签名 —— 全 PASS。
- 产物：`instrument/dist/BYD-kongche-3.20.83-secure5.apk`，11,650,892 bytes，SHA-256 `e5db9d162ba8ea1c70b50889f2acc71286cc976171de0e9f4b7c081064941780`。
- 设备 `24129PN74C` 已 `adb install -r` 覆盖安装：versionCode **608**、versionName **3.20.83-secure5**，进程正常，无 FATAL / NoSuchMethod。
- 设置页截图（`evidence/secure5-ble*.png`）确认「关于」卡只剩「加密上传日志到 NAS」与状态行。
- **未取证**：波形「停扫」格的实际渲染截图 —— 复测时手机正被用户使用（远程点击落到了飞书），没有强行抢占。
  该格由 APK 内 `id="scopePause"` + `pauseLabelOf` 单测 + 原生 `bgStopStat` 既有字段保证；上车时看一眼即可确认。

## 回滚

- 代码：`git revert` 本提交，重新跑 `build_secure.py` 得到 secure4 等价包；secure4 安装包仍在 NAS 归档 `/mnt/user/backup/byd-kongche/secure4-20261116/`。
- 设备：直接安装 secure4 APK 覆盖（同签名，保留数据）。
- 上传：如需恢复自动上传，把 `SecureUpload.init` 里的 `scheduleWithFixedDelay` 那行加回即可（本次是删除而非禁用）。
