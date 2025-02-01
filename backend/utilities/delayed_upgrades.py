#!/usr/bin/env python

"""
Performs automated OS maintenance!
Upgrade only the packages whose updates are more than "days_delay" days old.
Reboots (safely) if required, or if no reboot in last "days_force_reboot" days.
"""

crontab = """30 3 * * * /usr/bin/python3 /home/leet/EnshittificationMetrics/backend/utilities/delayed_upgrades.py""" # dev as root

crontab = """30 10 * * *     /usr/bin/python3 /home/bsea/em/utilities/delayed_upgrades.py     >> /home/bsea/em/utilities/cron_issues.log 2>&1""" # prod as bsea; PT = UTC - 7.5 so 10 UTC = 03:00 or 04:00 PT

if __file__.startswith('/home/bsea/em/'):
    log_path = '/home/bsea/em/utilities/delayed_upgrades.log' # EM prod
    days_delay = 9
    days_force_reboot = 36
    pipfile_locs = ["/home/bsea/em", "/var/www/em"]
else:
    log_path = '/home/leet/EnshittificationMetrics/backend/utilities/delayed_upgrades.log' # EM dev or CLI (testing)
    days_delay = 8
    days_force_reboot = 28
    pipfile_locs = ["/home/leet/EnshittificationMetrics/backend", "/home/leet/EnshittificationMetrics/www"]

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
import requests

today = datetime.date.today()
some_days_ago = today - datetime.timedelta(days=days_delay)


def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # check=True ensures completing successfully before proceeding
    except subprocess.CalledProcessError as e:
        logging.error(f'Error during subprocess.run({command}) attempt: {e}')
        return "" # works on all cases in this program while returning None fails
    return result.stdout


def get_upgradable_packages():
    run_command('sudo apt update')
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
    result = run_command(f'sudo apt install --only-upgrade -y {package_name}')
    logging.info(f'Upgrading {package_name}... Updated {last_update_date}. {result.stderr}')
    # result.stderr to check for errors; result.stdout to check what is happening when installing


def get_uptime():
    """ Runs the 'uptime' command, captures the output, converts to days, hours, and minutes. """
    output = run_command('uptime')
    # ex: ' 11:44:27 up 7 days,  8:13,  2 users,  load average: 0.16, 0.20, 0.17'
    # ex: ' 03:35:22 up 7 days, 4 min,  2 users,  load average: 0.22, 0.31, 0.27' # no hours!
    # ex: ' 12:34:56 up 5 hours, 42 mins,  3 users,  load average: 0.12, 0.15, 0.09' # no days!
    # ex: ' 03:30:02 up 23:59,  1 user,  load average: 0.18, 0.15, 0.10'
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
            uptime_pattern = re.compile(r"up\s+(\d+)\s+hours?,\s+(\d+)\s+mins?")
            match = uptime_pattern.search(output)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
            else:
                uptime_pattern = re.compile(r"up\s+(\d+):(\d+),\s+")
                match = uptime_pattern.search(output)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    ### seems to work in test but not prod
                else:
                    logging.warning(f'No match on uptime re; "output" was: {output[:-1]}') # slice off CR
                    ### maybe redo if-else with a capture btwn "up" and "users?", then check for "days?", "hours?", "mins?", or ":", then parse appropriately
    # Calculate uptime in days, hours, and minutes
    total_uptime = timedelta(days=days, hours=hours, minutes=minutes)
    return total_uptime


def check_logged_in_users():
    users = run_command("who -m") # with -m should show SSH and not WinSCP users
    if len(users) > 0:
        logging.info(f'who -m returned: {users[:-1]}') # slice off CR
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
    logging.info(f'No logged in users, no web server activity, no open files; reboot should be safe.')
    return True


def force_reboot():
    """ Run the 'reboot' command """
    if can_reboot():
        logging.info(f'Rebooting system...')
        run_command('sudo reboot')
    else:
        logging.warning("Reboot canceled due to active users or processes; should try again next crontab run.")


def get_library_last_update_date(package_name):
    url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        releases = data.get("releases", {})
        # Sort releases by version in reverse order
        for version, release_info in sorted(releases.items(), key=lambda x: x[0], reverse=True):
            if release_info:  # Ensure release_info is not empty
                release_date = release_info[0]["upload_time"]
                # returns str like '2010-07-31T06:23:55' but need in datetime.date type format of "DD-MM-YYYY"
                release_date = datetime.datetime.strptime(release_date, '%Y-%m-%dT%H:%M:%S').date()
            return release_date
    else:
        logging.error(f'Failed to fetch data from pypi.org for {package_name}')
        return None


def upgrade_library_package(pipfile_loc, package_name, last_update_date):
    """ run pipenv upgrade <package> and log result """
    pipenv_return = run_command(f'cd {pipfile_loc} && pipenv upgrade {package_name}')
    pattern = r"\bSuccess\b"
    matches = re.findall(pattern, pipenv_return)
    if matches:
        logging.info(f'Upgraded {pipfile_loc}/Pipfile {package_name} (updated {last_update_date}).')
    else:
        logging.error(f'Tried to upgrade {pipfile_loc}/Pipfile {package_name} (updated {last_update_date}) - but got no success. Detail: {pipenv_return}')


def main():
    runningas = run_command("whoami")
    logging.info(f'Running {__file__} as: {runningas[0:-1]}')
    
    """ I. if needed, reload apache2 """
    flag_path = os.path.dirname(log_path) + '/apache_reload_needed'
    # 'apache_reload_needed' created by 'copy_github_to_local.py'
    if os.path.exists(flag_path):
        try:
            run_command("sudo systemctl reload apache2")
            run_command(f"sudo rm {flag_path}")
            logging.info(f'Performed systemctl reload apache2 due to {flag_path}')
        except Exception as e:
            logging.error(f'Failed systemctl reload apache2 and rm due to {flag_path}, error: {e}')
    
    """ II. if needed and old enough, apt install package_name """
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
                    skipped_list += f'{package} (updated {last_update_date}), '
            else:
                logging.error(f'Could not retrieve changelog date for package "{package}".')
                logging.error(f'Need to figure out what was listed and tune "date_pattern" to deal with it.')
        if skipped_list:
            logging.info(f'Note: Skipped: {skipped_list[:-2]}')
        print(f'sleeping 3 min')
        time.sleep(3 * 60) # 3 min pause for updates to settle...
    
    """ III. if needed and old enough, pipenv upgrade package_name """
    for pipfile_loc in pipfile_locs:
        logging.info(f'Checking {pipfile_loc}/Pipfile')
        """ run pipenv update --outdated where the Pipfile is """
        outdated_packs = run_command(f"cd {pipfile_loc} && pipenv update --outdated")
        """ parse out the package name(s) from the results, like "Package 'orjson' out-of-date: {'ver..." """
        pattern = r"Package '(.*?)' out-of-date"
        packages = re.findall(pattern, outdated_packs)
        if not packages:
            logging.info(f'No upgradable packages right now.')
        else:
            """ loop thru update-able packages """
            skipped_list = ''
            need_pipenv_lock = False
            for package in packages:
                last_update_date = get_library_last_update_date(package)
                if last_update_date:
                    if last_update_date < some_days_ago:
                        """ update package """
                        upgrade_library_package(pipfile_loc, package, last_update_date)
                        need_pipenv_lock = True
                    else:
                        skipped_list += f'{package} (updated {last_update_date}), '
                else:
                    logging.error(f'Could not retrieve changelog date for package "{package}".')
                    logging.error(f'Need to figure out what was listed and tune to deal with it.')
            """ if any upgrades done then run lock """
            if need_pipenv_lock:
                pipenv_return = run_command(f'cd {pipfile_loc} && pipenv lock')
                pattern = r"\bSuccess\b"
                matches = re.findall(pattern, pipenv_return)
                if matches:
                    logging.info(f'Ran pipenv lock.')
                else:
                    logging.info(f'Tried pipenv lock - but got no success. Detail: {pipenv_return}')
            if skipped_list:
                logging.info(f'Note: Skipped: {skipped_list[:-2]}')
            print(f'sleeping 2 min')
            time.sleep(2 * 60) # 2 min pause for updates to settle...

    """ IV. if needed, reboot """
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
            logging.warning(f'Unable to get uptime. (Not rebooting.)')
    logging.info(f'Done run of {os.path.abspath(__file__)}\n')


if __name__ == "__main__":
    main()
