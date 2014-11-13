import os
import pprint
import fnmatch
import time
import subprocess
import argparse
import configparser
import errno

__version__ = '1.0.0'

def bold(msg):
    return '\033[1m{}\033[0m'.format(msg)

class RunningUnit(object):
    def __init__(self, unit_name):
        self.unit_name = unit_name
        self.reasons = set([])

    def append_reasons(self, reasons):
        self.reasons |= set(reasons)

    def get_reasons(self):
        return self.reasons

    def display(self):
        print(bold('Unit: {}'.format(self.unit_name)))
        if self.get_reasons():
            for reason in self.get_reasons():
                print('   ∙ {}'.format(reason))


class RunningProcess(object):
    def __init__(self, pid):
        self.pid = pid
        self.reasons = None
        self.cmdline = None
        self.unit = None

    def get_reasons(self):
        if not self.reasons:
            self.reasons = set()
            try:
                with open('/proc/{}/maps'.format(self.pid), 'r') as maps:
                    for mapline in maps.readlines():
                        mapline = mapline.strip()
                        if mapline.endswith('(deleted)') and ('/usr' in mapline or '/opt' in mapline):
                            reason = mapline[73:-10]  # Beginning of path to before (deleted)
                            self.reasons |= set([reason])
            except IOError as e:
                if e.errno == errno.EACCES:
                    print('  PID {} maps not readable.'.format(self.pid))
                else:
                    print('  PID {} maps read error: {}'.format(self.pid, e))
                self.reasons = set([])
        return self.reasons

    def get_cmdline(self):
        if not self.cmdline:
            try:
                with open('/proc/{}/cmdline'.format(self.pid), 'r') as cmdline:
                    lines = cmdline.readlines()
                    if len(lines) > 0:
                        self.cmdline = lines[0]
            except IOError as e:
                print('  PID {} cmdline read error: {}'.format(self.pid, e))
        if self.cmdline is None:
            self.cmdline = False
        return self.cmdline

    def get_unit(self):
        if not self.unit:
            try:
                with open('/proc/{}/cgroup'.format(self.pid), 'r') as cgroups:
                    for cgroup in cgroups.readlines():
                        if 'systemd' in cgroup:
                            unit = cgroup.strip().split('/')[-1]
                            if unit != '':
                                 self.unit = unit
                                 break
            except IOError as e:
                if e.errno == errno.EACCES:
                    print('  PID {} cgroups not readable.'.format(self.pid))
                else:
                    print('  PID {} cgroups read error: {}'.format(self.pid, e))
            if self.unit is None:
                self.unit = False
        return self.unit

    def display(self):
        print(bold('PID: {}'.format(self.pid)))
        if self.get_unit() is not False:
            print('  Unit: {}'.format(self.get_unit()))
        if self.get_cmdline() is not False:
            print('  cmdline: {}'.format(self.get_cmdline()))
        if len(self.get_reasons()) > 0:
            print('  Reasons to restart:')
            for reason in self.get_reasons():
                print('   ∙ {}'.format(reason))

def get_pids():
    return [ f for f in os.listdir('/proc') if f.isdigit() and os.path.isdir(os.path.join('/proc', f)) ]

def get_processes():
    processes = []
    for pid in get_pids():
        processes.append(RunningProcess(pid))
    return processes

def get_units_from_processes(processes):
    units = {}
    for process in processes:
        unit_name = process.get_unit()
        if unit_name is not None and len(process.get_reasons()):
            if units.get(unit_name) is None:
                units[unit_name] = RunningUnit(unit_name)
            units[unit_name].append_reasons(process.get_reasons())
    return units

def find_matches(services, whitelist):
    matches = set()
    for whitelist_item in whitelist:
        restart_services = fnmatch.filter(services, whitelist_item)
        matches |= set(restart_services)
    return matches

def restart_services(services):
    for service in services:
        print('Restarting {0}...'.format(service))
        result = subprocess.check_output(['/usr/bin/systemctl', 'restart', service], stderr=subprocess.STDOUT)
        print(result)
        print('    ...done')
        time.sleep(5)

def get_configuration():
    config = configparser.ConfigParser()
    config.read('/etc/pmr.ini')

    strategies = {}
    try:
        strategies['cmdline'] = dict(config.items('cmdline'))
    except configparser.NoSectionError:
        strategies['cmdline'] = {}
    try:
        strategies['unit'] = dict(config.items('unit'))
    except configparser.NoSectionError:
        strategies['unit'] = {}
    return strategies

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    strategies = get_configuration()
    print(strategies)

    processes = get_processes()
    units = get_units_from_processes(processes)

    if args.verbose:
        for unit in units.values():
            unit.display()
        for process in processes:
            if not process.get_unit():
                process.display()

    #whitelist = ['atlas-nginx*', '*yggdrasil*', '*styx*', 'ssl_nginx*', '*hyperion*', '*resurrector*', '*endpoint*', 'nginx_valhalla*', 'nginx.service', 'graphite-web.service', 'carbon-*', 'haproxy_carbon_relay*', 'statsd*', 'munin_to_graphite*', 'pyinotify_*', 'yum-updatesd.service', 'php_fpm_*', 'pantheonssh_*', 'postfix.service', 'rsyslog.service', '*site_exp_mon*', 'nginx_*']
    #whitelisted = find_matches(services, whitelist)
    #print('Whitelisted:')
    #pprint.pprint(whitelisted)

    #print('Not Whitelisted:')
    #pprint.pprint(services.difference(whitelisted))

    #if not args.dry_run:
    #    restart_services(whitelisted)
