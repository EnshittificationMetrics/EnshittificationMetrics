#!/usr/bin/env python

import os
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/var/www/em/'):
    logpath = '/var/www/em/log.log'
    my_name = 'enshittificationmetrics.com'
else:
    logpath = './log.log'
    my_name = '192.168.50.125:5000'

import logging
logging.basicConfig(level = logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format = '%(asctime)s -%(levelname)s - %(message)s')

from app import app, db
from app.forms import EntityAddForm, EntityEditForm, NewsForm, ArtForm, ReferencesForm, SelectForm, SelectAddForm
from app.forms import LoginForm, RegistrationForm, EditProfileForm, ChangePasswordForm, OtpcodeForm, SurveyNewUserForm, PasswordCheckForm
from app.models import Entity, News, Art, References, User, SurveyNewUser
from app.banners import banner_ads
from flask import render_template, redirect, url_for, flash, request, session, send_from_directory, jsonify
from flask_login import login_user, logout_user, current_user, login_required, user_loaded_from_cookie
# https://flask-login.readthedocs.io/en/latest/#
from flask_simple_captcha import CAPTCHA
from werkzeug.security import generate_password_hash, check_password_hash
import sqlalchemy as sa
from sqlalchemy import or_, asc, desc, func
import socket
# pipenv install Flask pyotp Flask-Mail
import pyotp
from flask_mail import Mail, Message
from dotenv import load_dotenv
from urllib.parse import urlsplit
import requests
import datetime
import random

load_dotenv('../.env')
hostn = socket.gethostname()

# posts on new user registrations, and on taking survey
ntfypost = True
alert_title = f'EM on {hostn} user activity'

# TOTP controls
validity_period = 90 # default 30 (seconds); validity period for TOTP object
interval_grace_period = 1 # default 0; flexibility, how many previous or future intervals (time steps) are allowed during verification

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') # secure Flask session management
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)

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
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
    random_art = Art.query.order_by(func.random()).limit(2).all()
    random_ref = References.query.order_by(func.random()).limit(2).all()
    recent_news = News.query.order_by(News.date_pub.desc()).limit(3).all()
    selected_ad = random.choice(banner_ads)
    return render_template('index.html',
                            art = random_art, 
                            references = random_ref, 
                            news = recent_news, 
                            banner = selected_ad, 
                            )

@app.route('/rankings')
def rankings():
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
    if current_user.is_anonymous:
        flash('Must be logged in to access page...')
        return render_template('anonymous.html',
                                then_next = 'rankings')
    # entities = Entity.query.all() # initial old "query"
    # SQLAlchemy queries are chained, each filter() adds to the query without overwriting it.
    # Initialize the query
    query = Entity.query
    # current_user.ranking_stat - filter - Live, Potential, Not Disabled, Disabled
    if current_user.ranking_stat.lower() == 'not disabled':
        query = query.filter(Entity.status != 'disabled')
    else:
        query = query.filter(Entity.status == current_user.ranking_stat.lower())

    # current_user.ranking_cats - filter - All, Social, Cloud, B2B, B2C, C2C, tech platform, P2P
    if current_user.ranking_cats.lower() != 'all':
        query = query.filter(or_(Entity.category.like(f"%{cat.strip()}%") for cat in current_user.ranking_cats.split(',')))

    # current_user.display_order - sort by recent first, oldest first
    if current_user.display_order.lower() == "oldest first":
        sorting_order = desc # no quotes as this is a callable
    else: # == recent first (default)
        sorting_order = asc 

    # current_user.ranking_sort - sort by Name ~ by Stage* ~ by Age
    if current_user.ranking_sort.lower() == "name":
        query = query.order_by(sorting_order(Entity.name))
    elif current_user.ranking_sort.lower() == "stage":
        if current_user.func_stage == 4: 
            query = query.order_by(sorting_order(Entity.stage_EM4view))
        else:
            query = query.order_by(sorting_order(Entity.stage_current))

    elif current_user.ranking_sort.lower() == "age":
        query = query.order_by(sorting_order(Entity.date_started))

    # Get the final results
    entities = query.all()
    selected_ad = random.choice(banner_ads)
    return render_template('rankings.html', 
                           entities = entities, 
                           banner = selected_ad)


@app.route('/entity_detail/<entname>')
@login_required
def entity_detail(entname):
    entity = db.session.scalar(sa.select(Entity).where(Entity.name == entname))
    news_ids = []
    if entity.stage_history:
        for news_item in entity.stage_history:
            if len(news_item) > 2 :
                news_ids.append(news_item[2])
    news = News.query.filter(News.id.in_(news_ids)).all()
    selected_ad = random.choice(banner_ads)
    return render_template('entity_detail.html', 
                           item = entity,
                           news = news, 
                           banner = selected_ad)


@app.route('/update-filtersort', methods=['POST'])
@login_required
def update_filtersort():
    data = request.get_json()
    if 'ranking_cats' in data:
        ### tweak from single value to multivalue
        current_user.ranking_cats = data['ranking_cats']
        db.session.commit()
        return jsonify({'status': 'success'})
    if 'ranking_sort' in data:
        current_user.ranking_sort = data['ranking_sort']
        db.session.commit()
        return jsonify({'status': 'success'})
    if 'ranking_stat' in data:
        current_user.ranking_stat = data['ranking_stat']
        db.session.commit()
        return jsonify({'status': 'success'})
    if 'display_order' in data:
        current_user.display_order = data['display_order']
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400


@app.route('/update-funcstage', methods=['POST'])
@login_required
def update_funcstage():
    data = request.get_json()
    if 'func_stage' in data:
        current_user.func_stage = data['func_stage']
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400


@app.route('/news')
def news():
    if current_user.is_anonymous:
        flash('Must be logged in to access page...')
        return render_template('anonymous.html',
                                then_next = 'news')
    # Initialize the query
    query = News.query
    
    ### # current_user.ranking_stat - filter - Live, Potential, Not Disabled, Disabled
    ### if current_user.ranking_stat.lower() == 'not disabled':
    ###     query = query.filter(Entity.status != 'disabled')
    ### else:
    ###     query = query.filter(Entity.status == current_user.ranking_stat.lower())

    ### # current_user.ranking_cats - filter - All, Social, Cloud, B2B, B2C, C2C, tech platform, P2P
    ### if current_user.ranking_cats.lower() != 'all':
    ###     query = query.filter(or_(Entity.category.like(f"%{cat.strip()}%") for cat in current_user.ranking_cats.split(',')))

    # current_user.display_order - sort by recent first, oldest first
    if current_user.display_order.lower() == "oldest first":
        sorting_order = desc # no quotes as this is a callable
    else: # == recent first (default)
        sorting_order = asc 

    # current_user.ranking_sort - sort by Name ~ by Stage* ~ by Age
    if current_user.ranking_sort.lower() == "name":
        query = query.order_by(sorting_order(News.text))
    elif current_user.ranking_sort.lower() == "stage":
        query = query.order_by(sorting_order(News.stage_int_value))
    elif current_user.ranking_sort.lower() == "age":
        query = query.order_by(sorting_order(News.date_pub))

    # Get the final results
    news = query.all()
    selected_ad = random.choice(banner_ads)
    return render_template('news.html', 
                           news = news, 
                           banner = selected_ad)


@app.route('/art')
def art():
    if current_user.is_anonymous:
        flash('Must be logged in to access page...')
        return render_template('anonymous.html',
                                then_next = 'art')
    # art = Art.query.all()
    query = Art.query
    if current_user.display_order.lower() == "oldest first":
        sorting_order = desc # no quotes as this is a callable
    else: # == recent first (default)
        sorting_order = asc 
    if current_user.ranking_sort.lower() == "name":
        query = query.order_by(sorting_order(Art.text))
    elif current_user.ranking_sort.lower() == "age":
        query = query.order_by(sorting_order(Art.date_pub))
    art = query.all()
    selected_ad = random.choice(banner_ads)
    return render_template('art.html', 
                           art = art, 
                           banner = selected_ad)


@app.route('/references')
def references():
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
    references = References.query.all()
    random.shuffle(references) # shuffle the list in place
    selected_ad = random.choice(banner_ads)
    return render_template('references.html', 
                           references = references, 
                           banner = selected_ad)


@app.route('/about')
def about():
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
    return render_template('about.html')


@app.route('/robots.txt')
def robots_txt():
    """
    This Flask robots.txt function will likely NOT be used at all as 
    /etc/apache2/sites-enabled/*.conf's
    <Directory /var/www/em/app/static> stanza will take care of it. 
    """
    return send_from_directory(app.static_folder, 'robots.txt')


@app.route('/update-viewing-mode', methods=['POST'])
@login_required
def update_viewing_mode():
    data = request.get_json()
    if 'viewing_mode' in data:
        current_user.viewing_mode = data['viewing_mode']
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400


# Authentication routes

@app.route('/captcha_test', methods=['GET','POST'])
def captcha_test():
    if request.method == 'GET':
        new_captcha_dict = SIMPLE_CAPTCHA.create()
        return render_template('captcha_test.html', 
                               captcha=new_captcha_dict)
    if request.method == 'POST':
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            return 'Success!'
        else:
            return 'Failed CAPTCHA...'


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
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
            # Flask-Login sets 365 day (default) expiration time for "remember me" cookie.
            flash("If you haven't done it yet, please take the survey when you get a chance.")
            user.last_access = datetime.datetime.now(datetime.timezone.utc).strftime('%Y %b %d') # ex: '2024 Sep 26'
            db.session.commit()
            logging.info(f'=*=*=*> User "{current_user.username}" logged in.')
            ip_addr = get_client_ip()
            logging.info(f'IP = {ip_addr}')
            logging.info(f'Agent = {get_user_agent()}')
            if 'user_referrer' not in session:
                session['user_referrer'] = 'None'
            logging.info(f"Referrer = {session['user_referrer']}")
            logging.info(f'Domain = {get_domain_from_ip(ip_addr)}')
            logging.info(f'ISP = {get_isp_from_ip(ip_addr)}')
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


@user_loaded_from_cookie.connect # flask-Login signal custom handler
def log_remember_me_login(sender, user):
    user.last_access = datetime.datetime.now(datetime.timezone.utc).strftime('%Y %b %d')
    db.session.commit()
    logging.info(f'=*=*=*> User "{user.username}" logged in via flask_login login_user "remember me" cookie.')


@app.route('/guest_sign_in')
def guest_sign_in():
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        form = LoginForm() ### delete this line? Not used...?
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    user = db.session.scalar(
        sa.select(User).where(User.username == 'Guest'))
    if user is None:
        flash('Invalid username')
        return redirect(url_for('login'))
    login_user(user, remember=False)
    flash('Take a look around and explore as Guest, then please take the survey.')
    logging.info(f'=*=*=*> User "{current_user.username}" logged in.')
    ip_addr = get_client_ip()
    logging.info(f'IP = {ip_addr}')
    logging.info(f'Agent = {get_user_agent()}')
    if 'user_referrer' not in session:
        session['user_referrer'] = 'None'
    logging.info(f"Referrer = {session['user_referrer']}")
    logging.info(f'Domain = {get_domain_from_ip(ip_addr)}')
    logging.info(f'ISP = {get_isp_from_ip(ip_addr)}')
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
    if 'user_referrer' not in session:
        temp_value = get_referrer()
        if temp_value:
            if my_name not in temp_value:
                session['user_referrer'] = temp_value
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
            email_value = form.email.data ### why this line?
            user = User(username=form.username.data, 
                        email=form.email.data, 
                        full_name=form.full_name.data, 
                        phone_number=form.phone_number.data,
                        role=set_role)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Congratulations, you are now a registered user!')
            logging.info(f'=*=*=*> New user registered! full_name="{form.full_name.data}" \
                username="{form.username.data}" email="{form.email.data}" phone #="{form.phone_number.data}"')
            if ntfypost:
                alert_data  = f'New user "{form.username.data}" registered; '
                alert_data += f'full name "{form.full_name.data}", '
                email_domain = form.email.data.split('@')[-1]
                alert_data += f'email domain "{email_domain}", '
                alert_data += f'phone area-code "{form.phone_number.data[0:3]}" '
                requests.post('https://ntfy.sh/000ntfy000EM000', headers={'Title' : alert_title}, data=(alert_data))
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
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    return render_template('user.html', 
                            title=f'{username}',
                            user=user,
                            form = OtpcodeForm(),
                            captcha=new_captcha_dict,
                            form_p = PasswordCheckForm())


@app.route('/send_otp')
def send_otp():
    email = current_user.email
    otp = pyotp.random_base32()  # Generate a secret for TOTP
    session['otp_secret'] = otp  # Store the OTP secret in session
    totp = pyotp.TOTP(otp, interval = validity_period)  # Time-based OTP (TOTP)
    otp_code = totp.now()   # Get the current OTP
    msg = Message('Your OTP Code', sender = app.config['MAIL_USERNAME'], recipients = [email])
    msg.body = f"Salutations,\n" \
               f"Your TOTP code for validating (email) user registration on EnshittificationMetrics.com is: {otp_code}\n" \
               f"Ideally enter it into the webpage within a minute or so of sending it. \n" \
               f"No one should ever ask you for this code, nor is there any value in keeping this code or email.\n" \
               f"Thanks,\n" \
               f"EnshittificationMetrics.com\n"
    mail.send(msg)
    next_page = request.args.get('next')
    if not next_page or urlsplit(next_page).netloc != '':
        next_page = url_for('index')  # fallback to the index page
    return redirect(next_page)


@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    form = OtpcodeForm()
    if form.validate_on_submit():
        user_input = form.otp_code.data
        totp = pyotp.TOTP(session['otp_secret'], interval = validity_period)
        if totp.verify(user_input, valid_window = interval_grace_period):
            try:
                current_user.validations = 'email' # will have to tweak behavior when adding SMS/TXT validation...
                db.session.commit()
                flash(f'TOTP valid - {current_user.email} validated.')
            except Exception as e:
                session.rollback()
                logging.error(f'Error {e} on assignment or commit of "validations = email" for current_user.username (with email "{current_user.email}")')
                flash(f'TOTP valid - {current_user.email} would be validated, however some error occured in saving validation to database.')
        else:
            flash(f'TOTP not valid, time window missed, or some other error - {current_user.email} not validated. Please try again.')
    next_page = request.args.get('next')
    if not next_page or urlsplit(next_page).netloc != '':
        next_page = url_for('index')  # fallback to the index page
    return redirect(next_page)


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
            # change only if different and new is not blank
            if (current_user.username != form.username.data) and (form.username.data != ''):
                current_user.username = form.username.data
            if (current_user.email != form.email.data) and (form.email.data != ''):
                current_user.email = form.email.data
                current_user.validations = '' # will have to tweak behavior when adding SMS/TXT validation...
                # above line to reset email validation if email is changed after being validated
            if (current_user.full_name != form.full_name.data) and (form.full_name.data != ''): 
                current_user.full_name = form.full_name.data
            if (current_user.phone_number != form.phone_number.data) and (form.phone_number.data != ''):
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


@app.route('/exportaccount', methods=['POST'])
@login_required
def exportaccount():
    from flask import Response
    import csv
    import io
    form_p = PasswordCheckForm(request.form)
    if form_p.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            logging.info(f'Bad CAPTCHA on export {current_user.username} data as CSV request.')
        else: #captcha correct
            if not current_user.check_password(form_p.password.data):
                flash('Password incorrect.')
                logging.info(f'Bad password on export {current_user.username} data as CSV request.')
            else: # CAPTCHA and password correct at this point, continue to export
                # Create an in-memory CSV file using io.StringIO
                output = io.StringIO()
                writer = csv.writer(output)
                # Write the header row and some data rows
                writer.writerow(['ID', 'Record Name', 'Value'])
                writer.writerow([1,  'id',            current_user.id])
                writer.writerow([2,  'username',      current_user.username])
                writer.writerow([3,  'email',         current_user.email])
                writer.writerow([4,  'password_hash', 'N/A'])
                writer.writerow([5,  'full_name',     current_user.full_name])
                writer.writerow([6,  'phone_number',  current_user.phone_number])
                writer.writerow([7,  'role',          current_user.role])
                writer.writerow([8,  'validations',   current_user.validations])
                writer.writerow([9,  'last_access',   current_user.last_access])
                writer.writerow([10, 'func_stage',    current_user.func_stage])
                writer.writerow([11, 'per_page',      current_user.per_page])
                writer.writerow([12, 'display_order', current_user.display_order])
                writer.writerow([13, 'ranking_sort',  current_user.ranking_sort])
                writer.writerow([14, 'ranking_cats',  current_user.ranking_cats])
                writer.writerow([15, 'ranking_stat',  current_user.ranking_stat])
                writer.writerow([16, 'viewing_mode',  current_user.viewing_mode])
                writer.writerow([17, 'to_view',       current_user.to_view])
                # Move to the beginning of the StringIO buffer
                output.seek(0)
                # Create a response with the CSV data
                response = Response(output, mimetype='text/csv')
                response.headers.set('Content-Disposition', 'attachment', filename=f'Enshittification_Metrics_{current_user.username}.csv')
                flash(f'Exported {current_user.username} data as CSV.')
                logging.info(f'Exported {current_user.username} data as CSV.')
                return response
    # form validation, or CAPTCHA, or password, failed
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    return render_template('user.html', 
                            title=f'{current_user.username}',
                            user=current_user,
                            form = OtpcodeForm(),
                            captcha=new_captcha_dict,
                            form_p = PasswordCheckForm())


@app.route('/deleteaccount', methods=['POST'])
@login_required
def deleteaccount():
    form_p = PasswordCheckForm(request.form)
    if form_p.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
            flash('CAPTCHA verification failed.')
            logging.info(f'Bad CAPTCHA on delete {current_user.username} account request.')
        else: #captcha correct
            if not current_user.check_password(form_p.password.data):
                flash('Password incorrect.')
                logging.info(f'Bad password on delete {current_user.username} account request.')
            else: # CAPTCHA and password correct at this point, continue to delete account
                del_name = current_user.username
                user_id = current_user.id
                logout_user() # clears session data
                user = User.query.get(user_id)
                if user:
                    db.session.delete(user) # current_user might still exist after logout due to lazy load, but just in case...
                    db.session.commit()
                    flash(f'Deleted {del_name} account.')
                    logging.info(f'Deleted {del_name} account.')
                    return redirect(url_for('index'))
                else:
                    flash(f'User {del_name} with ID {user_id} not found!?')
                    logging.error(f'Tried to delete non-existent user {del_name} with ID {user_id}.')
                    # continues below
    # form validation, or CAPTCHA, or password, failed
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    return render_template('user.html', 
                            title=f'{current_user.username}',
                            user=current_user,
                            form = OtpcodeForm(),
                            captcha=new_captcha_dict,
                            form_p = PasswordCheckForm())


# telemetry data gathers

def get_client_ip():
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
        # application is behind a reverse proxy like Apache with mod_proxy or a load balancer
    else:
        ip = request.remote_addr
    return ip


def get_user_agent():
    user_agent = request.headers.get('User-Agent')
    return user_agent


def get_referrer():
    referrer = request.headers.get('Referer') # Referrer misspelled in HTTP
    return referrer


def get_domain_from_ip(ip_address):
    try:
        domain = socket.gethostbyaddr(ip_address)
        return domain[0]  # Returns the primary domain name
    except socket.herror:
        return f'No domain name found'


def get_isp_from_ip(ip_address):
    try:
        response = requests.get(f"https://ipinfo.io/{ip_address}/json")
        data = response.json()
        return {
            "ip": data.get("ip"),
            "hostname": data.get("hostname"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "org": data.get("org")  # This gives the ISP/organization
        }
    except requests.RequestException as e:
        return {"error": str(e)}


@app.route('/survey', methods=['GET', 'POST'])
def survey():
    content = 'survey_new_user'
    form = SurveyNewUserForm()
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    if request.method == 'GET':
        if current_user.is_anonymous:
            content = 'please_logon'
            return render_template('survey.html', 
                                   content = content)
        else:
            return render_template('survey.html', 
                                   content = content, 
                                   form = form, 
                                   captcha = new_captcha_dict)
    elif request.method == 'POST':
        if form.validate_on_submit():
            c_hash = request.form.get('captcha-hash')
            c_text = request.form.get('captcha-text')
            if not SIMPLE_CAPTCHA.verify(c_text, c_hash):
                flash('CAPTCHA verification failed.')
                return render_template('survey.html', 
                                       content = content, 
                                       form = form, 
                                       captcha = new_captcha_dict)
            else:
                survey_datetime = datetime.datetime.now(datetime.timezone.utc).strftime('%Y %b %d @ %H:%M') # ex: '2024 Sep 27 @ 23:26'
                survey = SurveyNewUser(discovery = form.discovery.data, 
                                       thoughts = form.thoughts.data, 
                                       suggestions = form.suggestions.data, 
                                       monetization = form.monetization.data, 
                                       datetime = survey_datetime, 
                                       username = current_user.username)
                db.session.add(survey)
                db.session.commit()
                flash('Survey submitted successfully.')
                answers = f'User "{current_user.username}" submitted survey at {survey_datetime}: \n' \
                          f'discovery: {form.discovery.data} \n' \
                          f'suggestions: {form.suggestions.data} \n' \
                          f'monetization: {form.monetization.data}'
                logging.info(f'=*=*=*> {answers}')
                if ntfypost:
                    requests.post('https://ntfy.sh/000ntfy000EM000', headers={'Title' : alert_title}, data=(answers))
                next_page = request.args.get('next')
                if not next_page or urlsplit(next_page).netloc != '':
                    next_page = url_for('index')
                return redirect(next_page)
        else:
            flash("Some field(s) didn't validate - please edit answers as needed and resubmit.")
            return render_template('survey.html', 
                                   content = content, 
                                   form = form, 
                                   captcha = new_captcha_dict)
    else:
        flash('Must call survey by GET or POST!')
        return render_template('survey.html', 
                               content = content, 
                               form = form, 
                               captcha = new_captcha_dict)


# dev / administrator only routes - locked down


@app.route('/force_utilities', methods=['GET', 'POST'])
@login_required
def force_utilities():
    if current_user.role != 'administrator':
        return render_template('index.html')
    if call_type == 'POST':
        pass
        ### pull button values selected
        return 
    return render_template('force_utilities.html',)


@app.route('/show_values')
@login_required
def show_values():
    if current_user.role != 'administrator':
        return render_template('index.html')
    show_values = []
    show_values.append(f'==> MISC\n')
    show_values.append(f'script_directory: {script_directory}\n')
    show_values.append(f'logpath: {logpath}\n')
    show_values.append(f'==> NTFY\n')
    show_values.append(f'hostn: {hostn}\n')
    show_values.append(f'ntfypost: {ntfypost}\n')
    show_values.append(f'alert_title: {alert_title}\n')
    show_values.append(f'==> TOTP\n')
    show_values.append(f'validity_period: {validity_period}\n')
    show_values.append(f'interval_grace_period: {interval_grace_period}\n')
    show_values.append(f'==> MAIL\n')
    show_values.append(f"app.config['SECRET_KEY']: not shown\n")
    show_values.append(f"app.config['MAIL_SERVER']: {app.config['MAIL_SERVER']}\n")
    show_values.append(f"app.config['MAIL_PORT']: {app.config['MAIL_PORT']}\n")
    show_values.append(f"app.config['MAIL_USE_TLS']: {app.config['MAIL_USE_TLS']}\n")
    show_values.append(f"app.config['MAIL_USERNAME']: {app.config['MAIL_USERNAME']}\n")
    show_values.append(f"app.config['MAIL_PASSWORD']: not shown\n")
    show_values.append(f'==> CAPTCHA\n')
    show_values.append(f'CAPTCHA_CONFIG: {CAPTCHA_CONFIG}\n')
    show_values.append(f'==> current_user\n')
    show_values.append(f'current_user.id: {current_user.id}\n')
    show_values.append(f'current_user.username: {current_user.username}\n')
    show_values.append(f'current_user.email: {current_user.email}\n')
    show_values.append(f'current_user.password_hash: not shown\n')
    show_values.append(f'current_user.full_name: {current_user.full_name}\n')
    show_values.append(f'current_user.phone_number: {current_user.phone_number}\n')
    show_values.append(f'current_user.role: {current_user.role}\n')
    show_values.append(f'current_user.validations: {current_user.validations}\n')
    show_values.append(f'current_user.last_access: {current_user.last_access}\n')
    show_values.append(f'current_user.func_stage: {current_user.func_stage}\n')
    show_values.append(f'current_user.per_page: {current_user.per_page}\n')
    show_values.append(f'current_user.display_order: {current_user.display_order}\n')
    show_values.append(f'current_user.ranking_sort:  {current_user.ranking_sort}\n')
    show_values.append(f'current_user.ranking_cats: {current_user.ranking_cats}\n')
    show_values.append(f'current_user.ranking_stat: {current_user.ranking_stat}\n')
    show_values.append(f'current_user.viewing_mode: {current_user.viewing_mode}\n')
    show_values.append(f'current_user.to_view: {current_user.to_view}\n')
    show_values.append(f'==> END\n')
    return render_template('show_values.html',
                           show_values = show_values)


@app.route('/report_all')
@login_required
def report_all():
    if current_user.role != 'administrator':
        return render_template('index.html')
    entities = Entity.query.all()
    news = News.query.all()
    art = Art.query.all()
    references = References.query.all()
    return render_template('report.html', 
                           entities = entities, 
                           news = news, 
                           art = art, 
                           references = references)


@app.route('/report_entities')
@login_required
def report_entities():
    if current_user.role != 'administrator':
        return render_template('index.html')
    entities = Entity.query.all()
    return render_template('report.html', 
                           entities = entities, 
                           news = None, 
                           art = None, 
                           references = None)


@app.route('/report_news')
@login_required
def report_news():
    if current_user.role != 'administrator':
        return render_template('index.html')
    news = News.query.all()
    return render_template('report.html', 
                           entities = None, 
                           news = news, 
                           art = None, 
                           references = None)


@app.route('/report_art')
@login_required
def report_art():
    if current_user.role != 'administrator':
        return render_template('index.html')
    art = Art.query.all()
    return render_template('report.html', 
                           entities = None, 
                           news = None, 
                           art = art, 
                           references = None)


@app.route('/report_references')
@login_required
def report_references():
    if current_user.role != 'administrator':
        return render_template('index.html')
    references = References.query.all()
    return render_template('report.html', 
                           entities = None, 
                           news = None, 
                           art = None, 
                           references = references)


@app.route('/manual_add', methods=['GET', 'POST'])
@login_required
def manual_add():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = SelectAddForm()
    if form.validate_on_submit():
        match form.target_table.data:
            case "Entity":
                return redirect(url_for('manual_entity'))
            case "News":
                return redirect(url_for('manual_news'))
            case "Art":
                return redirect(url_for('manual_art'))
            case "References":
                return redirect(url_for('manual_reference'))
            case _:
                flash('Invalid target_table value.')
                logging.error(f'Invalid target_table value in routes.py manual_add function match.')
                return redirect(url_for('manual_add'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        return render_template('selectaddform.html', 
                               form = form)


@app.route('/manual_edit', methods=['GET', 'POST'])
@login_required
def manual_edit():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = SelectForm()
    if form.validate_on_submit():
        id = form.target_id.data
        match form.target_table.data:
            case "Entity":
                return redirect(url_for('manual_entity_edit', id = id))
            case "News":
                return redirect(url_for('manual_news_edit', id = id))
            case "Art":
                return redirect(url_for('manual_art_edit', id = id))
            case "References":
                return redirect(url_for('manual_reference_edit', id = id))
            case _:
                flash('Invalid target_table value.')
                logging.error(f'Invalid target_table value in routes.py manual_edit function match.')
                return redirect(url_for('manual_edit'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        return render_template('selectform.html', 
                               form = form,
                               header_text = 'edit')


@app.route('/manual_delete', methods=['GET', 'POST'])
@login_required
def manual_delete():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = SelectForm()
    if form.validate_on_submit():
        match form.target_table.data:
            case "Entity":
                delete_record = Entity.query.get_or_404(form.target_id.data)
                logging.info(f'Deleting {delete_record.name} (Entity ID #{form.target_id.data})')
                db.session.delete(delete_record)
                db.session.commit()
                flash(f'Deleted entity ID #{form.target_id.data}')
                return redirect(url_for('rankings'))
            case "News":
                delete_record = News.query.get_or_404(form.target_id.data)
                logging.info(f'Deleting {delete_record.text} (News ID #{form.target_id.data})')
                db.session.delete(delete_record)
                db.session.commit()
                flash(f'Deleted news ID #{form.target_id.data}')
                return redirect(url_for('news'))
            case "Art":
                delete_record = Art.query.get_or_404(form.target_id.data)
                logging.info(f'Deleting {delete_record.text} (Art ID #{form.target_id.data})')
                db.session.delete(delete_record)
                db.session.commit()
                flash(f'Deleted art ID #{form.target_id.data}')
                return redirect(url_for('art'))
            case "References":
                delete_record = References.query.get_or_404(form.target_id.data)
                logging.info(f'Deleting {delete_record.text} (Reference ID #{form.target_id.data})')
                db.session.delete(delete_record)
                db.session.commit()
                flash(f'Deleted reference ID #{form.target_id.data}')
                return redirect(url_for('references'))
            case _:
                flash('Invalid target_table value.')
                logging.error(f'Invalid target_table value in routes.py manual_delete function match.')
                return redirect(url_for('manual_delete'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        return render_template('selectform.html', 
                               form = form,
                               header_text = 'delete (no undo)')


@app.route('/manual_entity_add', methods=['GET', 'POST'])
@login_required
def manual_entity():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = EntityAddForm()
    if form.validate_on_submit():
        entity = Entity(status        = form.status.data, 
                        name          = form.name.data, 
                        stage_current = form.stage_current.data, 
                        stage_history = form.stage_history.data, 
                        stage_EM4view = form.stage_EM4view.data, 
                        date_started  = form.date_started.data, 
                        date_ended    = form.date_ended.data, 
                        summary       = form.summary.data, 
                        corp_fam      = form.corp_fam.data, 
                        category      = form.category.data, 
                        timeline      = form.timeline.data)
        db.session.add(entity)
        db.session.commit()
        flash(f'Added {form.name.data}')
        return redirect(url_for('rankings'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        blank = Entity(id            = 0,
                       status        = 'empty',
                       name          = 'empty',
                       stage_current = 1,
                       stage_history = [ ['YYYY MMM DD', 1], ['YYYY MMM DD', 2] ],
                       stage_EM4view = 1,
                       date_started  = 'empty',
                       date_ended    = 'empty',
                       summary       = 'empty',
                       corp_fam      = 'empty',
                       category      = 'empty',
                       timeline      = 'empty')
        return render_template('manual_entity.html', 
                               form = form,
                               entity = blank)


@app.route('/manual_news_add', methods=['GET', 'POST'])
@login_required
def manual_news():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = NewsForm()
    if form.validate_on_submit():
        news = News(date_pub  = form.date_pub.data, 
                    url       = form.url.data, 
                    text      = form.text.data, 
                    summary   = form.summary.data, 
                    ent_names = form.ent_names.data)
        db.session.add(news)
        db.session.commit()
        flash(f'Added {form.text.data}')
        return redirect(url_for('news'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        blank = News(id       = 0,
                     date_pub = 'empty',
                     url      = 'empty', 
                     text     = 'empty', 
                     summary  = 'empty',
                     ent_names = ['empty1', 'empty2'])
        return render_template('manual_news.html', 
                               form = form,
                               news = blank)


@app.route('/manual_art_add', methods=['GET', 'POST'])
@login_required
def manual_art():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = ArtForm()
    if form.validate_on_submit():
        ent_names = [item['item'] for item in form.ent_names.data]
        art = Art(date_pub  = form.date_pub.data, 
                  url       = form.url.data, 
                  text      = form.text.data, 
                  summary   = form.summary.data, 
                  ent_names = ent_names)
        db.session.add(art)
        db.session.commit()
        flash(f'Added {form.text.data}')
        return redirect(url_for('art'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        blank = Art(id       = 0,
                    date_pub = 'empty',
                    url      = 'empty', 
                    text     = 'empty', 
                    summary  = 'empty',
                    ent_names = ['empty1', 'empty2'])
        return render_template('manual_art.html', 
                               form = form, 
                               art = blank)


@app.route('/manual_reference_add', methods=['GET', 'POST'])
@login_required
def manual_reference():
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = ReferencesForm()
    if form.validate_on_submit():
        ref = References(date_pub = form.date_pub.data, 
                         url      = form.url.data, 
                         text     = form.text.data, 
                         summary  = form.summary.data)
        db.session.add(ref)
        db.session.commit()
        flash(f'Added {form.text.data}')
        return redirect(url_for('references'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        blank = References(id       = 0,
                           date_pub = 'empty',
                           url      = 'empty', 
                           text     = 'empty', 
                           summary  = 'empty')
        return render_template('manual_reference.html', 
                               form = form, 
                               reference = blank)


@app.route('/manual_entity_edit/<id>', methods=['GET', 'POST'])
@login_required
def manual_entity_edit(id):
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = EntityEditForm()
    entity = Entity.query.get_or_404(id)
    if form.validate_on_submit():
        entity.status        = form.status.data
        entity.name          = form.name.data
        entity.stage_current = form.stage_current.data
        entity.stage_history = form.stage_history.data
        entity.stage_EM4view = form.stage_EM4view.data
        entity.date_started  = form.date_started.data
        entity.date_ended    = form.date_ended.data
        entity.summary       = form.summary.data
        entity.corp_fam      = form.corp_fam.data
        entity.category      = form.category.data
        db.session.commit()
        flash(f'Edited {form.name.data}')
        return redirect(url_for('rankings'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        form.status.data = entity.status
        form.name.data = entity.name
        form.stage_current.data = entity.stage_current
        ### form.stage_history.data = entity.stage_history
        form.stage_EM4view.data = entity.stage_EM4view
        form.date_started.data = entity.date_started
        form.date_ended.data = entity.date_ended
        form.summary.data = entity.summary
        form.corp_fam.data = entity.corp_fam
        form.category.data = entity.category
        return render_template('manual_entity.html', 
                               form = form, 
                               entity = entity)


@app.route('/manual_news_edit/<id>', methods=['GET', 'POST'])
@login_required
def manual_news_edit(id):
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = NewsForm()
    news = News.query.get_or_404(id)
    if form.validate_on_submit():
        news.date_pub = form.date_pub.data
        news.url      = form.url.data
        news.text     = form.text.data
        news.summary  = form.summary.data
        news.ent_names= form.ent_names.data
        db.session.commit()
        flash(f'Edited {form.text.data}')
        return redirect(url_for('news'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        form.date_pub.data = news.date_pub
        form.url.data = news.url
        form.text.data = news.text
        form.summary.data = news.summary
        ### ent_names
        return render_template('manual_news.html', 
                               form = form, 
                               news = news)


@app.route('/manual_art_edit/<id>', methods=['GET', 'POST'])
@login_required
def manual_art_edit(id):
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = ArtForm()
    art = Art.query.get_or_404(id)
    if form.validate_on_submit():
        art.date_pub = form.date_pub.data
        art.url      = form.url.data
        art.text     = form.text.data
        art.summary  = form.summary.data
        art.ent_names= form.ent_names.data
        db.session.commit()
        flash(f'Edited {form.text.data}')
        return redirect(url_for('art'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        form.date_pub.data = art.date_pub
        form.url.data = art.url
        form.text.data = art.text
        form.summary.data = art.summary
        ### ent_names
        return render_template('manual_art.html', 
                               form = form, 
                               art = art)


@app.route('/manual_reference_edit/<id>', methods=['GET', 'POST'])
@login_required
def manual_reference_edit(id):
    if current_user.role != 'administrator':
        return render_template('index.html')
    form = ReferencesForm()
    reference = References.query.get_or_404(id)
    if form.validate_on_submit():
        reference.date_pub = form.date_pub.data
        reference.url      = form.url.data
        reference.text     = form.text.data
        reference.summary  = form.summary.data
        db.session.commit()
        flash(f'Edited {form.text.data}')
        return redirect(url_for('references'))
    else:
        if request.method == 'POST': print(f'form.errors = {form.errors}')
        form.date_pub.data = reference.date_pub
        form.url.data = reference.url
        form.text.data = reference.text
        form.summary.data = reference.summary
        return render_template('manual_reference.html', 
                               form = form, 
                               reference = reference)

