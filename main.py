import logging.config
import yaml
import tfmktparser

logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
tfmktparser.source = tfmktparser.LOCAL
season = tfmktparser.Season()
season.init_clubs()
season.init_players()