import unittest
from __init__ import Season

class TestParsedStatistics:
    def test_entries(self):
        s = Season(2017, Season.REMOTE)
        try:
            s['real-madrid']['keylor-navas']['CL']
        except:
            assert False