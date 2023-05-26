#!/usr/bin/env python
# -*- coding:utf-8 -*-

import subprocess

def ping(ip, count=50):
    """
    探测指定IP地址,返回丢包率和平均时延
    :param ip: IP地址
    :param count: 探测包数,默认为4个
    :return: 丢包率和平均时延(单位ms)
    """
    ping_result = subprocess.run(['ping', '-w', str(count), '-i', '1', ip], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 universal_newlines=True)
    output = ping_result.stdout.splitlines()
    # print(output)

    packet_loss_rate = None
    avg_rtt = None

    for line in output:
        if 'packet loss' in line:
            packet_loss_rate = line.split(',')[2].split()[0]
        elif 'rtt' in line:
            avg_rtt = line.split('/')[4]

    return packet_loss_rate, avg_rtt