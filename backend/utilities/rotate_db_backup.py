#!/usr/bin/env python

# script to back up em.db and rotate it; stores local in same directory

import os
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em/'):
    mode = 'prod'
    workingpath = '/var/www/em/app/instance/'
else:
    mode = 'dev'
    workingpath = '/home/leet/EnshittificationMetrics/www/app/instance/'
logging.basicConfig(level = logging.INFO,
                    filename = workingpath + 'db_backup.log',
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

import shutil
from datetime import datetime
from pathlib import Path

logging.info(f'Starting rotate_db_backup.py')
current_date = datetime.now()
date = current_date.strftime("%Y-%m-%d")
dom = current_date.strftime("%d")
curr_month = current_date.strftime("%m")
curr_year = current_date.strftime("%Y")

# copy the file along with its metadata
source = workingpath + 'em.db'
destination = workingpath + 'backup_em.db'
shutil.copy2(source, destination)

# rename backup to YYYY-MM-DD date format
current_file = destination
new_file = workingpath + date + '_em.db'
os.rename(current_file, new_file)
logging.info(f'Made backup {new_file}')

# if first of month clean up (delete) all two months ago except the first of that month
if dom == '01':
    del_month = str( ( int(curr_month) - 2) % 12 )
    if int(del_month) < 10:
        del_month = '0' + del_month
    if del_month == '00':
        del_month = '12' # If new_month is 0, it means December (12)
    if del_month == '12' or del_month == '11':
        del_year = str( int(curr_year) - 1 )
    else:
        del_year = curr_year
    for i in range(2, 32):
        file_path = Path(workingpath + del_year + '-' + del_month + '-' + str(i) + '_em.db')
        if file_path.exists():
            file_path.unlink()
            logging.info(f'Deleted {file_path}')

logging.info(f'Completed rotate_db_backup.py')
