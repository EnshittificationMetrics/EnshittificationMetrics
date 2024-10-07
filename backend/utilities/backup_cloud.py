#!/usr/bin/env python

# backup function - cloud instance to on-prem filesystem
# backup is live/prod config files, database(s), crontab, .env(s), and logs
# all else to rebuild or move is on GitHub (steps in tech_notes.md) and new cloud OS
# requires SSH key-based authentication between the on-prem server and the cloud server to avoid needing a password
# triggered by cronjob

import subprocess

local_backup_path = '/home/leet/EnshittificationMetrics/backups/em02/'
private_key_pathfile = '~/.ssh/id_rsa_rsync'
username = 'root'
cloud_server_name = '<IP>'

def run_rsync(source, destination):
    try:
        result = subprocess.run(['rsync', '-avz', '-e', f'"ssh -i {private_key_pathfile}"', f'{username}@{cloud_server_name}{source}', destination], 
                                check=True, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running rsync: {e.stderr}")

# sample
# source = ':/path/to/file1 :/path/to/file2 '
# destination = '/path/to/destination/'
# run_rsync(source, destination)
# rsync -avz -e "ssh -i /path/to/private/key" user@cloud-server:/path/to/file1 :/path/to/file2 /path/to/on-prem/backup/
# rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress /root/bigfile.txt 198.211.117.129:/root/ 
# rsync -avPz -e ssh /src/ user@remote:/path/to/dst
# rsync -avz -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" --progress /home/ubuntu/data.txt username@44.43.32.21:/home/ubuntu
# rsync -av -e 'ssh -i ~/.ssh/id_rsa_rsync' local/files* server:/remote/path/

# test (index.html)
source = ':/var/www/em/index.html '
destination = local_backup_path
run_rsync(source, destination)

# rsync -avz -e "ssh -i /media/leet/1TB-USB/NATback/share/_DropBox_SYNC/_stuff/_Finances/_ENC/one_drop_01.ppk root@143.198.73.217:/var/www/em/index.html /home/leet/EnshittificationMetrics/backups/em02/

# backup
source = ':/etc/apache2/apache2.conf ' \
         ':/etc/apache2/sites-available/em-le-ssl.conf ' \
         ':/etc/apache2/sites-available/em.conf ' \
         ':/etc/fail2ban/jail.local ' \
         ':/etc/logrotate.d/enshittification-metrics ' \
         ':/var/spool/cron/crontabs/bsea ' \
         ':/var/www/em/instance/em.db ' \
         ':/var/www/em/middleapp.wsgi '
destination = local_backup_path
run_rsync(source, destination)

# .env-s
### encrypt these!
# source = ':/home/bsea/em/.env '
# destination = local_backup_path + 'env/backend/'
# run_rsync(source, destination)
# source = ':/var/www/em/.env '
# destination = local_backup_path + 'env/www/'
# run_rsync(source, destination)

# logs
source = ':/home/bsea/em/scrape.log ' \
         ':/home/bsea/em/scrape.log.1 ' \
         ':/home/bsea/em/utilities/cronz.log ' \
         ':/home/bsea/em/utilities/cronz.log.1 ' \
         ':/home/bsea/em/utilities/delayed_upgrades.log ' \
         ':/home/bsea/em/utilities/delayed_upgrades.log.1 ' \
         ':/home/bsea/em/utilities/EM_github_pull.log ' \
         ':/home/bsea/em/utilities/EM_github_pull.log.1 ' \
         ':/var/www/em/app/instance/db_backup.log ' \
         ':/var/www/em/app/instance/db_backup.log.1 ' \
         ':/var/www/em/log.log ' \
         ':/var/www/em/log.log.1 '
destination = local_backup_path + 'logs/'
run_rsync(source, destination)

