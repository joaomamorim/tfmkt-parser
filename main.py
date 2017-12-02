import logging.config
import yaml
import tfmktparser

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs
from tfmktparser.Club import Club
from tfmktparser.Player import Player


logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
seas = tfmkse.Season(tfmkdefs.LOCAL)
seas.init_clubs()
seas['fc-paris-saint-germain'].create_soup()
seas['fc-paris-saint-germain'].init_players()
seas['fc-paris-saint-germain']['kylian-mbappe'].create_soup()
seas['fc-paris-saint-germain']['kylian-mbappe'].init_tables()
seas.soup_season()
seas.propagate_to_players(Player.init_tables)
#seas['fc-paris-saint-germain']['kylian-mbappe'].init_tables()
#seas['west-ham.*'].propagate_to_players(Player.create_soup)
#seas['west-ham.*'].propagate_to_players(Player.init_tables)
#seas.persist()

#lmessi = season['fc-barcelona']['lionel-messi']
#lmessi_tables = lmessi.create_soup.select("div.box div.responsive-table")


#season['fc-barcelona']['lionel-messi'].parse_tables()