# secure3 BLE / 上传只读审查（阶段性）

## 版本与范围

目标 APK SHA-256 实测 `b8fb2e9e7485ec0a2a5fd4769433fc53fdb0c0be69292ab2cffe1cd56eef0113`，与题给一致。检查了 SecureUpload、SafeLog、SecureRuntime、tls_log_server，以及最终解码清单和部分注入调用、BLE 回执路径。原版 JADX 仅供线索；未充分复核的 BLE 流程不作为现版漏洞结论。工作树 instrument 与 rea 为未跟踪文件，普通 git diff 不含其内容。

## P1：导出 Activity 可由其他应用覆盖上传认证配置

- 证据：最终解码 `AndroidManifest.xml:28` 的 MainActivity exported=true，未声明调用权限；最终 `smali_classes2/com/qinl/car/pub/MainActivity.smali:1880-1882` 在 onCreate 读取 Intent 并调用 `SecureRuntime.configure(Context,Intent)`；`instrument/harden/src/com/qinl/car/pub/trial/SecureRuntime.java:12-17` 接受符合格式的 extra 并无调用来源验证地写入 CredentialManager。`SecureUpload.java:35,47-51` 后续使用此值向固定服务认证。
- 条件：同设备应用可显式启动新 Activity 实例并携带符合格式的值；受 Android 后台启动限制影响，具体触发需设备版本与前后台状态验证。
- 影响：上传凭据被覆盖，后续上传认证失败，直到重新配置。固定 URL 和证书意味着现有证据不支持上传内容被重定向或攻击者得知原 token。
- 修复：配置入口独立为受签名权限保护的组件或仅限本机可信管理通道；显式用户确认并避免 Activity 公共 intent 直接更改持久凭据。验证第三方 UID 启动与用户正常配置分别覆盖拒绝/成功。

## P1：单线程 TLS 接收与逐次超时允许低速连接阻塞全部上传

- 证据：`instrument/harden/tls_log_server.py:127-150,298-306` 使用单线程 HTTPServer，并在 accept 后同步 TLS 握手；`144` 每 socket 超时五秒；`275` 同步读取整个 body。认证及限速在 244-260，均发生在握手和 HTTP 头解析之后。
- 条件：可访问监听端口的客户端持续占住握手或请求头/请求体读取，每次活动在 socket 超时前发生；请求体场景还需有效 token，握手及请求头阶段不需 token。超时为单次 socket 空闲超时而非全请求绝对截止。
- 影响：单个慢连接可拖延服务其他客户端，上传和 health 请求排队；网络暴露面与攻击持续时间依部署而定。
- 修复：使用有界并发的 TLS 前置代理或受限线程池，并设置握手、请求头、整个 body 的绝对期限和并发上限；加入口级限速。离线用受控连接慢速发送并并发检查 health 时延。

## P2：滚动日志只有单文件大小上限，缺总量/保留期

- 证据：`instrument/harden/tls_log_server.py:183-197` 文件超 5 MiB 时按时间重命名后继续创建新文件；代码未实现轮转文件数量、总字节或保留天数清理。`23-24,157-173` 是按源 IP 的请求数窗口，不能形成持久磁盘总量上限；正常调用和多个源也可持续累积。
- 条件：合法上传长期运行，或持有上传凭据的客户端持续提交。
- 影响：日志目录持续增长，最终可能挤占共享存储；实际剩余空间与外部轮转策略未审。
- 修复：设定总容量与保留期限、滚动文件数，原子清理并预留磁盘余量；针对达到配额和写满执行离线验证。

## 其他已确认与待验证

- `SecureUpload.java:36-46` 实际字段为输入 `lines`、输出 `logs`；客户端按 512 KiB 截断，服务端 `tls_log_server.py:79-124,261-285` 限大小、行数、行长，拒绝重复 JSON 键及非有限值；认证使用单个 `X-Log-Token` 与常量时间 digest 对比。TLS pin 不应被描述为跳过主机名验证：源码未设置自定义 hostname verifier。
- 最终 `AppLog.smali:158` 调用 `SafeLog.clean`，`LogUploader.smali:1213,3066` 分别调用 `SecureUpload.post(String,String)`、`init(Context)`；单凭原版日志路径不应报现版未过滤。
- 另一审查者用合成输入确认 `SafeLog.clean` 对 JSON 格式 `"response":"..."` 未触发 `response\s*[=:]` 分支：字段名尾引号阻断匹配；有原响应片段在日志中残留的风险。此处尚未独立核对真实调用点及最终成品内容，故暂列待交叉验证，不声称真实密钥泄露。
- 原版 JADX `BleDirectSession.java:2170-2220` 对回执解析 result 和 cmdType 并对 pending 的 expectEcho 做匹配；此为静态观察，不等于车门物理状态确认，也不等于已完整验证最终补丁、同命令迟到回执或并发竞态。
- 本次 Python 合成样例验证服务端手机号、帧和 Bearer 正则可匹配，语法编译通过；这些测试不涉及真实数据。语法编译/模块导入产生了 `instrument/harden/__pycache__/tls_log_server.cpython-314.pyc` 缓存，不属于业务代码。

## 未覆盖

BLE 锁链竞态、常连、全部车控回执和最终 smali 差异尚未完成逐路径审查；native JNI 解析与帧语义、服务真实部署、外部反向代理/防火墙/存储轮转、后端业务系统、设备实测均未覆盖。不据此作整包通过结论。无安装、登录、控车、读取 .private 或 commit。
