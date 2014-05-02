import os
import pprint
import fnmatch
import time
import subprocess

__version__ = '1.2.0'

def find_services_needing_restart():
    services = {}
    pids = [ f for f in os.listdir('/proc') if f.isdigit() and os.path.isdir(os.path.join('/proc', f)) ]

    for pid in pids:
        reasons = set()
        try:
            with open('/proc/{0}/maps'.format(pid), 'r') as maps:
                for map in maps.readlines():
                    if '(deleted)' in map and ('/usr' in map or '/opt' in map):
                        reasons |= set([map])
            if len(reasons) > 0:
                with open('/proc/{0}/cgroup'.format(pid), 'r') as cgroups:
                    for cgroup in cgroups.readlines():
                        if 'systemd' in cgroup:
                            service = cgroup.strip().split('/')[-1]
                            if service != '':
                                 services[service] = reasons
        except IOError as e:
            print('PID {0} went away: {1}'.format(pid, e))
    return services

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

__version__ = '1.2.0'

def main():
    """Entry point for the application script"""
    services = set(find_services_needing_restart().keys())

    whitelist = ['atlas-nginx*', '*yggdrasil*', '*styx*', 'ssl_nginx*', '*hyperion*', '*resurrector*', '*endpoint*', 'nginx_valhalla*', 'nginx.service', 'graphite-web.service', 'carbon-*', 'haproxy_carbon_relay*', 'statsd*', 'munin_to_graphite*', 'pyinotify_*', 'yum-updatesd.service', 'php_fpm_*', 'pantheonssh_*', 'postfix.service', 'rsyslog.service', '*site_exp_mon*', 'nginx_*']
    whitelisted = find_matches(services, whitelist)
    print('Whitelisted:')
    pprint.pprint(whitelisted)

    print('Not Whitelisted:')
    pprint.pprint(services.difference(whitelisted))

    restart_services(whitelisted)
