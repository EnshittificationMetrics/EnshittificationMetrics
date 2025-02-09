#!/usr/bin/env python

import os
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    mode = 'prod'
    logpath = '/home/bsea/em/scrape.log'
else:
    mode = 'dev'
    logpath = './scrape.log'
logging.basicConfig(level=logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format='%(asctime)s -%(levelname)s - %(message)s')

from bs4 import BeautifulSoup # https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from datetime import datetime
from semantics import semantic_processing
import html5lib # Parses HTML like a web browser, very lenient, handles malformed HTML, slower than native ‘html.parser’ or recommended 'lxml'
import re
import requests
import dateparser


site_url = 'https://slashdot.org/'
data_file = 'slashdot_data.txt'
max_size = 60 # each "page" is 15 items


def parse_slashdot_posts():
    logging.info(f'==> +++++++++ parse_slashdot_posts +++++++++++')
    note = ''
    req = requests.get(site_url)
    if req.status_code != 200:
        note += f'Unable to access {site_url}.\n'
        return note
    note += f'Processed {site_url}.\n'
    content = req.text
    soup = BeautifulSoup(content, 'html5lib')
    data_list = []
    # load ID / status file from disk
    if os.path.exists(data_file):
        with open(data_file, 'r') as file:
            for line in file:
                title_id, status = line.strip().split(maxsplit=1)
                data_list.append((title_id, status))
    else:
        note += f'{data_file} does not exist.\n'
        return note
    # For 'new' items in list, get post and send to semantic_processing func
    count = 0
    index = -1
    for title_id, status in data_list:
        index += 1
        if status == 'new':
            match = re.search(r'(\d+)', title_id) 
            if match: 
                number = match.group(1) 
            else: 
                note += f'No number in {title_id}.\n'
                data_list[index] = (data_list[index][0], 'error')
                ### instead hit the load more stories link at bottom and load that content 
                ### and look again for title_id - in case it's scrolled off the first page
                continue
            # get post title
            div_with_text = soup.find(id=title_id)
            if div_with_text:
                post_title = div_with_text.get_text(strip=True)
                # get post url
                a_tag = div_with_text.find('a', class_="story-sourcelnk", href=True)
                if a_tag:
                    post_source_url = a_tag['href'] ### this is not full URL to story, just TLD URL
                else:
                    note += f'No TLD URL for {title_id}. '
                    post_source_url = 'None'
                div_with_text = None # reset if used
            else:
                note += f'No post title for {title_id}.\n'
                data_list[index] = (data_list[index][0], 'error')
                continue
            # get post timestamp
            div_id = f'fhtime-{number}'
            div_with_text = soup.find(id=div_id)
            if div_with_text:
                sd_fhtime_text = div_with_text.get_text(strip=True)
                post_timestamp = yyyy_mmm_dd_format(sd_fhtime_text)
                post_timestamp = dateparser.parse(post_timestamp).date() # change to datetime; from "2025-FEB-07" to "2025-02-07"
                div_with_text = None # reset if used
            else:
                note += f'No timestamp for {title_id}.\n'
                post_timestamp = 'None'
            # get post text itself
            div_id = f'text-{number}'
            div_with_text = soup.find(id=div_id)
            if div_with_text:
                post_text = div_with_text.get_text(strip=True)
            else:
                note += f'No text content for {title_id}.\n'
                data_list[index] = (data_list[index][0], 'error')
                continue
            judgment = semantic_processing(title = post_title, 
                                           url = post_source_url, 
                                           date = post_timestamp, 
                                           content = post_text)
            note += f'/. item #{number} ({post_title}) judgment - {judgment}.\n'
            data_list[index] = (data_list[index][0], 'processed')
            count += 1
    note += f'Processed {count} posting(s).\n'
    # save ID / status file to disk
    with open(data_file, 'w') as file: ### add utf8 switch?
        for title_id, status in data_list:
            file.write(f"{title_id} {status}\n")
    return note


def yyyy_mmm_dd_format(sd_fhtime_text):
    # Slashdot dates come in looking like "on Saturday June 29, 2024 @11:34PM"
    pattern = r'\b(\w+)\s+(\d{1,2}),\s+(\d{4})'
    match = re.search(pattern, sd_fhtime_text)
    if match:
        month_str, day, year = match.groups()
        month_abbr = datetime.strptime(month_str, "%B").strftime("%b").upper()
        day = int(day)
        day_formatted = f"{day:02d}"
        post_timestamp = f"{year}-{month_abbr}-{day_formatted}"
    else:
        post_timestamp = 'UNK'    
    return post_timestamp


def process_slashdot_site():
    logging.info(f'==> +++++++++ process_slashdot_site +++++++++++')
    note = ''
    req = requests.get(site_url)
    if req.status_code != 200:
        note += f'Unable to access {site_url}. '
        return note
    note += f'Processed {site_url}. '
    content = req.text
    soup = BeautifulSoup(content, 'html5lib')
    # get story IDs
    story_titles = soup.find_all(class_='story-title')
    ids = [tag['id'] for tag in story_titles if tag.has_attr('id')]
    # check if any IDs are not tracked yet and add them to list as 'new'
    data_list = []
    if os.path.exists(data_file):
        with open(data_file, 'r') as file:
            for line in file:
                title_id, status = line.strip().split(maxsplit=1)
                data_list.append((title_id, status))
    else:
        note += f'{data_file} did not exist. '
    title_ids = {title_id for title_id, status in data_list}
    count = 0
    for id in ids:
        if id not in title_ids:
            data_list.append((id, 'new'))
            count += 1
    note += f'Added {count} story-title IDs. '
    # trim list down to keep at reasonable history size
    count = 0
    while len(data_list) > max_size:
        data_list.pop(0)
        count += 1
    note += f'Removed {count} old story-title IDs. '
    # save ID / status file to disk
    with open(data_file, 'w') as file: ### add utf8 switch?
        for title_id, status in data_list:
            file.write(f"{title_id} {status}\n")
    return note


# func for documentation reference, not actually run
def beautiful_soup_methods():
    soup = BeautifulSoup('<html><head><title>title</title></head><body><h1>heading</h1><p>text</p></body></html>', 'html5lib') 
    soup.find("head") # returns <head>
    soup.head # returns <head>
    soup.title # returns <title>
    soup.body.b # returns first <b> tag in <body>
    soup.a # returns first <a> tag
    soup.find_all('a') # returns all <a> tags
    soup("a") # convenience
    soup.head.contents # returns tag's children
    for child in soup.head.contents.children: # iterate over a tag’s children
        print(child)
    soup.find_all("a", class_="sister") # returns all <a> tags with class="sister"
    soup.find_all(string="Elsie") # returns all occurrences of the string
    soup.find_all(string=re.compile("Dormouse")) # returns all occurrences of the string's re variants
    soup.find_all("a", string="Elsie") # finds the <a> tags whose .string is “Elsie”
    soup.find_all("a", limit=2) # returns first two <a> tags
    soup.html.find_all("title", recursive=False) # consider only direct children
    soup.find('div', attrs = {'id':'text'})
    soup.find_all("div", class_="text")
    soup.find_all("p", class_="_text")
    print(soup.prettify()) # turn a Beautiful Soup parse tree into a nicely formatted Unicode string, with a separate line for each tag and each string
    soup.get_text() # human-readable text inside a document or tag
    soup.i.get_text()


def main():
    note = process_slashdot_site()
    logging.info(f'{note}')
    note = parse_slashdot_posts()
    logging.info(f'{note}')
    logging.info(f'==> ++++++++++ scrape done +++++++++++')


if __name__ == "__main__":
    main()

