#!/usr/bin/env python

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
from flask_login import LoginManager


app = Flask(__name__)
script_directory = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(script_directory, 'instance', 'em.db')
load_dotenv(os.path.join(script_directory, '..', '.env')) # Load the .env file located one directory up
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'

### Removed due to complexity. Setup as cron job. (Fails horribly as root cron, setup as user cron seems to work.)
### Tried @app.before_first_request but it is depreciated, tried @app.before_request but it runs on every route click and needs
### flask "g" to kluge it to run just once however "g" is limited to a weird sub-session, tried raw threading from __init__ (so as to run just once) 
### but this fails due to circular imports (app/__init__.py calls slashdot_scrape.py which calls semantics.py which calls app/__init__.py).
### import threading
### import time
### from scrape.slashdot_scrape import process_slashdot_site, parse_slashdot_posts
### def periodic():
###     while True:
###         logging.info(f'Running periodic func!!!')
###         process_slashdot_site()
###         parse_slashdot_posts()
###         time.sleep(3600)
### 
### thread = threading.Thread(target=periodic)
### thread.daemon = True  # Ensures periodic will run as a separate (parallel) thread, but also will exit when the main program exits
### thread.start()


from app import routes, models
# down here in this order to avoid circular import

