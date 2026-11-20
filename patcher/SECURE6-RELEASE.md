# secure6：停扫状态并进「连接」格

日期：2026-11-20。用户反馈：波形上单独加一格「停扫」不如直接把它放进「连接」——
停扫时那格本来写的就是「守护未开」，等于只说了"没跑"、没说"为什么没跑"。

## 改动

- **不再新增格子**：波形实时行仍是 连接 / 信号 / 判定 三格（`id="scopePause"` 已不存在）。
- **停扫时改写「连接」格**：`bgStopStat().paused == 1` 时
  `scopeConn` 直接显示 `WiFi停扫` / `定时停扫` / `定时+WiFi停扫` / `后台停扫`（红色、`link-standby` 样式），
  长按看详情（SSID + dBm + 门槛 / 定时时段）；条件解除后自动恢复「已直连 / 待命 / 未连接」并清掉红字。
- `pauseLabelOf` 对「没停扫 / 读不到」返回空串，避免把无关文字塞进连接格。
- 版本：versionCode **609** / versionName **3.20.83-secure6**（上一版 secure5 = 608）。

## 验证

- 40 项 unittest 通过（`test_pause_merged_into_connection_cell`、`test_pause_labels` 覆盖五种停扫标签与空串、
  断言页面里没有 `id="scopePause"`、JS 只改 `scopeConn`）。
- `verify_artifact.py`：`id="scopePause"` 不存在、`pauseLabelOf` 与 `bgStopStat` 在包内、版本 609、同签名、native 库不变 —— PASS。
- APK：11,650,892 bytes，SHA-256 `0573bd54ea9e8f864546158a922a1c0a7d466f995b4f08753a2ba1782182834b`。
- 设备 `24129PN74C` 覆盖安装成功：versionCode **609**、versionName **3.20.83-secure6**，进程 22605，无 FATAL。

## 回滚

`git revert` 本提交后重跑 `build_secure.py`；或直接装回 secure5 APK（同签名，保留数据）。
