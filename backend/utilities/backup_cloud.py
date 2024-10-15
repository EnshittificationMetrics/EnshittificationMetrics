#!/usr/bin/env python

"""
Performs backup functions; cloud instance to on-prem filesystem.
Backup is of live/prod config files, database(s), crontab (nope), .env(s)(nope), and logs.
All else needed to rebuild or move is a new cloud OS and files on GitHub (steps in tech_notes.md).
This requires password-less SSH key-based authentication between the on-prem server and the cloud server.
Triggered by cronjob.
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='/home/leet/EnshittificationMetrics/backend/.env') # hardcoded...

local_backup_path = '/media/leet/1TB-USB/EM-backup/'
username = os.getenv('CLOUD_USER') # user on remote to ssh into as
cloud_server_name = 'enshittificationmetrics.com'

import logging
logging.basicConfig(level = logging.INFO,
                    filename = local_backup_path + 'backup_cloud.log',
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

import subprocess

notes_on_ssh_key = """
On on-prem "machine D": ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "remote rsync key - Oct 2024"
Copy (via multitab WinSCP) contents of ~/.ssh/id_rsa.pub to ~/.ssh/authorized_keys of user on remote/cloud "machine P".
"machine D" will ssh into "machine P"; private key on "D" used to authenticate, public key on "P" validates key.
Public key must be correctly added to the authorized_keys file of the user on machine "P" that you wish to connect as.
rsync user@P:/path/to/file /local/destination/on/D # Pull from "P" to "D"
rsync /path/to/file user@P:/remote/destination/on/P # Push from "D" to "P"
Need to run first rsync on cli so as to confirm permanently adding to known hosts.
"""

backup_list = [
        # backup
        ['/etc/apache2/apache2.conf', local_backup_path], 
        ['/etc/apache2/sites-available/em-le-ssl.conf', local_backup_path], 
        ['/etc/apache2/sites-available/em.conf', local_backup_path], 
        ['/etc/fail2ban/jail.local', local_backup_path], 
        ['/etc/logrotate.d/enshittification-metrics', local_backup_path], 
        # ['/var/spool/cron/crontabs/bsea', local_backup_path], ### no rights to read this one
        ['/var/www/em/app/instance/em.db', local_backup_path], 
        ['/var/www/em/middleapp.wsgi', local_backup_path], 
        # logs
        ['/home/bsea/em/scrape.log', local_backup_path + 'logs/'], 
        ['/home/bsea/em/scrape.log.1', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/cronz.log', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/cronz.log.1', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/delayed_upgrades.log', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/delayed_upgrades.log.1', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/EM_github_pull.log', local_backup_path + 'logs/'], 
        ['/home/bsea/em/utilities/EM_github_pull.log.1', local_backup_path + 'logs/'], 
        ['/var/www/em/app/instance/db_backup.log', local_backup_path + 'logs/'], 
        ['/var/www/em/app/instance/db_backup.log.1', local_backup_path + 'logs/'], 
        ['/var/www/em/log.log', local_backup_path + 'logs/'], 
        ['/var/www/em/log.log.1', local_backup_path + 'logs/'], 
        # .env-s ### encrypt or obfuscate these!
        # ['/home/bsea/em/.env', local_backup_path + 'env/backend/'], 
        # ['/var/www/em/.env', local_backup_path + 'env/www/'], 
        ]

def run_rsync(source, destination):
    try:
        result = subprocess.run(['rsync', '-avz', f'{username}@{cloud_server_name}:{source}', destination], 
                                check=True, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                text=True)
        # logging.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running rsync: {e.stderr}")

notes_rsync = """
-a   archive mode
-v   increase verbosity
-z   compress file data during the transfer
"""

# test (index.html)
# source = '/var/www/em/index.html'
# destination = local_backup_path
# run_rsync(source, destination)

logging.info(f'Starting selected backup of {cloud_server_name}')
for backup_item in backup_list:
    source, destination = backup_item
    logging.info(f'rsync {source} to {destination}')
    run_rsync(source, destination)
logging.info(f'Finished run of {__file__}\n')

archive = """
rsync -avz -e "ssh -i /path/to/private/key" user@cloud-server:/path/to/file1 :/path/to/file2 /path/to/on-prem/backup/
rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress /root/bigfile.txt <IP>:/root/ 
rsync -avPz -e ssh /src/ user@remote:/path/to/dst
rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress /home/ubuntu/data.txt username@<IP>:/home/ubuntu
rsync -av -e 'ssh -i ~/.ssh/id_rsa_rsync' local/files* server:/remote/path/
rsync -avz -e "ssh -i /path/to/private/key root@<IP>:/var/www/em/index.html /path/to/on-prem/backup/
subprocess.run(['rsync', '-avz', '-e', f'"ssh -i {private_key_pathfile}"', f'{username}@{cloud_server_name}{source}', destination], 
"""
