#!/usr/bin/env python

"""
Converts from str 'stage 1' to int '1'. (Used early on in dev to deal w/ change in how stage stored.)
Tweaks status to 'potential' or 'live' as appropriate.
PLACEHOLDER for max_history_size; will also be in semantics.py.
"""

max_history_size = 25

import sys

if __file__.startswith('/home/bsea/em/'):
    sys.path.append('/var/www/em/app')
else:
    sys.path.append('/home/leet/EnshittificationMetrics/www')

from app import app, db
from app.models import Entity

with app.app_context():
    entities = Entity.query.all()
    for ent in entities:
        
        # change stage_current from str to int
        print(f'{ent.name} has stage: {ent.stage_current}')
        stage = str(ent.stage_current)
        if len(stage) > 1:
            stage_int_value = int(stage[-1]) # convert from str 'stage 1' to int '1'
            ent.stage_current = stage_int_value
            db.session.commit()
            print(f'==> Corrected to: {stage_int_value}')
        else:
            print(f'--> No change to stage made')
        
        # set entity status to potential if stage history is blank, to live if stage history is populated
        # if disabled leave as is
        print(f'{ent.name} has status: {ent.status}')
        stage_lenght = 0
        if ent.stage_history:
            stage_lenght = len(ent.stage_history)
        print(f'{ent.name} has stage_history of lenght: {stage_lenght}')
        if stage_lenght > 0:
            if ent.status == 'potential':
                ent.status = 'live'
                db.session.commit()
                print(f'==> Corrected to: {ent.status}')
            else:
                print(f'--> No change to status made')
        else:
            print(f'{ent.name} has stage_history of {ent.stage_history}')
            if ent.status == 'live':
                ent.status = 'potential'
                db.session.commit()
                print(f'==> Corrected to: {ent.status}')
            else:
                print(f'--> No change to status made')
        
        # from "Entity.stage_history" pop oldest stuff off list when gets too big
        if stage_lenght > max_history_size:
            pass
            ### pop oldest stuff off list
            print(f'==> Stage_history SHOULD BE trimmed to {max_history_size} items')
        
        print()