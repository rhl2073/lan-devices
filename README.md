# 局域网机器列表

实时发现局域网内设备，通过 UDP 广播收集计算机名和 IP 地址，以 Web 页面展示。

## 工作原理

```
┌──────────────────┐    UDP 广播 (3秒/次)    ┌──────────────────┐
│  机器 A          │ ◄────────────────────── │  机器 B          │
│  broadcast_service│                         │  broadcast_service│
│  listener_server │                         │                  │
│  (Web 页面 :5080)│ ──────────────────────► │                  │
└──────────────────┘    UDP 监听 :50001       └──────────────────┘
```

- **广播服务**：每 3 秒向局域网 UDP 广播本机名称和 IP
- **监听服务**：接收广播并存入内存，提供 Web API
- **Web 界面**：展示所有发现的设备，在线/离线状态实时更新

## 项目结构

```
lan_devices/
├── broadcast_service.py    # UDP 广播服务（需在每台机器上运行）
├── listener_server.py      # 监听服务 + Web 界面（CORS 支持）
├── requirements.txt        # Python 依赖
├── cloudflare/
│   └── index.html          # Cloudflare Pages 静态前端
└── .gitignore
```

## 安装与运行

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2. 启动监听 + Web 服务（作为服务器）

```bash
python3 listener_server.py
```

启动后：
- Web 界面：http://localhost:5080
- UDP 监听端口：50001
- 本机也会自动广播自己

### 3. 其他机器运行广播服务

在局域网内的每台机器上：

```bash
python3 broadcast_service.py
```

无需安装 Flask，纯标准库实现。

## Cloudflare Pages 部署

Web 前端可部署到 Cloudflare Pages，实现公网访问（数据仍来自本地后端）：

```bash
# 安装 wrangler
npm install -g wrangler

# 登录
wrangler login

# 部署
cd cloudflare
wrangler pages deploy . --project-name=lan-devices --branch=main
```

部署后，打开 Cloudflare Pages 提供的 URL，在输入框填入运行 `listener_server.py` 的机器地址（如 `http://192.168.1.100:5080`）即可查看设备列表。

## 技术栈

- **Python 3**：标准库 `socket`、`threading`、`platform`
- **Flask**：Web 服务框架
- **UDP 广播**：`255.255.255.255:50001`
- **Cloudflare Pages**：静态前端托管
