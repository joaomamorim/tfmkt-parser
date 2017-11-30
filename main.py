import logging.config
import yaml
import tfmktparser

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs


logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
seas = tfmkse.Season(tfmkdefs.LOCAL)
seas.soup_season()
#seas.persist()

#lmessi = season['fc-barcelona']['lionel-messi']
#lmessi_tables = lmessi.soup.select("div.box div.responsive-table")


#season['fc-barcelona']['lionel-messi'].parse_tables()