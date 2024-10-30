   # 1. zabbix
   ## 1.1. 描述
   使用 python3 获取主机各项指标并上报至zabbix server

   # 2. 开始
   ```
   # 互联网公网环境使用
   git clone https://gitlab.heilvqishi.top:6869/algoblu-public/zabbix.git
   ```

   # 3. 初始化
   ```
   # 制作python软链
   ln -s /usr/bin/python3 /usr/bin/python

   # 安装依赖包
   yum install gcc python3-devel
   
   # 运行项目中的 init.py文件 安装依赖库
   python3 init.py

   # 添加软件链接 (tcping)
   ln -s /your_path/zabbix/package/download/tcping /usr/local/sbin/tcping
   ```

   # 4. 使用
   ```
   # 运行项目中的 start.py文件 启动程序
   python3 start.py
   # 或者加入crontab 定时执行
   */1 * * * * python3 /path/zabbix/start.py
   ```

   init.py 
    初始化文件,用来安装依赖库
  
   start.py
    程序启动文件

   conf/config.ini
    监控配置文件
   
   core/main.py
    程序主文件

   package/*
    程序包文件

   log/*
    日志文件

   # 5. zabbix 监控添加
   Zabbix Server 添加主机监控模板时注意使用 "Template_sysload_Python_Nodata v1" 或 "Template_sysload_Python v1"

   # 6. 历史更新
   2023-11-21 version 1.04
   - 增加了 linux namespace 接口监控
   - 增加了 linux namespace ping监控
   
   2024-01-31 version 1.08
   - 修改IP为域名
   - 修改http为https

   2024-10-30 version 1.08.3
   - 添加tcping功能

