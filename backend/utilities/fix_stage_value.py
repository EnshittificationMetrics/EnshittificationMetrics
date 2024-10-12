#!/usr/bin/env python

""" script converts from str 'stage 1' to int '1', for ex. (used early on in dev to deal w/ change in how stage stored) """

from app import app, db
from app.models import Entity

with app.app_context():
    entities = Entity.query.all()
    for ent in entities:
        print(f'{ent.name} has stage "{ent.stage_current}"')
        stage = str(ent.stage_current)
        if len(stage) > 1:
            stage_int_value = int(stage[-1]) # convert from str 'stage 1' to int '1'
            ent.stage_current = stage_int_value
            db.session.commit()
            print(f'Corrected to {stage_int_value}')
