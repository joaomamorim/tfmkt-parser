import re
import os
import time
from bs4 import BeautifulSoup
import logging.config
import string
from itertools import izip
import urllib
import urllib2
import pandas as pd
from retrying import retry


LOCAL = 0
REMOTE = 1
HOST = "https://www.transfermarkt.co.uk"
source = REMOTE
#HOME_RAW = "C:\\Users\\david\\git\\tfmkt-parser\\"
HOME_RAW = "D:\\git-playground\\tfmkt-parser\\tfmkt-parser\\"


"""
Helper function. Downloads from URL with retries
"""
@retry(stop_max_attempt_number=3)
def safe_url_getter(uri):
        logger = logging.getLogger(__name__)
        try:
            req = urllib2.Request(uri, headers={'User-Agent': 'Mozilla/5.0'})
            file = urllib2.urlopen(req)
        except urllib2.HTTPError as err:
            logger.warn("Error retrieving file {}".format(uri), )
            if err.code == 404:
                return err.read()
        except urllib2.URLError:
            logger.warn("Attempt to download file {} failed: {}".format(uri, urllib2.URLError.message))
        else:
            return file.read()


class Season:

    """
    Constructor for the Season class looks for the master html file, either on the filesystem or on the transfer
    market server, and loads it into a BeautifulSoup object for a convenient parsing thereafter. The most important
    attribute in the class is the 'clubs' attribute. This is a list of Club objects representing the clubs found
    for this season. The 'clubs' list gets filled up when a call to the class method 'init_clubs' is made.
    The 'persist' method saves the season to filesystem using a known structure.
    """
    def __init__(self):
        # Get a logger reference for all objects of Season class to use
        self.logger = logging.getLogger(__name__)
        self.logger.info("Started season!")

        # Season initialization
        self.clubs = []
        self.clubs_desc = []

        # Load master html from either a local file of from the remote server
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + "raw/sub-master_2017.html".replace('/', '\\'))
        self.remote_uri = "https://www.transfermarkt.co.uk/vereins-statistik/wertvollstemannschaften/marktwertetop"
        master_uri = self.local_uri if source == LOCAL else self.remote_uri

        # Create a the BeautifulSoup object containing the html for the master

        self.soup = BeautifulSoup(safe_url_getter(master_uri), "html5lib")
        self.logger.debug("Master soup is ready")

    """
    Initialize the clubs for the season. Create a club in the 'clubs' list for each 'href' found in the master
    soup for a club. It parsed the club id and name from the url and instantiates a Club with this two attributes
    """
    def init_clubs(self):
        self.logger.info("Initizalizing clubs")
        start_time = time.time()
        # Remote urls are necessary in order to obtains clubs names and ids and therefore instantiate the clubs
        remote_urls = [HOST + tags['href'] for tags in self.soup.select("a.vereinprofil_tooltip")[::2]]

        # For each club url found in the master soup, create a Club object containing id, name and uri
        for remote_url in remote_urls:
            uri_re = re.match(
                "https://www.transfermarkt.co.uk/([\w\-]+)/startseite/verein/([0-9]+)/saison_id/2017",
                remote_url).groups()
            self.clubs.append(Club(int(uri_re[1]), uri_re[0], remote_url))
        elapsed_time = time.time() - start_time
        self.logger.info("Finished initializing clubs ({} seconds)".format(elapsed_time))

    """
    Force all players in a season to load their respective htmls from either local or remote and parse it into
    a BeautifulSoup object. If 'init_players' ends correctly, the season object is ready to call on the 'parse_tables'
    method
    """
    def init_players(self):
        self.logger.info("Initializing players")
        start_time = time.time()
        # Call for initialization of all reason players
        for club in self.clubs:
            club.init_players()
        elapsed_time = time.time() - start_time
        self.logger.info("Finished initializing players ({} seconds)".format(elapsed_time))

    """
    Persists the season to disk. It recursively saves the in-memory representation of the season to a directory tree with all the
    necessary html files needed to recover the state. All soup attributes from the Season, Clubs and Players need to be populated
    before we call this method
    """
    def persist(self):
        if not os.path.exists("raw"):
            os.makedirs("raw")
        with open("raw/sub-master_2017.html", 'w') as f:
            f.write(str(self.soup))
        for club in self.clubs:
            club.persist()

    """
    Implementation of the magic method __getitem_. Using this implementation we are able to find 'Club' objects
    in a season by looking them up by:
    1) Regex expression: When trying to index a season with a string, this is interpreted as a regular expresion
    and returns all clubs whose name matches the provided regex in an iterable. If the matching clubs is only one
    instance, the it returns the club itself rather than an iterable
    2) Position in the list: When the intex passed is an integer, then the function returns the club in this position
    in the 'clubs' list
    """
    def __getitem__(self, item):
        # If the search item is a string, assume regex and try to match all possible team names
        if isinstance(item, basestring):
            matching_clubs = [club for club in self.clubs if re.match(item, club.name)]
            if len(matching_clubs) == 0:
                return None
            # If we only have a match, just return it
            elif len(matching_clubs) == 1:
                return matching_clubs[0]
            # Else return all matches
            else:
                return matching_clubs
        # If the seach item is an integer, find by index
        if isinstance(item, int):
            return self.clubs[0]



class Club:
    """
    Constructor for the Club class looks for the club html file, either on the filesystem or on the transfer
    market server, and loads it into a BeautifulSoup object for a more convenient parsing thereafter. The most important
    attribute in the class is the 'players' attribute. This is a list of Player objects representing the players found
    for this club. The 'players' list gets filled up when a call to the class method 'init_players' is made.
    The 'persist' method saves the season to filesystem using a known structure.
    """
    def __init__(self, id, name, uri):
        # Get a logger reference for all objects of class Club
        self.logger = logging.getLogger(__name__)

        # Initialize basic attributes
        self.id = id
        self.name = name
        self.players = []

        # Set local and remote uri attributes
        self.remote_uri = uri
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + ("raw/clubs/CL_2017_%05d_%s.html" % (id, name)).replace('/', '\\'))

        # Select the uri to use for the current mode
        self.current_uri = self.remote_uri if source == REMOTE else self.local_uri

    def create_soup(self):
        # Initialize Club
        self.logger.info("Creating club from source {}".format(self.current_uri))
        self.soup = BeautifulSoup(safe_url_getter(self.current_uri), "html5lib")
        self.logger.info("Done initializing {}".format(self.__repr__()))

    def init_players(self):
        # Start filling up the 'players' list
        self.logger.info("Initialzing players in {}".format(self.name))

        # Remote urls are necessary in order to obtains clubs names and ids and therefore instantiate the clubs
        remote_urls = []
        for remote_url_compact in self.soup.select("span.hide-for-small a.spielprofil_tooltip"):
            remote_url = string.replace(HOST + remote_url_compact['href'] + "/saison/2017/plus/1#CL", "profil", "leistungsdaten") + "/saison/2017/plus/1#CL"
            remote_urls.append(remote_url)
            url_re = re.match(r"https://www.transfermarkt.co.uk/([\w\-]+)/leistungsdaten/spieler/([0-9]+)/.*$",
                              remote_url).groups()
            self.players.append(Player(int(url_re[1]), url_re[0], remote_url, self.id, self.name))
        self.logger.info("{} finished initializing players".format(self.__repr__()))

    def persist(self):
        if not os.path.exists("raw/clubs"):
            os.makedirs("raw/clubs")
        with open("raw/clubs/CL_2017_%05d_%s.html" % (self.id, self.name), 'w') as f:
            f.write(str(self.soup))
        if not os.path.exists("raw/clubs//CL_2017_%05d_%s" % (self.id, self.name)):
            os.makedirs("raw/clubs//CL_2017_%05d_%s" % (self.id, self.name))
        for player in self.players:
            player.persist()

    def __repr__(self):
        if self.players == None:
            return "<Club: '%s' %s>" % (self.name, "Empty")
        else:
            return "<Club: '%s' %d players>" % (self.name, len(self.players))

    def __getitem__(self, item):
        # If the search item is a string, assume regex and try to match all possible team names
        if isinstance(item, basestring):
            matching_players = [player for player in self.players if re.match(item, player.name)]
            if len(matching_players) == 0:
                return None
            # If we only have a match, just return it
            elif len(matching_players) == 1:
                return matching_players[0]
            # Else return all matches
            else:
                return matching_players
        # If the seach item is an integer, find by index
        if isinstance(item, int):
            return self.players[0]



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

