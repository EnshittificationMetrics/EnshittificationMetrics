#!/usr/bin/env python

"""
To be manually run when we want to push dev /home/leet/EnshittificationMetrics 
(already manually pushed to https://github.com/zake8/EnshittificationMetrics)
to 
prod https://github.com/EnshittificationMetrics/EnshittificationMetrics
(which is then auto pulled to prod web-server by another process).

Copies /home/leet/EnshittificationMetrics to /home/leet/github, then,
git add, commit, push to https://github.com/EnshittificationMetrics/EnshittificationMetrics.

ISSUE: Does not clean up or deal with renamed or deleted files!

To work from repo needs some authentication via Personal Access Token (PAT) for https...
"""

import logging
logging.basicConfig(level = logging.INFO,
                    filename = './EM_github_push.log',
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')
import subprocess
import os
import shutil

def main():
    """ Files and dirs to skip 'hardcoded' here. """
    routes_prod_fix = False # renames routes_prod.py, was True till 9/26/24 when set to False
    source_dir = '/home/leet/EnshittificationMetrics'
    clone_dir = '/home/leet/github'
    dir_to_skip = [
        '.git', # don't copy .git as this would cause many issues!!!
        '__pycache__', # don't copy pycache as this could cause problems
        ]
    files_to_skip = [
        # same as .gitignore
        '.db',
        '.env',
        '.log',
        'Pipfile.lock',
        'slashdot_data.txt',
        # a few files we _don't_ want on public prod github
        'dev_plan.md',
        'EM_biz.ods',
        'tech_notes_dev.md', # had all in tech_notes.md, broke out into tech_notes.md and tech_notes_dev.md OCT '24
        # 'copy_local_to_github.py', # actually okay as backup
        ]
    logging.info(f'Starting GitHub {clone_dir} sync and push.')
    place_files(source_dir, clone_dir, dir_to_skip, files_to_skip)
    if routes_prod_fix:
        tweak(clone_dir)
    if check_for_commitable(clone_dir):
        add_commit_push(clone_dir)
    logging.info(f'Completed.\n')

def place_files(src, dst, dir_to_skip, files_to_skip):
    files_copied = 0
    for dirpath, dirnames, filenames in os.walk(src):
        skip_outer_loop = False
        relative_path = os.path.relpath(dirpath, src)
        for name in dir_to_skip:
            if name in relative_path:
                skip_outer_loop = True
        if skip_outer_loop:
            continue
        dst_dirpath = os.path.join(dst, relative_path)
        if not os.path.exists(dst_dirpath): # Create directories in the destination if they don't exist
            os.makedirs(dst_dirpath)
            logging.info(f'Made directory {dst_dirpath}') # should never be triggered, unless new dir is actually added
        for filename in filenames: # Copy files, overwriting if they already exist in the destination
            skip_outer_loop = False
            for name in files_to_skip:
                if name in filename:
                    skip_outer_loop = True
            if skip_outer_loop:
                continue
            src_file = os.path.join(dirpath, filename)
            dst_file = os.path.join(dst_dirpath, filename)
            # copy only if doesn't exist or newer
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)  # copy2 preserves metadata (e.g., timestamps)
                # print(f'Copied new file {dst_file}') # for testing
                logging.info(f'Copied new file {dst_file}')
                files_copied += 1
            else:
                src_mtime = os.path.getmtime(src_file) # Source file modification time
                dst_mtime = os.path.getmtime(dst_file) # Destination file modification time
                if src_mtime > dst_mtime:
                    shutil.copy2(src_file, dst_file) # copy2 preserves metadata (e.g., timestamps)
                    # print(f'Copied updated file {dst_file}') # for testing
                    logging.info(f'Copied updated file {dst_file}')
                    files_copied += 1
    logging.info(f'Copied {files_copied} files.')

def tweak(dir):
    """ Renames {dir}/www/app/routes_prod.py to routes.py """
    old_path_file = os.path.join(dir, 'www/app/routes_prod.py')
    path_file = os.path.join(dir, 'www/app/routes.py')
    if os.path.exists(path_file):
        if os.path.exists(old_path_file):
            os.remove(path_file)
            os.rename(old_path_file, path_file)
            logging.info(f'deleted {path_file} and renamed {old_path_file} to {path_file}')
        else:
            logging.error(f'{old_path_file} does not exist to rename')
    else:
        logging.error(f'{path_file} does not exist to delete')

def check_for_commitable(repo_dir):
    result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=repo_dir)
    if "Changes not staged for commit" in result.stdout:
        logging.info(f'In {repo_dir} git status indicates changes available to commit.')
        return True
    else:
        logging.info(f'In {repo_dir} git status indicates nothing to commit.')
        return False

def add_commit_push(repo_dir):
    try:
        subprocess.run(["git", "add", "."], check=True, cwd=repo_dir)
        subprocess.run(["git", "commit", "-m", '"updates"'], check=True, cwd=repo_dir)
        subprocess.run(["git", "push", "EnshittificationMetrics"], check=True, cwd=repo_dir)
        logging.info(f'Git added commited and pushed updates in {repo_dir}.')
    except subprocess.CalledProcessError as e:
        logging.error(f'Error during add or commit or push: {e}')

if __name__ == '__main__':
    main()
