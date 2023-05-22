#!/usr/bin/env python
# -*- coding:utf-8 -*-
import psutil

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
    net_status = psutil.net_if_stats().get(interface_name)

    return bytes_received, bytes_sent, net_status
