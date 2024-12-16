#!/usr/bin/env python
""" list entities to add, one per line, as string item_list_string; except as duplicate, should add blank entity to DB """

print(f'Starting script')

import os
import sys
import logging

script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em/'):
    mode = 'prod'
    sys.path.append('/var/www/em')
    logpath = '/home/bsea/em/utilities/populate_list.log'
else: # path is likely /home/leet/EnshittificationMetrics/backend/
    mode = 'dev'
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
    logpath = './populate_list.log'

logging.basicConfig(level = logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

import re
from app import app, db
from app.models import Entity
from sqlalchemy.exc import IntegrityError

# list entities to add, one per line, just below as string
item_list_string = """
"""

item_list = item_list_string.splitlines()

with app.app_context():
    for item in item_list:
        if item == '' or item =='\n':
            continue
        try:
            entity = Entity(status        = 'potential', 
                            name          = item, 
                            stage_current = 2, 
                            stage_history = [], 
                            stage_EM4view = 2, 
                            date_started  = '', 
                            date_ended    = '', 
                            summary       = '', 
                            corp_fam      = '', 
                            category      = '')
            db.session.add(entity)
            db.session.commit()
            logging.info(f'Added entity: {item}')
            print       (f'Added entity: {item}')
        except IntegrityError as e:
            # Catch SQLAlchemy's IntegrityError (specific error for UNIQUE constraint)
            logging.info(f'(Likely entity "{item}" already exists in DB.) IntegrityError caught: {e.orig}')
            print       (f'(Likely entity "{item}" already exists in DB.) IntegrityError caught: {e.orig}')
            db.session.rollback()
        except Exception as e:
            logging.info(f'(For item "{item}".) An unexpected error occurred: {e}')
            print       (f'(For item "{item}".) An unexpected error occurred: {e}')
            db.session.rollback()

print(f'Completed script')

# AdBlock Plus
# Adobe
# AOL
# Apple
# Arm
# Asus
# Atari
# Azure
# Best Buy
# Bitchute
# BitTorrent
# Boeing 
# Boring Co
# Broadcom 
# buymeacoffee.com
# Cara
# Cloudflare
# Craig's List
# despair.com
# Dice
# Downdector.com
# DuckDuckGo
# EA
# eBay
# figma
# Fitbit
# Fiverr
# Ghostery
# Github
# Grok
# Grokster
# Groq
# gumloop
# HackerNews
# Happiest Baby
# icanhazip.com
# ICQ
# Instagram
# Intel
# IRC
# KaZaa
# LG
# LimeWire
# LinkedIn
# Lyft
# medium.com
# Meta
# Microsoft
# Mistral
# Morpheus
# MySpace
# Napster
# Neuralink
# NPR
# Nvidia 
# Oculus
# OGS
# OpenAI
# Oura
# PayPal
# Peloton
# Pinterest
# PostgreSQL
# Procreate
# Pwned
# reCAPTCHA 
# Ring
# Roku
# Rumble
# Samsung
# scamadviser.com
# Shipt
# Signal
# Skype
# Slashdot
# Snowflake
# Sonos
# StackOverflow
# Telegraph
# TikTok
# uBlock Origin
# United Airlines
# Upwork
# Valve
# VMWare
# Waymo
# WhatsApp
# Whole Foods
# Yahoo
