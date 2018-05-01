import os
import string
import time
import urllib
import urllib2
import logging
import re
import yaml
import sqlalchemy
import ConfigParser
import pandas as pd
from bs4 import BeautifulSoup
from retrying import retry
from itertools import izip
from enum import Enum
from sqlalchemy import create_engine
from dateutil import parser as date_parser

__all__ = ["Mode", "HOME_RAW", "HOST", "DATABASE", "safe_url_getter", "Season", "Club", "Player"]

"""
Possible modes are LOCAL (backed by locally cached data) and REMOTE (data is download and parsed in "real time")
"""
class Mode(Enum):
    LOCAL = 0
    REMOTE = 1

"""
Initialize global variables from configuration
"""
config = ConfigParser.ConfigParser()
config.read("conf/tfmkt.cfg")
HOST = config.get("global", "domain")
HOME_RAW = config.get("global", "data")
DATABASE = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    config.get("database", "user"),
    config.get("database", "password"),
    config.get("database", "host"),
    config.get("database", "port"),
    config.get("database", "database")
)

"""
Helper function. Downloads from URL with retries
"""
@retry(stop_max_attempt_number=3)
def safe_url_getter(uri):
    logger = logging.getLogger(__name__)
    if re.match(r"file://.*", uri):
        path = uri[8::]
        logger.debug("Retrieve from local filesystem {}".format(path))
        try:
            with open(path, 'r') as f:
                content = f.read()
                f.close()
                return content
        except:
            logger.error("Error reading local file {}".format(uri))
            return None
    else:
        try:
            req = urllib2.Request(uri, headers={'User-Agent': 'Mozilla/5.0'})
            file = urllib2.urlopen(req)
        except urllib2.HTTPError as err:
            logger.warn("Attempt to download file {} failed: {}".format(uri), err.read())
            return None
        except urllib2.URLError:
            logger.warn("Attempt to get file {} failed: {}".format(uri, urllib2.URLError))
            return None
        else:
            return file.read()


logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))

class Season:

    ##########################################################################################################
    # MAGIC                                                                                                  #
    ##########################################################################################################

    """
    Constructor for the Season class looks for the master html file, either on the filesystem or on the transfer
    market server, and loads it into a BeautifulSoup object for a convenient parsing thereafter. The most important
    attribute in the class is the 'clubs' attribute. This is a list of Club objects representing the clubs found
    for this season. The 'clubs' list gets filled up when a call to the class method 'init_clubs' is made.
    The 'persist' method saves the season to filesystem using a known structure.
    """
    def __init__(self, pages, source = Mode.LOCAL):
        # Get a logger reference for all objects of Season class to use
        self.logger = logging.getLogger(__name__)
        self.logger.info("Started season!")

        # Season initialization
        self.year = 2017
        self.clubs = []
        self.clubs_desc = []
        self.source = source
        self.soups = []

        # Load master html from either a local file of from the remote server
        #self.local_base_uri = "file:" + urllib.pathname2url(HOME_RAW + "raw/sub-master_2017_page%d.html".replace('/', '\\'))
        local_base_uri = "file:///" + HOME_RAW.replace('\\', '/') + "raw/sub-master_2017_page%d.html"
        #local_base_uri = "file:" + urllib.pathname2url(HOME_RAW + "raw/sub-master_2017_page%d.html".replace('/', '\\'))
        remote_base_uri = "https://www.transfermarkt.co.uk/vereins-statistik/wertvollstemannschaften/marktwertetop?page=%d"
        self.local_uris = [ local_base_uri % page for page in pages]
        self.remote_uris = [ remote_base_uri % page for page in pages]
        master_base_uris = self.local_uris if self.source == Mode.LOCAL else self.remote_uris

        # Urls are necessary in order to obtains clubs names and ids and therefore instantiate the clubs
        # All 100 clubs are splitted among a total of 4 pages. We loop throw all pages, concatenating all the
        # clubs we find to 'remote_urls' list.
        for url in master_base_uris:
            html = safe_url_getter(url)
            if html is not None:
                self.soups.append(BeautifulSoup(html, "html5lib"))
                self.logger.debug("Master soup page is ready: {}".format(url))
            else:
                self.logger.error("Unable to obtain html from master page: {}".format(url))

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

    """
    Create official string representation of a season. Let us give a summary of clubs an players in one
    liner and thats all
    """
    def __repr__(self):
        if self.clubs == None:
            return "<Season: '%d' %s>" % (self.year, "Empty")
        else:
            return "<Season: '%d' %d clubs (%d souped)>" % (self.year, self.size, self.size_souped)

    ##########################################################################################################
    # PROPERTIES                                                                                             #
    ##########################################################################################################

    """
    Total number of club object currently in the season
    """
    @property
    def size(self):
        if self.clubs is not None:
            return len(self.clubs)
        else:
            return None

    """
    Total number of club objects currently in the season which have loaded their html create_soup
    """
    @property
    def size_souped(self):
        return len(filter(lambda x: x.soup is not None, self.clubs))

    ##########################################################################################################
    # PROPAGATION METHODS                                                                                    #
    ##########################################################################################################

    """
    Propagates an operation to all clubs in the season
    """
    def propagate_to_clubs(self, function):
        self.logger.info("Propagating {} to all clubs".format(function))
        start_time = time.time()
        if self.size is not None and self.size > 0:
            # Call for initialization of all reason players
            for club in self.clubs:
                function(club)
            elapsed_time = time.time() - start_time
            self.logger.info("Finished propagating %s (%.2f seconds)" % (function, elapsed_time))
        else:
            self.logger.error("State of 'clubs' does not allow for propagation (null or empty)")

    """
    Propagates an operation to all players in the season.
    *arguments optional parameter allows for specfifying parameters to function of the player instance.
    Parameters in *arguments can be functions as well as values. This is the case, for example, for the
    'update_players_soup' method, which propagates the method 'update_soup_if' down to all players. This
    method takes as parameters a function and an argument (a condition evaluator and an argument to such
    evaluator)
    """
    def propagate_to_players(self, function, *arguments):
        self.logger.info("Propagating {} to all players".format(function))
        start_time = time.time()
        if self.size is not None and self.size > 0:
            # Call for initialization of all reason players
            for i, club in enumerate(self.clubs):
                self.logger.info("[%3s/%-3s] %s propagating %s" % (str(i), str(len(self.clubs)), club.__repr__(), str(function)))
                if arguments is None or len(arguments) == 0:
                    club.propagate_to_players(function)
                else:
                    club.propagate_to_players(function, arguments)
            elapsed_time = time.time() - start_time
            self.logger.info("Finished propagating %s (%.2f seconds)" % (function, elapsed_time))
        else:
            self.logger.error("State of 'clubs' does not allow for propagation (null or empty)")

    ##########################################################################################################
    # REGULAR METHODS                                                                                        #
    ##########################################################################################################
    """
    Initialize the clubs for the season. Create a club in the 'clubs' list for each 'href' found in the master
    create_soup for a club. It parses the club id and name from the url and instantiates a Club with this two attributes
    """
    def init_clubs(self, force = False):
        # Avoid double initialization of players. If the players vector is not empty, do not run unless
        # 'force' flag is passed
        if len(self.clubs) > 0 and not force:
            self.logger.warning("{} skipped 'clubs' intialization to avoid double initialization. Force initialization by passing 'force' flag".format(self.__repr__()))
            return
        self.logger.info("Initizalizing clubs")
        start_time = time.time()

        # Scan master pages for club urls
        # Cummulate all urls the 'remote_urls' vector
        remote_urls = []
        for page in self.soups:
            remote_urls += [HOST + tags['href'] for tags in page.select("a.vereinprofil_tooltip")[::2]]

        # For each club url found in the master create_soup, create a Club object containing id, name and uri
        for remote_url in remote_urls:
            uri_re = re.match(
                "https://www.transfermarkt.co.uk/([\w\-]+)/startseite/verein/([0-9]+)/saison_id/2017",
                remote_url).groups()
            self.clubs.append(Club(int(uri_re[1]), uri_re[0], remote_url, self.source))
        elapsed_time = time.time() - start_time
        self.logger.info("Finished initializing clubs (%.2f seconds)" % (elapsed_time))
        #self.logger.info("Finished initializing clubs ({} seconds)".format(elapsed_time))

    """
    Initializes 'players' vector on every club in the season. After initialization, 'players' contains a list
    of all available players, identified by 'name', 'id', 'club_name' and 'club_id'. They also hold a reference
    to both the local and remote own sources.
    """
    def init_players(self):
        self.propagate_to_clubs(Club.init_players)

    """
    Triggers the souping of all clubs in the season, and propagates it down to all players also.
    It is equivalent to a full download of the season when source is REMOTE. If 'soup_reason' 
    ends correctly, the season object is ready to call on 'init_tables'
    """
    def soup_season(self):
        start_time = time.time()
        if self.clubs is None or self.size == 0:
            self.logger.error("Clubs are not initialized, run 'init_clubs' first")
            return
        self.propagate_to_clubs(Club.create_soup)
        self.propagate_to_clubs(Club.init_players)
        self.propagate_to_players(Player.create_soup)

    """
    Triggers initialization of all tables in a season (all tables form all players)
    """
    def init_tables(self):
        self.propagate_to_players(Player.init_tables)

    """
    Persists the season to disk. It recursively saves the in-memory representation of the season to a directory tree with all the
    necessary html files needed to recover the state. All create_soup attributes from the Season, Clubs and Players need to be populated
    before we call this method
    """
    def persist(self):
        self.logger.debug("Persisting season {}".format(self.__repr__()))
        for i, soup in enumerate(self.soups):
            if not os.path.exists("raw"):
                os.makedirs("raw")
            with open("raw/sub-master_2017_page%d.html" % (i+1), 'w') as f:
                f.write(str(soup))
        self.propagate_to_clubs(Club.persist)
        self.propagate_to_players(Player.persist)

    """
    Persist a season to disk, but making a less intensive usage of memory.
    """
    def persist_on_demand(self):
        self.logger.debug("Persisting season {}".format(self.__repr__()))
        for i, soup in enumerate(self.soups):
            if not os.path.exists("raw"):
                os.makedirs("raw")
            with open("raw/sub-master_2017_page%d.html" % (i+1), 'w') as f:
                f.write(str(soup))
        self.propagate_to_clubs(Club.persist_on_demand)
        self.propagate_to_players(Player.persist_on_demand)


    """
    Toggle mode form LOCAL to REMOTE or viceversa. It propagates the change all over the season clubs and players
    """
    def toggle_source(self):
        self.logger.info("{} source is {}, toggling...".format(self.__class__.__name__, self.source))
        # Toggle source attribute
        self.source = Mode.REMOTE if self.source == Mode.LOCAL else Mode.LOCAL
        # Update current uri
        self.update_current_uris()
        self.propagate_to_clubs(Club.toggle_source)
        self.propagate_to_players(Player.toggle_source)
        self.logger.info("{} source is {}".format(self.__class__.__name__, self.source))

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uris(self):
        self.current_uris = self.local_uris if self.source == Mode.LOCAL else self.remote_uris

    """
    Triggers update of all players matching a certain condition from the remote server. The idea is to be able
    to download only those players who require so because their are likely to have new entries in their tables
    """
    def update_players_soup(self, condition, argument):
        self.propagate_to_players(Player.update_soup_if, condition, argument)

    """
    Same as the previous one, but persisting and freeing the memory for the soup after each update
    """
    def update_players_soup_on_demand(self, condition, argument):
        self.propagate_to_players(Player.update_soup_if_on_demand, condition, argument)

    """
    Update mysql table
    """
    def update_mysql(self):
        engine = create_engine(DATABASE)
        engine.execute("DELETE FROM tfmkt.appearances_buffer;")
        self.propagate_to_players(Player.to_mysql, engine)
        engine.execute("REPLACE INTO tfmkt.appearances SELECT * FROM tfmkt.appearances_buffer;")

class Club:

    ##########################################################################################################
    # MAGIC                                                                                                  #
    ##########################################################################################################

    """
    Constructor for the Club class looks for the club html file, either on the filesystem or on the transfer
    market server, and loads it into a BeautifulSoup object for a more convenient parsing thereafter. The most important
    attribute in the class is the 'players' attribute. This is a list of Player objects representing the players found
    for this club. The 'players' list gets filled up when a call to the class method 'init_players' is made.
    The 'persist' method saves the season to filesystem using a known structure.
    """
    def __init__(self, id, name, uri, source=Mode.LOCAL):
        # Get a logger reference for all objects of class Club
        self.logger = logging.getLogger(__name__)

        # Initialize basic attributes
        self.id = id
        self.name = name
        self.players = []
        self.soup = None
        self.source = source

        # Set local and remote uri attributes
        self.remote_uri = uri
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + ("raw/clubs/CL_2017_%05d_%s.html" % (id, name)))

        # Select the uri to use for the current mode
        self.update_current_uri()

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

    ##########################################################################################################
    # PROPERTIES                                                                                             #
    ##########################################################################################################

    @property
    def is_souped(self):
        return True if self.soup is not None else False

    ##########################################################################################################
    # PROPAGATION METHODS                                                                                    #
    ##########################################################################################################
    """
    Propagates a function to all players in the club. Propagation can optionally pass parameters together with
    the function whose propagation is performing.
    """
    def propagate_to_players(self, function, *arguments):
        if self.players is None or len(self.players) == 0:
            self.logger.debug("{} cannot continue propagation: 'players' is null or empty".format(self.__repr__()))
            return

        for player in self.players:
            if arguments is None or len(arguments) == 0:
                function(player)
            else:
                function(player, arguments)

    ##########################################################################################################
    # REGULAR METHODS                                                                                        #
    ##########################################################################################################
    def init_players(self, force=False):
        # Avoid double initialization of players. If the players vector is not empty, do not run unless
        # 'force' flag is passed
        if len(self.players) > 10 and not force:
            self.logger.warning("{} skipped 'players' intialization to avoid double initialization. Force initialization by passing 'force' flag".format(self.__repr__()))
            return
        # The club create_soup needs to be up and ready before we try to initialize players.
        # We check for 'soupness' frist
        if not self.is_souped:
            self.logger.error("{} soup is not initialized, 'soup' first".format(self.__repr__()))
            return

        # Start filling up the 'players' list
        self.logger.info("Initialzing players in {}".format(self.name))

        # Remote urls are necessary in order to obtains clubs names and ids and therefore instantiate the clubs
        remote_urls = []
        for remote_url_compact in self.soup.select("span.hide-for-small a.spielprofil_tooltip"):
            remote_url = string.replace(HOST + remote_url_compact['href'] + "/saison/2017/plus/1#CL", "profil", "leistungsdaten") + "/saison/2017/plus/1#CL"
            remote_urls.append(remote_url)
            url_re = re.match(r"https://www.transfermarkt.co.uk/([\w\-\%]+)/leistungsdaten/spieler/([0-9]+)/.*$",
                              remote_url).groups()
            self.players.append(Player(int(url_re[1]), url_re[0], remote_url, self.id, self.name, self.source))
        self.logger.info("{} finished initializing players".format(self.__repr__()))

    """
    Retrieves the html resource from the current sources and parses it into a BeautifulSoup object
    """
    def create_soup(self, force=False):
        self.logger.info("{} souping".format(self.__repr__()))
        # Keep souping from going ahead if a create_soup is already available. We can force souping to happend anyways
        # by passing 'force'=True as an argument
        if self.is_souped and not force:
            self.logger.debug("{} already souped, skipping. Force souping by passing 'force' flag".format(self.__repr__()))
            return
        # Go on and try to get the html resource from source
        html = safe_url_getter(self.current_uri)
        if html is None:
            self.logger.error("{} error creating soup. We can try again later with 'soup_season'".format(self.__repr__()))
            return
        # Initialize Club
        self.logger.debug("Creating club from source {}".format(self.current_uri))
        self.soup = BeautifulSoup(html, "html5lib")
        self.logger.debug("Done initializing {}".format(self.__repr__()))

    def init_players_on_demand(self):
        self.create_soup()
        self.init_players()
        self.soup = None

    def persist_on_demand(self):
        self.create_soup()
        self.persist()
        self.soup = None

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uri(self):
        self.current_uri = self.local_uri if self.source == Mode.LOCAL else self.remote_uri

    def persist(self):
        if not self.is_souped:
            self.logger.debug("{} is not souped, skip".format(self.__repr__()))
            return
        if not os.path.exists("raw/clubs"):
            os.makedirs("raw/clubs")
        with open("raw/clubs/CL_2017_%05d_%s.html" % (self.id, self.name), 'w') as f:
            f.write(str(self.soup))
        if not os.path.exists("raw/clubs//CL_2017_%05d_%s" % (self.id, self.name)):
            os.makedirs("raw/clubs//CL_2017_%05d_%s" % (self.id, self.name))
        for player in self.players:
            if player.soup is not None:
                player.persist()

    """
    Toggle mode form LOCAL to REMOTE or viceversa. It propagates the change all over the season clubs and players
    """
    def toggle_source(self):
        self.logger.debug("{} source is {}, toggling...".format(self.__class__.__name__, self.source))
        # Toggle source attribute
        self.source = Mode.REMOTE if self.source == Mode.LOCAL else Mode.LOCAL
        # Update current uri
        self.update_current_uri()
        self.logger.debug("{} source is {}".format(self.__class__.__name__, self.source))

class Player:
    # In order to calculate the score for a given appearance we need to know the players
    # position. It has to fall into one of the categories below.
    GK  = 1
    DEF = 2
    MID = 3
    FOR = 4
    UNK = 0

    # The position mapper is just for pairing the raw position as it is parsed from the
    # soup in string format to an integer representing the position on one of the categories
    # above
    POSITION_MAPPER = {
        "Keeper" :              GK,
        "Centre-Back" :         DEF,
        "Left-Back" :           DEF,
        "Right-Back" :          DEF,
        "Defensive Midfield" :  MID,
        "Left Midfield":        MID,
        "Right Midfield":       MID,
        "Central Midfield" :    MID,
        "Attacking Midfield" :  MID,
        "Left Wing" :           FOR,
        "Right Wing" :          FOR,
        "Secondary Striker":    FOR,
        "Centre-Forward" :      FOR
    }

    # Some times we find tables in the data that are messing up the constraint of 'one-appearance-per-day'
    # for the player. This is because some players are in an intermediate stage between the first and the
    # second team, and BOTH appearances are shown for a game of the first team and the second team. To avoid
    # a situation when we have a player with two appearances in the same day, we filter out tables for
    # secondary leagues and youth tournaments.
    IGNORE_TABLES = ["19YL", "ES2", "GB21", "GB18", "RLB3", "IJ1", "RLW3", "RLSW",
                     "RLN3", "RLN4", "L3", "OLW3", "PO2", "RU2", "NLJV", "CGB", "AJ3",
                     "POMX"]



    ##########################################################################################################
    # MAGIC                                                                                                  #
    ##########################################################################################################
    """
    Class constructor...
    """
    def __init__(self, id, name, remote_uri, club_id, club_name, source=Mode.LOCAL):
        # Get a logger reference for all objects of player class to use
        self.logger = logging.getLogger(__name__)

        # Attributes initialization
        self.id = id
        self.name = name
        self.club_id = club_id
        self.club_name = club_name
        self.raw_position = ""
        self.birthdate = None
        self.position = None
        self.soup = None
        self.tables = {}
        self.stats = None
        self.source = source

        # Set local and remote uri attributes
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + 'raw/clubs/CL_2017_%05d_%s/PL_%05d_%s.html' % (club_id, club_name, self.id, self.name))
        self.remote_uri = remote_uri

        # Select uri to be used according to set mode
        self.update_current_uri()

    def __repr__(self):
        return "<Player: '%s' %d tables%s>" % (self.name, len(self.tables), " (not souped)" if self.soup is None else "")

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

    ##########################################################################################################
    # PROPERTIES                                                                                             #
    ##########################################################################################################

    @property
    def is_souped(self):
        return True if self.soup is not None else False

    ##########################################################################################################
    # REGULAR METHODS                                                                                        #
    ##########################################################################################################

    def create_soup(self, force=False):
        # Keep souping from going ahead if a create_soup is already available. We can force souping to happend anyways
        # by passing 'force'=True as an argument
        if self.is_souped and not force:
            self.logger.debug("{} already souped, skipping. Force souping by passing 'force' flag".format(self.__repr__()))
            return
        # Go on and try to get the html resource from source
        html = safe_url_getter(self.current_uri)
        if html is None:
            self.logger.error("{} [{}] souping failed. Retry with 'soup_season'".format(self.__repr__(), self.club_name))
            self.soup = None
            return
            # Create a the BeautifulSoup object containing the html for the master
        self.logger.debug("Player URI is {}, creating soup".format(self.current_uri))
        self.soup = BeautifulSoup(html, "html5lib")
        self.logger.debug("{} soup is ready".format(self.__repr__()))

    def set_position(self):
        try:
            self.position = Player.POSITION_MAPPER[self.raw_position]
            self.logger.debug("Setted {0} ({1}) position to {2}({3})".format(self.name, self.id, self.raw_position, self.position))
        except:
            self.logger.debug("{} unable to set position {}".format(self.__repr__(), self.raw_position))
            self.position = self.UNK

    def init_tables(self, force=False):
        # Avoid double initialization of tables
        if len(self.tables) > 0 and not force:
            self.logger.warning("{} avoided unintended initialization of tables, use 'force' flag to force it".format(self.__repr__()))
            return
        # We require the player to be souped before we can parse any stats
        elif not self.is_souped:
            self.logger.debug("{} is not souped, cannot init tables".format(self.__repr__()))
            return
        # If the player is souped, the we are ready to parse the stats.
        # We make sure the tables are empty and start with the parsing.
        else:
            self.tables = {}

        # Just before parsing tables, try to find some general information from the main panel of the player
        # page. At the moment, we parse the player birthdate and the position in the field
        # Collect the informations in the panel into an iterable
        main_panel_figures = self.soup. \
            find('div', class_ = 'dataMain'). \
            find_next_sibling('div', class_ = 'dataContent'). \
            select('div div p span.dataItem')
        # The information about the position we will find it in the sibling node to the 'Postion' tag
        self.raw_position = filter(lambda x: "Position" in x.string.strip(),main_panel_figures)[0]. \
            find_next_sibling().string.strip()
        self.set_position()
        # Similiarly, the birth date we find it in the "Born/age" element
        raw_date = filter(lambda x: "Born/age" in x.string.strip(),main_panel_figures)[0]. \
            find_next_sibling().string.strip()
        #self.birthdate = date_parser.parse(raw_date)

        # Find all responsive tables in the document. Keep in mind that the first one is a summary table
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
            if id not in ("gesamt"):
                self.tables[id] = self.parse_table(id, table)
                self.tables[id].set_index('_DATE_', inplace=True)
                #self.tables[id]
            else:
                self.logger.debug("{} found invalid table with id {}".format(self.__repr__(), id))
            self.logger.debug("Finished parsing table {}".format(id))
        # Regenerate stats attribute (simply a merging of all tables)
        # Some tables contain duplicate appearances (such as 'YL19', where a parallel game is played between young
        # teams every time an official 'CL' game is played)
        filtered_stats = {key : value for (key, value) in self.tables.items() if key not in Player.IGNORE_TABLES} if len(self.tables) > 0 else None
        self.stats = pd.concat(filtered_stats.values()) if filtered_stats is not None and len(filtered_stats) > 0 else None

    def parse_table(self, id,  table):
        self.logger.debug("{} raw table dump {}".format(self.__repr__(), table.find("tbody")))
        header_elements = table.find("thead").find_all("th")
        header_dict = Player.parse_headers(header_elements)

        #self.logger.debug("{} all rows in list form: {}".find(self.__repr__(), sall_rows)))
        #rows = [row for row in table.find("tbody").find_all("tr") if row.has_attr('class') and not row['class'][0] in ("bg_rot_20", "bg_gelb_20", "bg_blau_20")]
        rows = [row for row in table.find("tbody").find_all("tr")]
        self.logger.debug("Found {} rows in this table".format(len(rows)))
        parsed_rows = [self.parse_row(id, header_dict,row) for row in rows]
        return pd.DataFrame.from_dict([row for row in parsed_rows if row is not None], orient='columns')

    @staticmethod
    def parse_headers(headers):
        header_dict = {}
        for i, element in enumerate(headers):
            if element.string == "Match day":
                header_dict['_MD_'] = i
            elif element.string == "Date":
                header_dict['_DATE_'] = i
            elif element.string == "Home team":
                header_dict['_HT_'] = i
            elif element.string == "Visiting team":
                header_dict['_AT_'] = i
            elif element.string == "Result":
                header_dict['_AGG_'] = i
            elif element.string == "Pos.":
                header_dict['_POS_'] = i
            else:
                # The column has no name, try to identify de column by the sibbling class to 'icons_sprite'
                try:
                    sibling_class = element.find('span')['class'][1]
                    if sibling_class == "icon-tor-table-header":
                        header_dict['_GS_'] = i
                    elif sibling_class == "icon-vorlage-table-header":
                        header_dict['_AS_'] = i
                    elif sibling_class == "icon-eigentor-table-header":
                        header_dict['_GSS_'] = i
                    elif sibling_class == "icon-gelbekarte-table-header":
                        header_dict['_YC_'] = i
                    elif sibling_class == "icon-gelbrotekarte-table-header":
                        header_dict['_Y2_'] = i
                    elif sibling_class == "icon-rotekarte-table-header":
                        header_dict['_RC_'] = i
                    elif sibling_class == "icon-einwechslungen-table-header":
                        header_dict['_SO_'] = i
                    elif sibling_class == "icon-auswechslungen-table-header":
                        header_dict['_SI_'] = i
                    elif sibling_class == "icon-spielernote":
                        header_dict['_R_'] = i
                    elif sibling_class == "icon-minuten-table-header":
                        header_dict['_MIN_'] = i
                    else:
                        print "No match: " + sibling_class
                        return None
                except :
                    print "Exception"
                    return None
        return header_dict

    def parse_row(self, id, headers, row):
        self.logger.debug("%s parsing row \n{\n %s \n}" % (self.__repr__(), row))
        # If the row is of class 'bg_blau_20' then it's a dummy row and we wont be able to parse anything from it
        # Skip it
        if row.find('td').has_attr('class') and "bg_blau_20" in row.find('td')['class']:
            self.logger.debug("{} found blue row, skipping".format(self.__repr__()))
            return None
        # Assume at least the game information is present in the row. Getting ready
        # to parse game info. Get all row elemnts, excluding those with the 'no-border-rechts'
        # class, since these mess up the column indices
        all_figures = row.find_all("td")
        figures = filter(lambda x: not "no-border-rechts" in x['class'],all_figures)
        self.logger.debug("{} dump mappings figure name -> element".format(self.__repr__()))
        for key, value in headers.iteritems():
            try:
                element_as_string = figures[value]
            except IndexError:
                element_as_string = "Empty"
            self.logger.debug("%s(%d)  -> %s" % (key, value, element_as_string))
        # Init row
        appearance = {}
        # Some row fields are available even before we start parsing the html
        # These are the ones already parsed from the club html and the player url
        appearance['_PID_'] = self.id               # The player numeric ID
        appearance['_PNAME_'] = self.name           # The player name
        appearance['_RPOS_'] = self.raw_position    # The player raw position
        appearance['_POS_'] = self.position
        appearance['_CID_'] = self.club_id          # The club id
        appearance['_CNAME_'] = self.club_name      # The club name
        # The appearance is 'invalid' unless this is changed down in the flow
        appearance['_V_'] = False
        # Assign the competition 'id'. This is passed as a parameter to the parse_row function by the parse_table
        # which actually extracts out the current competition id from the html
        appearance['_C_'] = id
        # Date in the 'detailed' view table is an a format such as 'Sep 30, 2017'. We extract the element and parse it
        # into datetime value. We use the date_parser third party library, which automatically detects the correct
        # format in the date string
        appearance['_DATE_'] = date_parser.parse(figures[headers['_DATE_']].string.strip())
        # Extract the name of the club. Normally it should be easy to find the team name in the 'href' attribute in the
        # vereinprofil class
        try:
            href_with_teamh_name = figures[headers['_HT_']].find("a", class_="vereinprofil_tooltip")['href']
            appearance['_HT_'] = re.match(r"/([\w\-]+)/.*",href_with_teamh_name).group(1)
        # but it can happen that the href has strange characteres. In such case the regex match
        # fails and we run into a 'AttributeError'. We capture this exception, give a warning and assign 'None' to
        # the 'HT' element for this appearance.
        # Example: 'jan-bednarek' from 'fc-southampton' has an 'href' for the first game of the Europa Leage Qualifiers
        # in 2017 of '/lech-pozna%C5%84/spielplan/verein/238/saison_id/2017'.
        except AttributeError:
            appearance['_HT_'] =  re.match(r"/([\w\-\%]+)/.*",href_with_teamh_name).group(1)
            self.logger.debug("{} was not able to extract 'HT' name from 'href' '{}', reattempting".format(self.__repr__(), href_with_teamh_name))
        appearance['_HTID_'] = (figures[headers['_HT_']].find("a", class_="vereinprofil_tooltip"))['id']
        # The 'AT' (Away Team) attribute is analogous to 'HT' and it can go through the same situations
        try:
            href_with_teama_name = figures[headers['_AT_']].find("a", class_="vereinprofil_tooltip")['href']
            appearance['_AT_'] = re.match("/([\w\-]+)/.*", href_with_teama_name).group(1)
        except AttributeError:
            appearance['_AT_'] = re.match("/([\w\-\%]+)/.*", href_with_teama_name).group(1)
            self.logger.debug("{} was not able to extract 'AT' name from 'href' '{}', reattempting".format(self.__repr__(), href_with_teama_name))
        appearance['_ATID_'] = (figures[headers['_AT_']].find("a", class_="vereinprofil_tooltip"))['id']
        # The game is usually an attribute in row number 6 (inside de 'a' tag)
        # Try to extract it by querying this 'id' inside of 'a'
        try:
            appearance['_GID_'] = int(figures[headers['_AGG_']].find("a")['id'])
        # It can happen that the attribute 'id' is not present in some row, in such case fallback to extract
        # the game id from the 'href' of the game
        except KeyError:
            self.logger.debug("{} missing attribute game 'id' for the row, attepting extraction from 'href'".format(self.__repr__()))
            appearance['_GID_'] = int(re.search(r".*/([0-9]+)$", figures[headers['_AGG_']].find("a")['href']).group(1))
        parsed_result = re.search("([0-9]+):([0-9]+)", figures[headers['_AGG_']].find("span").text.strip())
        appearance['_GSH_'] = int(parsed_result.group(1))
        appearance['_GSA_'] = int(parsed_result.group(2))
        # If the player had not played the game, trying to parse the rest of the statistics would give an error
        # therefore we finish the parsing here when we find an identifier for 'not played'. Such identifier is
        # the presence of any of the "bg_rot_20", "bg_gelb_20" or "bg_blau_20" class identifiers in the row
        if row.has_attr('class') and row['class'][0] in ("bg_rot_20", "bg_gelb_20", "bg_blau_20"):
            return appearance
        # If the player played the game (we assume so if we have come this far) flag the appearance to 'valid'
        appearance['_V_'] = True
        #appearance['_POS_'] = figures[7].find("a").string.strip() if figures[7].find("a") is not None else None
        appearance['_GS_'] = int(figures[headers['_GS_']].string) if figures[headers['_GS_']].string is not None else 0
        appearance['_AS_'] = int(figures[headers['_AS_']].string) if figures[headers['_AS_']].string is not None else 0
        appearance['_GSS_'] = int(figures[headers['_GSS_']].string) if figures[headers['_GSS_']].string is not None else 0
        # Yellow and red card columns usually contain the minute of the game that the player got the card. The last
        # character in the string is a ' character signaling 'minutes'. We remove this character and try to cast the
        # rest of the string as an integer. Example:
        # <td class="zentriert">90'</td>
        # It can happend that, the casting fails. This could be caused by some malformed or unexpected value in the
        # string. In this case we flag the value as '-1', to inform that something was found but we were unable to
        # parse it. Example: A 'checked' sign instead of the minute.
        try:
            appearance['_YC_'] = int(figures[headers['_YC_']].string[:-1:]) if figures[headers['_YC_']].string is not None else None
        except ValueError:
            appearance['_YC_'] = -1
        try:
            appearance['_RC_'] = int(figures[headers['_RC_']].string[:-1:]) if figures[headers['_RC_']].string is not None else None
        except ValueError:
            appearance['_RC_'] = -1
        # Some players are also rated by trasfermarkt for their performance in the game.
        # If we where going to save this rating as well, we can do so by completing the following line
        # appearance['_R_'] = ... alexander-schwolow
        # given that the row element in this case looks like this
        # <paste-a-row-form-alexander-schwolow-from-freiburg>
        # Note that when we will try to upload the player to mysql server, this column has to exist in
        # the destination table
        # Minutes are parsed analogously to yellow/red cards
        appearance['_MIN_'] = int(figures[headers['_MIN_']].string[:-1:]) if figures[headers['_MIN_']].string is not None else "0"
        return appearance

    def init_tables_on_demand(self):
        if self.stats is None or len(self.stats) == 0:
            self.create_soup()
            self.init_tables()
            self.soup = None
        else:
            self.logger.debug("{} has been initialized, skipping on-demand initialization".format(self.__repr__()))

    def persist_on_demand(self):
        self.create_soup()
        self.persist()
        self.soup = None


    def persist(self):
        if not self.is_souped:
            self.logger.debug("{} is not souped, skip".format(self.__repr__()))
            return
        club_dir = "raw/clubs/CL_2017_%05d_%s" % (self.club_id, self.club_name)
        if not os.path.exists(club_dir):
            os.makedirs(club_dir)
        with open("%s/PL_%05d_%s.html" % (club_dir, self.id, self.name), 'w') as f:
            f.write(str(self.soup))

    """
    Toggle mode form LOCAL to REMOTE or viceversa. It propagates the change all over the season clubs and players
    """
    def toggle_source(self):
        self.logger.debug("{} source is {}, toggling...".format(self.__class__.__name__, self.source))
        # Toggle source attribute
        self.source = Mode.REMOTE if self.source == Mode.LOCAL else Mode.LOCAL
        # Update current uri
        self.update_current_uri()
        self.logger.debug("{} source is {}".format(self.__class__.__name__, self.source))

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uri(self):
        self.current_uri = self.local_uri if self.source == Mode.LOCAL else self.remote_uri

    """
    Triggers updating from remote
    """
    def update_soup_if(self, matcher):
        condition, argument = matcher[0]
        if condition(self, argument):
            self.logger.info("{} matches condition {} for updating, refreshing".format(self.__repr__(), matcher[0]))
            if self.source == Mode.LOCAL:
                self.toggle_source()
                self.create_soup(force=True)
                self.init_tables(force=True)
                self.toggle_source()
            else:
                self.create_soup(force=True)
                self.init_tables(force=True)
        else:
            self.logger.debug("{} does not match condition for updating".format(self.__repr__()))

    def update_soup_if_on_demand(self, matcher):
        self.update_soup_if(matcher)
        self.persist()
        self.soup = None

    """
    Conditions
    """
    def has_table(self, table):
        return True if table in self.tables.keys() else False

    """
    Loads the player into a mysql table
    """
    def to_mysql(self, conn):
        if self.stats is not None:
            self.logger.debug("{} to mysql".format(self.__repr__()))
            try:
                self.stats.to_sql('appearances_buffer', conn[0][0], if_exists='append')
            except sqlalchemy.exc.IntegrityError, err:
                self.logger.error("{} threw an integrity error: {}".format(self.__repr__(), str(err)))

        else:
            self.logger.debug("{} has no stats, skip load to mysql".format(self.__repr__()))
