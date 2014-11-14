import os
import pprint
import fnmatch
import time
import subprocess
import argparse
import configparser
import errno

__version__ = '2.0.0'

def bold(msg):
    return '\033[1m{}\033[0m'.format(msg)

def header_okay(msg):
    return '\033[92m\033[1m{}\033[0m'.format(msg)

def header_failure(msg):
    return '\033[91m\033[1m{}\033[0m'.format(msg)

def header_warning(msg):
    return '\033[93m\033[1m{}\033[0m'.format(msg)

class Restartable(object):
    def __init__(self, name, restart_command):
        self.name = name
        self.reasons = set([])
        self.restart_command = restart_command

    def append_reasons(self, reasons):
        self.reasons |= set(reasons)

    def get_reasons(self):
        return self.reasons

    def display(self, verbose=False):
        if not self.get_reasons() and not verbose:
            return
        title = header_okay(self.name)
        if self.get_reasons():
            if self.restart_command is not None:
                title = header_warning(self.name)
            else:
                title = header_failure(self.name)
        print(title)
        if self.get_reasons():
            for reason in self.get_reasons():
                print('   ∙ {}'.format(reason))    

    def matches_strategy(self, strategy):
        hit = False
        for match, effect in strategy.items():
            if fnmatch.fnmatch(self.name, match):
                if effect:
                    hit = True
                else:
                    return False
        return hit

class RunningUnit(Restartable):
    def __init__(self, name):
        restart_command = 'systemctl restart {}'.format(name)
        super(RunningUnit, self).__init__(name, restart_command)

class RunningCmdline(Restartable):
    def __init__(self, name):
        restart_command = None
        super(RunningCmdline, self).__init__(name, restart_command)

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
        return self.unit

    def display(self):
        print(bold('PID: {}'.format(self.pid)))
        if self.get_unit() is not False:
            print('  Unit: {}'.format(self.get_unit()))
        if self.get_cmdline() is not False:
            print('  Cmdline: {}'.format(self.get_cmdline()))
        if len(self.get_reasons()) > 0:
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
        if unit_name is not None:
            if units.get(unit_name) is None:
                units[unit_name] = RunningUnit(unit_name)
            units[unit_name].append_reasons(process.get_reasons())
    return units

def get_cmdlines_from_processes(processes):
    cmdlines = {}
    for process in processes:
        cmdline = process.get_cmdline()
        if cmdline is not None:
            if cmdlines.get(cmdline) is None:
                cmdlines[cmdline] = RunningCmdline(cmdline)
            cmdlines[cmdline].append_reasons(process.get_reasons())
    return cmdlines

def find_matches(items, whitelist, blacklist=None):
    matches = set()
    for whitelist_item in whitelist:
        matches |= set(fnmatch.filter(items, whitelist_item))

    if blacklist:
        for blacklist_item in blacklist:
            matches -= set(fnmatch.filter(matches, blacklist_item))

    return matches

def restart_services(services):
    for service in services:
        print('Restarting {0}...'.format(service.name))
        result = subprocess.check_output(['/usr/bin/systemctl', 'restart', service.name], stderr=subprocess.STDOUT)
        print(result)
        if result:
            print('    ...success')
        else:
            print('    ...failed')            
        time.sleep(5)

def get_configuration():
    config = configparser.ConfigParser()
    config.read('/etc/pmr.ini')

    strategies = {}
    strategies['cmdline'] = {}
    try:
        for key, value in dict(config.items('cmdline')).items():
            strategies['cmdline'][key] = (value == 'true')
    except configparser.NoSectionError:
        strategies['cmdline'] = {'*': True}

    strategies['unit'] = {}
    try:
        for key, value in dict(config.items('unit')).items():
            strategies['unit'][key] = (value == 'true')
    except configparser.NoSectionError:
        strategies['unit'] = {'*.service': True}
    return strategies

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    strategies = get_configuration()
    #print(strategies)

    processes = get_processes()
    units = get_units_from_processes(processes)
    cmdlines = get_cmdlines_from_processes(processes)

    services_to_restart = []

    for unit in units.values():
        if unit.matches_strategy(strategies['unit']):
            unit.display(args.verbose)
            if unit.get_reasons():
                services_to_restart.append(unit)
    for cmdline in cmdlines.values():
        if cmdline.matches_strategy(strategies['cmdline']):
            cmdline.display(args.verbose)

    if not args.dry_run:
        restart_services(services_to_restart)
