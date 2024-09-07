#!/usr/bin/env python

import os
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/var/www/em/'):
    mode = 'prod'
    logpath = '/var/www/em/log.log'
else:
    mode = 'dev'
    logpath = './log.log'

import logging
logging.basicConfig(level = logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

from app import app, db
from app.forms import EntityAddForm, EntityEditForm, NewsForm, ArtForm, ReferencesForm, SelectForm, SelectAddForm
from app.models import Entity, News, Art, References
from flask import render_template, redirect, url_for, flash, request


# live prod routes

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', 
                           mode = mode)


@app.route('/rankings')
def rankings():
    entities = Entity.query.all()
    # sort by: Alphabetically ~ by Stage ~ by Age
    # Filter by Category Type: All, Social, Cloud
    return render_template('rankings.html', 
                           entities = entities,
                           mode = mode)


@app.route('/news')
def news():
    news = News.query.all()
    return render_template('news.html', 
                           news = news,
                           mode = mode)


@app.route('/art')
def art():
    art = Art.query.all()
    return render_template('art.html', 
                           art = art,
                           mode = mode)


@app.route('/references')
def references():
    references = References.query.all()
    return render_template('references.html', 
                           references = references,
                           mode = mode)


@app.route('/about')
def about():
    return render_template('about.html',
                           mode = mode)

