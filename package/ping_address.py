#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess

def ping(ip, sec=50 , interval='0.25'):
    """
    探测指定IP地址,返回丢包率和平均时延
    :param ip: IP地址
    :param count: 探测包数,默认为4个
    :return: 丢包率和平均时延(单位ms)
    """
    ping_result = subprocess.run(['ping', '-w', str(sec), '-i', interval, '-q', ip], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 universal_newlines=True)
    output = ping_result.stdout
    
    packet_loss_rate = re.search(r"(\d+)%", output)
    packet_loss_rate = packet_loss_rate.group(1) if packet_loss_rate else None
    
    avg_rtt = re.search(r"avg\/max\/mdev = (\d+\.\d+)\/\d+\.\d+\/\d+\.\d+\/\d+\.\d+", output)
    avg_rtt = avg_rtt.group(1) if avg_rtt else None
    
    if packet_loss_rate:
        packet_loss_rate = packet_loss_rate
        if packet_loss_rate == '100':
            avg_rtt = 0
    else:
        packet_loss_rate = 100
        avg_rtt = 0
        
    return packet_loss_rate, avg_rtt

