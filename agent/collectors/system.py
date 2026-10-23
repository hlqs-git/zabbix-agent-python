def get_system_load():
    import psutil
    load = psutil.getloadavg()
    return {'cpu': psutil.cpu_percent(interval=1), 'load_1': load[0],
            'load_5': load[1], 'load_15': load[2],
            'mem_used_percent': psutil.virtual_memory().percent,
            'disk_used_percent': psutil.disk_usage('/').percent}
