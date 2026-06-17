"""
局域网广播服务
每3秒向局域网广播本机的计算机名称和IP地址
"""
import socket
import time
import json
import platform

BROADCAST_PORT = 50001
BROADCAST_INTERVAL = 3  # 秒


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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
