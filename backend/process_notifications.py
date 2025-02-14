#!/usr/bin/env python

""" 
Script to run daily to go through each user's alerts and put something together for them as appropriate and send it
"""

crontab = """ 0   7 * * * cd /home/leet/EnshittificationMetrics/backend/ && pipenv run python3 process_notifications.py >> /home/leet/EnshittificationMetrics/backend/notifications.log 2>&1 """
crontab = """ 30 17 * * * cd /home/bsea/em/ && pipenv run python3 process_notifications.py >> /home/bsea/em/utilities/cron_issues.log 2>&1 """

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
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_core.output_parsers import StrOutputParser
import dateparser
import re

llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') # secure Flask session management
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
# app.config['MAIL_DEBUG'] = True  # Debug mode quite verbose in logs

mail = Mail(app)


def create_report(user):
    logging.info(f'==> ++++++++++ creating report for {user.username} with last_sent value of {user.last_sent} +++++++++++')
    report = ""
    """ report on art items since last_sent """
    if user.alert_on_art_item:
        report_art = ""
        query = Art.query
        query = query.filter(Art.date_pub > user.last_sent).order_by(asc(Art.date_pub))
        art_objs = query.all()
        for art in art_objs:
            report_art += f'*  On {art.date_pub} indexed "{art.text}" at {art.url}\n\n'
        if report_art:
            report += "alert_on_art_items:\n\n"
            report += report_art + "\n"
            logging.info(f'==> ++++++++++ {len(report_art)} characters on art +++++++++++')
    """ report on reference items since last_sent """
    if user.alert_on_reference_item:
        report_ref = ""
        query = References.query
        query = query.filter(References.date_pub > user.last_sent).order_by(asc(References.date_pub))
        ref_objs = query.all()
        for ref in ref_objs:
            report_ref += f'*  On {ref.date_pub} indexed "{ref.text}" at {ref.url}\n\n'
        if report_ref:
            report += "alert_on_reference_item:\n\n"
            report += report_ref + "\n"
            logging.info(f'==> ++++++++++ {len(report_ref)} characters on references +++++++++++')
    """ report on entities and/or categories followed """
    if user.alert_on_news_item or user.alert_on_stage_change:
        query = Entity.query
        query = query.filter(Entity.status != 'disabled')
        entities_objs = query.all()
        for ent in entities_objs: # tried to define entities_objs at top of script in inti area but didn't work, maybe due to lack of with app.app_context()
            ent_hit = False
            report_news = ""
            report_stage = ""
            if ent.name in user.entities_following: ent_hit = True
            words = ent.category.split(", ") # string so need to comma separate
            for cat in words:
                if cat in user.categories_following: ent_hit = True
            if not ent_hit: continue
            logging.info(f'==> Checking {ent.name}') # might comment this logging line as too chatty, or summarize somehow
            """ report news items listed in stage_history for this entity in time since last_sent """
            if user.alert_on_news_item:
                for item in ent.stage_history:
                    if dateparser.parse(str(item[0])) > user.last_sent: # news item date # last_sent is defined/stored as datetime already
                        if item[2]: # news item id
                            query = News.query.filter(News.id == item[2])
                            news_item = query.first() # Returns a single User object or None, not a list
                            report_news += f'*  {ent.name} {news_item.date_pub} (stage {ent.stage_current} event) "{news_item.text}"; at {news_item.url}\n\n'
                            logging.info(f'==> bullet for news item ID #{news_item.id}')
            """ report stage value changes for this entity in time since last_sent """
            if user.alert_on_stage_change:
                stage_values = str(ent.stage_current)
                for item in ent.stage_history:
                    if dateparser.parse(str(item[0])) > user.last_sent: # news item date
                        stage_values += str(item[1]) # stage value
                unique_chars = ''.join(set(stage_values)) # set makes, for ex., {'3', '2', '1'}, then we join it into a str, for ex. '321'
                unique_count = len(unique_chars)
                if unique_count == 1:
                    pass # that's okay
                elif unique_count == 2:
                    report_stage += f'*  {ent.name} crossed stages {unique_chars[0]} and {unique_chars[1]}.\n'
                    logging.info(f'==> bullet for stage crossing {unique_chars}')
                elif unique_count == 3:
                    report_stage += f'*  {ent.name} crossed stages {unique_chars[0]} and {unique_chars[1]} and {unique_chars[2]}.\n'
                    logging.info(f'==> bullet for stage crossing {unique_chars}')
                elif unique_count == 4:
                    report_stage += f'*  {ent.name} crossed stages {unique_chars[0]} and {unique_chars[1]} and {unique_chars[2]} and {unique_chars[3]}.\n'
                    logging.info(f'==> bullet for stage crossing {unique_chars}')
                else:
                    logging.error(f"stage_values didn't resolve to an expected unique_count: {stage_values}")
            if report_news:
                report += report_news
                logging.info(f'==> ++++++++++ {len(report_news)} characters on news +++++++++++')
            if report_stage:
                report += report_stage + "\n"
                logging.info(f'==> ++++++++++ stage history values: {unique_chars} +++++++++++')
    """ ai_suggestions """
    if user.ai_suggestions:
        pass # future development...
        report += "ai_suggestions:\n"
        report += "None at this time...\n"
    logging.info(f'==> ++++++++++ report creation complete +++++++++++')
    return report


def large_lang_model(query):
    large_lang_model = ChatMistralAI(model_name = 'open-mixtral-8x7b', 
                                     mistral_api_key = llm_api_key, 
                                     temperature = llm_temp, 
                                     verbose = True )
    return large_lang_model


SNAPPY_SUBJECT_TEMPLATE = """
Summarize this report down to a nice terse email subject line. 
Should convey some of the report content, but not be too long to wrap or go off-screen when read. 
As possible and appropriate, give email subject line a little "pop" with an enshittification pun or something. 
Here is report: 
{report}
"""


def generate_snappy_subject(report):
    content_prompt = ChatPromptTemplate.from_template(SNAPPY_SUBJECT_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    try:
        snappy_subject = chain.invoke({"report": report})
        logging.info(f'snappy_subject: "{snappy_subject}"')
    except Exception as e:
        snappy_subject = None
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    snappy_subject = snappy_subject.replace("\n", " ") # Email headers must not contain newlines as they can be exploited for email header injection
    match = re.search(r'"(.*?)"', snappy_subject) # Extract first quoted section; not sure why LLM returned quoted content, this is not requested in prompt
    snappy_subject = match.group(1) if match else snappy_subject # Sorry LLM, if you offer multiple options I'm just taking first one
    return snappy_subject


def send_report_to_user(report, user, now):
    
    default_subject_text = f"""EnshittificationMetrics.com Alert"""
    
    salutation_text = f""""Alerts" from EnshittificationMetrics.com for {user.username}.\n"""
    
    timerange_text = f"""Alert time-range is from {user.last_sent.strftime("%Y-%b-%d %H:%M")} to {now.strftime("%Y-%b-%d %H:%M")}.\n\n"""
    
    signature_text = f"""Thanks, \nEnshittificationMetrics.com\n"""
    
    footer_text = """To change or stop these alerts, please use the "Alert Subscriptions Notification Settings" area in EnshittificationMetrics.com, https://www.enshittificationmetrics.com/alerts."""
    ### Eventually will add a reply with UNSUBSCRIBE or STOP feature.
    
    logging.info(f'==> ++++++++++ sending report to {user.username} +++++++++++')
    ### need to tweak the reply-to on this email!?
    email = user.email
    snappy_subject = generate_snappy_subject(report=report)
    if not snappy_subject:
        snappy_subject = default_subject_text
    msg = Message(snappy_subject, sender = app.config['MAIL_USERNAME'], recipients = [email])
    msg.body = f'{salutation_text}\n' \
               f"{timerange_text}\n" \
               f"{report}\n" \
               f"{signature_text}\n" \
               f"{footer_text}\n"
    test_print(report=report, snappy_subject=snappy_subject, un=user.username, email=email)
    mail.send(msg)
    logging.info(f'==> ++++++++++ {snappy_subject} - report sent +++++++++++')


def test_print(report, snappy_subject, un, email):
    tp =  f'Alerts Report\n'
    tp += f'email: {email}\n'
    tp += f'snappy_subject: {snappy_subject}\n'
    tp += f'un: {un}\n'
    tp += f'report: {report}\n'
    ### print(tp)
    logging.info(tp)


def one_off_report_to_user(username_str):
    """ few checks, just force an alert out for that user """
    now = datetime.now()
    testing = True
    logging.info(f'==> ++++++++++ one-off alert starting against user "{username_str}" +++++++++++')
    with app.app_context():
        query = User.query.filter(User.username == username_str)
        user = query.first()  # Returns a single User object or None
        if not user:
            logging.warning(f'==> ++++++++++ user "{username_str}" not found +++++++++++')
            return False
        if not user.enable_notifications:
            logging.warning(f'==> ++++++++++ user.enable_notifications == False +++++++++++')
            return False
        if testing:
            user.last_sent = now - timedelta(days=10)
            print(f'In test mode - dropped last_sent to {user.last_sent}')
        report = create_report(user=user)
        if report:
            send_report_to_user(report=report, user=user, now=now)
            user.last_sent = now
            db.session.commit()
        else:
            logging.info(f'==> ++++++++++ blank report generated, nothing to send +++++++++++')
    logging.info(f'==> ++++++++++ one-off alert done +++++++++++\n')
    return True


def create_send_alerts():
    logging.info(f'')
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
                        send_report_to_user(report=report, user=user, now=now)
                        user.last_sent = now
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
