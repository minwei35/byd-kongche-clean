# 独立 TLS 日志收集服务部署

## 部署方式

由父代理部署独立容器 `byd-log-upload`，复用已有镜像 `byd-keyless:0.1`。8787 车控进程保持原样；新容器运行 `python /app/tls_log_server.py`，开放 TLS 8788。不修改主服务、不加入主服务线程。

新容器只挂以下两个目录：

| 宿主路径 | 容器路径 | 内容 |
|---|---|---|
| `/mnt/user/appdata/byd-log-upload` | `/app`（只读） | 日志服务模块、独立 token、证书和私钥 |
| `/mnt/user/appdata/byd-keyless/logs` | `/app/logs`（可写） | 现有日志目录 |

不挂主服务 `.env`、车控源码、账号凭据、主服务 token 或 Docker socket。模块仅依赖 Python 标准库，不导入车控模块、不建立上游连接、没有转发入口。以 Linux 容器中的 Python 3.9+ 运行。

## 父代理准备

先在宿主创建 `/mnt/user/appdata/byd-log-upload`，将服务模块复制为 `/mnt/user/appdata/byd-log-upload/tls_log_server.py`，并准备：

- `/app/.log-upload-token`：独立随机上传 token，推荐 `secrets.token_hex(32)`；ASCII 可打印字符，16～4096 字节，可带末尾换行。每次上传重新读取，原子替换文件即可轮换。
- `/app/.log-tls-cert.pem`：PEM 服务器证书，SAN 必须包含客户端实际连接的域名或 IP。
- `/app/.log-tls-key.pem`：对应 PEM 私钥。
- `/app/logs`：已存在的日志目录，可由运行 UID 追加文件；日志仅在服务端读取管理，8788 不开放读取接口。

父代理生成证书及客户端 pin，不在文档中记录 token、私钥或实际 pin。若客户端使用 SPKI SHA-256 pin，计算方式如下；证书 DER SHA-256 与 SPKI SHA-256 是两种不同格式，须与客户端实现一致：

```bash
openssl x509 -in /mnt/user/appdata/byd-log-upload/.log-tls-cert.pem -pubkey -noout \
  | openssl pkey -pubin -outform DER \
  | openssl dgst -sha256 -binary \
  | openssl base64 -A
```

宿主上 token 与私钥设置为仅运行 UID 可读。模块和证书可设 `0644`，token 和私钥设 `0600`，应用目录 `0700`。日志目录权限由父代理按现有服务 UID 配置。

以下命令作为父代理的部署模板；执行前先确认已有镜像及目录权限，不拉取新镜像：

```bash
docker run -d --name byd-log-upload \
  --restart unless-stopped \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -p 8788:8788 \
  -v /mnt/user/appdata/byd-log-upload:/app:ro \
  -v /mnt/user/appdata/byd-keyless/logs:/app/logs:rw \
  --workdir /app --entrypoint python \
  byd-keyless:0.1 /app/tls_log_server.py
```

`--entrypoint python` 避免复用镜像原入口启动车控进程；挂载的 `/app` 也覆盖镜像该目录的原源码。8788 限制为预期客户端可达网段。镜像中若已有非 `/app` 的凭据，应先检查清除再复用。新容器 token 不得与 8787 认证 token 相同。

启动时证书或 token 缺失/无效直接退出，不降级到明文。TLS 最低版本 1.2；每个连接包含 TLS 握手及 HTTP 读取均有 5 秒 socket timeout。证书更新后重启新容器；token 更新每次请求自动生效。

## 最小接口

### GET /health

无需上传 token，返回 HTTP 200 与 `{"ok":true}`。只表示 TLS 服务可响应，不代表磁盘写入或 token 当前可用；不包含 VIN、token、配置、路径或日志内容。默认响应不暴露 Python 版本。

### POST /applog

路径必须精确匹配，没有查询参数。请求头：

```http
Content-Type: application/json; charset=utf-8
X-Log-Token: <从独立token文件读取的值>
Content-Length: <UTF-8请求体字节数>
```

请求体示例（只用合成数据）：

```json
{
  "ts": "2026-11-16 12:00:00",
  "device": "client-test",
  "state": {"kind": "thirdparty-instrument", "app": "trial", "source": "app"},
  "logs": ["connection ready", "upload complete"]
}
```

- 根对象必须为 JSON dict；`logs` 必须为字符串数组，可为空。
- 最大请求体 512 KiB、最多 600 行、每行最多 2048 个 Unicode 字符；规范化后超限同样返回 413，不截断伪报成功。
- `ts`、`device` 为可选字符串或 null，字符串最多 2048 字符。
- `state` 为可选 dict，仅保留 `kind`、`app`、`source` 三个字符串字段，各最多 2048 字符。其余字段不写入。
- 拒绝重复 JSON key、NaN/Infinity、无效 UTF-8、孤立 Unicode surrogate、重复 token/Content-Length、Transfer-Encoding 和非 JSON Content-Type。
- 不接受旧 `X-Auth`；token 对比使用固定长度 SHA-256 摘要和 `hmac.compare_digest`。
- 每个来源 IP 每 60 秒最多 30 次上传尝试（包含认证失败），超限 429 并带 `Retry-After`；不使用客户端 `X-Forwarded-For`。最多记录 4096 个 IP 桶，饱和时新 IP 暂时受限。
- 每次响应关闭连接，不处理流水线/keep-alive 的剩余请求体。

成功仅在文件追加并 flush 后返回 HTTP 200：

```json
{"ok":true,"lines":2}
```

`lines` 是接受并持久追加的日志数组长度，不包括文件头；不返回服务器文件名、绝对路径或日志内容。客户端成功判定必须同时要求 HTTP 2xx 和 JSON `ok` 严格等于 `true`，不以健康接口代替上传确认。flush 是 Python/OS 写入确认，不承诺断电级持久性。

| 状态码 | 含义 |
|---|---|
| 400 | JSON、字段类型、Unicode 或请求 framing 无效 |
| 401 | token 缺失、错误、重复，或仅使用旧认证头 |
| 403 | GET `/applog` 或 GET `/applog?tail=...` |
| 404 | 控制端点、其他路径/方法、非精确上传路径 |
| 408 | 请求体读取超时 |
| 413 | 请求字节、日志行数、行长或元数据长度超限 |
| 415 | Content-Type 不是 application/json |
| 429 | 来源 IP 上传节流 |
| 500 | 写日志失败，错误响应不包含异常细节 |
| 503 | 运行期间 token 文件不可读或内容无效 |

`/unlock`、`/lock`、`/awake`、`/state`、`/ble/keyprobe` 等全部 404，无重定向、无转发；GET `/logs/...` 为 404。只有 GET `/health` 和 POST `/applog` 返回成功。

## 日志格式与脱敏

写入既有 `/app/logs/app-YYYYMMDD.log`，UTF-8，格式：

```text
### {"ts":"...","device":"...","state":{"kind":"..."},"count":2}
first line
second line
```

每个日志数组元素对应一条物理行；CRLF/CR/LF 统一转换为字面 `\n`，其余控制字符、Unicode 行分隔符转义，防止伪造新的日志头。元数据 JSON 编码，不接受客户端路径或文件名。

日志头不含 VIN；入库字符串对完整 17 位 VIN、手机号、常见 password/token/key/pin 等凭据字段、Bearer 值、当前上传 token、20 字节 `5B B5 … F5 FA` 帧载荷脱敏。帧保留类型和首尾字节，原始上传内容不打印到 stderr。客户端仍应先完成自身脱敏；这里采用模式和字段白名单，不宣称识别任意自由文本秘密。

单个活动文件追加后预计超过 5 MiB 时，旧文件轮转为 `app-YYYYMMDD-HHMMSS-<time_ns>.log`；新文件使用 `0600`，已有文件权限保持不变。跨容器共用目录时，父代理负责关闭旧 8787 日志上传入口或协调其他写入者；本模块的单 HTTPServer 串行写入只约束自身，未建立跨进程锁。历史保留/磁盘配额由父代理配置。

## 本地验证

在本目录执行（不读生产 token、不连接 NAS/SSH）：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_tls_log_server.py -v
```

测试使用临时目录和 `127.0.0.1` 随机端口，真实 HTTP handler 验证认证、路由、限制、JSON、脱敏、换行、写失败、轮换、节流和超时。TLS 单独测试使用本地 `openssl` 生成一次性证书，验证受信 loopback 握手、健康响应、明文不被接受及下一客户端恢复；生产服务本身没有 OpenSSL CLI 依赖。若本地没有 `openssl`，仅 TLS 证书生成测试显示 skip，其余照常执行。

当前本地 Python 3.14.4 / OpenSSL 3.5.9；最终测试结果由实施代理在交付报告中给出。部署后的网络与容器检查由父代理完成，不能将本地测试视为已部署证明。

## 回滚

父代理停止并删除 `byd-log-upload` 容器即可关闭 8788，保留日志目录和证书/token目录作回滚依据。8787 主容器未被改动。回滚客户端时仍保持独立凭据隔离，不恢复已暴露的共用车控 token。
