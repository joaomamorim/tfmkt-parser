import unittest
from sets import Set
from tfmktparser import *

class TestParsedStatistics(unittest.TestCase):

    # Here we validate that certain values in the tables have the expected values.
    def test_entries(self):
        # Load page 1
        seas = Season([1], 0)
        # Kylian Mbappe gave one assist on his game in the French Ligue 1 on 2017-09-30
        self.assertTrue(validate_by_season_coordinates(seas, 'fc-paris-saint-germain', 'kylian-mbappe', 'FR1', '2017-09-30', '_AS_', 1))
        # Test game id is extracted correctly when 'id' tag is not present (as-rome/alisson/Dec 1, 2017)
        self.assertTrue(validate_by_season_coordinates(seas, 'as-rom', 'alisson', 'IT1', '2017-12-1', '_GID_', 2897443))
        # Test yellow cards are extracted correctly
        # Sergio Ramos got a yellow card on his Champions League game on 2017-11-1 in the 90'
        self.assertTrue(validate_by_season_coordinates(seas, 'real-madrid', 'sergio-ramos', 'CL', '2017-11-1', '_YC_', 90))
        # Test validity of an appearance: played/not played. Flagged by '_V_' field
        # Arjen Robben was not of the game on 2017-09-19
        self.assertFalse(init_by_coodrinates(seas,'fc-bayern-munchen', 'arjen-robben').stats.loc['2017-09-19', '_V_'][0])
        # but he played on 2017-10-18 and gave an assist
        self.assertTrue(
            init_by_coodrinates(seas,'fc-bayern-munchen', 'arjen-robben').stats.loc['2017-10-18', '_V_'][0] and
            init_by_coodrinates(seas,'fc-bayern-munchen', 'arjen-robben').stats.loc['2017-10-18', '_AS_'][0] == 1
        )

    def test_filtering(self):
        seas = Season([1], 0)
        player_with_dupes = init_by_coodrinates(seas, 'fc-paris-saint-germain', 'alec-georgen')
        self.assertTrue("19YL" in player_with_dupes.tables.keys())
        self.assertTrue(len(player_with_dupes.stats['2017-09-12']) == 1)

    def test_update(self):
        seas = Season([1], 0)
        seas['fc-barcelona']['luis-suarez']['ES1']
        try:
            self.assertTrue(validate_by_season_coordinates(seas, 'fc-barcelona', 'luis-suarez', 'ES1', '2017-12-2', '_GS_', None))
        except IndexError:
            self.assertTrue(True)
        seas.update_players_soup(Player.has_table, "ES1")
        self.assertTrue(validate_by_season_coordinates(seas, 'fc-barcelona', 'luis-suarez', 'ES1', 'Dec 2, 2017', '_GS_', 1))

    # 'nicolas-pareja' from 'sevilla' has a trailing invalid table, this test makes sure
    # this kind of situation does not affect a correct parsing of valid tables
    def test_filter_invalid_tables(self):
        seas = Season([1], 0)
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
        season = Season([1], 1)
        remote_player = init_by_coodrinates(season,'fc-barcelona', 'lionel-messi')
        season.persist()
        del season
        season_local = Season([1], 0)
        local_player = init_by_coodrinates(season_local,'fc-barcelona', 'lionel-messi')
        lmessi_remote = remote_player['CL']
        lmessi_local = local_player['CL']
        del season_local
        self.assertEqual(
            lmessi_remote.loc['2017-09-12']['_GS_'],
            lmessi_local.loc['2017-09-12']['_GS_']
         )

# Helper to validate a value in a table by coodrinates
def validate_by_season_coordinates(season, club, player, table, date, stat ,value):
    table_to_be_checked = init_by_coodrinates(season, club, player)[table]
    return table_to_be_checked.loc[date][stat] == value

# Loads a player and initializes it's tables
def init_by_coodrinates(season, club, player):
    season.init_clubs()
    season[club].create_soup()
    season[club].init_players()
    season[club][player].create_soup()
    season[club][player].init_tables()
    return season[club][player]

if __name__ == '__main__':
    unittest.main()