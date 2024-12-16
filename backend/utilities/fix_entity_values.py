#!/usr/bin/env python

"""
Converts from str 'stage 1' to int '1' in entity. (Used early on in dev to deal w/ change in how stage stored.)
Tweaks status to 'potential' or 'live' as appropriate.
Does max_history_size cleanup (will also one day be in semantics.py)
Converts from str 'stage 1' to int '1' in stage_history in entity. 
Finds and fills in some news id # (and quality) in entity stage_history where missing.
"""

max_history_size = 25

import sys

if __file__.startswith('/home/bsea/em/'):
    sys.path.append('/var/www/em/app')
else:
    sys.path.append('/home/leet/EnshittificationMetrics/www')

from app import app, db
from app.models import Entity, News

with app.app_context():
    entities = Entity.query.all()
    for ent in entities:
        
        # FIX
        # change stage_current from str to int
        stage = str(ent.stage_current)
        if len(stage) > 1:
            print(f'{ent.name} has stage: {ent.stage_current}')
            stage_int_value = int(stage[-1]) # convert from str 'stage 1' to int '1'
            ent.stage_current = stage_int_value
            db.session.commit()
            print(f'==> Corrected to: {stage_int_value}')
        
        # FIX
        # set entity status to potential if stage history is blank, to live if stage history is populated
        # if disabled leave as is
        ### print(f'{ent.name} has status: {ent.status}')
        stage_lenght = 0
        if ent.stage_history:
            stage_lenght = len(ent.stage_history)
        if stage_lenght > 0:
            if ent.status == 'potential':
                print(f'{ent.name} has stage_history of lenght: {stage_lenght}')
                ent.status = 'live'
                db.session.commit()
                print(f'==> Corrected to: {ent.status}')
        else:
            if ent.status == 'live':
                print(f'{ent.name} has stage_history of {ent.stage_history}')
                ent.status = 'potential'
                db.session.commit()
                print(f'==> Corrected to: {ent.status}')
        
        # FIX
        # from "Entity.stage_history" pop oldest mundane stuff off list when gets too big
        if stage_lenght > max_history_size:
            print(f'{ent.name} stage_history SHOULD BE trimmed to {max_history_size} items; {stage_lenght} too big.')
            trimmed = 0
            while stage_lenght > max_history_size:
                # pop oldest mundane item off list
                pop_index = 0
                while pop_index < stage_lenght:
                    if len(ent.stage_history[pop_index]) > 2:
                        if ent.stage_history[pop_index][3] != 'foundational':
                            oldest_stage_history = ent.stage_history.pop(pop_index)
                            db.session.commit()
                            stage_lenght = len(ent.stage_history)
                            trimmed += 1
                            break #exit the while
                        else:
                            pop_index += 1
                    # kind of bad code but here if stage_history item had only date and stage values
                    oldest_stage_history = ent.stage_history.pop(pop_index)
                    db.session.commit()
                    stage_lenght = len(ent.stage_history)
                    trimmed += 1
                    break #exit the while
            print(f'==> Trimmed {trimmed} items from {ent.name} stage_history')
        
        # loop thru ent.stage_history
        # hist_item.[0] = str date
        # hist_item.[1] = int stage value
        # hist_item.[2] = int news item id
        # hist_item.[3] = str 'foundational' or 'mundane'
            
        # FIX
        # fix stage value from str to int if needed
        for hist_item in ent.stage_history:
            stage = hist_item[1]
            if type(stage) != int:
                if len(stage) > 1:
                    stage_int_value = int(stage[-1]) # convert from str 'stage 1' to int '1'
                    hist_item[1] = stage_int_value # can set existing
                    db.session.commit()
                    print(f'==> Corrected {ent.name} stage_history from {stage} to: {stage_int_value}')
            
        # FIX
        # if has date and stage value, and, news item id and quality are empty # figure out news item id from search of News
        for hist_item in ent.stage_history:
            if len(hist_item) == 2: ### was: if hist_item[0] and hist_item[1] and not hist_item[2] and not hist_item[3]:
                query = News.query.filter(News.date_pub == hist_item[0])
                count = query.count()
                if count == 1: # Since there's only one result, this will return a list with one item
                    target_news_items = query.all()
                    for target_news_item in target_news_items:
                        hist_item.append(target_news_item.id) #must append non-existing
                        hist_item.append('mundane')
                        db.session.commit()
                        print(f'==> Set {ent.name} stage_history for {hist_item[0]} to news id #{hist_item[2]} and quality {hist_item[3]}.')
                elif count == 0:
                    print(f'==> No single date matches from {hist_item[0]}, to a news.pub_date.')
                elif count > 1:
                    print(f'==> {ent.name} got MULTIPLE ({count}) date matches from {hist_item[0]}, stage {hist_item[1]} - which one? Needs action.')
                    target_news_items = query.all()
                    for target_news_item in target_news_items:
                        print(f'--> News ID #{target_news_item.id} w/ stage {target_news_item.stage_int_value} and ent names: {target_news_item.ent_names}')
        
        print()