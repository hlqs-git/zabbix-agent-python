import logging
from ..audit import event

logger = logging.getLogger('agent.collectors.system')


def get_system_load():
    import psutil
    load = psutil.getloadavg()
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    event(logger, logging.DEBUG, 'system_raw', load=load, cpu_percent=cpu,
          memory=memory._asdict(), disk=disk._asdict(), disk_path='/')
    return {'cpu': cpu, 'load_1': load[0],
            'load_5': load[1], 'load_15': load[2],
            'mem_used_percent': memory.percent, 'disk_used_percent': disk.percent}
