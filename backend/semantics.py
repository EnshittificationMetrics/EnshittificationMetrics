#!/usr/bin/env python

import os
import sys
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    mode = 'prod'
    sys.path.append('/var/www/em')
    logpath = '/home/bsea/em/scrape.log'
else:
    mode = 'dev'
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
    logpath = './scrape.log'
logging.basicConfig(level=logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format='%(asctime)s -%(levelname)s - %(message)s')

from app import app, db
from app.models import Entity, News
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_mistralai.chat_models import ChatMistralAI
# from langchain_community.llms import Ollama
import re
import requests
import socket
import math
from datetime import datetime, timezone
from populate_blanks import create_timeline_content, create_data_map_content
import dateparser

hostn = socket.gethostname()

# posts on judgments made
ntfypost = False
alert_title = f'EM on {hostn} judgment'

llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25

# Exponential decay factor
# Controls how fast weights decay with time
# Smaller values = faster decay
decay_factor = 30

JUDGMENT_TEMPLATE = """
Judge the enshittification stage of the entity/entities: {entities}.
(Note that there may be some tricky entity names, for example: 
"X" is what "Twitter" was renamed to and is often referred to as "X, formerly Twitter" as just the letter x is vague and may not be referring to the entity at all, 
"Nothing" is a common word, so will need to reference content to see if this is the smartphone hardware vendor or not, 
"EA" is a common letter combination, so need to reference content to see if this is the video game company or not, 
"Ring" is a common word, so reference content to see if this is the smart doorbell company or not.)
(Do not 'blame the messenger', a news story might be delivered on X or on Slashdot, 
as such this is just the news aggregator, not the entity to be judged; be sure to check this.)
Enshittification stages / life-cycle is defined as follows.
"None"    - Irrelevant text insofar as enshittification.
"Stage 1" - Attraction - great UX; innovation and features
"Stage 2" - Monetization - introduce ads, premium features, subscription models; increased data collection
"Stage 3" - Exploitation - algorithms tweaked for revenue, terms for creators less favorable, intrusive ads, paywalls
"Stage 4" - Exodus - dissatisfied users, negative reviews, migration to alternatives, platform doubles down on profit maximization
Note that true/false flag for the word enshittification, or some variant, in this text is {enshit_hit}.
Return "None", "Stage 1", "Stage 2", "Stage 3", or, "Stage 4". Please start response with none or stage number, then can follow with optional explanation. 
Please provide a judgment (and any justification) for all the entities involved at once in a individual numerical stage value.
Text to judge follows. 
{text}
"""


SUMMARY_TEMPLATE = """
Provide a brief one or two sentence summary of the text. 
Summary will be show by, or in mouse-over, link to full item. 
Summary should get at the nature of the meaning, or gist, or heart, of the text. 
Text to summarize follows. 
{text}
"""


def semantic_judgment(enshit_hit, text, entities):
    logging.info(f'==> +++++++++ semantic_judgment +++++++++++')
    prompt_judgment = ChatPromptTemplate.from_template(JUDGMENT_TEMPLATE)
    chain = ( prompt_judgment
            | large_lang_model 
            | StrOutputParser() 
            )
    stage = chain.invoke({"entities": entities, "enshit_hit": enshit_hit, "text": text})
    # to invoke runable w/ >1 var pass as dict
    return stage


SINGLE_JUDGMENT_TEMPLATE = """
Judge the enshittification stage of the specific entity {entity} based on the news item text.

Please return valid JSON with NO additional text; 
"skip" is a true/false boolean, 
"judgment" is an integer of value 1, 2, 3, or, 4, 
"notes" is an optional string - if using new line codes these must be escaped, 
like \\n (back-slash back-slash n) or \\r\\n (back-slash back-slash r back-slash back-slash n).
(Underscore characters, if used, do NOT get a backslash escape, as this will break JSON loads.)

Example JSON response:
{{
  "skip": true, 
  "judgment": 0, 
  "notes": "Don't blame the messenger! Entity X simply vehicle sharing the story, Y is the enshittification agent here."
}}

Example JSON response:
{{
  "skip": false, 
  "judgment": 3, 
  "notes": "Clear situation of pitting service customers and service providers on this platform against each other so as to make more money for the platform."
}}

Example JSON response:
{{
  "skip": false, 
  "judgment": 2, 
  "notes": ""
}}

Setting "skip" to true will skip over and NOT assign any judgment to {entity} for this situation. 
(Other entities may be judged on their own separate pass.)
Setting "skip" to false will assign a judgment to {entity} for this situation. (Either {stage_judgement} or what is assigned in "judgment".)
Set "judgment" to 1, 2, 3, or, 4, to override default of {stage_judgement} (in this case); 
"judgment" is only germane if "skip" is true, otherwise can set to 0 (zero) or even leave blank.
Value of "notes" is not shared with users, it is only used internally by site administrators, 
some human in the loop, or possibly other GenAI processes.

Do not 'blame the messenger', a news story might be delivered on X or on Slashdot, 
as such this is just the news aggregator, not the entity to be judged; be sure to check this.

Enshittification stages / life-cycle is defined as follows.
0 - Irrelevant text insofar as enshittification.
1 - Attraction - great UX; innovation and features
2 - Monetization - introduce ads, premium features, subscription models; increased data collection
3 - Exploitation - algorithms tweaked for revenue, terms for creators less favorable, intrusive ads, paywalls
4 - Exodus - dissatisfied users, negative reviews, migration to alternatives, platform doubles down on profit maximization

Authoritative notes on {entity} to help guide judgment:
{seed}

Today is {date_today}, this news story text date is {news_date}.

Previous LLM inference judgment about this same text but against all listed entities is {stage_judgement}.

Text to judge: 
{text}
"""


def single_semantic_judgment(text, entity_name, seed, stage_int_value, date):
    logging.info(f'==> +++++++++ single_semantic_judgment - against {entity_name} +++++++++++')
    prompt_judgment = ChatPromptTemplate.from_template(SINGLE_JUDGMENT_TEMPLATE)
    chain = ( prompt_judgment
            | large_lang_model 
            | JsonOutputParser() 
            )
    try:
        single_judgment = chain.invoke({"entity": entity_name, 
                                        "text": text, 
                                        "seed": seed, 
                                        "stage_judgement": stage_int_value, 
                                        "news_date": date, 
                                        "date_today": datetime.now(timezone.utc)})
    except Exception as e:
        logging.error(f'LLM single_semantic_judgment INVOKE failed w/ error {e}')
        single_judgment = {"skip": True, "judgment": 0, "notes": "LLM single_semantic_judgment invoke failed"}
    # needs to return False, 1, 2, 3, or, 4
    try:
        skip = single_judgment.get('skip')
        judgment = single_judgment.get('judgment')
        notes = single_judgment.get('notes')
    except Exception as e:
        logging.error(f'Reading from LLM JSON reply failed w/ error {e}')
        skip = True
        judgment = 0
        notes = "Reading from LLM JSON reply failed"
    logging.info(f'Skip = {skip}; judgment = {judgment}; notes = {notes}')
    if skip:
        return False # return False to skip judging this entity
    else:
        return judgment


def write_summary(text):
    logging.info(f'==> +++++++++ write_summary +++++++++++')
    prompt_summary = ChatPromptTemplate.from_template(SUMMARY_TEMPLATE)
    chain = ( prompt_summary 
            | large_lang_model 
            | StrOutputParser() 
            )
    summary = chain.invoke(text)
    return summary


def large_lang_model(query):
    large_lang_model = ChatMistralAI(model_name = 'open-mixtral-8x7b', 
                                     mistral_api_key = llm_api_key, 
                                     temperature = llm_temp, 
                                     verbose = True )
    # large_lang_model = Ollama(model = 'mistral', 
    #                           temperature = llm_temp, 
    #                           verbose = True )
    return large_lang_model


def semantic_processing(title, url, date, content):
    logging.info(f'==> +++++++++ semantic_processing +++++++++++')
    judgment = ''
    """ look for enshit* in text """
    enshit_hit = False
    text = title + '\n' + content
    pattern = r'enshit'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        enshit_hit = True
        judgment += f'Got hit for enshit* term! '
    """ pull entity names from DB, look for them in text """
    with app.app_context():
        entities = Entity.query.all()
        items = []
        for result in entities:
            if result.status != 'disabled':
                items.append(result.name)
        # was, before weeding out disableds: items = [result.name for result in entities]
    escaped_items = [re.escape(item) for item in items]
    pattern = '|'.join(escaped_items)
    logging.info(f'==> Entities searching for in post text: {pattern}') ### Comment this logging if all works and it clutters up scrape.log too much
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        """ if no relevant entity listed, do nothing """
        judgment += f'No relevant entity listed. '
        return judgment
    entities = remove_duplicates(input_list = matches)
    judgment += f'Got hit(s) for {str(entities)}. '
    """ send text to LLM for semantic judgment """
    stage = semantic_judgment(enshit_hit = enshit_hit,
                              text = text, 
                              entities = entities)
    pattern = r'(stage 1|stage 2|stage 3|stage 4)'
    matches = re.search(pattern, stage, re.IGNORECASE)
    if not matches:
        judgment += f'Judged irrelevant to enshittification: {stage}. '
        return judgment
    ### want to do something more if enshit_hit is True yet judgment returns None - like create a news item and make an entity set as potential.
    judgment += f'judgment rendered: {stage}. '
    """ write up a summary """
    summary = write_summary(text)
    stage_str_from_llm = matches[0]
    stage_int_value = int(stage_str_from_llm[-1]) # convert from str 'stage 1' to int '1'
    """ add news item to DB """
    with app.app_context():
        new_record = News(date_pub = date, 
                          url = url, 
                          text = title, ### is this including 'post_text'? where is the title combine w/ URL in parens? (need to add a space)
                          summary = summary, 
                          ent_names = entities, # entities includes count of # of items
                          judgment = judgment, 
                          stage_int_value = stage_int_value)
        db.session.add(new_record)
        db.session.commit()
        """ Add news item's id to each entity's stage_history """
        news_item_id = new_record.id
        for entity in entities:
            per_ent_stage_judge = stage_int_value # this line may be frivolous
            record = Entity.query.filter_by(name=entity).first()
            if record:
                """ call here to check story and judgment against each entity; "continue" if not relevant, otherwise do code below """
                per_ent_stage_judge = single_semantic_judgment(text = text, entity_name = entity, seed = record.seed, stage_int_value = stage_int_value, date = date)
                if per_ent_stage_judge == False:
                    logging.info(f'Skipping for judgment against {entity}')
                    continue
                else:
                    if not ( (per_ent_stage_judge == 1) or (per_ent_stage_judge == 2) or (per_ent_stage_judge == 3) or (per_ent_stage_judge == 4) ):
                        per_ent_stage_judge = stage_int_value
                """ add stage to entity stage history """
                logging.info(f'Processing "{entity}" to add stage to entity stage_history and update stage_current.')
                if record.stage_history is None:
                    record.history = []
                record.stage_history.append([date, per_ent_stage_judge, news_item_id]) 
                """ set entity stage """
                record.stage_current = weighted_avg_stage_hist(record.stage_history)
                # record.stage_current = stage_int_value # older code prior to weighted_avg_stage_hist
                
                ### add code to from "Entity.stage_history" pop oldest stuff off list when gets too big (but don't pop foundationals)
                ### instead of just popping oldest - if over 15 or 20 datapoints/linked news items for an entity, pair down to 10 or 12
                ### asking LLM which 10 to keep of 15 existing; this is less LLM calls/data then doing which 10 of 11 five times
                ### then have to archive news item if no longer referenced by any entity.
                
                """ update (or make for first time) entity timeline to reflect new stage_current and new linked news item"""
                timeline = create_timeline_content(record)
                if timeline:
                    record.timeline = timeline
                    logging.info(f'set timeline to: {timeline}') ### comment out if log is too busy - keep "Raw LLM content return" log in populate_blanks.py
                """ if needed, transition entity from potential to live with stage population """
                if record.status == 'potential':
                    record.status = 'live'
                    logging.info(f'set status from potential to live')
                """ generate new data_map for entity as stuff has changed """
                record.data_map = create_data_map_content(record)
                alert_data = f'Set {entity} to stage {record.stage_current} (weighted avg), due to new news of stage {per_ent_stage_judge}! '
                judgment += alert_data
                alert_data += f'(Per text from "{title}" referencing "{url}".) '
                alert_data += f'New "{entity}" timeline: {timeline}'
                logging.info(f'EM judgment: {alert_data}')
                ### alert_title += f' {stage_int_value}' # doesn't work - UnboundLocalError: cannot access local variable 'alert_title' where it is not associated with a value
                if ntfypost: requests.post('https://ntfy.sh/000ntfy000EM000', 
                    headers={'Title' : alert_title}, data=(alert_data))
        db.session.commit()
    return judgment


def weighted_avg_stage_hist(stage_values):
    # updated format and structure
    #   each (mutable) list item in stage_values should be [0] date (datetime type in str type?), [1] stage value (int), [2] news item ID (int)
    #   ex: [ ['2025-01-22 00:00:00', 2, 813], ['2025-01-28 00:00:00', 2, 853], ['2025-02-06 00:00:00', 3, 903], ] 
    # original format and structure
    #   each (mutable) list item in stage_values should be date (str %Y-%b-%d) and stage value (int) pair
    #   ex: [['2024-AUG-17', 2], ['2024-AUG-18', 1], ['2024-SEP-06', 3], ['2024-SEP-06', 1], ['2024-SEP-09', 3], ['2024-SEP-11', 3]]
    #   most_recent_date = max([datetime.strptime(entry[0], '%Y-%b-%d').date() for entry in stage_values])
    #   time_diff = (most_recent_date - datetime.strptime(date, '%Y-%b-%d').date()).days
    ### logging.info(f'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    ### logging.info(f'check why dateparser throws TypeError: Input type must be str')
    ### for entry in stage_values:
    ###     logging.info(f'value: {entry[0]} - type{type(entry[0])}')
    ### logging.info(f'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    most_recent_date = max([dateparser.parse(str(entry[0])).date() for entry in stage_values]) # added str() as sometimes threw TypeError: Input type must be str
    total_weighted_value = 0
    total_weight = 0
    for date, value, *rest in stage_values:
        news_item_id = rest
        # Calculate time difference in days
        time_diff = (most_recent_date - dateparser.parse(str(date)).date()).days
        # Calculate weight using exponential decay (more recent = higher weight)
        weight = math.exp(-time_diff / decay_factor)
        # Accumulate weighted value and weight
        if type(value) == str:
            value = int(value[-1]) # Catches some old entries where str "Stage 2" is instead of int "2"
        total_weighted_value += value * weight
        total_weight += weight
    weighted_average = total_weighted_value / total_weight if total_weight != 0 else 0
    # round float and keep btwn 1 and 4 (integer 1, 2, 3, or, 4)
    stage_value = max(1, min(round(weighted_average), 4))
    logging.info(f'1. Will remove these four logging lines once monitored and tuned; decay_factor: {decay_factor}')
    logging.info(f'2. stage_values: {stage_values}')
    logging.info(f'3. weighted_average: {weighted_average}')
    logging.info(f'4. stage_value: {stage_value}')
    return stage_value


def remove_duplicates(input_list):
    unique_list = []
    for item in input_list:
        if item not in unique_list:
            unique_list.append(item)
    return unique_list
