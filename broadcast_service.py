"""
局域网广播服务
每3秒向局域网广播本机的计算机名称和IP地址
"""
import socket
import time
import json
import platform
import subprocess
import re

BROADCAST_PORT = 50001
BROADCAST_INTERVAL = 3  # 秒


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
    # 192.168.x.x, 10.x.x.x, 172.16-31.x.x
    return (a == 10) or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


def get_local_ip():
    """获取本机局域网IP地址，使用多种方法确保拿到真实局域网IP"""

    # 方法1: 直接解析 ifconfig / ipconfig 输出（最可靠，不受VPN干扰）
    ip = _get_ip_via_ifconfig()
    if ip:
        return ip

    # 方法2: 尝试连接局域网网关IP（VPN通常不会劫持LAN网段路由）
    for target in ["192.168.1.1", "192.168.0.1", "10.0.0.1", "172.16.0.1"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if is_lan_ip(ip):
                return ip
        except Exception:
            pass

    # 方法3: 通过连接公网IP获取默认路由IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if is_lan_ip(ip):
            return ip
    except Exception:
        pass

    # 方法4: 连接 10.255.255.255 尝试获取IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if is_lan_ip(ip):
            return ip
    except Exception:
        pass

    # 方法5: 通过 getaddrinfo 枚举所有本机IP
    try:
        hostname = socket.gethostname()
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip = addr[4][0]
            if is_lan_ip(ip):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def _get_ip_via_ifconfig():
    """通过系统命令 ifconfig/ipconfig 获取局域网IP"""
    try:
        # macOS / Linux
        result = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, timeout=5
        )
        pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
        matches = re.findall(pattern, result.stdout)
        for ip in matches:
            if is_lan_ip(ip):
                return ip
    except Exception:
        pass
    try:
        # Windows 备选
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=5,
            shell=True
        )
        pattern = r'IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)'
        matches = re.findall(pattern, result.stdout)
        for ip in matches:
            if is_lan_ip(ip):
                return ip
    except Exception:
        pass
    return None


def get_computer_name():
    """获取计算机名称"""
    return platform.node()


def broadcast_loop():
    """循环广播本机信息"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    computer_name = get_computer_name()
    local_ip = get_local_ip()

    print(f"[广播服务] 本机名称: {computer_name}, IP: {local_ip}")
    print(f"[广播服务] 开始每 {BROADCAST_INTERVAL} 秒广播一次...")

    while True:
        try:
            message = json.dumps({
                "hostname": computer_name,
                "ip": local_ip
            })
            sock.sendto(message.encode("utf-8"), ("255.255.255.255", BROADCAST_PORT))
            print(f"[广播] 已发送: {computer_name} ({local_ip})")
        except Exception as e:
            print(f"[广播] 发送失败: {e}")

        time.sleep(BROADCAST_INTERVAL)


if __name__ == "__main__":
    broadcast_loop()
