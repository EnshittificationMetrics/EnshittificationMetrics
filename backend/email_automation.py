#!/usr/bin/env python

""" Check email in and perform action as able and send email as appropriate """

crontab = """ 50 0-22/2 * * * cd /home/bsea/em/ && pipenv run python3 email_automation.py      >> /home/bsea/em/email_automations.log 2>&1 """

import os
import sys
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    sys.path.append('/var/www/em')
    logpath = '/home/bsea/em/email_automations.log'
else:
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
    logpath = './email_automations.log'
logging.basicConfig(level=logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format='%(asctime)s -%(levelname)s - %(message)s')
from app import app, db
from app.models import User
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.policy import default
from email.utils import parsedate_to_datetime
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
import re
import socket

load_dotenv('.env')

# LLM stuff
llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25

SMTP_TO_USE = "sendgrid" # "sendgrid" or "smtp"

# Email Server Settings
IMAP_SERVER   = os.getenv('IMAP_SERVER')
if SMTP_TO_USE == "smtp":
    import smtplib
    MAIL_SERVER   = os.getenv('MAIL_SERVER') # SMTP
    SMTP_SSL_PORT = os.getenv('SMTP_SSL_PORT')
elif SMTP_TO_USE == "sendgrid":
    import sendgrid
    # was from sendgrid.helpers.mail import *, but Email conflicted w/ import email
    from sendgrid.helpers.mail import To, Content, Mail
    from sendgrid.helpers.mail import Email as SGEmail
    sendgrid_api_key=os.environ.get('SENDGRID_API_KEY')
    sg = sendgrid.SendGridAPIClient(sendgrid_api_key)
else:
    logging.error(f'SMTP_TO_USE set impropperly to "{SMTP_TO_USE}"; needs to be "smtp" or "sendgrid"')

# Email Account Details
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
INBOX_NAME    = os.getenv('INBOX_NAME')
SENT_BOX_NAME = os.getenv('SENT_BOX_NAME') # "Sent" or "[Gmail]/Sent Mail" or "INBOX.Sent"
JUNK_BOX_NAME = os.getenv('JUNK_BOX_NAME')
HITL_BOX_NAME = os.getenv('HITL_BOX_NAME')
LLM_BOX_NAME = os.getenv('LLM_BOX_NAME')


def fetch_unseen_imap():
    """ only reads single unseen """
    """ Connect to an IMAP server, authenticate """
    current_date = datetime.now(timezone.utc)
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        mail.login(MAIL_USERNAME, MAIL_PASSWORD)
        mail.select(INBOX_NAME)
        from_header = 'no email'
        subject = 'no email'
        body = 'no email'
        date_sent = 'no email'
        spoof = ''
        remaining = 0
        email_uid = ""
        # Search for unread emails
        status, email_ids = mail.uid("search", None, "UNSEEN") # get UID # was status, messages = mail.search(None, "UNSEEN") # get MSN (Message Sequence Number)
        email_ids = email_ids[0].split() # was email_ids = messages[0].split()
        if email_ids:
            remaining = len(email_ids) - 1
            """ Fetches the oldest unread email """
            oldest_unread_email_id = email_ids[0] # [0] to fetch the oldest unread email, whereas [-1] would be the newest
            status, msg_data = mail.uid("fetch", oldest_unread_email_id, "(RFC822)") # use of RFC822 auto-marks email as read! # was status, msg_data = mail.fetch(oldest_unread_email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1], policy=default) # Extract & clean email content
                    """ extracts key headers. """
                    email_uid = oldest_unread_email_id.decode() # Convert UID from bytes to string
                    date_sent = str(msg["Date"]) # convert _UniqueDateHeader to a str
                    from_header = msg["From"]
                    from_header_match = re.search(r"<([^<>]+)>", from_header)
                    from_header = from_header_match.group(1) if from_header_match else from_header
                    logging.info(f'Processing email UID {email_uid} sent {date_sent} from {from_header}')
                    return_path = msg["Return-Path"]
                    return_path_match = re.search(r"<([^<>]+)>", return_path)
                    return_path = return_path_match.group(1) if return_path_match else return_path
                    received_headers = msg.get_all("Received")
                    dkim_header = msg["DKIM-Signature"]
                    spf_header = msg["Authentication-Results"]
                    # spoof checks
                    if from_header != return_path:
                        spoof += f'Potential Spoofing: From "{from_header}" and Return-Path "{return_path}" do not match! '
                    # If the sending domain (From address) and IP location don't match, it could be a spoof.
                    ### this section doesn't work quite right - gets for example, sending_domain == "LAPTOP-VLGID64J" and sending_ip == 192.168.50.180
                    ### sender_domain = from_header.split("@")[-1]
                    ### if received_headers:
                    ###     first_received = received_headers[-1]  # The first Received header in the chain
                    ###     ip_match = re.search(r"\[([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\]", first_received)
                    ###     if ip_match:
                    ###         sending_ip = ip_match.group(1)
                    ###         # Get the domain of the sending IP
                    ###         try:
                    ###             sending_domain = socket.gethostbyaddr(sending_ip)[0]
                    ###         except socket.herror:
                    ###             sending_domain = "Unknown"
                    ### if sender_domain.lower() not in sending_domain.lower():
                    ###     spoof += f'Possible Spoofing Detected: Sender domain "{sender_domain}" and sending IP domain "{sending_domain}" do not match! Sending IP is {sending_ip}. '
                    if not dkim_header:
                        spoof += "No DKIM Signature: Email may be spoofed! "
                    if "spf=fail" in spf_header.lower():
                        spoof += f'SPF Failed: This email may be spoofed! "{spf_header}". '
                    if parsedate_to_datetime(date_sent) > current_date + timedelta(days = 2 * 365.25):
                        spoof += f'Likely SPAM - date at least two years in future; {date_sent}. '
                    """ parses subject & body (handles plain text & multipart emails) """
                    subject, encoding = decode_header(msg["Subject"])[0]
                    subject = subject.decode(encoding or "utf-8") if isinstance(subject, bytes) else subject
                    # Extract email content
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore") # was .decode(), this should avoid some crashes
                                break  # Only read the first plain-text part
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                    break  # Only process the first unread email
        else:
            remaining = 0
        # mail.logout() # dont' needs as using with
    return email_uid, from_header, subject, body, date_sent, spoof, remaining


def send_email(email_to, email_subj, email_body):
    """ Send via SMTP & Store via IMAP """
    """ If provider does not automatically store sent emails, need to save them manually using IMAP """
    logging.info(f'Sending email to {email_to}')
    # Set email content - for both smtp and save imap sent
    msg = MIMEText(email_body)
    msg["From"] = MAIL_USERNAME
    msg["To"] = email_to
    msg["Subject"] = email_subj
    if SMTP_TO_USE == "smtp":
        # Send via SMTP
        with smtplib.SMTP_SSL(MAIL_SERVER, SMTP_SSL_PORT) as smtp:
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            failed_recipients = smtp.sendmail(MAIL_USERNAME, email_to, msg.as_string())
            if failed_recipients:
                logging.error(f"Some recipients failed: {failed_recipients}")
                ### should do something else here, resend later, or abort and set the inbound email to unread again for the next script run
            else:
                logging.info("Email successfully handed off to SMTP server.")
    elif SMTP_TO_USE == "sendgrid":
        from_email = SGEmail(MAIL_USERNAME)
        to_email = To(email_to)
        subject = email_subj
        content = Content('text/plain', email_body)
        mail = Mail(from_email, to_email, subject, content)
        send_attempts = 0
        not_sent = True
        while not_sent:
            response = sg.client.mail.send.post(request_body=mail.get())
            send_attempts += 1
            rspns = response.status_code # int; 200 = No error, 201 = Successfully created, 202 = Accepted, 204 = Successfully deleted, 4xx status codes indicate a client-side error, 5xx status codes which indicate server-side errors
            if rspns < 300:
                logging.info(f'response.status_code: {rspns}')
                not_sent = False
                # logging.info(f'response.body: {response.body})
                # logging.info(f'response.headers: {response.headers})
            else:
                logging.error(f'response.status_code: {rspns}')
                time.sleep((2 + send_attempts) * 60)
                if send_attempts >= 5:
                    not_sent = False
                    logging.info(f'==> ++++++++++ Email NOT sent, tried {send_attempts} +++++++++++')
    else:
        logging.error(f'SMTP_TO_USE set impropperly to "{SMTP_TO_USE}"; needs to be "smtp" or "sendgrid"')
    # Save Sent Email to IMAP "Sent" Folder
    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        mail.login(MAIL_USERNAME, MAIL_PASSWORD)
        mail.select(f'"{SENT_BOX_NAME}"')
        # Append email to Sent folder
        mail.append(SENT_BOX_NAME, None, None, msg.as_bytes())
        # None, None → Flags (e.g., "\Seen" can be used if needed).
        # msg.as_bytes() → Converts the email into RFC822 format for saving.
    return None


    ### """ code to, before sending, check if the recipient's server accepts the email """
    ### with smtplib.SMTP_SSL(MAIL_SERVER, SMTP_SSL_PORT) as smtp:
    ###     smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
    ###     code, response = smtp.rcpt(email_to)
    ###     if code != 250:
    ###         logging.error(f"Recipient rejected: {response.decode()}")
    ###     else:
    ###         logging.info(f"Recipient accepted: {response.decode()}")
    ###     failed_recipients = smtp.sendmail(MAIL_USERNAME, email_to, msg.as_string())


def list_available_IMAP_folders():
    """ for testing to figure out names of folders """
    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        mail.login(MAIL_USERNAME, MAIL_PASSWORD)
        status, folders = mail.list()
        print("IMAP Folders:")
        for folder in folders:
            print(folder.decode())  # Decode bytes to string


def disable_users_alerts(target):
    """ pull up user via email address and set alerts to False """
    with app.app_context():
        query = User.query.filter(User.email == target)
        user = query.first()  # Returns a single User object or None
        if user:
            if user.enable_notifications == True:
                try:
                    user.enable_notifications = False
                    db.session.commit()
                    mess = "Enshittification Notification Alerts turned OFF! "
                except Exception as e:
                    logging.warning(f'In trying to set notifications off for "{target}" got error: {e}')
                    mess = "UNABLE to turn alerts off programmatically... "
            else: # user not enabled
                mess = "Enshittification Notification Alerts are already OFF... "
        else: # user not found
            mess = f'Curiously, no user for email "{target}" found, NO changes made... '
    logging.info(f'For user {user.username} (ID #{user.id}), {mess}')
    return mess


def move_email(email_from, email_uid, email_to, mark_unread):
    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        mail.login(MAIL_USERNAME, MAIL_PASSWORD)
        status, _ = mail.select(email_from)
        if status != "OK":
            raise Exception(f"Failed to select source folder: {email_from}")
        status, email_ids = mail.uid("search", None, f"UID {email_uid}")
        if email_ids[0]:
            email_id = email_ids[0].split()[0] # Extract the actual email UID
            # Copy email to the target folder
            status, _ = mail.uid("copy", email_id, email_to)
            if status != "OK":
                raise Exception(f"Failed to copy email to {email_to}")
            if mark_unread:
                # Mark email as unread in the target folder
                status, _ = mail.select(email_to)
                if status != "OK":
                    raise Exception(f"Failed to select target folder: {email_to}")
                status, new_email_ids = mail.uid("search", None, "ALL")
                if status != "OK" or not new_email_ids[0]:
                    raise Exception("Failed to find copied email in target folder.")
                new_email_uid = new_email_ids[0].split()[-1] # last added email should be copied one
                mail.uid("store", new_email_uid, "-FLAGS", "\\Seen") # Remove \Seen flag (mark as unread)
            # Delete original email from INBOX (to complete move)
            status, _ = mail.select(email_from)
            if status != "OK":
                raise Exception(f"Failed to re-select source folder: {email_from}")
            mail.uid("store", email_id, "+FLAGS", "\\Deleted") # Mark as deleted
            mail.expunge() # Permanently remove deleted emails


def large_lang_model(query):
    large_lang_model = ChatMistralAI(model_name = 'open-mixtral-8x7b', 
                                     mistral_api_key = llm_api_key, 
                                     temperature = llm_temp, 
                                     verbose = True )
    return large_lang_model


EMAIL_REPLY_ACTION_TEMPLATE = """
Can you compose a reasonable reply end-user's email?
You are essentially: a calm, polite, technical, customer support agent, representing enshittificationmetrics.com.

Please return valid JSON with NO additional text; 
"replyable" and "disablealerts" are booleans, 
"reply" and "notes" are strings, where if using new line codes these must be escaped, 
like \\n (back-slash back-slash n) or \\r\\n (back-slash back-slash r back-slash back-slash n).
(Underscore characters, if used, do NOT get a backslash escape, as this will break JSON loads.)

Example JSON response:
{{
  "replyable": false, 
  "disablealerts": false, 
  "reply": "NA", 
  "notes": "Unable to confidently understand what the user was talking about."
}}

Example JSON response:
{{
  "replyable": true, 
  "disablealerts": true, 
  "reply": "Salutations, \\r\\nThank you for your email. \\nUnderstand you appreciate the emailed alerts but want to pause them for a bit. \\nHave initiated disabling your alerts. \\r\\nHave a great day! \\nEnshittificationMetrics.com Team", 
  "notes": "User requested that Enshittification Metrics notification alerts be disabled. They like them, but need to pause them for a bit and will manually re-enable them on the website in a few weeks."
}}

Example JSON response:
{{
  "replyable": true, 
  "disablealerts": false, 
  "reply": "Greetings, \\r\\nThere is no need to reply to emailed OTP codes. \\nPlease simply request another code from on the Enshittification Metrics website; when you receive the code in email, enter it onto the appropriate form on the website. \\nThis validates that the email address is correct and controlled by you. \\r\\nThanks for using the site! \\nEnshittificationMetrics.com", 
  "notes": "NA"
}}

Example JSON response:
{{
  "replyable": true, 
  "disablealerts": false, 
  "reply": "Hi. \\r\\nUnderstand you received an unexpected OTP code. This should not happen. \\nBest practice would be to log into Enshittification Metrics website, check your registered email address, validate it if needed, change your password, and enable MFA as available. \\r\\nThanks, \\nEM", 
  "notes": "User claimed they never requested a code..."
}}

Setting "replyable" to true results in replying to the user's email with the content of "reply" as the email reply body. 
Setting "replyable" to false means not to send any email reply. 
Setting "disablealerts" to true initiates disabling alerts for the specific user. 
Setting "disablealerts" to false means to do nothing, leave the user's alert setting as is. 
Value of "reply" is sent as reply email content to user, assuming "replyable" is true. 
Value of "notes" is not shared with users, it is only used internally by site administrators, some human in the loop, or possibly other GenAI processes.

You are a GenAI inference tasked with ingesting email from a site user, trying to comprehend it, and generating a response.
You are representing enshittificationmetrics.com! If it's not crystal clear what the user is asking or stating, then do not reply. 
(You can reply stating you don't really understand what they're after, and request clarification or re-phrasing.) 
It is critical NOT to make up some answer. 
Don't say something is due to a system glitch (admits fault), or to look for an update shortly, 
or we're investigating or working on it (likely not true).
Don't say stuff just because it sounds good, or you think that's what the user wants to hear. 
Stick to the facts - worst case say, it is unfortunate you feel that way.
It is important to be polite and tactful, not to say anything potentially controversial or embarrassing, or which might get us sued or fined. 

Enshittification Metrics, www.enshittificationmetrics.com, is a site that gathers and displays enshittification metrics for (popular) tech platforms. 
Transparency and fairness in judgment and assignment of metric scores is a goal of this site; 
as such all judgment processes algorithms and LLM use are exposed - 
visit github.com slash EnshittificationMetrics to see all code in use. 
This site strives to be fully automated, enabling all news gathering and metrics value determinations to occur automatically 
by way of software code and generative-AI agentic functions. 
Our Ethics Board serves as critical human-in-the-loop; ensuring the autonomous metric gathering and reporting is reasonable and human-friendly.
The "EnshittificationMetrics.com" site is just an agent collecting and collating publicly available news articles and internet forum postings. 
Note that positive and constructive suggestions, comments, and discussion, are welcome on our sub Reddit r slash Enshitif underscore Metrics 
Branded gear is available at enshitif-metrics.printify.me/products. 
Enshittification (noun) - Coined by Cory Doctorow; transformation of a tech platform from a user-centric service to a profit-centric one. 
The Four Stages of the Downward Enshittification Spiral:
- Stage 1 - Attraction - great UX; innovation and features
- Stage 2 - Monetization - introduce ads, premium features, subscription models; increased data collection
- Stage 3 - Exploitation - algorithms tweaked for revenue, terms for creators less favorable, intrusive ads, paywalls
- Stage 4 - Exodus - dissatisfied users, negative reviews, migration to alternatives, platform doubles down on profit maximization

The current date is {current_date}.

Here is email from user: 
Date sent: {date_sent}
From email address: {from_header}
Email subject: {subject}
Email body content: 
{body}
"""


def main():
    salutation_text = f"""Salutations, \n"""
    signature_text = f"""Thanks, \nEnshittificationMetrics.com\n"""
    current_date = datetime.now(timezone.utc)
    logging.info(f'')
    logging.info(f'Starting email automations run')
    # loop thru getting oldest unseen emails from inbox till all read
    remaining = 0.5
    while remaining > 0:
        email_uid, from_header, subject, body, date_sent, spoof, remaining = fetch_unseen_imap()
        """ if there's no email there """
        if from_header == 'no email':
            continue
        """ If a spoofing email - ignore - log and move """
        if spoof:
            move_email(email_from = INBOX_NAME, email_uid = email_uid, email_to = JUNK_BOX_NAME, mark_unread = True)
            logging.warning(f'Email ignored! Moved to Junk. From {from_header} sent {date_sent} with subject {subject} flagged: {spoof}')
            continue
        """ Deal with replies to OTP codes """
        if "Your OTP Code" in subject:
            email_to = from_header
            email_subj = f'Re: {subject}'
            email_body = f"{salutation_text}\n" \
                         f"This is basically an un-monitored email box. \n" \
                         f"There's generally no need to reply to OTPs; just request another code sent in UI. \n" \
                         f"{signature_text}\n" \
                         f"\n~~~Forewarded text~~~\n" \
                         f"{body}"
            send_email(email_to = email_to, email_subj = email_subj, email_body = email_body)
            logging.info(f'Generic email reply to reply to OTP email sent.')
            continue
        """ Try to deal with replies to Notification Alert emails """
        if (subject.lower() == "stop" or subject.lower() == "unsubscribe") or (body.lower() == "stop" or body.lower() == "unsubscribe"):
            mess = disable_users_alerts(target = from_header)
            email_to = from_header
            email_subj = f'Re: {subject}'
            email_body = f"{salutation_text}\n" \
                         f"{mess} \n" \
                         f'To change / enable / disable alerts, please use the "Alert Subscriptions Notification Settings" ' \
                         f'area in EnshittificationMetrics.com, https://www.enshittificationmetrics.com/alerts. \n' \
                         f"{signature_text}\n" \
                         f"\n~~~Forewarded text~~~\n" \
                         f"{body}"
            send_email(email_to = email_to, email_subj = email_subj, email_body = email_body)
            logging.info(f'Alert Notifications turned off for {from_header}.')
            continue
        """ Send to LLM to try to figure out and respond """
        content_prompt = ChatPromptTemplate.from_template(EMAIL_REPLY_ACTION_TEMPLATE)
        chain = ( content_prompt
                | large_lang_model 
                | JsonOutputParser()
                )
        try:
            content = chain.invoke({"current_date": current_date, 
                                    "date_sent": date_sent, 
                                    "from_header": from_header, 
                                    "subject": subject, 
                                    "body": body})
        except Exception as e:
            logging.error(f'LLM email reply INVOKE failed w/ error {e}')
            content = {"replyable": False, "disablealerts": False, "reply": "NA", "notes": "LLM email reply invoke failed"}
        try:
            replyable = content.get('replyable')
            disable_alerts = content.get('disablealerts')
            reply = content.get('reply')
            notes = content.get('notes')
        except Exception as e:
            logging.error(f'Reading from LLM JSON reply failed w/ error {e}')
        if replyable:
            if disable_alerts:
                mess = disable_users_alerts(target = from_header)
                logging.info(f'Alert Notifications turned off for {from_header}.')
            else:
                mess = False
            email_to = from_header
            email_subj = f'Re: {subject}'
            email_body = f""
            if mess:
                email_body += f"{mess} \n"
            email_body += f'\n{reply}\n\n' \
                          f'\nNote: this response written by LLM.\n' \
                          f'To change / enable / disable alerts, please use the "Alert Subscriptions Notification Settings" ' \
                          f'area in EnshittificationMetrics.com, https://www.enshittificationmetrics.com/alerts. \n' \
                          f"\n~~~Forewarded text~~~\n" \
                          f"{body}"
            send_email(email_to = email_to, email_subj = email_subj, email_body = email_body)
            move_email(email_from = INBOX_NAME, email_uid = email_uid, email_to = LLM_BOX_NAME, mark_unread = False)
            logging.info(f'LLM authored reply which was sent! Email moved to LLM folder.')
            logging.info(f'reply content: {reply}')
            logging.info(f'LLM notes: {notes}')
            continue
        else: # not replyable
            # 5 hours window with cron every 2 hours should try each email 2 or 3 times
            if parsedate_to_datetime(date_sent) + timedelta(hours = 5) > current_date:
                """ email is fresh, mark unread again, leaving for next run of this script to try again """
                with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
                    mail.login(MAIL_USERNAME, MAIL_PASSWORD)
                    status, _ = mail.select(INBOX_NAME)
                    if status != "OK":
                        raise Exception(f"Failed to select source folder: {INBOX_NAME}")
                    mail.uid("store", email_uid, "-FLAGS", "\\Seen") # Remove \Seen flag (mark as unread)
                logging.info(f'LLM UNable to pen a reply; replyable = {replyable}')
                logging.info(f'LLM notes: {notes}')
                logging.warning(f'Email left unread for another try at next run; email from {from_header} sent {date_sent} with subject {subject} - please check it out.')
            else:
                """ email getting stale, flag for HITL """
                move_email(email_from = INBOX_NAME, email_uid = email_uid, email_to = HITL_BOX_NAME, mark_unread = True)
                logging.info(f'LLM UNable to pen a reply; replyable = {replyable}')
                logging.info(f'LLM notes: {notes}')
                logging.warning(f'Email moved to HITL folder; email from {from_header} sent {date_sent} with subject {subject} - please check it out.')
            continue
        """ dropped all the way thru with no meaning found and no action taken (technically should never get here) """
        move_email(email_from = INBOX_NAME, email_uid = email_uid, email_to = HITL_BOX_NAME, mark_unread = True)
        logging.warning(f'Email moved to HITL folder; no idea what to do with email from {from_header} sent {date_sent} with subject {subject} - please check it out.')
    ### should implement some check on mailbox size used, delete older Junk and read emails in Inbox and read emails in HITL
    logging.info(f'Ended email automations run')


if __name__ == "__main__":
    main()
