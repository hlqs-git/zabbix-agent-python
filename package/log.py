#!/usr/bin/python
# -*- coding:utf-8 -*-

import logging
import time
import os


class Log(object):
    '''
封装后的logging
    '''

    def __init__(self, logger=None, log_cate='search'):
        '''
            指定保存日志的文件路径，日志级别，以及调用文件
            将日志存入到指定的文件中
        '''

        # 创建一个logger
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)
        # 创建一个handler，用于写入日志文件
        self.log_time = time.strftime("%Y_%m_%d")
        # Windows下使用
        # file_dir = os.getcwd() + '\log'
        # Linux 下使用
        file_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/log'
        # print(file_dir)
        if not os.path.exists(file_dir):
            os.mkdir(file_dir)
        self.log_path = file_dir
        # Linux 下使用
        self.log_name = self.log_path + "/" + log_cate + "." + self.log_time + '.log'
        # Windows 下使用
        # self.log_name = self.log_path + "\\" + log_cate + "." + self.log_time + '.log'
        # print(self.log_name)
        
        # 输出到日志文件
        # fh = logging.FileHandler(self.log_name, 'a')  # 追加模式  这个是python2的
        fh = logging.FileHandler(self.log_name, 'a', encoding='utf-8')  # 这个是python3的
        fh.setLevel(logging.INFO)

        # 再创建一个handler，用于输出到控制台
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # 定义handler的输出格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s]%(message)s')
        # 输入日志文件
        fh.setFormatter(formatter)
        # 输出到终端
        ch.setFormatter(formatter)

        # 给logger添加handler
        # 输入日志文件
        self.logger.addHandler(fh)
        # 输出到终端
        # self.logger.addHandler(ch)

        #  添加下面一句，在记录日志之后移除句柄
        # self.logger.removeHandler(ch)
        # self.logger.removeHandler(fh)
        # 关闭打开的文件
        fh.close()
        # ch.close()

    def getlog(self):
        return self.logger