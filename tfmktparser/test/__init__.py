#C:\Python27\python.exe -m unittest tfmktparser.test
import unittest
import logging.config
import yaml

from sets import Set

import tfmktparser.Season as tfmkse
import tfmktparser.settings as tfmkdefs
from tfmktparser.Player import Player

#logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))

class TestParsedStatistics(unittest.TestCase):

    # Here we validate that certain values in the tables have the expected values.
    def test_entries(self):
        # Test Messi appearance
        seas = tfmkse.Season(0)
        #self.assertTrue(validate_by_season_coordinates(seas, 'fc-barcelona', 'lionel-messi', 'ES1', 'Dec 2, 2017', '_GS_', 1))
        # Test Mbappe appearance
        self.assertTrue(validate_by_season_coordinates(seas, 'fc-paris-saint-germain', 'kylian-mbappe', 'FR1', 'Sep 30, 2017', '_AS_', 1))
        # Test game id is extracted correctly when 'id' tag is not present (as-rome/alisson/Dec 1, 2017)
        self.assertTrue(validate_by_season_coordinates(seas, 'as-rom', 'alisson', 'IT1', 'Dec 1, 2017', '_GID_', 2897443))

    def test_update(self):
        seas = tfmkse.Season(0)
        try:
            is_valid = validate_by_season_coordinates(seas, 'fc-barcelona', 'luis-suarez', 'ES1', 'Dec 2, 2017', '_GS_', 1)
            self.assertTrue(False)
        except IndexError:
            self.assertTrue(True)
        seas.update_players_soup(Player.has_table, "ES1")
        self.assertTrue(validate_by_season_coordinates(seas, 'fc-barcelona', 'luis-suarez', 'ES1', 'Dec 2, 2017', '_GS_', 1))

    # 'nicolas-pareja' from 'sevilla' has a trailing invalid table, this test makes sure
    # this kind of situation does not affect a correct parsing of valid tables
    def test_filter_invalid_tables(self):
        seas = tfmkse.Season(0)
        seas.init_clubs()
        seas['fc-sevilla'].create_soup()
        seas['fc-sevilla'].init_players()
        seas['fc-sevilla']['nicolas-pareja'].create_soup()
        try:
            seas['fc-sevilla']['nicolas-pareja'].init_tables()
            table_ids = Set(seas['fc-sevilla']['nicolas-pareja'].tables.keys())
            # Obtained tables need to be Leage, Cup, Champions and Champions qualifiers
            # If tables in this player are not these (the order should not matter)
            # we fail the test
            self.assertTrue(table_ids == Set(['ES1', 'CDR', 'CLQ', 'CL']))
        except:
            self.assertTrue(False)

    # Test persistence is operating correctly by starting a local and remote season
    # and validating that an arbitrary appearance from an arbitrary player is equal
    # in both cases
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

# Helper to validate a value in a table by coodrinates
def validate_by_season_coordinates(season, club, player, table, date, stat ,value):
    season.init_clubs()
    season[club].create_soup()
    season[club].init_players()
    season[club][player].create_soup()
    season[club][player].init_tables()
    table_to_be_checked = season[club][player][table]
    return table_to_be_checked[table_to_be_checked._DATE_ == date].iloc[0][stat] == value

if __name__ == '__main__':
    unittest.main()