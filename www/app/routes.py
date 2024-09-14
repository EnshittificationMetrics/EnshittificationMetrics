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
from app.forms import LoginForm, RegistrationForm, EditProfileForm, ChangePasswordForm
from app.models import Entity, News, Art, References, User
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
# https://flask-login.readthedocs.io/en/latest/#
from flask_simple_captcha import CAPTCHA
from werkzeug.security import generate_password_hash, check_password_hash
import sqlalchemy as sa

CAPTCHA_CONFIG = {
    'SECRET_CAPTCHA_KEY': 'LONG_KEY',
    'CAPTCHA_LENGTH': 9,
    'CAPTCHA_DIGITS': True,
    'EXPIRE_SECONDS': 600,
    'CAPTCHA_IMG_FORMAT': 'JPEG',
    'EXCLUDE_VISUALLY_SIMILAR': True,
    'BACKGROUND_COLOR': (95, 87, 110), 
    'TEXT_COLOR': (232, 221, 245), 
    'ONLY_UPPERCASE': True, 
    }
SIMPLE_CAPTCHA = CAPTCHA(config=CAPTCHA_CONFIG)
app = SIMPLE_CAPTCHA.init_app(app)
# https://github.com/cc-d/flask-simple-captcha


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


# Authentication routes

@app.route('/captcha_test', methods=['GET','POST'])
def captcha_test():
    if request.method == 'GET':
        new_captcha_dict = SIMPLE_CAPTCHA.create()
        return render_template('captcha_test.html', captcha=new_captcha_dict)
    if request.method == 'POST':
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            return 'Success!'
        else:
            return 'Failed CAPTCHA...'


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            return render_template('login.html', 
                                    title='Sign In (c_fail)',
                                    form=form,
                                    captcha=new_captcha_dict)
        else:
            user = db.session.scalar(
                sa.select(User).where(User.username == form.username.data))
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            logging.info(f'=*=*=*> User "{current_user.username}" logged in.')
            if current_user.role == 'disabled':
                logging.info(f'=*=*=*> Disabled user "{current_user.username}" as their role is "{current_user.role}".')
                logout_user()
                flash('Unable to login.')
                return redirect(url_for('login'))
            next_page = request.args.get('next')
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('index')
            return redirect(next_page)
    elif request.method == 'GET':
        return render_template('login.html', 
                                title='Sign In (get)',
                                form=form,
                                captcha=new_captcha_dict)
    return render_template('login.html', 
                            title='Sign In (return)', 
                            form=form,
                            captcha=new_captcha_dict)


@app.route('/guest_sign_in')
def guest_sign_in():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        form = LoginForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    user = db.session.scalar(
        sa.select(User).where(User.username == 'Guest'))
    if user is None:
        flash('Invalid username')
        return redirect(url_for('login'))
    login_user(user, remember=False)
    logging.info(f'=*=*=*> User "{current_user.username}" logged in.')
    if current_user.role == 'disabled':
        logging.info(f'=*=*=*> Disabled user "{current_user.username}" as their role is "{current_user.role}".')
        logout_user()
        flash('Unable to login.')
        return redirect(url_for('login'))
    next_page = request.args.get('next')
    if not next_page or urlsplit(next_page).netloc != '':
        next_page = url_for('index')
    return redirect(next_page)


@app.route('/logout')
def logout():
    if current_user.is_anonymous:
        logging.info(f'=*=*=*> Non logged in user (unknown) logging out.')
        flash('Must be logged in to logout...')
    else:
        logging.info(f'=*=*=*> User "{current_user.username}" logging out.')
        # was getting AttributeError: 'AnonymousUserMixin' object has no attribute 'username', so added is_anonymous logic...
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            return render_template('register.html', 
                                    title='Register (c_fail)',
                                    form=form,
                                    captcha=new_captcha_dict)
        else:
            set_role = 'regular'
            email_value = form.email.data
            if email_value.endswith("@vingtsunsito.com"): ### temp test, re-code once email verification is in place
                set_role = 'vts'
            user = User(username=form.username.data, 
                        email=form.email.data, 
                        full_name=form.full_name.data, 
                        phone_number=form.phone_number.data,
                        role=set_role)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Congratulations, you are now a registered user!')
            logging.info(f'=*=*=*> New user registered! full_name="{form.full_name.data}" username="{form.username.data}" email="{form.email.data}" phone #="{form.phone_number.data}"')
            return redirect(url_for('login'))
    elif request.method == 'GET':
        return render_template('register.html', 
                                title='Register (get)',
                                form=form, 
                                captcha=new_captcha_dict)
    return render_template('register.html', 
                            title='Register (return)',
                            form=form,
                            captcha=new_captcha_dict)


@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    return render_template('user.html', 
                            title=f'{username}',
                            user=user)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            return render_template('edit_profile.html', 
                                    title='Edit Profile (c_fail)',
                                    form=form, 
                                    captcha=new_captcha_dict)
        elif current_user.role == 'guest':
            flash('Unable to modify guest account.')
            return render_template('edit_profile.html', 
                                    title='Edit Profile (g_fail)',
                                    form=form, 
                                    captcha=new_captcha_dict)
        else:
            current_user.username     = form.username.data
            current_user.email        = form.email.data
            current_user.full_name    = form.full_name.data
            current_user.phone_number = form.phone_number.data
            try:
                db.session.commit()
            except exc.IntegrityError as e:
                session.rollback()
                flash(f'Unable to modify due to IntegrityError ({e}); username or email may have been used already.')
                return render_template('edit_profile.html', 
                                        title='Edit Profile (i_fail)',
                                        form=form, 
                                        captcha=new_captcha_dict)
            except exc.SQLAlchemyError as e:  # Generic SQLAlchemy error
                session.rollback()
                flash(f'Unable to modify due to SQLAlchemyError ({e}); username or email may have been used already.')
                return render_template('edit_profile.html', 
                                        title='Edit Profile (i_fail)',
                                        form=form, 
                                        captcha=new_captcha_dict)
            except Exception as e:
                flash(f'Unable to modify due to error ({e}).')
                return render_template('edit_profile.html', 
                                        title='Edit Profile (i_fail)',
                                        form=form, 
                                        captcha=new_captcha_dict)
            flash('Your changes have been saved.')
            logging.info(f'=*=*=*> User "{current_user.username}" edited profile')
            return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        return render_template('edit_profile.html', 
                                title='Edit Profile (get)',
                                form=form, 
                                captcha=new_captcha_dict)
    return render_template('edit_profile.html', 
                            title='Edit Profile (return)',
                            form=form, 
                            captcha=new_captcha_dict)


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            return render_template('change_password.html', 
                                    title='Change Password (c_fail)',
                                    form=form, 
                                    captcha=new_captcha_dict)
        else:
            if not check_password_hash(current_user.password_hash, form.password.data):
                flash('Incorrect current/old password - NO changes saved.')
                return redirect(url_for('change_password'))
            elif current_user.role == 'guest':
                flash('Unable to modify guest account - NO changes saved.')
                return redirect(url_for('change_password'))
            else:
                current_user.password_hash = generate_password_hash(form.new_password.data)
                db.session.commit()
                flash('Your changes have been saved.')
                logging.info(f'=*=*=*> User "{current_user.username}" changed password')
                return redirect(url_for('change_password'))
    elif request.method == 'GET':
        return render_template('change_password.html', 
                                title='Change Password (get)',
                                form=form, 
                                captcha=new_captcha_dict)
    return render_template('change_password.html', 
                            title='Change Password (return)',
                            form=form, 
                            captcha=new_captcha_dict)

