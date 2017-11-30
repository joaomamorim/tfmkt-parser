#C:\Python27\python.exe -m unittest tfmktparser.test
import unittest
import logging.config
import yaml

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs

#logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))

class TestParsedStatistics(unittest.TestCase):
    def test_entries(self):
        season = tfmkse.Season(1)
        season.init_clubs()
        season['fc-barcelona'].create_soup()
        season['fc-barcelona'].init_players()
        season['fc-barcelona']['lionel-messi'].create_soup()
        season['fc-barcelona']['lionel-messi'].init_tables()
        lmessi_cl = season['fc-barcelona']['lionel-messi']['CL']
        self.assertEqual(lmessi_cl[lmessi_cl._DATE_ == "Sep 12, 2017"].iloc[0]['_GS_'], 2)

    def test_persistence(self):
        season = tfmkse.Season(1)
        season.init_clubs()
        season['fc-barcelona'].create_soup()
        season['fc-barcelona'].init_players()
        season['fc-barcelona']['lionel-messi'].create_soup()
        season['fc-barcelona']['lionel-messi'].init_tables()
        season.persist()
        #del season
        season_local = tfmkse.Season(0)
        season_local.init_clubs()
        season_local['fc-barcelona'].create_soup()
        season_local['fc-barcelona'].init_players()
        season_local['fc-barcelona']['lionel-messi' ].create_soup()
        season_local['fc-barcelona']['lionel-messi' ].init_tables()
        lmessi_remote = season['fc-barcelona']['lionel-messi']['CL']
        lmessi_local = season_local['fc-barcelona']['lionel-messi']['CL']
        self.assertEqual(
            lmessi_remote[lmessi_remote._DATE_ == "Sep 12, 2017"].iloc[0]['_GS_'],
            lmessi_local[lmessi_local._DATE_ == "Sep 12, 2017"].iloc[0]['_GS_']
         )

if __name__ == '__main__':
    unittest.main()