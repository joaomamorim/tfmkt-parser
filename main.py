import logging.config
import yaml
import tfmktparser

logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
tfmktparser.source = tfmktparser.REMOTE
season = tfmktparser.Season()
season.init_clubs()
season['real-madrid'].create_soup()
season['real-madrid'].init_players()
season['real-madrid']['keylor-navas'].create_soup()
season['real-madrid']['keylor-navas'].init_tables()

#lmessi = season['fc-barcelona']['lionel-messi']
#lmessi_tables = lmessi.soup.select("div.box div.responsive-table")


#season['fc-barcelona']['lionel-messi'].parse_tables()