#!/usr/bin/env python

"""
Backs up (rotates) em.db; stores locally in same directory.
Backups in YYYY-MM-DD date format.
At first of month deletes all two months ago except the first of that month.
"""

import os
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em/'):
    workingpath = '/var/www/em/app/instance/'
else:
    workingpath = '/home/leet/EnshittificationMetrics/www/app/instance/'
logging.basicConfig(level = logging.INFO,
                    filename = workingpath + 'db_backup.log',
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

import shutil
from datetime import datetime
from pathlib import Path

# logging.info(f'Starting rotate_db_backup.py') # unneeded cluttery log entry
current_date = datetime.now()
date = current_date.strftime("%Y-%m-%d")
dom = current_date.strftime("%d")
curr_month = current_date.strftime("%m")
curr_year = current_date.strftime("%Y")

# copy the file along with its metadata
# rename backup to YYYY-MM-DD date format
source = workingpath + 'em.db'
destination = workingpath + 'backup_em.db'
current_file = destination
new_file = workingpath + date + '_em.db'
try:
    shutil.copy2(source, destination)
    os.rename(current_file, new_file)
    logging.info(f'Made backup {new_file}')
except Exception as e:
    logging.error(f'Unable to make backup {new_file}; error {e}')

# if first of month clean up (delete) all two months ago except the first of that month
if dom == '01':
    del_month = str( ( int(curr_month) - 2) % 12 )
    if int(del_month) < 10:
        del_month = '0' + del_month
    if del_month == '00':
        del_month = '12' # If new_month is 0, it means December (12)
    if del_month == '12' or del_month == '11':
        del_year = str( int(curr_year) - 1 ) # If Dec or Nov these are last year
    else:
        del_year = curr_year
    for i in range(2, 32):
        if i > 9:
            double_digit_day_str = str(i)
        else:
            double_digit_day_str = '0' + str(i)
        file_path = Path(workingpath + del_year + '-' + del_month + '-' + double_digit_day_str + '_em.db')
        if file_path.exists():
            try:
                file_path.unlink()
                logging.info(f'Deleted {file_path}')
            except Exception as e:
                logging.error(f'Unable to delete {file_path}; error {e}')

logging.info(f'Completed rotate_db_backup.py\n') # new line for clean space (except if crashes)
