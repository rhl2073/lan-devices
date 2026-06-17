"""
监听服务器 + Web界面
- 接收局域网内所有广播信息
- 提供Web页面展示收到的所有机器列表
"""
import socket
import json
import threading
import time
import platform
from flask import Flask, render_template_string

BROADCAST_PORT = 50001
WEB_PORT = 5080

# 存储发现的设备: {ip: {hostname, ip, last_seen}}
discovered_devices = {}
lock = threading.Lock()

# 超时时间（秒），超过此时间未收到广播则认为设备离线
TIMEOUT = 15


def is_lan_ip(ip):
    """判断是否为局域网IP"""
    if ip.startswith("127."):
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return (a == 10) or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def get_local_ip():
    """获取本机局域网IP地址，优先匹配常见的局域网网段"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if is_lan_ip(ip):
            return ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if is_lan_ip(ip):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip != "127.0.0.1" and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

app = Flask(__name__)

# CORS 支持 - 允许 Cloudflare Pages 等外部页面跨域访问
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>局域网机器列表</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 40px 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 30px;
            font-size: 0.9rem;
        }
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .stat-card {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 16px 28px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-card .number {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card .label {
            font-size: 0.85rem;
            color: #888;
            margin-top: 4px;
        }
        .device-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 16px;
        }
        .device-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .device-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
        }
        .device-card.offline::before {
            background: linear-gradient(90deg, #ff6b6b, #c0392b);
        }
        .device-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        .device-icon {
            font-size: 2.2rem;
            margin-bottom: 10px;
        }
        .device-hostname {
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
            word-break: break-all;
        }
        .device-ip {
            font-size: 0.95rem;
            color: #3a7bd5;
            margin-top: 6px;
            font-family: "SF Mono", "Fira Code", monospace;
        }
        .device-time {
            font-size: 0.78rem;
            color: #666;
            margin-top: 8px;
        }
        .status-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-top: 8px;
        }
        .status-online {
            background: rgba(46, 204, 113, 0.2);
            color: #2ecc71;
        }
        .status-offline {
            background: rgba(231, 76, 60, 0.2);
            color: #e74c3c;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #555;
        }
        .empty-state .icon { font-size: 4rem; margin-bottom: 16px; }
        .refresh-hint {
            text-align: center;
            color: #555;
            font-size: 0.8rem;
            margin-top: 30px;
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>局域网机器列表</h1>
        <p class="subtitle">实时发现局域网内的设备</p>

        <div class="stats">
            <div class="stat-card">
                <div class="number" id="totalCount">0</div>
                <div class="label">总设备数</div>
            </div>
            <div class="stat-card">
                <div class="number" id="onlineCount" style="background: linear-gradient(90deg, #2ecc71, #27ae60); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">0</div>
                <div class="label">在线设备</div>
            </div>
        </div>

        <div class="device-grid" id="deviceGrid">
            <div class="empty-state">
                <div class="icon">📡</div>
                <p>正在监听广播...</p>
                <p style="font-size:0.8rem;margin-top:8px;">等待局域网内其他设备发送广播信号</p>
            </div>
        </div>

        <p class="refresh-hint pulse">页面每 3 秒自动刷新</p>
    </div>

    <script>
        async function fetchDevices() {
            try {
                const resp = await fetch('/api/devices');
                const data = await resp.json();
                renderDevices(data.devices);
                document.getElementById('totalCount').textContent = data.total;
                document.getElementById('onlineCount').textContent = data.online;
            } catch (e) {
                console.error('获取设备列表失败:', e);
            }
        }

        function renderDevices(devices) {
            const grid = document.getElementById('deviceGrid');
            if (devices.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📡</div>
                        <p>尚未发现任何设备</p>
                        <p style="font-size:0.8rem;margin-top:8px;">请确保其他设备正在运行广播服务</p>
                    </div>`;
                return;
            }
            grid.innerHTML = devices.map(d => `
                <div class="device-card ${d.online ? '' : 'offline'}">
                    <div class="device-icon">${d.online ? '💻' : '💤'}</div>
                    <div class="device-hostname">${escapeHtml(d.hostname)}</div>
                    <div class="device-ip">${escapeHtml(d.ip)}</div>
                    <div class="device-time">最后活跃: ${d.last_seen}</div>
                    <span class="status-badge ${d.online ? 'status-online' : 'status-offline'}">
                        ${d.online ? '在线' : '离线'}
                    </span>
                </div>
            `).join('');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 初始加载
        fetchDevices();
        // 每3秒刷新
        setInterval(fetchDevices, 3000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/devices")
def api_devices():
    with lock:
        devices_list = []
        now = time.time()
        online_count = 0
        for ip, info in discovered_devices.items():
            online = (now - info["last_seen"]) < TIMEOUT
            if online:
                online_count += 1
            devices_list.append({
                "hostname": info["hostname"],
                "ip": info["ip"],
                "last_seen": time.strftime("%H:%M:%S", time.localtime(info["last_seen"])),
                "online": online
            })
        # 按在线状态排序，在线的在前
        devices_list.sort(key=lambda x: (not x["online"], x["hostname"]))
        return {
            "devices": devices_list,
            "total": len(devices_list),
            "online": online_count
        }


def udp_listener():
    """UDP监听线程，接收局域网广播"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", BROADCAST_PORT))

    print(f"[UDP监听] 端口 {BROADCAST_PORT} 已启动")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = json.loads(data.decode("utf-8"))
            hostname = message.get("hostname", "Unknown")
            ip = message.get("ip", addr[0])

            with lock:
                discovered_devices[ip] = {
                    "hostname": hostname,
                    "ip": ip,
                    "last_seen": time.time()
                }
            print(f"[发现] {hostname} ({ip})")
        except Exception as e:
            print(f"[UDP监听] 错误: {e}")


def cleanup_thread():
    """定期清理离线过久的设备"""
    while True:
        time.sleep(30)
        with lock:
            now = time.time()
            expired = [ip for ip, info in discovered_devices.items()
                       if now - info["last_seen"] > 300]  # 5分钟无响应则移除
            for ip in expired:
                del discovered_devices[ip]
            if expired:
                print(f"[清理] 已移除 {len(expired)} 个过期设备")


def self_broadcast():
    """自己也定期广播，这样本机也能被发现"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # 获取本机信息
    hostname = platform.node()
    local_ip = get_local_ip()

    print(f"[自广播] 本机名称: {hostname}, IP: {local_ip}")

    while True:
        try:
            message = json.dumps({"hostname": hostname, "ip": local_ip})
            sock.sendto(message.encode("utf-8"), ("255.255.255.255", BROADCAST_PORT))
        except Exception:
            pass
        time.sleep(3)


if __name__ == "__main__":
    # 启动自广播线程（让本机也能被发现）
    broadcast_thread = threading.Thread(target=self_broadcast, daemon=True)
    broadcast_thread.start()

    # 启动UDP监听线程
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()

    # 启动清理线程
    clean_thread = threading.Thread(target=cleanup_thread, daemon=True)
    clean_thread.start()

    print(f"[Web服务] 启动于 http://0.0.0.0:{WEB_PORT}")

    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)
