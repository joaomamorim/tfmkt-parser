import logging.config
import yaml
import tfmktparser

logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
tfmktparser.source = tfmktparser.LOCAL
season = tfmktparser.Season()
season.init_clubs()
season['fc-barcelona'].create_soup()
season['fc-barcelona'].init_players()
season['fc-barcelona']['lionel-messi'].create_soup()
season['fc-barcelona']['lionel-messi'].init_tables()

#season['fc-barcelona']['lionel-messi'].parse_tables()