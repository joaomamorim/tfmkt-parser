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
seas.propagate_to_players(Player.init_tables_on_demand)
seas.persist()
#seas.propagate_to_players(Player.init_tables)
#seas.update_mysql()
#seas['fc-paris-saint-germain']['kylian-mbappe'].init_tables()
#seas['west-ham.*'].propagate_to_players(Player.create_soup)
#seas['west-ham.*'].propagate_to_players(Player.init_tables)
#seas.persist()

#lmessi = season['fc-barcelona']['lionel-messi']
#lmessi_tables = lmessi.create_soup.select("div.box div.responsive-table")


#season['fc-barcelona']['lionel-messi'].parse_tables()