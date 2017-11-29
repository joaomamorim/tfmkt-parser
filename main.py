import logging.config
import yaml
import tfmktparser

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs


logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
tfmkdefs.source = tfmkdefs.LOCAL
season_local = tfmkse.Season()
season_local.init_clubs()
season_local['real-madrid'].create_soup()
season_local['real-madrid'].init_players()
season_local['real-madrid']['keylor-navas'].create_soup()

#lmessi = season['fc-barcelona']['lionel-messi']
#lmessi_tables = lmessi.soup.select("div.box div.responsive-table")


#season['fc-barcelona']['lionel-messi'].parse_tables()