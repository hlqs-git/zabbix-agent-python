import json
import subprocess
from package.log import Log


log = Log(__name__).getlog()


def tcping(host, port, count=50, timeout=1, namespace=None):
    if namespace is None:
        tcping_result = subprocess.run(['/usr/local/sbin/tcping', '-4', '-c', str(count), 
                                          '-t', str(timeout), '-j', host, str(port)],
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        universal_newlines=True)
    else:
        tcping_result = subprocess.run(['/usr/sbin/ip', 'netns', 'exec', namespace, '/usr/local/sbin/tcping', '-4', '-c', str(count), 
                                          '-t', str(timeout), '-j',  host, str(port)],
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        universal_newlines=True)
    output = tcping_result.stdout
    output_lines = output.strip().splitlines()
    
    if output_lines:  # 确保输出不为空
        last_json = output_lines[-1]  # 获取最后一行
        try:
            output_data = json.loads(last_json)  # 将字符串解析为 JSON 对象
            # print(json.dumps(output_data, indent=4))  # 格式化输出 JSON
            log.debug(f"TCPing 调试日志输出: {json.dumps(output_data, indent=4)}")
        except json.JSONDecodeError:
            # print("最后一行不是有效的 JSON 数据:", last_json)
            log.error(f"TCPing 错误日志输出: {last_json}")
    else:
        # print("没有输出")
        log.error(f"TCPing 错误日志输出: 没有输出")
    
    if output_data['type'] == 'error':
        # print(f"Error: {output_data['message']}")
        log.debug(f"TCPing 调试日志输出: {output_data['message']}")
        dst_addr = False
        loss_pak = '100.00'
        avg_time = '0.00'
        return dst_addr, float(loss_pak), float(avg_time)
    elif output_data['type'] == 'statistics':
        # print(f"TCP Ping statistics for {host}:{port}:")
        dst_addr = output_data['addr']
        loss_pak = output_data['total_packet_loss']
        if loss_pak != '100.00':
            avg_time = output_data['latency_avg']
        else:
            avg_time = '0.00'
        # print(f"TCPing {host}:{port} - {dst_addr}:{port} - Loss: {loss_pak}% - Avg: {avg_time}ms")
        log.debug(f"TCPing 调试日志输出: TCPing {host}:{port} - {dst_addr}:{port} - Loss: {loss_pak}% - Avg: {avg_time}ms")
        
        return dst_addr, float(loss_pak), float(avg_time)

# if __name__ == "__main__":
#     host = 'www.baidu.com'
#     port = 443                              
#     count = 2
#     tcping(host, port, count=count)

"""

import socket
import time

def tcp_ping(host, port, count=50, timeout=1):
    successful_pings = 0
    total_time = 0

    for i in range(count):
        start_time = time.time()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((host, port))
                successful_pings += 1
                end_time = time.time()
                round_trip_time = (end_time - start_time) * 1000  # 转换为毫秒
                total_time += round_trip_time
                print(f"Ping {i + 1}: {host}:{port} is reachable - RTT: {round_trip_time:.2f} ms")
        except (socket.timeout, socket.error):
            # print(f"Ping {i + 1}: {host}:{port} is not reachable")
            log.debug(f"Ping {i + 1}: {host}:{port} is not reachable")

        time.sleep(1)  # 等待1秒再进行下一次ping

    if successful_pings > 0:
        average_rtt = total_time / successful_pings
        packet_loss = (count - successful_pings) / count * 100
        # print(f"\n--- {host}:{port} TCP Ping statistics ---")
        # print(f"{count} packets transmitted, {successful_pings} received, {packet_loss:.2f}% packet loss")
        # print(f"average RTT = {average_rtt:.2f} ms")
        log.info(f"{host}:{port} TCP Ping statistics; {count} packets transmitted, {successful_pings} received, {packet_loss:.2f}% packet loss; average RTT = {average_rtt:.2f} ms")
        
    else:
        # print(f"\n--- {host}:{port} TCP Ping statistics ---")
        # print(f"{count} packets transmitted, 0 received, 100.00% packet loss")
        log.info(f"{host}:{port} TCP Ping statistics; {count} packets transmitted, 0 received, 100.00% packet loss")

# 示例使用
if __name__ == "__main__":
    host = "example.com"  # 替换为目标主机
    port = 80             # 替换为目标端口
    tcp_ping(host, port)
"""