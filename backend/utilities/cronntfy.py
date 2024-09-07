#!/usr/bin/env python

# Script to test end to end: cron --> python script --> console and logging and ntfy
# v1.10

import datetime
import requests
import logging
import socket

ntfypost = True
titletest = "cronz notify; Enshittification Metrics droplet live!"

def GetMachineID():
    # hostname, or last four of hostname if more than 10 chars
    hostn = socket.gethostname()
    l = int( len(hostn) )
    if l > 10: hostn = hostn[l-4:l]
    return hostn

def main():
    logging.basicConfig(level=logging.INFO, 
                        filename='/home/bsea/cronz.log', 
                        filemode='a', 
                        format='%(asctime)s -%(levelname)s - %(message)s'
    )
    hostn = GetMachineID()
    alertmsgt = f'{hostn} {titletest}'
    alertmsgb = str( datetime.datetime.now() )
    lenminusfour = len(alertmsgb) - 4
    alertmsgb = alertmsgb[0:lenminusfour] # truncate off 100s of seconds and beyond
    print(f'{alertmsgt}; print to console. {alertmsgb}')
    logging.info(f'{alertmsgt}; logging to log. {alertmsgb}')
    if ntfypost: requests.post('https://ntfy.sh/000ntfy000topic000backup000', 
        headers={'Title' : alertmsgt}, data=(alertmsgb))

if __name__ == '__main__':
    main()
