#!/usr/bin/env python

import sys
import socket
import logging

sys.path.insert(0, '/var/www/em')

activate_this = '/home/bsea/.local/share/virtualenvs/em-eHcyI4u8/bin/activate_this.py'

with open(activate_this) as file_:
	exec(file_.read(), dict(__file__=activate_this))

from EnshittificationMetrics import app as application
