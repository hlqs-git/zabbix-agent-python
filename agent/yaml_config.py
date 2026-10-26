"""Strict, safe YAML parsing with user-facing field paths."""
from .config import Config
from .models import Target
from ipaddress import IPv4Address


def _mapping(value, allowed, location):
    if not isinstance(value, dict):
        raise ValueError('{} 必须是字段集合'.format(location))
    for key in value:
        if key not in allowed:
            raise ValueError('{} 包含未知字段：{}'.format(location, key))
    return value


def _text(value, location):
    if isinstance(value, str):
        value = value.strip()
    if not isinstance(value, str) or not value.strip() or value.startswith('-') or any(c in value for c in '\r\n\x00'):
        raise ValueError('{} 必须是非空文本，且不能以 - 开头'.format(location))
    return value.strip()


def _integer(value, location, maximum=None):
    if type(value) is not int or value < 1:
        raise ValueError('{} 必须是正整数'.format(location))
    if maximum is not None and value > maximum:
        raise ValueError('{} 必须在 1～{} 之间'.format(location, maximum))
    return value


def load_yaml(path):
    try:
        import yaml
    except ImportError as exc:
        raise ValueError('读取 YAML 需要 PyYAML，请执行 python -m pip install -r requirements.txt') from exc

    class UniqueLoader(yaml.SafeLoader):
        pass

    def unique_mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str):
                raise ValueError('第 {} 行：字段名必须是文本'.format(key_node.start_mark.line + 1))
            if key in result:
                raise ValueError('第 {} 行：重复字段 {}'.format(key_node.start_mark.line + 1, key))
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
    try:
        with path.open(encoding='utf-8-sig') as source:
            data = yaml.load(source, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        where = '第 {} 行，第 {} 列'.format(mark.line + 1, mark.column + 1) if mark else str(path)
        raise ValueError('YAML 格式错误（{}），请检查缩进和冒号：{}'.format(where, getattr(exc, 'problem', str(exc)))) from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError('无法读取配置 {}：{}'.format(path, exc)) from exc
    return parse_yaml(data)


def parse_yaml(data):
    data = _mapping(data, {'zabbix', 'runtime', 'system', 'interfaces', 'ping', 'tcp'}, '配置')
    zabbix = _mapping(data.get('zabbix'), {'server', 'hostname', 'port', 'send_timeout_seconds'}, 'zabbix')
    runtime = _mapping(data.get('runtime', {}), {'max_workers'}, 'runtime')
    system = data.get('system', False)
    if type(system) is not bool:
        raise ValueError('system 必须填写 true 或 false，不要加引号')
    interfaces, probes = [], []
    for section in ('interfaces', 'ping', 'tcp'):
        entries = data.get(section, [])
        if not isinstance(entries, list):
            raise ValueError('{} 必须是列表，每个目标以 - 开头；不需要时请删除该项或填写 []'.format(section))
        for index, entry in enumerate(entries, 1):
            location = '{} 第 {} 个目标'.format(section, index)
            allowed = {'name', 'namespace', 'device'} if section == 'interfaces' else {'name', 'namespace', 'address'}
            allowed |= {'duration_seconds', 'source_ip'} if section == 'ping' else ({'port', 'count', 'connect_timeout_seconds'} if section == 'tcp' else set())
            entry = _mapping(entry, allowed, location)
            address_field = 'device' if section == 'interfaces' else 'address'
            address = _text(entry.get(address_field), location + '.' + address_field)
            if section != 'interfaces' and ':' in address:
                raise ValueError('{} 暂不支持 IPv6；端口请单独填写 port'.format(location))
            namespace = _text(entry['namespace'], location + '.namespace') if 'namespace' in entry else None
            name = _text(entry.get('name', address), location + '.name')
            if any(c in name for c in '[],"'):
                raise ValueError('{} .name 不能包含逗号、引号或方括号'.format(location))
            if section == 'interfaces':
                interfaces.append(Target('network', address, name, namespace))
            elif section == 'ping':
                source_ip = None
                if 'source_ip' in entry:
                    try:
                        source_ip = str(IPv4Address(_text(entry['source_ip'], location + '.source_ip')))
                    except ValueError as exc:
                        raise ValueError('{} .source_ip 必须是有效的 IPv4 地址'.format(location)) from exc
                probes.append(Target('icmp', address, name, namespace, duration=_integer(entry.get('duration_seconds', 50), location + '.duration_seconds'), source_ip=source_ip))
            else:
                port = _integer(entry.get('port'), location + '.port', 65535)
                probes.append(Target('tcp', address, '{}:{}'.format(name, port), namespace, port,
                                     _integer(entry.get('count', 10), location + '.count'),
                                     _integer(entry.get('connect_timeout_seconds', 1), location + '.connect_timeout_seconds')))
    for group in (interfaces, probes):
        names = set()
        for target in group:
            if target.name in names:
                raise ValueError('监控名称重复：{}，请为目标填写不同的 name'.format(target.name))
            names.add(target.name)
    return Config(_text(zabbix.get('server'), 'zabbix.server'),
                  _integer(zabbix.get('port', 10051), 'zabbix.port', 65535),
                  _text(zabbix.get('hostname'), 'zabbix.hostname'), system, interfaces, probes,
                  _integer(runtime.get('max_workers', 16), 'runtime.max_workers'),
                  _integer(zabbix.get('send_timeout_seconds', 5), 'zabbix.send_timeout_seconds'))


def describe_config(config):
    lines = ['配置检查通过', '', '发送到：{}:{}'.format(config.server, config.port),
             '主机名：{}'.format(config.hostname), '', '将采集：']
    if config.system:
        lines.append('  系统指标：CPU、负载、内存、根分区')
    for target in config.interfaces + config.probes:
        detail = '网卡 {}'.format(target.address) if target.kind == 'network' else (
            'Ping {}（{} 秒）'.format(target.address, target.duration) if target.kind == 'icmp' else
            'TCP {}:{}（{} 次，单次超时 {} 秒）'.format(target.address, target.port, target.duration, target.timeout))
        if target.namespace:
            detail += '，Namespace：' + target.namespace
        if target.source_ip:
            detail += '，源 IP：' + target.source_ip
        detail += '，监控名称：' + target.name
        lines.append('  ' + detail)
    if not config.system and not config.interfaces and not config.probes:
        lines.append('  无；当前配置不会采集指标')
    lines += ['', '提示：此检查尚未连接 Zabbix Server，也未执行设备探测。',
              '删除目标后会发送空发现集合，旧资源按 Zabbix 的丢失资源策略处理。']
    return '\n'.join(lines)
