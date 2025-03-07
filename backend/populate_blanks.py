#!/usr/bin/env python

"""
Finds all entities with blank summaries and tries to create content for them.
Queries Wikipedia and DDG.
Queries LLM for "summary", "date_started", "date_ended", "corp_fam", "category", "ent_url".
Limited to a max number of summaries, count_max_sm.

Finds all entities with blank timeline and tries to create content for them.
Limited to a max number of timelines, count_max_tl.

Finds all entities with no data map and tries to create content for them.
Limited to a max number of data maps, count_max_dm.

Finds all entities with no URL and tries to create content for them.
Limited to a max number of URLs, count_max_ur.

Code also run against entities with new news items linked to them.
Create / update timeline(s) for entities.
Reads (existing) "summary", "date_started", "date_ended", "corp_fam", "category"
If timeline reads new news items (for entity) since last timeline write.
If no timeline yet reads all news items (for entity).
generate new / updated timeline
fresh Queries to Wikipedia and DDG...
update if needed "summary", "date_started", "date_ended", "corp_fam", "category".
update if needed stage_current and stage_history.
Merges old and new timelines together.
"""

crontab = """00 10 * * *     cd /home/bsea/em/ && pipenv run python3 populate_blanks.py       >> /home/bsea/em/utilities/cron_issues.log 2>&1""" # prod
crontab = """#0 3 * * * cd /home/leet/EnshittificationMetrics/backend/ && pipenv run python3 populate_blanks.py >> /home/leet/EnshittificationMetrics/backend/scrape.log 2>&1""" # dev

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
# pipenv install duckduckgo-search langchain-community
   
from langchain_community.tools import DuckDuckGoSearchRun
### langchain_community/utilities/duckduckgo_search.py:64: UserWarning: 'api' backend is deprecated, using backend='auto'

# from langchain_community.tools import DuckDuckGoSearchResults
# from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
# pipenv install wikipedia
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
import html5lib
import json
from json import JSONDecodeError
import requests
from httpx import HTTPStatusError
# import graphviz # sudo apt install graphviz (for local display!?) # pipenv install graphviz (this is in Pipfile)
from datetime import datetime
import dateparser

llm_api_key = os.getenv('MISTRAL_API_KEY')
llm_temp = 0.25

# this script should end up being run daily
count_max_sm = 7 # max how many summaries to do
count_max_tl = 2 # max how many timelines to do - keep low as many tokens used
count_max_dm = 28 # max how many data maps to do - can be big as just DB and text process, no LLM calls
count_max_ur = 0 # max how many URLs to do


CREATE_SUMMARY_CONTENT_TEMPLATE = """
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
For date entity ended return "None" if entity is current and continues to exist.

For corporate family return corporate parent name, "None" if not a subsidiary or child corp, or "UNK" if undetermineable.

For category return 
"social" if a social media platform, 
"cloud" if a cloud provider, 
"B2B" if a business to business platform, 
"B2C" if a business to consumer platform, 
"C2C" if a consumer to consumer platform, 
"tech platform" if a tech stack platform (SaaS), 
"P2P" if a peer to peer platform, or, 
"None" if none of these categories.
(Multiple comma separated categories may be returned.)

For ent_url return the authoritative single main URL for the entity on the internet. 
If URL is not mentioned or it is not quite clear what it is, no guesses, just return "UNK".

Format response _must_ be json, like for example: 
{{
  "summary": "This is the summary.", 
  "date_started": "2024 JUL 04", 
  "date_ended": "None", 
  "corp_fam": "None", 
  "category": "None"
  "ent_url": "UNK"
}}

To obtain date(s), category, family, and summary - relevant Wikipedia page, corporate homepage, and Duck Duck Go search results are provided.

Content pulled from Wikipedia may be incorrect or partially incorrect as containing undisambiguationed hits of the entity name; 
Relevant Wikipedia page content: {wikipedia_page_results} \n

Content from search may be incorrect or partially incorrect due to multiple different hits for a single entity name; 
Duck Duck Go search result content: {ddg_results} \n

For entity "{entity}" return summary, date_started, date_ended, corp_fam, category, and, ent_url in JSON format.
"""


CREATE_TIMELINE_CONTENT_TEMPLATE = """
Entity is "{entity}"; we need to write up its timeline.
Current date is {current_date}.

A timeline is: 
* A condensed short story, like equivalent to a few paragraphs of text. (Our absolute max is 4096 characters.)  
* A brief overview history of "{entity}" from it's start to current, or start to finish, (or pre-start to prediction for the future). 
* A chronology of actions over words resulting in the entities' current brand sentiment. 
* Ideally something that gives the gist of what the entity is about, why it exists. 

Examples:
* A very short story arching from stage 1 to 4 of the enshittification spiral.
* A very short story about staying stage 1 [its whole existence] do far. 
* A very short story about swaying / oscillating / bouncing / flapping btwn stages 2 and 3. 
* A short bulleted list of noteworthy [news] events (dates should be in YYYY-MMM-DD format); the few critical points which match changes in stage. Not just listing all news items verbatim. 

Some foundational info about "{entity}": 
* Started "{date_started}", ended "{date_ended}" 
* In corporate family "{corp_fam}" 
* In category "{category}" 
* Currently judged to be at: stage {stage_current} 
* URL: {ent_url} 
* Summary: {summary} 
* Some authoritative guidance: {seed} 

News items related to "{entity}" include: 
{news_items}
(Note that stage values in news items are actually a weighted avgerages of news judgments, a sequence of stage_current-s captured in stage_history.)

Wikipedia results (content pulled from Wikipedia may be incorrect or partially incorrect as containing undisambiguationed hits of the entity name): {wikipedia_page_results} 

Duck Duck Go search results (content from search may be incorrect or partially incorrect due to multiple different hits for a single entity name): {ddg_results} 

Please return timeline for entity "{entity}".
"""


SHRINK_NEWS_TEMPLATE = """
Need to shrink down / summarize / condense this news item list. Task is to take in news_list and output a much smaller news_list.

News items with no information may be dropped or grouped and condensed.
Recurring formatting can be removed; words can be abbreviated.
If a news item has a huge story, vastly summarize or condense it.

Entity is "{entity}"
started: "{date_started}"
ended: "{date_ended}"
corporate family: "{corp_fam}"
category: "{category}"
{entity} currently judged to be at: stage {stage_current}
{entity} summary: {summary}

News items list to return shortened form of: 
{news_items}

Please return shortened form of news items list for "{entity}".
"""


SHRINK_WIKIP_TEMPLATE = """
Need to shrink down / summarize / condense these Wikipedia returns. Task is to take in wikipedia_page_results and output a much smaller wikipedia_page_results.

Wikipedia results may be incorrect or partially incorrect as containing undisambiguationed hits of the entity name. 
Sometimes one or more of the return blocks, "page:" section, can simply be dropped as irrelevant.
If the entity name is weird or a noun or sounds like something else, then the (source) returns are more likely to be managed.

Entity is "{entity}"
started: "{date_started}"
ended: "{date_ended}"
corporate family: "{corp_fam}"
category: "{category}"
{entity} currently judged to be at: stage {stage_current}
{entity} summary: {summary}

Wikipedia results to return shortened form of: 
{wikipedia_page_results} 

Please return shortened form of wikipedia results for "{entity}".
"""


SHRINK_DDG_TEMPLATE = """
Need to shrink down / summarize / condense these DDG web search engine results. Task is to take in ddg_results and output a much smaller ddg_results.

Duck Duck Go search results may be incorrect or partially incorrect due to multiple different hits for a single entity name. 
Sometimes one or more of the return blocks can simply be dropped as irrelevant.
If the entity name is weird or a noun or sounds like something else, then the (source) returns are more likely to be managed.

Entity is "{entity}"
started: "{date_started}"
ended: "{date_ended}"
corporate family: "{corp_fam}"
category: "{category}"
{entity} currently judged to be at: stage {stage_current}
{entity} summary: {summary}

Search results to return shortened form of: 
{ddg_results} 

Please return shortened form of search results for "{entity}".
"""


def dt_parse(date_in):
    """ use dateparser.parse() to convert whatever to datetime """
    if isinstance(date_in, datetime):
        """ if input is datetime just pass as is """
        logging.info(f'dt_parse: already datetime!')
        date_out = date_in
    elif isinstance(date_in, str):
        """ if input is str, and value is 'None' just pass as is, otherwise run through dateparser """
        if date_in == 'None':
            logging.info(f'dt_parse: value str "None"')
            date_out = 'None'
        else:
            logging.info(f'dt_parse: type str')
            date_out = dateparser.parse(date_in)
    else:
        """ anything else try to convert to str and then run through dateparser """
        logging.info(f'dt_parse: input of "{date_in}" is type {type(date_in)} - trying conver to str and parse')
        try:
            date_out = dateparser.parse(str(date_in))
        except Exception as e:
            logging.error(f'dateparser failed with error {e}')
            date_out = 'None'
    return date_out


def create_summary_content(name):
    """
    Query Wikipedia and DDG on name.
    Query LLM w/ wikipedia and DDG results and ask for json of "summary", "date_started", "date_ended", "corp_fam", "category", "ent_url".
    If good json then copy out results, otherwise return summary None.
    """
    summary = None
    date_started = None
    date_ended = None
    corp_fam = None
    category = None

    wikipedia_page_results = ''
    wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=1))
    wikipedia_page_results = wikipedia.run(f'about {name} corp')
    logging.info(f'==> wikipedia_page_results results for {name}: {wikipedia_page_results}.')

    ddg_results = ''
    try:
        search = DuckDuckGoSearchRun()
        ddg_results = search.run(f'about {name} corp')
        logging.info(f'==> ddg_results results for {name}: {ddg_results}.')
    except Exception as e:
        logging.error(f'==> ddg search returned {e}.')
        # raise RatelimitException(f"{resp.url} {resp.status_code} Ratelimit")
        # duckduckgo_search.exceptions.RatelimitException: https://duckduckgo.com/ 202 Ratelimit

    content_prompt = ChatPromptTemplate.from_template(CREATE_SUMMARY_CONTENT_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | JsonOutputParser() # automatically parses the output into a Python dictionary
            )
    try:
        content = chain.invoke({"entity": name, 
                                "wikipedia_page_results": wikipedia_page_results, 
                                "ddg_results": ddg_results})
         # JsonOutputParser returns a dictionary
        logging.info(f'==> Raw content return (which should be json) for {name}:\n{content}')
    except HTTPStatusError as e:
        content = ''
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
            # httpx.HTTPStatusError: Error response 401 while fetching https://api.mistral.ai/v1/chat/completions: {"message":"Unauthorized"}
        else:
            logging.error(f'==> chain.invoke Mistral LLM (HTTPStatusError) failed: {e}')
    except Exception as e:
        content = ''
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    try:
        summary = content.get('summary')
        date_started = dt_parse(content.get('date_started'))
        date_ended = dt_parse(content.get('date_ended'))
        corp_fam = content.get('corp_fam')
        category = content.get('category')
        ent_url = content.get('ent_url')
    except Exception as e:
        summary = None
        logging.error(f'==> For {name}, unable to process return from LLM into needed variables; got error: {e} ~ Value of content: {content}')
    return summary, date_started, date_ended, corp_fam, category, ent_url


CREATE_URL_CONTENT_TEMPLATE = """
Objective is to return the authoritative single main URL for the entity "{entity}" on the internet. 
If URL is not mentioned or it is not quite clear what it is, no guesses, just return "UNK".

Format response _must_ be json, like for example: 
{{
  "ent_url": "http://www.example.com/index"
}}

Entity in question is: {entity}
"Seed" text (may not be any): {seed_text}
Brief summary of entity (may not be any): {summary}
Corporate family (may not be any): {corp_fam}
Category (may not be any): {category}
Web search results: {ddg_results}

For entity "{entity}" return ent_url in JSON format.
"""


def create_ent_url_content(entity):
    """ web search and LLM call to find entity URL """
    name = entity.name
    ent_url = None
    ddg_results = ''
    try:
        search = DuckDuckGoSearchRun()
        ddg_results = search.run(f'official website for "{name}"')
        logging.info(f'==> ddg_results results for {name}: {ddg_results}.')
    except Exception as e:
        logging.error(f'==> ddg search errored: {e}')
    content_prompt = ChatPromptTemplate.from_template(CREATE_URL_CONTENT_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | JsonOutputParser()
            )
    try:
        content = chain.invoke({"entity": name, 
                                "seed_text": entity.seed, 
                                "summary": entity.summary, 
                                "corp_fam": entity.corp_fam, 
                                "category": entity.category, 
                                "ddg_results": ddg_results})
        logging.info(f'==> Raw content return (which should be json) for {name}:\n{content}')
    except Exception as e:
        content = ''
        logging.error(f'==> chain.invoke LLM failed: {e}')
    try:
        ent_url = content.get('ent_url')
    except Exception as e:
        ent_url = None
        logging.error(f'==> For {name}, unable to process return from LLM into needed variables; got error: {e}')
    return ent_url


def shrink_news_items(news_items, entity):
    shrink_news_prompt = ChatPromptTemplate.from_template(SHRINK_NEWS_TEMPLATE)
    chain = ( shrink_news_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    try:
        news_items = chain.invoke({"entity": entity.name, 
                                   "news_items": news_items, 
                                   "summary": entity.summary, 
                                   "date_started": entity.date_started, 
                                   "date_ended": entity.date_ended, 
                                   "corp_fam": entity.corp_fam, 
                                   "category": entity.category, 
                                   "stage_current": entity.stage_current, })
    except HTTPStatusError as e:
        news_items = "No news items"
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
        else:
            logging.error(f'==> chain.invoke Mistral LLM failed (HTTPStatusError): {e}')
    except Exception as e:
        news_items = "No news items"
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    return news_items


def shrink_wikip_results(wikipedia_page_results, entity):
    shrink_wikip_prompt = ChatPromptTemplate.from_template(SHRINK_WIKIP_TEMPLATE)
    chain = ( shrink_wikip_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    try:
        wikipedia_page_results = chain.invoke({"entity": entity.name, 
            "summary": entity.summary, 
            "date_started": entity.date_started, 
            "date_ended": entity.date_ended, 
            "corp_fam": entity.corp_fam, 
            "category": entity.category, 
            "wikipedia_page_results": wikipedia_page_results, 
            "stage_current": entity.stage_current, })
    except HTTPStatusError as e:
        wikipedia_page_results = "No wikipedia results"
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
        else:
            logging.error(f'==> chain.invoke Mistral LLM failed (HTTPStatusError): {e}')
    except Exception as e:
        wikipedia_page_results = "No wikipedia results"
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    return wikipedia_page_results


def shrink_ddg_results(ddg_results, entity):
    shrink_ddg_prompt = ChatPromptTemplate.from_template(SHRINK_DDG_TEMPLATE)
    chain = ( shrink_ddg_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    try:
        ddg_results = chain.invoke({"entity": entity.name, 
            "summary": entity.summary, 
            "date_started": entity.date_started, 
            "date_ended": entity.date_ended, 
            "corp_fam": entity.corp_fam, 
            "category": entity.category, 
            "ddg_results": ddg_results, 
            "stage_current": entity.stage_current, })
    except HTTPStatusError as e:
        ddg_results = "No DDG results"
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
        else:
            logging.error(f'==> chain.invoke Mistral LLM failed (HTTPStatusError): {e}')
    except Exception as e:
        ddg_results = "No DDG results"
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    return ddg_results


TIMELINE_MERGE_TEMPLATE = """
Task is to merge existing old timeline text together with newly created timeline text, 
to form final new current timeline for "{entity}". 
A smaller merged/updated timeline is preferable; 
concise and quickly illustrative.

Existing old timeline text: 
{existing_old_timeline}

Newly created timeline text: 
(newly_generated_timeline)

Please return timeline for entity "{entity}" ;-)
"""


def make_new_timeline(entity):
    logging.info(f'==> +++++++++ create_timeline_content +++++++++++')
    name = entity.name

    news_items = ""
    for item in entity.stage_history: # each list item should be date and stage value, with hopefully a third, news item id
        num_fields = len(item)
        news_items += f"date: {item[0]}; " ### wanna sort by this, do in later pass, add temp var, sort, pass to LLM less confusing
        news_items += f"stage value: {item[1]}; "
        if num_fields == 2:
            news_items += f"no news id; "
        if num_fields == 3:
            target_item_id = item[2]
            news_items += f"news id #{target_item_id}; "
            target = db.session.get(News, target_item_id)
            # was: target = News.query.get(target_item_id) # 2025DEC26 which throws this line:
            # LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. 
            # The method is now available as Session.get() (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
            news_items += f"text: {target.text}; "
            news_items += f"summary: {target.summary}; "
        ### news_items += "\n" # removed this line as LLM spit these back out and unescaped newline characters break json parsing in json.loads later
    ### this might be too long for LLM, 18000 characters for Meta 2024-12-21 01:20:21,879
    news_tokens = int( len(news_items) / 4 ) # A rough estimate for English text: 1 token ≈ 4 characters
    logging.info(f'==> {news_tokens} token count news_items for {name}: {news_items}')

    wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=1))
    wikipedia_page_results = wikipedia.run(f'timeline about {name} corp')
    wikip_tokens = int( len(wikipedia_page_results) / 4 )
    logging.info(f'==> {wikip_tokens} token count for wikipedia_page_results results for {name}: {wikipedia_page_results}.')

    ddg_results = ""
    try:
        search = DuckDuckGoSearchRun()
        ddg_results = search.run(f'timeline about {name} corp')
        logging.info(f'==> ddg_results for {name}: {ddg_results}.')
    except Exception as e:
        logging.error(f'==> ddg search returned {e}.')
        # raise RatelimitException(f"{resp.url} {resp.status_code} Ratelimit")
        # duckduckgo_search.exceptions.RatelimitException: https://duckduckgo.com/ 202 Ratelimit
    ddg_tokens = int( len(ddg_results) / 4 )
    logging.info(f'==> {ddg_tokens} token count for DDG results for {name}.')

    token_thresh = 2500 # set token thresh-hold over which to shrink content (1 token ≈ 4 characters)

    if news_tokens > token_thresh:
        news_items = shrink_news_items(news_items = news_items,
                                       entity = entity)
        logging.info(f'==> Shrunk! news_items: {news_items}')

    if wikip_tokens > token_thresh:
        wikipedia_page_results = shrink_wikip_results(wikipedia_page_results = wikipedia_page_results,
                                                      entity = entity)
        logging.info(f'==> Shrunk! wikipedia_page_results: {wikipedia_page_results}.')

    if ddg_tokens > token_thresh:
        ddg_results = shrink_ddg_results(ddg_results = ddg_results,
                                         entity = entity)
        logging.info(f'==> Shrunk! ddg_results: {ddg_results}.')

    content_prompt = ChatPromptTemplate.from_template(CREATE_TIMELINE_CONTENT_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | StrOutputParser() 
            )
    """ Dump all this stuff into LLM, get back timeline content """
    try:
        content = chain.invoke({"entity": name, 
                                "current_date": datetime.today().strftime('%B %d, %Y'), # format is "January 17, 2020"
                                "stage_current": entity.stage_current, 
                                "ent_url": entity.ent_url, 
                                "seed": entity.seed, 
                                "date_started": entity.date_started, 
                                "date_ended": entity.date_ended, 
                                "summary": entity.summary, 
                                "corp_fam": entity.corp_fam, 
                                "category": entity.category, 
                                "news_items": news_items, 
                                "wikipedia_page_results": wikipedia_page_results, 
                                "ddg_results": ddg_results, 
        })
        logging.info(f'==> Raw LLM content return: {content}') # keep this logging and comment one in semantics.py
    except HTTPStatusError as e:
        content = "No timeline"
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
        else:
            logging.error(f'==> chain.invoke Mistral LLM failed (HTTPStatusError): {e}')
    except Exception as e:
        content = "No timeline"
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    return content


def merge_timelines(entity, new_timeline):
    logging.info(f'==> +++++++++ merge_timeline_contents +++++++++++')
    content_prompt = ChatPromptTemplate.from_template(TIMELINE_MERGE_TEMPLATE)
    chain = ( content_prompt
            | large_lang_model 
            | StrOutputParser() ### is there a json output parser?
            )
    try:
        merged_timeline = chain.invoke({"entity": entity.name, 
                                "existing_old_timeline": entity.timeline, 
                                "newly_generated_timeline": new_timeline, })
        logging.info(f'==> Raw LLM merged_timeline return: {merged_timeline}') # keep this logging and comment one in semantics.py
    except HTTPStatusError as e:
        merged_timeline = "No timeline"
        if e.response.status_code == 401:
            logging.error(f'==> Error: Unauthorized. Please check your API key.')
        else:
            logging.error(f'==> chain.invoke Mistral LLM failed (HTTPStatusError): {e}')
    except Exception as e:
        merged_timeline = "No timeline"
        logging.error(f'==> chain.invoke Mistral LLM failed: {e}')
    """ Decide which of the three timelines to use! """
    len_old = len(entity.timeline) if entity.timeline else 0
    # If bla is truthy (i.e., not empty), len(bla) is assigned to len_old.
    # If bla is falsy (e.g., None, '', []), 0 is assigned to len_old.
    len_new = len(new_timeline) # just generated moments ago (w/ new news item)
    len_mer = len(merged_timeline) # LLM attempt to merge old and new timelines
    if len_mer >= ( ( (len_old + len_new) / 2 ) * .20 ):
        # this should catch 80% of the flow (may be slightly more errors and some lossyness though) merged is not truncated relative to avg of old and new
        content = merged_timeline
        logging.info(f'==> content = (1) merged_timeline - {len_mer} >= 20% avg of other two')
    elif len_new >= len_old:
        # new at least bigger than old; this should catch 10% of the flow (one less llm hop, or just new)
        content = new_timeline
        logging.info(f'==> content = (2) new_timeline - new {len_new} > old {len_old}')
    elif len_old >= ( ( (len_mer + len_new) / 2 ) * .25 ):
        # ~2%, old has some content, new and/or merge are truncated or none 
        content = entity.timeline
        logging.info(f'==> content = (3) entity.timeline - {len_old} > 25% avg of other two')
    else:
        # hope it worked
        content = merged_timeline
        logging.info(f'==> content = (4) merged_timeline - hope all the LLM calls worked...')
    # replaced w/ JsonOutputParser() from langchain_core.output_parsers.json!
    return content


def create_timeline_content(entity):
    """
    Grab all news items linked to entity, for each getting text, summary, date, and stage value.
    Query Wikipedia and DDG on entity timeline.
    Query LLM w/ wikipedia and DDG results, existing summary etc, and ask for json of "timeline".
    Extract the content between first '{' and last '}'...
    If good json then copy out results, otherwise return timeline None.
    Compare existing "entity.timeline" and newly created "timeline" and merge them into one final new timeline 
    """
    new_timeline = make_new_timeline(entity)
    timeline = merge_timelines(entity = entity, new_timeline = new_timeline)
    return timeline


def create_data_map_content(entity):
    edge_data = []
    node_data = []
    """ main center node """
    node_data.append( {"data": {"id": "name", "label": f"{entity.name}" }})
    """ stage node, and edge """
    node_data.append( {"data": {"id": "stage", "label": f"Stage {entity.stage_current} ({entity.stage_EM4view})" }})
    edge_data.append( {"data": {"id": "name1", "source": "name", "target": "stage"}})
    # Haven't figured how to implement this one yet, don't have a current_user.func_stage as this is a backend process
    # Have it in parenthesis in the stage node - ex: "Stage 2 (2)"
    # node_data.append( {"data": {"id": "stage4", "label": f"Stage {entity.stage_EM4view}" }})
    # edge_data.append( {"data": {"id": "stagestage4", "source": "stage", "target": "stage4"}})
    ### Ideally add a few more here like: wikipedia, URLs, word cloud of nature of entity, market cap, EBICD, stock summary, daily active users
    # Status seems irrelevant and confusing here - not displaying, just using for filter search on rankings page
    # node_data.append( {"data": {"id": "status", "label": f"status: {entity.status}" }})
    # edge_data.append( {"data": {"id": "namestatus", "source": "name", "target": "status"}})
    """ date started node, and edge """
    if entity.date_started != 'UNK':
        node_data.append( {"data": {"id": "started", "label": f"started: {entity.date_started}"}})
        edge_data.append( {"data": {"id": "namestarted", "source": "name", "target": "started"}})
    """ date ended node, and edge """
    if entity.date_ended != 'current' and entity.date_ended != 'None':
        node_data.append( {"data": {"id": "ended", "label": f"ended: {entity.date_ended}"}})
        edge_data.append( {"data": {"id": "nameended", "source": "name", "target": "ended"}})
    """ category node and edge; then node and edge for each category member listed """
    if entity.category:
        if entity.category != 'None':
            node_data.append( {"data": {"id": "category", "label": "categories"}})
            edge_data.append( {"data": {"id": "namecategory", "source": "name", "target": "category"}})
            cats_list = entity.category.split(", ") if ", " in entity.category else [entity.category]
            for count, cat in enumerate(cats_list, start=1):
                node_data.append({"data": {"id": f"cat#{count}", "label": cat}})
                edge_data.append({"data": {"id": f"cat#{count}cat", "source": f"cat#{count}", "target": "category"}})
    """ family node and edge; then node and edge for each family member listed """
    if entity.corp_fam:
        if entity.corp_fam != 'None':
            node_data.append( {"data": {"id": "fam", "label": f"family"}})
            edge_data.append( {"data": {"id": "namefam", "source": "name", "target": "fam"}})
            corp_fam_list = entity.corp_fam.split(", ") if ", " in entity.corp_fam else [entity.corp_fam]
            for count, item in enumerate(corp_fam_list, start=1):
                node_data.append({"data": {"id": f"fam#{str(count)}", "label": item}})
                edge_data.append({"data": {"id": f"fam#{str(count)}fam", "source": f'fam#{str(count)}', "target": "fam"}})
    """ summary node, and edge - reference only, not content """
    if entity.summary:
        node_data.append( {"data": {"id": "summary", "label": f"summary" }})
        edge_data.append( {"data": {"id": "namesummary", "source": "name", "target": "summary"}})
    """ linked news items node, and edge - details numbers in label, not content """
    if entity.stage_history: ### could make each a sub-link
        node_data.append( {"data": {"id": "news", "label": f"{len(entity.stage_history)} linked news items!" }})
        edge_data.append( {"data": {"id": "namenews", "source": "name", "target": "news"}})
    """ timeline node, and edge - reference only, not content """
    if entity.timeline: # reference only, not content
        node_data.append( {"data": {"id": "timeline", "label": f"timeline" }})
        edge_data.append( {"data": {"id": "nametimeline", "source": "name", "target": "timeline"}})
    graph_data = {"edges": edge_data, "nodes": node_data}
    """ json.dumps to serialize for storage as text in SQLite """
    map_data = json.dumps(graph_data, indent=4)
    return map_data


def large_lang_model(query):
    large_lang_model = ChatMistralAI(model_name = 'open-mixtral-8x7b', 
                                     mistral_api_key = llm_api_key, 
                                     temperature = llm_temp, 
                                     verbose = True )
    return large_lang_model


def parse_for_blank_summary(count_max_sm):
    """
    Pulls all entities from DB; skips disabled; if summary None (blank) then call create_content.
    If create_content returns summary None then logs and continues, otherwise sets values for summary etc and commits.
    """
    count_summeried = 0
    count_skipped = 0
    logging.info(f'==> +++++++++ parse_for_blank_summary +++++++++++')
    with app.app_context():
        entities = Entity.query.all()
        for entity in entities:
            if count_summeried >= count_max_sm:
                count_skipped += 1
                continue
            if entity.status != 'disabled':
                if entity.summary:
                    continue
                # if entity is not disabled, and has a blank summary, then try to fill in blanks
                summary, date_started, date_ended, corp_fam, category, ent_url = create_summary_content(name = entity.name)
                if not summary:
                    # if summary comes back None, then go to next entity
                    logging.info(f'==> Tried, but unable to get content for {entity.name}. ')
                    continue
                entity.summary = summary
                entity.date_started = dt_parse(date_started)
                entity.date_ended = dt_parse(date_ended)
                # don't overwrite existing content for these
                if not entity.corp_fam:
                    entity.corp_fam = corp_fam
                if not entity.category:
                    entity.category = category
                if (not entity.ent_url) or (entity.ent_url == "UNK"):
                    entity.ent_url = ent_url
                db.session.commit()
                logging.info(f'==> Populated blanks for {entity.name}:\n summary = {summary}\n date_started = {date_started}\n date_ended = {date_ended}\n corp_fam = {corp_fam}\n category = {category}')
                count_summeried += 1
    logging.info(f'==> Summary populated a total of {count_summeried} entities; skipped {count_skipped}')
    return None


def parse_for_blank_timeline(count_max_tl):
    """
    Pulls all entities from DB; skips disabled; if timeline None (blank) then call create_content.
    If create_content returns timeline None then logs and continues, otherwise sets value for timeline and commits.
    """
    count_timelined = 0
    count_skipped = 0
    logging.info(f'==> ++++++++++ parse_for_blank_timeline +++++++++++')
    with app.app_context():
        entities = Entity.query.all()
        for entity in entities:
            if count_timelined >= count_max_tl:
                count_skipped += 1
                continue
            if entity.status != 'disabled':
                if entity.timeline:
                    continue
                if entity.summary == None:
                    continue
                # if entity is not disabled, and has a blank timeline, but has a summary already, then try to fill in the timeline
                timeline = create_timeline_content(entity)
                if not timeline:
                    # if timeline comes back None, then go to next entity
                    logging.info(f'==> Tried, but unable to get timeline for {entity.name}. ')
                    continue
                entity.timeline = timeline
                db.session.commit()
                logging.info(f'==> Populated timeline for {entity.name}:\n timeline = {timeline}')
                count_timelined += 1
    logging.info(f'==> Timeline populated a total of {count_timelined} entities; skipped {count_skipped}')
    return None


def parse_for_blank_data_map(count_max_dm):
    """
    Pulls all entities from DB; skips disabled; if data_map None (blank) then call create_content.
    If create_content returns None then logs and continues, otherwise sets value for timeline and commits.
    """
    count_mapped = 0
    count_skipped = 0
    logging.info(f'==> ++++++++++ parse_for_blank_data_map +++++++++++')
    with app.app_context():
        entities = Entity.query.all()
        for entity in entities:
            if count_mapped >= count_max_dm:
                count_skipped += 1
                continue
            if entity.status != 'disabled':
                if entity.data_map:
                    continue
                # if entity is not disabled, and has a blank data_map, then try to fill in the data_map
                data_map = create_data_map_content(entity)
                if not data_map:
                    # if data_map comes back None, then go to next entity
                    logging.info(f'==> Tried, but unable to get data_map for {entity.name}. ')
                    continue
                entity.data_map = data_map
                db.session.commit()
                logging.info(f'==> Populated data map for {entity.name}! (len = {len(data_map)})')
                count_mapped += 1
    logging.info(f'==> Data map populated a total of {count_mapped} entities; skipped {count_skipped}')
    return None


def parse_for_blank_url(count_max_ur):
    """
    Pulls all entities from DB; skips disabled; if ent_url None (blank) or "UNK" then call create_content.
    If create_content returns None then logs and continues, otherwise sets value for ent_url and commits.
    """
    count_mapped = 0
    count_skipped = 0
    logging.info(f'==> ++++++++++ parse_for_blank_URL +++++++++++')
    with app.app_context():
        entities = Entity.query.all()
        for entity in entities:
            if count_mapped >= count_max_ur:
                count_skipped += 1
                continue
            if entity.status != 'disabled':
                if entity.ent_url and (entity.ent_url != "UNK"):
                    continue
                # if entity is not disabled, and has a blank or "UNK" ent_url, then try to fill in the ent_url
                ent_url = create_ent_url_content(entity)
                if not ent_url:
                    # if ent_url comes back None, then go to next entity
                    logging.info(f'==> Tried, but unable to get URL for {entity.name}. ')
                    continue
                entity.ent_url = ent_url
                db.session.commit()
                logging.info(f'==> Populated URL for {entity.name}! {ent_url}')
                count_mapped += 1
    logging.info(f'==> URL populated for a total of {count_mapped} entities; skipped {count_skipped}')
    return None


def create_data_map_for_entity(entity_name_str):
    logging.info(f'==> ++++++++++ create_data_map_for_entity +++++++++++')
    with app.app_context():
        entity = Entity.query.filter_by(name=entity_name_str).first()
        data_map = create_data_map_content(entity)
        if not data_map:
            logging.info(f'==> Tried, but unable to get data_map for {entity.name}. ')
        entity.data_map = data_map
        db.session.commit()
        logging.info(f'==> Populated data map for {entity.name}:\n data_map = {data_map}')


def create_timeline_for_entity(entity_name_str):
    """
    Click in GUI utility submits name of entity selected to run a timeline creation on.
    Also useful in testing from CLI.
    Pulls entity object from Entities, passes to create_timeline_content.
    Saves new timeline
    """
    with app.app_context():
        entity = Entity.query.filter_by(name=entity_name_str).first()
        if entity.summary == None:
            summary, date_started, date_ended, corp_fam, category, ent_url = create_summary_content(name = entity_name_str)
            if not summary:
                logging.info(f'==> Tried, but unable to get content for {entity.name}. ')
                logging.info(f'==> Summary needed for timeline, exited before timeline creation. ')
                return None
            entity.summary = summary
            entity.date_started = dt_parse(date_started)
            # if something came back, use it
            if date_ended:
                entity.date_ended = dt_parse(date_ended)
            if corp_fam:
                entity.corp_fam = corp_fam
            if category:
                entity.category = category
            if ent_url:
                entity.ent_url = ent_url
            db.session.commit()
            logging.info(f'==> Populated blanks for {entity.name}:\n summary = {summary}\n date_started = {date_started}\n date_ended = {date_ended}\n corp_fam = {corp_fam}\n category = {category}')
        timeline = create_timeline_content(entity)
        if not timeline:
            logging.info(f'==> Tried, but unable to get timeline for {entity.name}. ')
        else:
            entity.timeline = timeline
            db.session.commit()
            logging.info(f'==> Populated timeline for {entity.name}: {timeline}')
    return None


def main():
    parse_for_blank_summary(count_max_sm)
    parse_for_blank_timeline(count_max_tl)
    parse_for_blank_data_map(count_max_dm)
    parse_for_blank_url(count_max_ur)
    logging.info(f'==> ++++++++++ filling blanks done +++++++++++\n')

if __name__ == "__main__":
    main()


# manual cli steps:
# ssh
# cd ~/EnshittificationMetrics/backend/ OR cd ~/em
# pipenv shell
# python3
# from populate_blanks import create_data_map_for_entity
# create_data_map_for_entity("entity_name")
