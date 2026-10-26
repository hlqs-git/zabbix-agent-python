"""Select YAML or legacy INI and normalize collection targets."""
import ast
import warnings
from configparser import ConfigParser, Error
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .models import Target

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    server: str
    port: int
    hostname: str
    system: bool
    interfaces: List[Target]
    probes: List[Target]
    workers: int = 16
    send_timeout: int = 5
    log_level: str = 'INFO'
    log_console: bool = True
    log_retention_days: int = 14


def load_config(path=None):
    if path is None:
        candidates = [ROOT / 'conf' / name for name in ('config.yaml', 'config.yml', 'config.ini')]
        existing = [candidate for candidate in candidates if candidate.is_file()]
        if len(existing) > 1:
            raise ValueError('发现多个配置文件，请使用 --config 明确指定：' + ', '.join(str(p) for p in existing))
        path = existing[0] if existing else candidates[0]
    path = Path(path)
    if path.suffix.lower() in ('.yaml', '.yml'):
        from .yaml_config import load_yaml
        return load_yaml(path)
    if path.suffix.lower() != '.ini':
        raise ValueError('配置文件扩展名必须是 .yaml、.yml 或 .ini')
    warnings.warn('正在读取旧版 INI 配置；建议参考 conf/config.example.yaml 迁移到 YAML。', FutureWarning, stacklevel=2)
    cfg = ConfigParser(interpolation=None)
    try:
        with path.open(encoding='utf-8-sig') as source:
            cfg.read_file(source)
        return _parse(cfg)
    except (Error, OSError, SyntaxError, TypeError) as exc:
        raise ValueError('Invalid configuration: {}'.format(exc)) from exc


def _parse(cfg):
    def positive(section, key, default):
        value = cfg.getint(section, key, fallback=default)
        if value < 1:
            raise ValueError('{} must be positive'.format(key))
        return value

    def entries(section, key):
        if not cfg.has_option(section, key):
            return []
        values = [value.strip() for value in cfg.get(section, key).split(',')]
        if not all(values):
            raise ValueError('{} contains an empty target'.format(key))
        return values

    def parts(value, count):
        result = [part.strip() for part in value.split(':')]
        if len(result) != count or not all(result):
            raise ValueError('Invalid target format (IPv6 is not supported here): {}'.format(value))
        return result

    def validate_port(value):
        value = int(value)
        if not 1 <= value <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return value

    interfaces, probes = [], []
    enabled = lambda key: cfg.getboolean('zabbix item', 'Item.' + key, fallback=False)
    if enabled('if'):
        interfaces.extend(Target('network', value, value) for value in entries('if', 'if_nic'))
        for value in entries('if', 'if_nic_alias'):
            alias, address = parts(value, 2)
            interfaces.append(Target('network', address, alias))
    if enabled('ns_if'):
        for value in entries('ns_if', 'ns_if_nic'):
            namespace, address = parts(value, 2)
            interfaces.append(Target('network', address, address, namespace))
        if cfg.has_option('ns_if', 'ns_if_nic_alias'):
            mapping = ast.literal_eval(cfg.get('ns_if', 'ns_if_nic_alias'))
            if not isinstance(mapping, dict):
                raise ValueError('ns_if_nic_alias must be a nested dictionary')
            for namespace, aliases in mapping.items():
                if not isinstance(aliases, dict):
                    raise ValueError('Namespace aliases must be a dictionary')
                for alias, address in aliases.items():
                    interfaces.append(Target('network', address, alias, namespace))
    if enabled('ping'):
        duration = positive('ping', 'ping_time', 50)
        for address in entries('ping', 'ping_address'):
            probes.append(Target('icmp', address, address, duration=duration))
        for value in entries('ping', 'ping_address_alias'):
            alias, address = parts(value, 2)
            probes.append(Target('icmp', address, alias, duration=duration))
        count = positive('ping', 'tcping_count', positive('ping', 'tcping_time', 50))
        timeout = positive('ping', 'tcping_timeout', 1)
        for option, aliased in [('tcping_address', False), ('tcping_address_alias', True)]:
            for value in entries('ping', option):
                fields = parts(value, 3 if aliased else 2)
                alias, address, port = fields if aliased else (fields[0], fields[0], fields[1])
                port = validate_port(port)
                probes.append(Target('tcp', address, '{}:{}'.format(alias, port), port=port, duration=count, timeout=timeout))
    if enabled('ns_ping'):
        duration = positive('ns_ping', 'ns_ping_time', 50)
        for value in entries('ns_ping', 'ns_ping_address'):
            namespace, address = parts(value, 2)
            probes.append(Target('icmp', address, address, namespace, duration=duration))
    for group in (interfaces, probes):
        names = set()
        for target in group:
            for value in (target.address, target.name, target.namespace):
                if value is not None and (not isinstance(value, str) or not value.strip() or value.startswith('-') or any(c in value for c in '\r\n\x00')):
                    raise ValueError('Invalid target field: {!r}'.format(value))
            if any(c in target.name for c in '[],"'):
                raise ValueError('Unsafe Zabbix key name: {}'.format(target.name))
            if target.name in names:
                raise ValueError('Duplicate monitoring key: {}; configure a unique alias'.format(target.name))
            names.add(target.name)
    server = cfg.get('zabbix conf', 'Server').strip()
    hostname = cfg.get('zabbix conf', 'Hostname').strip()
    if not server or not hostname:
        raise ValueError('Server and Hostname are required')
    log_level = cfg.get('logging', 'level', fallback='INFO').upper()
    if log_level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        raise ValueError('logging.level must be DEBUG/INFO/WARNING/ERROR/CRITICAL')
    return Config(server, validate_port(cfg.get('zabbix conf', 'ServerPort')), hostname,
                  enabled('sys'), interfaces, probes,
                  positive('runtime', 'workers', 16), positive('runtime', 'send_timeout', 5),
                  log_level, cfg.getboolean('logging', 'console', fallback=True), positive('logging', 'retention_days', 14))
