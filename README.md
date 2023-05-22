   # 1. zabbix
   ## 1.1. 描述
   使用 python3 获取主机各项指标并上报至zabbix server

   # 2. 开始
   ```
   # algoblu office 内网环境使用
   git clone http://192.168.11.7/algoblu-public/zabbix.git

   # 互联网公网环境使用
   git clone http://101.36.148.155:6869/algoblu-public/zabbix.git
   ```

   # 3. 初始化
   ```
   # 运行项目中的 init.py文件 安装依赖库
   python3 init.py
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

