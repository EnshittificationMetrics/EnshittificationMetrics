#!/usr/bin/env python

"""
Tries to make a giant map of all entities.
"""

import os
import sys
import logging
script_directory = os.path.dirname(os.path.abspath(__file__))
if script_directory.startswith('/home/bsea/em'):
    sys.path.append('/var/www/em')
    logpath = '/home/bsea/em/giant_map.log'
else:
    sys.path.append('/home/leet/EnshittificationMetrics/www/')
    logpath = './giant_map.log'
logging.basicConfig(level=logging.INFO,
                    filename = logpath,
                    filemode = 'a',
                    format='%(asctime)s -%(levelname)s - %(message)s')

from app import app, db
from app.models import Entity, News
from dotenv import load_dotenv
import json


def make_giant_map():
    edge_data = []
    node_data = []
    """ node for each of the four stages """
    node_data.append( {"data": {"id": f"stage 1", "label": f"stage 1" }})
    node_data.append( {"data": {"id": f"stage 2", "label": f"stage 2" }})
    node_data.append( {"data": {"id": f"stage 3", "label": f"stage 3" }})
    node_data.append( {"data": {"id": f"stage 4", "label": f"stage 4" }})
    """ node for each category """
    node_data.append( {"data": {"id": f"social", "label": f"social" }})
    node_data.append( {"data": {"id": f"cloud", "label": f"cloud" }})
    node_data.append( {"data": {"id": f"B2B", "label": f"B2B" }})
    node_data.append( {"data": {"id": f"B2C", "label": f"B2C" }})
    node_data.append( {"data": {"id": f"C2C", "label": f"C2C" }})
    node_data.append( {"data": {"id": f"tech platform", "label": f"tech platform" }})
    node_data.append( {"data": {"id": f"P2P", "label": f"P2P" }})
    with app.app_context():
        """ get all the entities """
        entities = Entity.query.all()
        for entity in entities:
            """ filter not disabled, live or potential only """
            if entity.status == 'live':
                """ node w/ id entity.id and label entity.name """
                node_data.append( {"data": {"id": f"ent#{entity.id}", "label": f"{entity.name}" }})
                """ edge to entity.stage_current """
                edge_data.append( {"data": {"id": f"ent#{entity.id}-stage{entity.stage_current}", "source": f"ent#{entity.id}", "target": f"stage {entity.stage_current}"}})
                """ break down entity.category by comma sep phrases """
                if entity.category != 'None':
                    cat_list = entity.category.split(", ") if ", " in entity.category else [entity.category]
                    for count, item in enumerate(cat_list, start=1):
                        """ edge to each item in .category """
                        edge_data.append( {"data": {"id": f"ent#{entity.id}-{item}", "source": f"ent#{entity.id}", "target": f"{item}"}})
                ### make node for each fam member in .corp_fam - don't duplicate, check if node already exists
                ### edge to each fam member in .corp_fam
                ### edge to each news item in .stage_history ??? - too many
    graph_data = {"edges": edge_data, "nodes": node_data}
    map_data = json.dumps(graph_data, indent=4)
    return map_data


### way too many of these, have to do a separate big news map
#       with app.app_context():
#           """ get all the news """
#           news_items = News.query.all()
#           for story in news_items:
#               """ node w/ id story.id and label story.text """
#               node_data.append( {"data": {"id": f"news#{story.id}", "label": f"{story.text}" }})
#               if story.stage_int_value: # some are None and can't edge to a "stageNone"
#                   """ edge to story.stage_int_value """
#                   edge_data.append( {"data": {"id": f"news#{story.id}-stage{story.stage_int_value}", "source": f"news#{story.id}", "target": f"stage {story.stage_int_value}"}})
#               ### break down by comma sep phrases
#               # for linked_ent in story.ent_names:
#                   # """ edge to each item in story.ent_names """
#                   # edge_data.append( {"data": {"id": f"news#{story.id}-{linked_ent}", "source": f"news#{story.id}", "target": f"{linked_ent}" }})


def main():
    logging.info(f'+++++ starting {__file__} +++++')
    map_data = make_giant_map()
    logging.info(f'created giant map (size = {len(map_data)})')
    # print(map_data)
    file_path = "/home/leet/EnshittificationMetrics/backend/giant_map.json"
    with open(file_path, "w") as file:
        file.write(map_data)  # Write the JSON string to the file
    logging.info(f'saved as {file_path}')
    logging.info(f'+++++ finished {__file__} +++++\n')


if __name__ == "__main__":
    main()
