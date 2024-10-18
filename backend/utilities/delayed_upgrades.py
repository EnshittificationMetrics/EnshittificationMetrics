#!/usr/bin/env python

"""
Performs automated OS maintenance!
Upgrade only the packages whose updates are more than "days_delay" days old.
Reboots (safely) if required, or if no reboot in last "days_force_reboot" days.
"""

if __file__.startswith('/home/bsea/em/'):
    log_path = '/home/bsea/em/utilities/delayed_upgrades.log' # EM prod
    days_delay = 9
    days_force_reboot = 36
else:
    log_path = '/home/leet/EnshittificationMetrics/backend/utilities/delayed_upgrades.log' # EM dev or CLI (testing)
    days_delay = 21
    days_force_reboot = 5

import logging
logging.basicConfig(level = logging.INFO,
                    filename = log_path,
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

import subprocess
import datetime
import re
import os
from datetime import timedelta
import time

today = datetime.date.today()
some_days_ago = today - datetime.timedelta(days=days_delay)

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        logging.error(f'Error during subprocess.run({command}) attempt: {e}')
        return "" # works on all cases in this program while returning None fails
    return result.stdout

def get_upgradable_packages():
    output = run_command('apt list --upgradable')
    packages = []
    for line in output.splitlines():
        if '/' in line:
            package_name = line.split('/')[0]
            packages.append(package_name)
    return packages

def get_last_update_date(package_name):
    """ Reads package changelog and matches ".com>  Day, DD Mmm YYYY HH:MM:SS ±HHMM" and captures "DD Mmm YYYY" """
    output = run_command(f'apt changelog {package_name}')
    date_pattern = re.compile(r"\.com>\s{2}[A-Z][a-z]{2},\s(\d{2}\s\w{3}\s\d{4})\s\d{2}:\d{2}:\d{2}\s[+-]\d{4}")
    dates = date_pattern.findall(output)
    if dates:
        # Return the most recent date (first one found)
        return datetime.datetime.strptime(dates[0], '%d %b %Y').date()
    return None

def upgrade_package(package_name, last_update_date):
    run_command(f'sudo apt install -y {package_name}')
    logging.info(f'Upgrading {package_name}... Updated {last_update_date}.')

def get_uptime():
    """ Runs the 'uptime' command, captures the output, converts to days, hours, and minutes. """
    output = run_command('uptime')
    # ex: ' 11:44:27 up 7 days,  8:13,  2 users,  load average: 0.16, 0.20, 0.17'
    # ex: ' 03:35:22 up 7 days, 4 min,  2 users,  load average: 0.22, 0.31, 0.27' # no hours!
    # ex: ' 12:34:56 up 5 hours, 42 mins,  3 users,  load average: 0.12, 0.15, 0.09' # no days!
    days = 0
    hours = 0
    minutes = 0
    # extract days, hours, and minutes
    uptime_pattern = re.compile(r"up\s+(\d+)\s+days?,\s+(\d+):(\d+)")
    match = uptime_pattern.search(output)
    if match:
        days = int(match.group(1))
        hours = int(match.group(2))
        minutes = int(match.group(3))
    else:
        uptime_pattern = re.compile(r"up\s+(\d+)\s+days?,\s+(\d+)\s+min")
        match = uptime_pattern.search(output)
        if match:
            days = int(match.group(1))
            minutes = int(match.group(2))
        else:
            uptime_pattern = re.compile(r"up\s+(\d+)\s+hours?,\s+(\d+)\s+mins")
            match = uptime_pattern.search(output)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
            else:
                logging.error(f'No match on uptime re; "output" was: {output}')
    # Calculate uptime in days, hours, and minutes
    total_uptime = timedelta(days=days, hours=hours, minutes=minutes)
    return total_uptime

def check_logged_in_users():
    users = run_command("who -m") # with -m should show SSH and not WinSCP users
    if len(users) > 0:
        logging.info(f'who -m returned: {users}')
        return True
    return False

def check_web_server_activity():
    """ Checks for active web server connections; Apache on port 80 or 443. """
    connections = run_command("sudo ss -tuln | grep -E ':80|:443'")
    # if just 'listen' skip/ignore as cause to not reboot
    conn_lines = connections.split('\n')
    for line in conn_lines:
        if (len(line) > 3) and ('LISTEN' not in line):
            logging.info(f"sudo ss -tuln | grep ':80\\|:443' returned: {connections}")
            return True
    return False

def check_open_files():
    open_files = run_command("lsof /var/www/")
    if len(open_files) > 0:
        logging.info(f"lsof /var/www/ returned: {open_files}")
        return True
    return False

def can_reboot():
    if check_logged_in_users():
        logging.warning(f'Users are currently logged in. Reboot is not safe.')
        return False
    if check_web_server_activity():
        logging.warning(f'Web server is active. Reboot is not safe.')
        return False
    if check_open_files():
        logging.warning(f'There are open files in the web server directory. Reboot is not safe.')
        return False
    return True

def force_reboot():
    """ Run the 'reboot' command """
    if can_reboot():
        logging.info(f'Rebooting system...')
        run_command('sudo reboot')
    else:
        logging.warning("Reboot canceled due to active users or processes; should try again next crontab run.")

def main():
    runningas = run_command("whoami")
    logging.info(f'Running {__file__} as: {runningas[0:-1]}')
    
    # restart section
    flag_path = os.path.dirname(log_path) + '/apache_reload_needed'
    if os.path.exists(flag_path):
        run_command("sudo systemctl reload apache2")
        run_command(f"sudo rm {flag_path}")
    # Note: 'apache_reload_needed' will (when needed) be created by 'copy_github_to_local.py'
    
    # update section
    upgradable_packages = get_upgradable_packages()
    if not upgradable_packages:
        logging.info(f'No upgradable package right now.')
    else:
        skipped_list = ''
        for package in upgradable_packages:
            last_update_date = get_last_update_date(package)
            if last_update_date:
                if last_update_date < some_days_ago:
                    upgrade_package(package, last_update_date)
                else:
                    # print(f"{package} last updated on {last_update_date}, skipping as less than {days_delay} days old.")
                    skipped_list += f'{package} updated {last_update_date}, \n'
            else:
                logging.error(f'Could not retrieve changelog date for package "{package}".')
                logging.error(f'Need to figure out what was listed and tune "date_pattern" to deal with it.')
        if skipped_list:
            logging.info(f'Note: Skipped: \n{skipped_list}')
        time.sleep(5 * 60) # 5 min pause for updates to settle...
    
    # reboot section
    reboot_file = "/var/run/reboot-required" # on Ubuntu
    if os.path.isfile(reboot_file):
        logging.info(f'Reboot needed per "{reboot_file}".')
        force_reboot()
    else:
        uptime = get_uptime()
        if uptime:
            logging.info(f'Uptime is {uptime}.')
            if uptime > timedelta(days=days_force_reboot):
                logging.info(f'Should reboot due to no reboot in {uptime} (greater than {days_force_reboot} days).')
                force_reboot()
            else:
                logging.info(f'Not rebooting as not required and uptime ({uptime}) less than {days_force_reboot} days.')
        else:
            logging.error(f'Unable to get uptime. (Not rebooting.)')
    logging.info(f'Done run of {os.path.abspath(__file__)}\n')

if __name__ == "__main__":
    main()
