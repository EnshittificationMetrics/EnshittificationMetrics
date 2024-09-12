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
from app.models import Entity
from dotenv import load_dotenv
# pipenv install duckduckgo-search langchain-community
from langchain_community.tools import DuckDuckGoSearchRun
# from langchain_community.tools import DuckDuckGoSearchResults
# from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
# pipenv install wikipedia
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
import html5lib
import json
import requests


llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25


CREATE_CONTENT_TEMPLATE = """
Entity is: "{entity}"

For this entity need to write up:
a summary, 
the date entity started, 
date entity ended (none if still current), 
corporate "family" (umbrella) if any, and 
category, if any.

Summary needs to be severely limited in length. 
The maximum summary size which will be stored in database is 1024 characters; 
however for aesthetics and readability in form where summary will be displayed, 
summary size should be 160 characters or less. 
Summary is what the gist of the entity is, what it's about, what it exists to do, its mission. 

Dates are to be in YYYY-MMM-DD format where YYYY is four digit year, MMM is three character month abbreviation, and DD is two (or one) digit day of month. 
Date entity started can be "UNK" if unknown or undetermineable, 
just year if just year and not month and day can not be determined, 
or just year and month if day can not be determined.
For date entity ended return "None" is entity is current and continues to exist.

For corporate family return corporate parent name, "None" if not a subsidiary or child corp, or "UNK" if undetermineable.

For category return "social" if a social media platform, "cloud" if a cloud provider, or "None" if neither of these categories.

Format response _must_ be json, like: 
{{
  "summary": "This is the summary.", 
  "date_started": "2024 JUL 04", 
  "date_ended": "None", 
  "corp_fam": "None", 
  "category": "None"
}}

To obtain date(s), category, family, and summary - relevant Wikipedia page, corporate homepage, and Duck Duck Go search results are provided.

Content pulled from Wikipedia may be incorrect or partially incorrect as containing undisambiguationed hits of the entity name; 
Relevant Wikipedia page content: {wikipedia_page_results} \n

Content from search may be incorrect or partially incorrect due to multiple different hits for a single entity name; 
Duck Duck Go search result content: {ddg_results} \n

For entity "{entity}" return summary, date_started, date_ended, corp_fam, and category.
"""
 

def create_content(name):
    summary = None
    date_started = None
    date_ended = None
    corp_fam = None
    category = None
    wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
    wikipedia_page_results = wikipedia.run(f'about {name} corp')
    search = DuckDuckGoSearchRun()
    ddg_results = search.run(f'about {name} corp')
    logging.info(f'==> wikipedia_page_results results for {name}: {wikipedia_page_results}.')
    logging.info(f'==> ddg_results results for {name}: {ddg_results}.')
    content_prompt = ChatPromptTemplate.from_template(CREATE_CONTENT_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    content = chain.invoke({"entity": name, 
                            "wikipedia_page_results": wikipedia_page_results, 
                            "ddg_results": ddg_results})
    logging.info(f'==> Raw content return (which should be json) for {name}:\n{content}')
    # extract the content between first '{' and last '}' as LLM tends to be chatty and bookend the needed json with intro and explanation
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and start < end:
        content = content[start:end + 1]
        logging.info(f'==> Content btwn first open and last close curly bracket (which should be only json) for {name}:\n{content}')
    try:
        data = json.loads(content)
        summary = data.get('summary')
        date_started = data.get('date_started')
        date_ended = data.get('date_ended')
        corp_fam = data.get('corp_fam')
        category = data.get('category')
    except Exception as e:
        summary = None
        logging.info(f'==> For {name}, unable to process return from LLM into needed variables; got error: {e} ')
    return summary, date_started, date_ended, corp_fam, category


def large_lang_model(query):
    large_lang_model = ChatMistralAI(model_name = 'open-mixtral-8x7b', 
                                     mistral_api_key = llm_api_key, 
                                     temperature = llm_temp, 
                                     verbose = True )
    return large_lang_model


def parse_for_blanks():
    with app.app_context():
        entities = Entity.query.all()
        for entity in entities:
            if entity.status != 'disabled':
                if entity.summary:
                    continue
                # if entity is not disabled, and has a blank summary, then try to fill in blanks
                summary, date_started, date_ended, corp_fam, category = create_content(name = entity.name)
                if not summary:
                    # if summary comes back None, then go to next entity
                    logging.info(f'==> Tried, but unable to get content for {entity.name}. ')
                    continue
                entity.summary = summary
                entity.date_started = date_started
                entity.date_ended = date_ended
                if not entity.corp_fam:
                    entity.corp_fam = corp_fam
                if not entity.category:
                    entity.category = category
                db.session.commit()
                logging.info(f'==> Populated blanks for {entity.name}:\n summary = {summary}\n date_started = {date_started}\n date_ended = {date_ended}\n corp_fam = {corp_fam}\n category = {category}')
    return None


def main():
    logging.info(f'==> +++++++++ starting populate_blanks.py +++++++++++')
    parse_for_blanks()
    logging.info(f'==> ++++++++++ ending populate_blanks.py +++++++++++')

if __name__ == "__main__":
    main()


