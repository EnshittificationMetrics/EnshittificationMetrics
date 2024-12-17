#!/usr/bin/env python

"""
# Script to test end to end: cron --> python script (grabs MOTD stuff) --> console and logging and ntfy
v1.21
"""

import datetime
import requests
import logging
import socket


ntfypost = True
titletest = "cronz notify; Enshittification Metrics droplet live!"


def GetMachineID():
    """ Gets hostname, or last four of hostname if more than 10 chars """
    hostn = socket.gethostname()
    l = int( len(hostn) )
    if l > 10: hostn = hostn[l-4:l]
    return hostn


def MOTD_content():
    import os
    import shutil
    import psutil
    import socket
    import subprocess
    motd = ''
    
    load1, load5, load15 = os.getloadavg()
    motd += (f"Load Avg over last 1 5 and 15 mins: {load1:.2f}, {load5:.2f}, {load15:.2f}" + '\n')
    
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    motd += (f"Memory usage: {memory.percent}%" + ' ~ ')
    motd += (f"Swap usage: {swap.percent}%" + '\n')

    total, used, free = shutil.disk_usage("/")
    motd += (f"Drive usage of /: {used / total * 100:.2f}% of {total / (1024**3):.2f}GB" + '\n')

    users = psutil.users()
    motd += (f"Users logged in: {len(users)}" + ' ~ ')

    process_count = len(psutil.pids())
    motd += (f"Processes: {process_count}" + '\n')

    addrs = psutil.net_if_addrs()
    ipv4_addresses = {
        iface: addr.address
        for iface, iface_addrs in addrs.items()
        for addr in iface_addrs
        if addr.family == socket.AF_INET
    }
    motd += (f"IPv4 address: {ipv4_addresses['wlan0']}" + '\n')

    motd += (get_updates_from_cache() + ' ~ ')

    motd += (is_restart_required() + '\n')

    return motd


def get_updates_from_cache():
    try:
        with open("/var/lib/update-notifier/updates-available", "r") as f:
            for line in f:
                if "updates can be applied immediately" in line:
                    return line.strip()
        return "No update information found."
    except FileNotFoundError:
        return "Update notifier cache not found."


def is_restart_required():
    try:
        # Check if the reboot-required file exists
        with open("/var/run/reboot-required", "r") as f:
            return f"System restart required: {f.read().strip()}"
    except FileNotFoundError:
        return "No system restart required."


def main():
    logging.basicConfig(level=logging.INFO, 
                        filename='/home/bsea/em/utilities/cronz.log', 
                        filemode='a', 
                        format='%(asctime)s -%(levelname)s - %(message)s'
    )
    hostn = GetMachineID()
    alertmsgt = f'{hostn} {titletest}'
    alertmsgb = str( datetime.datetime.now() )
    lenminusfour = len(alertmsgb) - 4
    alertmsgb = alertmsgb[0:lenminusfour] # truncate off 100s of seconds and beyond
    alertmsgb = MOTD_content() + alertmsgb
    print(f'{alertmsgt}; print to console. {alertmsgb}')
    logging.info(f'{alertmsgt}; {alertmsgb}')
    if ntfypost: requests.post('https://ntfy.sh/000ntfy000topic000backup000', 
        headers={'Title' : alertmsgt}, data=(alertmsgb))

if __name__ == '__main__':
    main()
