#!/usr/bin/env python

# git status checks GitHub repo for changes / updates
# git pull pulls repo to clone_dir
# copies clone_dir out to dest_dir_www and dest_dir_back
### ISSUE: Need to reset dir/file owner/permissions???
### ISSUE: Need to restart/reset Apache???
### ISSUE: Does not clean up or deal with renamed or deleted files!

import logging
logging.basicConfig(level = logging.INFO,
                    filename = '/home/bsea/em/utilities/EM_github_pull.log',
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')
import subprocess
import os
import shutil

def main():
    # Define directories
    clone_dir = '/home/bsea/github'
    dest_dir_www = '/var/www/em'
    dest_dir_back = '/home/bsea/em'
    logging.info(f'Starting GitHub {clone_dir} sync and file copy to {dest_dir_www} and {dest_dir_back}.')
    if check_for_updates(clone_dir):
        fetch_and_pull(clone_dir)
        place_files(clone_dir, dest_dir_www, dest_dir_back)
    logging.info(f'Completed.')

def check_for_updates(repo_dir):
    subprocess.run(["git", "fetch"], check=True, cwd=repo_dir)
    result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=repo_dir)
    if "Your branch is behind" in result.stdout:
        logging.info(f'In {repo_dir} git fetch / status indicates updates available.')
        return True
    else:
        logging.info(f'In {repo_dir} git fetch / status indicates up to date.')
        return False

def fetch_and_pull(repo_dir):
    try:
        subprocess.run(["git", "fetch"], check=True, cwd=repo_dir) # don't really need this as just done in check_for_updates
        subprocess.run(["git", "pull"], check=True, cwd=repo_dir)
        logging.info(f'Git fetched and pulled updates in {repo_dir}.')
    except subprocess.CalledProcessError as e:
        logging.error(f'Error during fetch or pull: {e}')

def place_files(src, dest_www, dest_back):
    files_copied = 0
    for dirpath, dirnames, filenames in os.walk(src):
        if 'www' in dirpath:
            dst = dest_www
        elif 'backend' in dirpath:
            dst = dest_back
        else:
            continue # misc git related stuff we don't need to copy
        rough_relative_path = os.path.relpath(dirpath, src)
        # print(f'rough_relative_path = {rough_relative_path}') # for testing
        # split relative path, remove first part (www or backend) and rejoin back together
        path_parts = rough_relative_path.split(os.sep)
        if len(path_parts) > 1:
            relative_path = os.path.join(*path_parts[1:])
        else:
            relative_path = ''
        dst_dirpath = os.path.join(dst, relative_path)
        if not os.path.exists(dst_dirpath): # Create directories in the destination if they don't exist
            # print(f'Made directory {dst_dirpath}') # for testing
            os.makedirs(dst_dirpath)
            logging.info(f'Made directory {dst_dirpath}') # should never be triggered, unless new dir is actually added
        for filename in filenames: # Copy files, overwriting if they already exist in the destination
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

if __name__ == '__main__':
    main()
