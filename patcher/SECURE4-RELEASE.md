# secure4 修复与验收记录

日期：2026-11-16。用户要求修复后，子任务中断，后续实现、测试、构建与部署均由主进程接管完成。

## 交付

- [secure4 APK](<../dist/BYD-kongche-3.20.83-secure4.apk>)，versionCode **607**，versionName **3.20.83-secure4**。
- 大小：11,671,513 bytes。
- SHA-256：`0e7b1970bc54194dc08e5e69a85060645990cefc419526bad1eea70a4e3d0feb`。
- [SHA校验文件](<../dist/BYD-kongche-3.20.83-secure4.apk.sha256>)。
- 与secure3同试用签名；保留secure3产物，不卸载、不清应用数据。蓝牙native库逐字节不变，BLE类除既有RAW_DUMP禁用外与原版相同。

## F01—F09落实

| 编号 | 修复 | 验证 |
|---|---|---|
| F01 | 8槽有界工作线程内处理TLS/HTTP，accept不做握手；5s空闲超时+10s绝对请求deadline；rate/append共享锁；关闭服务等待worker回收 | 本地慢头并发health、滴流头/body超时、TLS握手不堵accept、线程上限、并发限速测试 |
| F02 | 首次迁移异常转migration_incomplete状态而非向Activity抛出；runtime/advanced每键原子写值+进度，已成功步骤不重复；已完成secure3标志保留，阈值只补缺失值 | Java prefs模拟commit失败、CredentialManager初始化失败、重试保留用户修改、完成后不重复应用 |
| F03 | state、journal、retained_at、boot_count在同一Editor同步提交；失败还原本轮内存候选与journal，回传persistence_failed；自动结束失败保留旧状态并重试；status/UI显示storage_error | Android SDK34编译、源码边界检查；尚未执行实机磁盘满/杀进程故障注入 |
| F04 | 外部Intent只提出配置请求，所有新/变更token经原生确认后写入；取消保留旧值，相同值不重复弹窗，非Activity上下文不配置 | Java Activity/AlertDialog替身验证确认前不变、确认后才写、同值/无效值/非Activity不写 |
| F05 | SafeLog识别带引号response与dk；WatchApiClient.log在源头改为固定无payload事件，直接logcat与原verbose回调均不输出响应正文 | 真实Java红绿负例、smali补丁幂等与前置替换测试、最终APK独立解码核实 |
| F06 | signalNumber接受Hz紧跟左括号的真实诊断格式，拒绝Hz垃圾尾缀 | Java真实诊断字符串及负例 |
| F07 | 自动近/远快照缺省统一false | 源码检查、既有native契约测试 |
| F08 | 采样恢复记录boot_count，不同boot/未知boot不继续旧active；墙钟回拨清理过期队列；旧secure3无boot数据保守结束，不碰钥匙 | 编译及源码边界检查；时钟/boot实机组合故障未注入 |
| F09 | 本服务命名日志7天、100MiB总量、32文件上限，5MiB轮转；清理仅匹配合法日期命名常规文件，不处理未知文件/符号链接 | 配额失败恢复、旧日期/总量/数量、无关文件保留测试 |

首次迁移仍保持自动动作优先关闭；若存储本身始终失败，设置落盘仍依赖设备恢复，界面会显示迁移未完成。secure3已经完成推荐设置的设备不因secure4再次覆盖用户调参。

校准仍只保留最近一轮；新开轮次会替代上一轮，离线采样后先上传再开下一轮。观察/标记不触发车控。

## 本次测试结果

- `python -B -m unittest discover -s instrument/harden/tests -p test_*.py`：**41/41通过**。
- Bemfa补丁独立回归：**8/8通过**。
- `build_secure.py`：Java11/Android SDK34 javac、D8、apktool、zipalign成功；apksigner **v2/v3通过**。
- `verify_artifact.py`：CSP、禁用Bemfa、桥保护、文件访问、BLE受限差异、版本607、同签名通过。
- 从交付APK独立apktool解码：WatchApi日志正文已移除、classes3含boot/storage错误字段、原生配置确认存在。
- 回归中先复现了旧版静默token覆盖、quoted response漏过滤、帧率缺失、服务慢请求排队/无配额，再落实相应修正。迁移补充运行测试在实现后加入，不夸称每个测试都经历过红阶段。

## NAS上线

仅更新独立`byd-log-upload`容器的日志代码，未重启`byd-keyless`车控容器；未发任何车控命令。

- 部署路径：`/mnt/user/appdata/byd-log-upload/tls_log_server.py`。
- 原代码备份：同目录`tls_log_server.py.bak-secure3-20261116`。
- 先stage `.new`并在容器中ast解析通过，再替换并restart。
- 本地/远程源码SHA一致：`9a59db71176a18342a61579b7bc9c2a0ecbff707938cabfcc3fa81dd1789d51d`。
- 8788 health返回`{"ok":true}`；8787仍健康。健康检查使用curl临时忽略证书验证以核实存活；APK内证书信任及默认hostname验证没有放宽。
- 未轮换/显示上传token、证书私钥或扫码材料。服务不访问车控接口。
- 回滚：将上述备份复制回原代码位置，再`docker restart byd-log-upload`；日志及凭据不删除。

## 项目备份

- 便携归档（源码/测试/报告+APK，排除`.private`、keystore和REA全量生成树）：`/mnt/user/backup/byd-kongche/secure4-20261116/secure4-20261116.zip`。
- NAS已执行`sha256sum -c`验证；归档SHA-256：`841d5d739b31f58dd97d9528eaff76f600a260a2b18c933459cefa30720efeab`。
- 本地同内容归档及校验清单在`SECURE4-BACKUP-20261116/`，该归档目录本身加入gitignore，避免把APK二进制副本提交进源码仓库。

## 手机状态与下一步

**手机已通过`adb install -r`覆盖安装并确认最新版**：设备`24129PN74C`，包versionCode=607、versionName=3.20.83-secure4；安装包SHA-256与构建值相同：`0e7b1970bc54194dc08e5e69a85060645990cefc419526bad1eea70a4e3d0feb`。secure3/secure4 apksigner证书SHA-256相同，覆盖升级成功保留应用数据。

启动后`pidof com.qinl.car.pub`有进程，最近logcat未见FATAL EXCEPTION、ClassNotFoundException或NoSuchMethodError。用原USB provisioning入口提交现有专用log token后，NAS接收端返回`{"ok":true,"lines":1}`，表明TLS上传路径工作。该上传响应不能证明手机这条人工样例与后台普通自动日志的每个字段完全相同。未能成功拉取UIAutomator XML（PowerShell/MSYS路径转换将`/sdcard`改写），故确认弹窗实际视觉点击状态未取证；Java对话框测试及设备存活是现有证据。未重扫码、未清数据、未发车控。

实机验收仍待做：校准教程/手动标记/结束、离线重启恢复、原车钥匙真实可用及车辆近场动作；这些需要单独观察，不以APK版本与进程存活代替。

## 修改入口

- [接收器](<tls_log_server.py>)、[接收器测试](<tests/test_tls_log_server.py>)。
- [Calibration](<src/com/qinl/car/pub/trial/Calibration.java>)、[CalibrationPolicy](<src/com/qinl/car/pub/trial/CalibrationPolicy.java>)、[Baseline](<src/com/qinl/car/pub/trial/Baseline.java>)。
- [SecureRuntime](<src/com/qinl/car/pub/trial/SecureRuntime.java>)、[SafeLog](<src/com/qinl/car/pub/trial/SafeLog.java>)、[日志源补丁](<reliability_patch.py>)。
- [构建](<build_secure.py>)、[产物核验](<verify_artifact.py>)、[USB配置脚本](<provision_phone.py>)、[校准UI](<assets/calibration.js>)。
- [迁移故障测试](<tests/test_android_durability.py>)、[配置确认测试](<tests/test_provision_confirmation.py>)、[修复回归](<tests/test_secure4_fixes.py>)。

未提交或推送git；保留当前工作区原有未跟踪状态。
