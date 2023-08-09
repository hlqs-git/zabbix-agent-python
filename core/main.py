#!/usr/bin/env python
# -*- coding:utf-8 -*-
import socket
from os import path
from time import time
from json import dumps
from datetime import datetime
from threading import Thread
from package.log import Log
from configparser import ConfigParser
from package.ping_address import ping
from package.system_load import get_system_load
from package.zabbix_requst import report_to_zabbix
from package.interface_traffic import get_net_io_counters


log = Log(__name__).getlog()

cfg = ConfigParser()
cfg.read(path.dirname(path.dirname(path.abspath(__file__))) + '/conf/config.ini')
cfg.sections()

server_ip = cfg.get('zabbix conf','Server')
server_port = cfg.get('zabbix conf','ServerPort')
host_name = cfg.get('zabbix conf','Hostname')
discovery_hours= cfg.get('zabbix conf','DiscoveryHours')

# 统一监控上报时间
timestamp = int(time())

def zabbix_get_item(key, value):
    
    '''获取 zabbix item'''
    
    log.debug(f' Zabbix 监控项数据上报 {key} : {value}')
    try:
        retun_value = report_to_zabbix(server_ip, 
                                    int(server_port), 
                                    host_name, 
                                    key, 
                                    value, 
                                    timestamp)
    except OSError:
        log.error(f' 网络不可达: {server_ip}')
        retun_value = 'Error'
        pass
    finally:
        return retun_value


def zabbix_item_descover(key, value, type):
    '''zabbix item 自动发现'''

    if int(discovery_hours) == datetime.now().hour:
        
        value = {'data': [{type : value}]}
        value = dumps(value)
        
        retun_value = zabbix_get_item(key, value)
        log.info(f' Zabbix 监控项自动发现 {key} : {value} ; zabbix 返回值: {retun_value}')
        return retun_value


def sys_load():
    '''获取主机负载信息'''
    sys_load = get_system_load()
    sys_cpu_zabbix = zabbix_get_item('sysload_get[CPU]', sys_load['cpu'])
    sys_1_zabbix = zabbix_get_item('sysload_get[load_avg_1]', sys_load['load_1'])
    sys_5_zabbix = zabbix_get_item('sysload_get[load_avg_5]', sys_load['load_5'])
    sys_15_zabbix = zabbix_get_item('sysload_get[load_avg_15]', sys_load['load_15'])
    sys_mem_zabbix = zabbix_get_item('sysload_get[memory]', sys_load['mem_used_percent'])
    sys_disk_zabbix = zabbix_get_item('sysload_get[disk]', sys_load['disk_used_percent'])
    
    log.info(f' CPU使用率: {sys_load["cpu"]}, CPU使用率 zabbix: {sys_cpu_zabbix}')
    log.info(f' 1分钟负载: {sys_load["load_1"]}, 1分钟负载 zabbix: {sys_1_zabbix}')
    log.info(f' 5分钟负载: {sys_load["load_5"]}, 5分钟负载 zabbix: {sys_5_zabbix}')
    log.info(f' 15分钟负载: {sys_load["load_15"]}, 15分钟负载 zabbix: {sys_15_zabbix}')
    log.info(f' 内存使用率: {sys_load["mem_used_percent"]}, 内存使用率 zabbix: {sys_mem_zabbix}')
    log.info(f' 磁盘使用率: {sys_load["disk_used_percent"]}, 磁盘使用率 zabbix: {sys_disk_zabbix}')
    

def interface_traffic(nic_name, nic_alias=None):
    '''获取网卡流量信息'''
    try:
        rx_bytes, tx_bytes, nic_status = get_net_io_counters(nic_name)
    except ValueError:
        log.error(f' 无效的网络接口名称: {nic_name}')
    else:
        if nic_alias:
            zabbix_item_descover('Zabbix.interface', nic_alias, '{#IFNAME}')
            if_rx_zab = zabbix_get_item(f'IF_get[{nic_alias},In_traff]', rx_bytes)
            if_tx_zab = zabbix_get_item(f'IF_get[{nic_alias},Out_traff]', tx_bytes)
            if_status_zab = zabbix_get_item(f'IF_get[{nic_alias},status]', nic_status)
            # log.info(f' {nic_alias}: Received {rx_bytes} bytes, Sent {tx_bytes} bytes')
            log.info(f' {nic_alias}, 接收: {rx_bytes} bytes, RX zabbix: {if_rx_zab}; 发送: {tx_bytes} bytes, TX zabbix: {if_tx_zab}; 状态: {nic_status}, 状态 zabbix: {if_status_zab}')
        else:
            # log.info(f' {nic_name}, Received {rx_bytes} bytes, Sent {tx_bytes} bytes')
            zabbix_item_descover('Zabbix.interface', nic_name, '{#IFNAME}')
            if_rx_zab = zabbix_get_item(f'IF_get[{nic_name},In_traff]', rx_bytes)
            if_tx_zab = zabbix_get_item(f'IF_get[{nic_name},Out_traff]', tx_bytes)
            if_status_zab = zabbix_get_item(f'IF_get[{nic_name},status]', nic_status)
            log.info(f' {nic_name}, 接收: {rx_bytes} bytes RX zabbix: {if_rx_zab}; 发送: {tx_bytes} bytes TX zabbix: {if_tx_zab}; 状态: {nic_status}, 状态 zabbix: {if_status_zab}')
    

def ping_address(ip_address, ip_time, ip_alias=None):
    '''获取 ping 信息'''
    packet_loss_rate, avg_rtt = ping(ip_address, ip_time)
    
    try:
        float(avg_rtt)
    except (ValueError, TypeError):
        avg_rtt = 0

    if ip_alias:
        zabbix_item_descover('Zabbix.ping.dst_ip', ip_alias, '{#DST_IP}')
        ping_loss_zab = zabbix_get_item(f'ping_get[{ip_alias},loss]', int(packet_loss_rate))
        ping_rtt_zab = zabbix_get_item(f'ping_get[{ip_alias},delay]', float(avg_rtt))
        log.info(f' 地址: {ip_alias} ,丢包率: {packet_loss_rate} Loss zabbix: {ping_loss_zab} ;平均时延: {float(avg_rtt)} ms, Delay zabbix: {ping_rtt_zab}')
    else:
        zabbix_item_descover('Zabbix.ping.dst_ip', ip_address, '{#DST_IP}')
        ping_loss_zab = zabbix_get_item(f'ping_get[{ip_address},loss]', int(packet_loss_rate))
        ping_rtt_zab = zabbix_get_item(f'ping_get[{ip_address},delay]', float(avg_rtt))
        log.info(f' 地址: {ip_address} ,丢包率: {packet_loss_rate} Loss zabbix: {ping_loss_zab} ;平均时延: {float(avg_rtt)} ms, Delay zabbix: {ping_rtt_zab}')


def get_config():

    if cfg.getboolean('zabbix item','Item.sys'):
        sys_load()
    
    if cfg.getboolean('zabbix item','Item.if'):
        
        if 'if_nic' in cfg.options('if'):
            if_list = [item.strip() for item in cfg.get('if', 'if_nic').split(',')]
            for if_key in if_list:
                '''
                开启多线程
                thread_if = threading.Thread(target=interface_traffic, 
                                            args=(if_key,))
                thread_if.start()
                '''
                interface_traffic(if_key)
        
        if 'if_nic_alias' in cfg.options('if'):
            for if_alias_key in cfg.get('if', 'if_nic_alias').split(','):
                if_key, if_value = [item.strip() for item in if_alias_key.split(':')]
                '''
                开启多线程
                thread_if = threading.Thread(target=interface_traffic, 
                                             args=(if_value,if_key,))
                thread_if.start()
                '''
                interface_traffic(if_value, if_key)
        
    if cfg.getboolean('zabbix item','Item.ping'):
        
        if 'ping_time' in cfg.options('ping'):
            ping_time = cfg.getint('ping', 'ping_time')
        else:
            ping_time = 50
        
        if 'ping_address' in cfg.options('ping'):
            ping_list = [item.strip() for item in cfg.get('ping', 'ping_address').split(',')]
            for ping_key in ping_list:
                thread_ping = Thread(target=ping_address, args=(ping_key, ping_time,))
                thread_ping.start()
            
        if 'ping_address_alias' in cfg.options('ping'):
            for ping_alias_key in cfg.get('ping', 'ping_address_alias').split(','):
                ping_key, ping_value = [item.strip() for item in ping_alias_key.split(':')]
                thread_ping = Thread(target=ping_address, args=(ping_value, ping_key, ping_time,))
                thread_ping.start()


def main():
    get_config()