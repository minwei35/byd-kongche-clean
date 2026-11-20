# secure3 WebView / 桥 / 扫码与凭据审查（只读静态子审）

## 结论与证据边界

建议修复：确认 2 个 P2；另有待验证风险。目标 APK SHA-256 实测为 `b8fb2e9e7485ec0a2a5fd4769433fc53fdb0c0be69292ab2cffe1cd56eef0113`，与指定值相符。APK 中 `assets/ui/index.html`、`assets/ui/app.js` 与 `C:/Users/KURO/AppData/Local/Temp/kongche-secure3` 同名资源 SHA-256 均一致。临时目录 smali 是构建工作树证据，不等同于重新从 APK 独立反汇编得到的证据；未逐项证明所有 smali 与最终 dex 一致。原版 JADX 仅用作代码定位，关键分支核对了工作树 smali。未登录、安装、启动、控车、访问网络或读取 .private，未改业务文件、重建或提交。

## P2：外部应用可覆盖日志上传令牌

- 位置：`instrument/harden/src/com/qinl/car/pub/trial/SecureRuntime.java:12-17`；注入点 `instrument/harden/build_secure.py:65-69`；解码清单 `C:/Users/KURO/AppData/Local/Temp/kongche-secure3/AndroidManifest.xml:28`。
- 事实：MainActivity exported=true；onCreate 调用 configure(context,intent)，读取名为 `loguploadtoken` 的字符串 extra，只检查字符和长度，随后覆盖 CredentialManager 中上传令牌；未检查调用方身份或已有配置。移除 extra 发生在接收之后，非来源认证。
- 触发：另一应用显式启动导出的 MainActivity，并提交格式合格的自选令牌；不要求用户扫码或拥有原令牌。
- 影响：已有上传令牌可被替换；在服务端不接受该值时，后续定时上传认证失败，造成日志传输可用性损失。上传目标和 TLS 证书仍固定；现有证据不支持声称因此直接窃取车钥匙或转移日志目的地。
- 修复：从导出 Activity 移除该写入口，采用签名级权限保护的独立非导出组件或经过设备本地明确确认的一次性配置通道；增加只初始化一次及变更审计、显式轮换流程。
- 验证：静态源码及 manifest；尚未在设备上发送 Intent，也未验证服务端权限策略。

## 撤回：旧日志清理正则误报

源码实测是两个反斜杠，Java 字符串转义正确；先前误读工具显示层，撤回该发现。

## P2：Watch API 响应绕过 AppLog 脱敏直接进入 logcat

- 位置：原版 `rea/jadx/sources/com/qinl/car/pub/cloud/WatchApiClient.java:271-277,349-358`；现版工作树 `C:/Users/KURO/AppData/Local/Temp/kongche-secure3/smali_classes2/com/qinl/car/pub/cloud/WatchApiClient.smali:1326-1332`；补丁仅在 `instrument/harden/build_secure.py:50` 给 AppLog.add 加清洗。
- 事实：post 对响应正文截取前 200 字符后传入 log；log 先调用 Android Log.i，后调用 verboseLog；当前 SafeLog 在 AppLog.add，不位于 Log.i 调用之前。响应实际格式和内容由服务端决定，外层可能是封装或密文，不能假定一定明文包含钥匙。
- 触发：调用 Watch API，且 HTTP 响应前缀包含服务端错误、标识或其他敏感值；具备日志读取条件的主体可见对应 logcat。
- 影响：潜在泄露响应片段和可关联信息，取决于响应结构及设备日志访问权限；属于脱敏覆盖缺口，并非已证明真实 token 泄露。
- 修复：在日志源头取消响应正文，仅输出端点、HTTP 状态、耗时及随机关联 ID；使所有日志出口共用 allowlist，而不是仅匹配敏感关键词。
- 验证：调用签名与 `Log.i` 在当前工作树 smali 中核实，未发送网络请求或采集 logcat。

## 已覆盖与未覆盖

- 审查了四个指定补丁的关键安全路径，并检查 `SecureRuntime`、`SafeLog`、`SecureUpload` 与原版 `MainActivity`、`WebBridge.config/saveConfig`、`WatchQrService.saveKey`、`WatchApiClient.post/log` 的相关调用。`calibration_patch.py:9-10` 调用 credential patch，后者初始化失败保留原数据并置 storage_unavailable，未见其失败分支主动删除密钥；这不是完整并发或升级迁移证明。
- 工作树 MainActivity smali 1705-1719 显示 JavaScript 开启、普通文件访问关闭；`MainActivity$onCreate$4.smali:59-82` 显示仅放行 asset UI 路径前缀；`build_secure.py:74` 注入 CSP。原版宽泛 `file://` 跳转和原版 config 返回密码已分别被路径收紧及 `publicConfig` 过滤，未作为现版确认缺陷报告。
- 桥仍提供高权限方法；工作树路径白名单是字符串前缀，WebView 导航、重定向、POST、子框架、规范化差异和桥跨 frame 的真实行为未做动态验证，故不声称发现可达的外部网页桥接攻击链。建议在隔离设备做这些场景的负例测试。
- 扫码字段 `saveKey` 的实际调用为 `saveWatchAuth(dk,encryToken,signToken,keyNo,mac,vin,identifier,watchImei)`，蓝牙口令非空时单独保存；未逐条审完混淆协程状态机及 CredentialManager 保存实现，不对跨账号重扫和空字段密钥保留完整性作结论。
- Native `.so`、后端认证/接口、证书签发及服务器权限、设备现有状态、所有 UI 输入和所有桥方法、APK dex 与解码目录的逐项独立一致性均未覆盖。未运行安装、联网、车控或真实凭据测试。文件与行号为本次静态快照。
