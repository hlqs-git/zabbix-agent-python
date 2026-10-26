"""Human-readable projection. The separate JSON audit sink retains all events."""
from datetime import datetime
import json
import logging
import shlex
from .precision import metric_value


def inline(value):
    text = str(value)
    return ''.join(char if ord(char) >= 32 and ord(char) != 127 else '\\x{:02x}'.format(ord(char)) for char in text)


def clock(value):
    try:
        return datetime.fromtimestamp(value).astimezone().strftime('%Y-%m-%d %H:%M:%S%z')
    except (TypeError, ValueError, OSError, OverflowError):
        return inline(value)


class ReadableFilter(logging.Filter):
    HIDDEN = {'metric_collected', 'metric_send', 'zabbix_response', 'system_raw', 'network_raw', 'discovery_cache_saved'}

    def filter(self, record):
        if getattr(record, 'event', None) in self.HIDDEN:
            return False
        # These stack events are followed by a concise delivery/collection error.
        if record.exc_info and record.name in {'agent.runtime', 'agent.sender', 'agent.collectors.command'}:
            return False
        return True


class ReadableFormatter(logging.Formatter):
    def __init__(self, run_id):
        super().__init__()
        self.run_id = run_id

    def format(self, record):
        fields = getattr(record, 'fields', {})
        name = getattr(record, 'event', '')
        title, body = self.describe(name, fields, record)
        timestamp = datetime.fromtimestamp(record.created).astimezone().isoformat(timespec='milliseconds', sep=' ')
        return '{} [{}] [{}] {}'.format(timestamp, record.levelname, title, body)

    def describe(self, name, f, record):
        if name == 'agent_start':
            return '启动', '运行编号={} 等级={} 保留={}天\n    运行日志={}\n    完整审计={}'.format(
                inline(self.run_id), inline(f.get('log_level')), f.get('retention_days'),
                inline(f.get('log_path', 'log/agent.log')), inline(f.get('audit_path', 'log/audit.jsonl')))
        if name == 'cycle_start':
            return '本轮任务', '主机={} 服务端={}:{} 系统={} 网卡={} 探测={} 并发={} 发送={}'.format(
                inline(f.get('host')), inline(f.get('server')), f.get('port'), '开启' if f.get('system') else '关闭',
                f.get('interfaces'), f.get('probes'), f.get('workers'), '逐条确认' if f.get('send_mode') == 'per_metric' else '批量')
        if name == 'collector_start':
            target = f.get('target', {})
            kind = target.get('kind', f.get('kind', 'system'))
            if kind == 'system':
                return '采集开始', '系统 CPU、负载、内存、根分区'
            label = {'network': '网卡', 'icmp': 'Ping', 'tcp': 'TCP'}.get(kind, kind)
            body = '{} {}（名称={}）'.format(label, inline(target.get('address')), inline(target.get('name')))
            if target.get('port') is not None:
                body += ' 端口=' + inline(target['port'])
            for field, label in (('namespace', 'Namespace'), ('source_ip', '源IP')):
                if target.get(field):
                    body += ' {}={}'.format(label, inline(target[field]))
            return '采集开始', body
        if name in ('command_start', 'command_result', 'command_error'):
            command = shlex.join([str(part) for part in f.get('command', [])])
            if name == 'command_start':
                return '执行命令', '{} 超时={}秒'.format(inline(command), f.get('timeout'))
            body = '{} | 退出码={} | 耗时={}ms'.format(inline(command), f.get('returncode', '未取得'), f.get('elapsed_ms', '?'))
            if f.get('error'):
                body += '\n    错误=' + inline(f['error'])
            for field in ('stdout', 'stderr'):
                if f.get(field):
                    output = f[field].decode('utf-8', errors='replace') if isinstance(f[field], bytes) else str(f[field])
                    body += '\n    {}:\n'.format(field) + '\n'.join('    | ' + inline(line) for line in output.splitlines())
            return ('执行失败' if name == 'command_error' else '原始输出'), body
        if name == 'metric_delivery':
            title = {'accepted': '上报成功', 'rejected': '服务端拒收', 'unconfirmed': '上报未确认', 'not_sent': '尚未发送'}.get(f.get('status'), '上报状态未知')
            wire = f.get('wire_value')
            try:
                collected = metric_value(f.get('value'))
            except ValueError:
                collected = f.get('value')
            body = '{} | 采集值={} | 发送值={}'.format(inline(f.get('key')), inline(collected), inline(wire) if wire is not None else '未生成')
            body += '\n    采集时间={} 耗时={}ms 主机={} 指标编号={}'.format(clock(f.get('clock')), f.get('elapsed_ms', '?'), inline(f.get('host', '')), inline(f.get('metric_id', '')))
            if f.get('response'):
                body += ' 响应=' + json.dumps(f['response'], ensure_ascii=False)
            if f.get('error'):
                body += '\n    原因=' + inline(f['error'])
            return title, body
        if name == 'discovery_decision':
            reason = {'first_or_invalid_cache': '首次运行或缓存不可用，发送完整列表', 'changed': '目标变化，立即发送',
                      'heartbeat': '达到一小时，补发完整列表', 'unchanged': '未变化，本轮跳过'}.get(f.get('reason'), f.get('reason'))
            return '自动发现', '{} | {}'.format(inline(f.get('key')), inline(reason))
        if name == 'cycle_end':
            return '本轮完成', '确认成功={} 未成功确认={}（其中未确认={}） 采集错误={} 耗时={}秒'.format(
                f.get('processed'), f.get('failed'), f.get('unconfirmed'), f.get('collection_errors'), f.get('elapsed_seconds'))
        if name == 'collection_failed':
            return '采集失败', inline(f.get('error'))
        message = record.getMessage()
        replacements = {
            'DEBUG audit mode: individual metric requests; increases request count': 'DEBUG 审计模式：逐条确认上报结果；完整原始事件和堆栈见 audit.jsonl',
            'Discovery unchanged; next heartbeat is due within one hour': '发现集合未变化，最迟一小时后补发',
            'Previous cycle is still running; skipping': '上一轮尚未结束，本轮跳过',
        }
        body = inline(replacements.get(message, message))
        if record.exc_info:
            body += '（异常堆栈见 audit.jsonl）'
        return ('错误' if record.levelno >= logging.ERROR else '运行'), body
