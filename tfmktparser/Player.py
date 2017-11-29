import os
import urllib
import re
import pandas as pd
from itertools import izip
from bs4 import BeautifulSoup

from settings import *

class Player:

    GK  = 1
    DEF = 2
    MID = 3
    FOR = 4
    UNK = 0

    POSITION_MAPPER = {
        "Keeper" :              GK,
        "Centre-Back" :         DEF,
        "Left-Back" :           DEF,
        "Right-Back" :          DEF,
        "Defensive Midfield" :  MID,
        "Central Midfield" :    MID,
        "Attacking Midfield" :  MID,
        "Left Wing" :           FOR,
        "Right Wing" :          FOR,
        "Centre-Forward" :      FOR
    }

    def __init__(self, id, name, remote_uri, club_id, club_name):
        # Get a logger reference for all objects of player class to use
        self.logger = logging.getLogger(__name__)

        # Attributes initialization
        self.id = id
        self.name = name
        self.club_id = club_id
        self.club_name = club_name
        self.position = ""
        self.soup = None
        self.tables = {}

        # Set local and remote uri attributes
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + 'raw\\clubs\\CL_2017_%05d_%s\\PL_%05d_%s.html' % (club_id, club_name, self.id, self.name))
        self.remote_uri = remote_uri

        # Select uri to be used according to set mode
        self.current_uri = self.local_uri if source == LOCAL else self.remote_uri

    def create_soup(self):
        # Create a the BeautifulSoup object containing the html for the master
        self.logger.debug("Player URI is {}, creating soup".format(self.current_uri))
        self.soup = BeautifulSoup(safe_url_getter(self.current_uri), "html5lib")
        self.logger.debug("{} soup is ready".format(self.__repr__()))

    def __repr__(self):
        return "<Player: '%s' %d tables>" % (self.name, len(self.tables))

    def __getitem__(self, item):
        # If the search item is a string, assume regex and try to match all possible team names
        if isinstance(item, basestring):
            matching_tables = [table for table in self.tables.keys() if re.match(item, table)]
            if len(matching_tables) == 0:
                return None
            # If we only have a match, just return it
            elif len(matching_tables) == 1:
                return self.tables[matching_tables[0]]
            # Else return all matches
            else:
                return [self.tables[table_id] for table_id in matching_tables]
        # If the seach item is an integer, find by index
        if isinstance(item, int):
            return self.tables[0]

    def set_position(self, position):
        try:
            self.position = self.POSITION_MAPPER[position]
            self.logger.debug("Setted {0} ({1}) position to {2}".format(self.name, self.id, position))
        except:
            self.position = self.UNK

    def init_tables(self):
        # Finds all responsive tables in the document. Keep in mind that the first one is a summary table
        # that we want to discard
        root_tables = self.soup.select("div.box div.responsive-table")
        # The table itself comes after the 'table' tag for each responsive table
        tables = [table.find("table") for table in root_tables[-len(root_tables) + 1::]]
        # To find the table id we have to navigate back to the closest sibling with a class 'table-header'
        table_ids = [root_table.find_previous_sibling("div", class_="table-header").find("a")['name'] for root_table in root_tables[-len(root_tables) + 1::]]
        # Zip tables and ids in an iterable pair key-value
        id_table_pairs = izip(table_ids, tables)
        for id, table in id_table_pairs:
            self.logger.debug("Parsing table {}".format(id))
            self.tables[id] = self.parse_table(table)
            self.logger.debug("Finished parsing table {}".format(id))

    def parse_table(self, table):
        rows = [row for row in table.find("tbody").find_all("tr") if not row['class'][0] in ("bg_rot_20", "bg_gelb_20")]
        self.logger.debug("Found {} valid rows in this table".format(len(rows)))
        return pd.DataFrame.from_dict([self.parse_row(row) for row in rows], orient='columns')

    def parse_row(self, row):
        self.logger.debug("[%40s] parsing row \n{\n %s \n}" % (self.name, row))
        figures = row.select("td")
        appearance = {}
        appearance['_DATE_'] = figures[1].string.strip()
        appearance['_HT_'] = re.match("/([\w\-]+)/.*",figures[2].find("a", class_="vereinprofil_tooltip")['href']).group(1)
        appearance['_HTID_'] = (figures[2].find("a", class_="vereinprofil_tooltip"))['id']
        appearance['_AT_'] = re.match("/([\w\-]+)/.*", figures[4].find("a", class_="vereinprofil_tooltip")['href']).group(1)
        appearance['_ATID_'] = (figures[4].find("a", class_="vereinprofil_tooltip"))['id']
        appearance['_GID_'] = int(figures[6].find("a")['id'])
        parsed_result = re.search("([0-9]+):([0-9]+)", figures[6].find("span").text.strip())
        appearance['_GSH_'] = int(parsed_result.group(1))
        appearance['_GSA_'] = int(parsed_result.group(2))
        appearance['_POS_'] = figures[7].find("a").string.strip() if figures[7].find("a") is not None else None
        appearance['_GS_'] = int(figures[8].string) if figures[8].string is not None else 0
        appearance['_AS_'] = int(figures[9].string) if figures[9].string is not None else 0
        appearance['_GSS_'] = int(figures[10].string) if figures[10].string is not None else 0
        appearance['_YC_'] = int(figures[10].string) if figures[10].string is not None else 0
        try:
            appearance['_RC_'] = int(figures[12].string) if figures[12].string is not None else 0
        except:
            self.logger.error("Unable to assign _RC_ for {}".format(self.name))
        return appearance

    def persist(self):
        club_dir = "raw/clubs/CL_2017_%05d_%s" % (self.club_id, self.club_name)
        if not os.path.exists(club_dir):
            os.makedirs(club_dir)
        with open("%s/PL_%05d_%s.html" % (club_dir, self.id, self.name), 'w') as f:
            f.write(str(self.soup))

