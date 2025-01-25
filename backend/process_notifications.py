#!/usr/bin/env python

""" 
Script to run daily to go through each user's alerts and put something together for them as appropriate and send it
"""

crontab = """ 0 7 * * * cd /home/leet/EnshittificationMetrics/backend/ && pipenv run python3 process_notifications.py >> /home/leet/EnshittificationMetrics/backend/notifications.log 2>&1 """
crontab = """ once this code is on prod, set crontab for daily nightly """

import os
import sys
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    sys.path.append('/var/www/em')
    logpath = '/home/bsea/em/notifications.log'
else:
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
    logpath = './notifications.log'
logging.basicConfig(level=logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format='%(asctime)s -%(levelname)s - %(message)s')
from app import app, db
from app.models import Entity, News, Art, References, User
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask_mail import Mail, Message
from sqlalchemy import or_, asc, desc, func
import sqlalchemy as sa

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') # secure Flask session management
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

mail = Mail(app)


def create_report(user):
    logging.info(f'==> ++++++++++ creating report for {user.username} +++++++++++')
    report = ""
    """ report on art items since last_sent """
    if user.alert_on_art_item:
        report_art = ""
        query = Art.query
        query = query.filter(Art.date_pub > user.last_sent).order_by(asc(Art.date_pub))
        art_objs = query.all()
        for art in art_objs:
            report_art += f'On {art.date_pub} indexed "{art.text}" at {art.url}\n'
        if report_art:
            report += "alert_on_art_items:\n"
            report += report_art + "\n"
            logging.info(f'==> ++++++++++ {len(report_art)} characters on art +++++++++++')
    """ report on reference items since last_sent """
    if user.alert_on_reference_item:
        report_ref = ""
        query = References.query
        query = query.filter(References.date_pub > user.last_sent).order_by(asc(References.date_pub))
        ref_objs = query.all()
        for ref in ref_objs:
            report_ref += f'On {ref.date_pub} indexed "{ref.text}" at {ref.url}\n'
        if report_ref:
            report += "alert_on_reference_item:\n"
            report += report_ref + "\n"
            logging.info(f'==> ++++++++++ {len(report_ref)} characters on references +++++++++++')
    """ report on entities and/or categories followed """
    query = Entity.query
    query = query.filter(Entity.status != 'disabled')
    entities_objs = query.all()
    for ent in entities_objs: # defined in top init section of script
        ent_hit = False
        if ent.name in user.entities_following: ent_hit = True
        for cat in ent.categories: 
            if cat in user.categories_following: ent_hit = True
        if not ent_hit: continue
        logging.info(f'==> ++++++++++ hit for {ent.name} +++++++++++')
        """ report news items listed in stage_history for this entity in time since last_sent """
        if user.alert_on_news_item:
            report_news = ""
            for item in ent.stage_history:
                if item[0] > user.last_sent: # news item date
                    if item[2]: # news item id
                        query = News.query
                        query = query.filter(News.id == item[2])
                        news_item = query.all()
                        report_news += f'On {news_item.date_pub} indexed stage {stage_int_value} "{news_item.text}" at {news_item.url}\n'
        """ report stage value changes for this entity in time since last_sent """
        if user.alert_on_stage_change:
            report_stage = ""
            stage_values = str(ent.stage_current)
            for item in ent.stage_history:
                if item[0] > user.last_sent: # news item date
                    stage_values += str(item[1]) # stage value
            unique_chars = set(stage_values)
            unique_count = len(unique_chars)
            if unique_count == 1:
                pass # that's okay
            elif unique_count == 2:
                report_stage += f'Crossed stages {unique_chars[0]} and {unique_chars[1]}.'
            elif unique_count == 3:
                report_stage += f'Crossed stages {unique_chars[0]} and {unique_chars[1]} and {unique_chars[2]}.'
            elif unique_count == 4:
                report_stage += f'Crossed stages {unique_chars[0]} and {unique_chars[1]} and {unique_chars[2]} and {unique_chars[3]}.'
            else:
                logging.error(f"stage_values didn't resolve to an expected unique_count: {stage_values}")
        if report_news or report_stage:
            report += f"alert on entity {ent.name}\n"
            report += report_news + report_stage + "\n"
            logging.info(f'==> ++++++++++ {len(report_news)} characters on news +++++++++++')
            logging.info(f'==> ++++++++++ stage history values: {unique_chars} +++++++++++')
    """ ai_suggestions """
    if user.ai_suggestions:
        pass # future development...
        report += "ai_suggestions:\n"
        report += "\n"
    logging.info(f'==> ++++++++++ report creation complete +++++++++++')
    return report


def generate_snappy_subject(report):
    ### langchain llm call with prompt to summarize the report down to a nice short subject line and maybe give it a little pop with a enshittification pun
    return None


def send_report_to_user(report, user):
    logging.info(f'==> ++++++++++ sending report to {user.username} +++++++++++')
    ### need to tweak the reply-to on this email!?
    email = user.email
    snappy_subject = generate_snappy_subject(report=report)
    if not snappy_subject:
        snappy_subject = 'EnshittificationMetrics.com Alert'
    msg = Message(snappy_subject, sender = app.config['MAIL_USERNAME'], recipients = [email])
    msg.body = f'"Alerts" from EnshittificationMetrics.com for {user.username}.\n' \
               f"{report}\n" \
               f"\n" \
               f"Thanks,\n" \
               f"EnshittificationMetrics.com\n"
               ### add bit about changing or stopping via alerts settings tab on EM, or worst case can reply with unsubscribe or no.
    # mail.send(msg)
    test_print(report=report, snappy_subject=snappy_subject, un=user.username, email=email)
    logging.info(f'==> ++++++++++ {snappy_subject} - report sent +++++++++++')


def test_print(report, snappy_subject, un, email):
    tp =  f'Test Alerts Report\n'
    tp += f'email: {email}\n'
    tp += f'snappy_subject: {snappy_subject}\n'
    tp += f'un: {un}\n'
    tp += f'report: {report}\n'
    print(tp)
    logging.info(tp)


def one_off_report_to_user(username_str):
    """ few checks, just force an alert out for that user """
    logging.info(f'==> ++++++++++ one-off alert starting against user "{username_str}" +++++++++++')
    with app.app_context():
        query = User.query
        query = query.filter(User.username == username_str)
        user = query.all()
        if not user:
            logging.warning(f'==> ++++++++++ user "{username_str}" not found +++++++++++')
            return False
        if not user.enable_notifications:
            logging.warning(f'==> ++++++++++ user.enable_notifications == False +++++++++++')
            return False
        now = datetime.now()
        report = create_report(user=user)
        if report:
            send_report_to_user(report=report, user=user)
            user.last_sent = datetime.now()
            db.session.commit()
        else:
            logging.info(f'==> ++++++++++ blank report generated, nothing to send +++++++++++')
    logging.info(f'==> ++++++++++ one-off alert done +++++++++++\n')
    return True


def create_send_alerts():
    logging.info(f'==> ++++++++++ alerts starting +++++++++++')
    """ loop through all the users """
    with app.app_context():
        query = User.query
        query = query.filter(User.role != 'disabled')
        all_users = query.all()
        for user in all_users:
            if (user.role == "disabled") or (user.role == "guest"):
                continue
            if not "email" in user.validations:
                continue
            """ check enable_notifications """
            if user.enable_notifications:
                logging.info(f'{user.username} has enable_notifications on!')
                now = datetime.now() # set now for each user, rather than once for all user passes in case it takes a long time
                if (not user.last_sent) or (user.last_sent == "None"):
                    user.last_sent = now 
                    # deals with first alert notification run made when last_sent is not defined yet, to avoid time math errors
                    # behavior is enable_notifications first set, script runs within 24 hours but generates blank report (except maybe AI piece)
                    # then count starts so next run may do something
                    db.session.commit()
                """ check notification_frequency and last_sent """
                freq = 7
                match user.notification_frequency:
                    case "daily"    : freq = 1
                    case "weekly"   : freq = 7
                    case "fortnight": freq = 10
                    case "monthly"  : freq = 30.43
                    case "quarterly": freq = 91.31
                    case "annually" : freq = 365.25
                timechange_or_compute_delay = timedelta(hours=1.5)
                if now - user.last_sent + timechange_or_compute_delay >= timedelta(days=freq):
                    """ create report """
                    report = create_report(user=user)
                    if report:
                        """ send report """
                        send_report_to_user(report=report, user=user)
                        user.last_sent = datetime.now()
                        db.session.commit()
                    else:
                        logging.info(f'==> ++++++++++ blank report generated, nothing to send +++++++++++')
                else:
                    logging.info(f"Not yet time for {user.username}'s report - scheduled for {user.last_sent + timedelta(days=freq)} UTC or later")
    logging.info(f'==> ++++++++++ alerts done +++++++++++\n')


def main():
    create_send_alerts()


if __name__ == "__main__":
    main()
