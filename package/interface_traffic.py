#!/usr/bin/env python
# -*- coding:utf-8 -*-
import psutil
import subprocess

def get_net_io_counters(interface_name):
    """
    Get bytes received and transmitted by a network interface
    :param interface_name: Network interface name, such as 'eth0'
    :return: A tuple of bytes received and transmitted by the interface
    """
    net_io_counters = psutil.net_io_counters(pernic=True).get(interface_name)
    if net_io_counters is None:
        raise ValueError("Invalid network interface name: {}".format(interface_name))
    
    bytes_received = net_io_counters.bytes_recv
    bytes_sent = net_io_counters.bytes_sent
    net_status = psutil.net_if_stats().get(interface_name).isup
    if net_status is False:
        net_status = 0
    else:
        net_status = 1

    return bytes_received, bytes_sent, net_status


def get_ns_net_io_counters(namespace, interface_name):
    '''
    This function is used to get the number and \
    status of bytes sent and received by the network \
    interface in the linux network namespace.
    
    namespace: Namespace Name
    interface_name: Interface Name
    '''
    
    shell_cmd = "ip netns exec {} ip ad sh {}".format(namespace, interface_name)
    shell_cmd_out = subprocess.run(shell_cmd, 
                                shell=True,
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                universal_newlines=True)
    
    # print(shell_cmd_out.stdout)
    if f"{shell_cmd_out.stdout}None" == "None" :
        raise ValueError("NameSpac {} Invalid network interface name: {}".format(namespace, interface_name))
    
    rx_cmd = "ip netns exec {} ifconfig {} | grep 'RX' \
            | grep 'bytes' | awk '{{print $5}}'".format(namespace, interface_name)
    rx_cmd_out = subprocess.run(rx_cmd, 
                                shell=True,
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                universal_newlines=True)
    
    tx_cmd = "ip netns exec {} ifconfig {} | grep 'TX' \
            | grep 'bytes' | awk '{{print $5}}'".format(namespace, interface_name)
    tx_cmd_out = subprocess.run(tx_cmd, 
                                shell=True,
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                universal_newlines=True)
    
    status_cmd = "ip netns exec {} ifconfig {} | grep 'RUNNING'".format(namespace, interface_name)
    status_cmd_out = subprocess.run(status_cmd , 
                                shell=True,
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                universal_newlines=True)
    
    bytes_received = rx_cmd_out.stdout.strip()
    bytes_sent = tx_cmd_out.stdout.strip()
    net_status = status_cmd_out.stdout.strip()
    if f"{net_status}None" == "None":
        net_status = 0
    else:
        net_status = 1

    return bytes_received, bytes_sent, net_status
