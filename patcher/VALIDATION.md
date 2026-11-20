# secure2 验收记录

2026-11-16，安全精简试用版 3.20.83-secure2，versionCode605。

## 已完成
- 巴法云：7个派生文件、98方法封堵远程命令/网络/同步/明文备份；去掉对应UI正文，保留隐藏空兼容节点；8项回归测试通过。
- 日志：AppLog入口过滤凭据、认证载荷与原始云响应；关闭RAW_DUMP；旧私有日志清理失败可重试；上传取末600条。
- 页面：更新源为空、下载关闭、changelog使用textContent；CSP；禁止普通文件访问；原生config不再返回密码/PIN/巴法UID。
- 上传：独立NAS容器byd-log-upload，TLS8788，固定证书，独立日志token，只支持POST/applog，无控制路由与读取日志权限；21项服务测试通过。
- 旧共用车控token已轮换，NAS备份仅保留私有.env.before-logtoken-isolation，本机Clean的.log-token同步。其他已配置旧token的客户端需更新，旧logtrial1上传会失效。
- 新APK不编入任何上传/车控token；经USB配置的日志token通过原EncryptedSharedPreferences保存。
- APK native库逐字节不变，BLE smali仅改变RAW_DUMP，原协议/扫码代码不变；v2/v3签名与4KiB zipalign通过；同试用版签名可覆盖升级。
- 打包内容验收通过：版本605、同签名、CSP、更新HTML、巴法云网络无执行路径、桥与文件访问补丁。

## 手机与NAS实测
- USB设备6c37574c，24129PN74C，覆盖安装Success，没有卸载/清除应用数据。
- 专用日志token已配置，新进程32604，criticalErrors=0（未发现VerifyError/FATAL EXCEPTION/Uncaught TypeError/ReferenceError/脚本拒载）。
- NAS读回真实手机元数据：13:38:51.627上传51条，13:39:51.636上传113条，13:40:51.643上传182条，app=3.20.83-secure2，source=AppLog-filtered。
- 手机处于锁屏，无法据此验收可见UI布局；此次未重新扫码、未发送实车控制命令。钥匙数据未主动修改，但钥匙状态/车边BLE认证仍待用户解锁手机测试。

## 产物
BYD-kongche-3.20.83-secure2.apk，11646796 bytes。
SHA256：79a01ab13265b59987868a20689d01613ad094d31ce47e8d5661d92d1518add2。

## 剩余边界
不宣称全APK无漏洞，native/云后端未全审计。NAS旧8787主服务仍为HTTP车控，仅此次上传链路迁到TLS并分权；它的车控token已轮换。独立日志服务单文件5MiB轮转，但累计历史保留仍待配置。旧的外部Download配置备份如曾分享不自动撤回，巴法云账号UID如曾泄漏需在账号侧轮换。此次去除巴法云运行路径不等于撤销第三方云端已保存的备份。
