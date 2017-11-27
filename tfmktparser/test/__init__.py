#C:\Python27\python.exe -m unittest tfmktparser.test
import unittest
import tfmktparser

class TestParsedStatistics(unittest.TestCase):
    def test_entries(self):
        tfmktparser.source = tfmktparser.LOCAL
        season = tfmktparser.Season()
        season.init_clubs()
        season['fc-barcelona'].create_soup()
        season['fc-barcelona'].init_players()
        season['fc-barcelona']['lionel-messi'].create_soup()
        season['fc-barcelona']['lionel-messi'].init_tables()
        lmessi_cl = season['fc-barcelona']['lionel-messi']['CL']
        self.assertEqual(lmessi_cl[lmessi_cl._DATE_ == "Sep 12, 2017"].iloc[0]['_GS_'], 2)

if __name__ == '__main__':
    unittest.main()