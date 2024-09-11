#!/usr/bin/env python

import os
import sys
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    mode = 'prod'
    sys.path.append('/var/www/em')
else:
    mode = 'dev'
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
from app import app, db
from app.models import Entity, News
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_mistralai.chat_models import ChatMistralAI
# from langchain_community.llms import Ollama
import re


llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25


JUDGMENT_TEMPLATE = """
Judge the enshittification stage of the entity/entities, {entities}.
Enshittification stages / life-cycle is defined as follows.
"None"    - Irrelevant text insofar as enshittification. 
"Stage 1" - Attraction - great UX; innovation and features
"Stage 2" - Monetization - introduce ads, premium features, subscription models; increased data collection
"Stage 3" - Exploitation - algorithms tweaked for revenue, terms for creators less favorable, intrusive ads, paywalls
"Stage 4" - Exodus - dissatisfied users, negative reviews, migration to alternatives, platform doubles down on profit maximization
Note that flag for the word enshittification, or some variant, in this text is {enshit_hit}.
Return "None", "Stage 1", "Stage 2", "Stage 3", or, "Stage 4". Please start response with none or stage number, then can follow with optional explanation. 
Text to judge follows. 
{text}
"""


SUMMARY_TEMPLATE = """
Provide a brief one or two sentence summary of the text. 
Summary will be show by, or in mouse-over, link to full item. 
Summary should get at the nature of the meaning, or gist, or heart, of the text. 
{text}
"""


def semantic_judgment(enshit_hit, text, entities):
    prompt_judgment = ChatPromptTemplate.from_template(JUDGMENT_TEMPLATE)
    chain = ( prompt_judgment
            | large_lang_model 
            | StrOutputParser() 
            )
    stage = chain.invoke({"entities": entities, "enshit_hit": enshit_hit, "text": text})
    # to invoke runable w/ >1 var pass as dict
    return stage


def write_summary(text):
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
    judgment = ''
    # look for enshit* in text
    enshit_hit = False
    text = title + '\n' + content
    pattern = r'enshit'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        enshit_hit = True
        judgment += f'Got hit for enshit* term! '
    # pull entity names from DB, look for them in text
    with app.app_context():
        entities = Entity.query.all()
        items = []
        for result in entities:
            if result.status != 'disabled':
                items.append(result.name)
        # items = [result.name for result in entities] # orig line before weeding out disableds
    escaped_items = [re.escape(item) for item in items]
    pattern = '|'.join(escaped_items)
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        # if no relevant entity listed, do nothing
        judgment += f'No relevant entity listed. '
        return judgment
    entities = remove_duplicates(input_list = matches)
    judgment += f'Got hit(s) for {str(entities)}. '
    # send text to LLM for semantic judgment
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
    summary = write_summary(text)
    with app.app_context():
        # add_news item to DB
        new_record = News(date_pub = date, 
                          url = url, 
                          text = title, 
                          summary = summary, 
                          ent_names = entities)
        db.session.add(new_record)
        # add data-point to entity in DB
        stage_str_from_llm = matches[0]
        stage_int_value = int(stage_str_from_llm[-1]) # convert from str 'stage 1' to int '1'
        for entity in entities:
            record = Entity.query.filter_by(name=entity).first()
            if record:
                record.stage_current = stage_int_value
                if record.stage_history is None:
                    record.history = []
                record.stage_history.append([date, stage_int_value])
        db.session.commit()
    return judgment


def remove_duplicates(input_list):
    unique_list = []
    for item in input_list:
        if item not in unique_list:
            unique_list.append(item)
    return unique_list

