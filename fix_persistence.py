import logging.config
import yaml
from sqlalchemy import create_engine
import tfmktparser

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs
import tfmktparser.test as testutils
from tfmktparser.Club import Club
from tfmktparser.Player import Player


logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
seas = tfmkse.Season([1, 2, 3, 4], tfmkdefs.LOCAL)
seas.init_clubs()
# seas['deportivo-la-coruna'].create_soup()
# seas['deportivo-la-coruna'].init_players()
# seas['deportivo-la-coruna']['luisinho'].create_soup()
# seas['deportivo-la-coruna']['luisinho'].init_tables()
# full_player = testutils.init_by_coodrinates(seas, 'real-madrid', 'sergio-ramos')
# full_player = testutils.init_by_coodrinates(seas, 'fc-barcelona', 'luis-suarez')
# full_player = testutils.init_by_coodrinates(seas, 'fc-bayern-munchen', 'arjen-robben')
# full_player = testutils.init_by_coodrinates(seas, 'fc-paris-saint-germain', 'alec-georgen')
#seas.soup_season()
seas.propagate_to_clubs(Club.init_players_on_demand)
def fix_persistence(player):
    player.create_soup()
    if not player.is_souped:
        player.toggle_source()
        player.create_soup()
        player.persist()
        player.toggle_source()
    player.soup = None

seas.propagate_to_players(fix_persistence)