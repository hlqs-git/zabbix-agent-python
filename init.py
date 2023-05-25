#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

file_path = os.path.dirname(os.path.abspath(__file__))

try:
    import psutil
except ImportError or ModuleNotFoundError:
    
    print(file_path)
    os.system(f'pip3 install {file_path}/package/download/psutil-5.9.5.tar.gz')
    import psutil

try:
    import pyzabbix
except ImportError or ModuleNotFoundError:
    os.system(f'pip3 install {file_path}/package/download/py_zabbix-1.1.7-py3-none-any.whl')
    import pyzabbix