# Python external modules
import urllib
import time
import os
from bs4 import BeautifulSoup
from sqlalchemy import create_engine

# Module specific imports
from settings import *
from tfmktparser.Club import Club
from tfmktparser.Player import Player

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
    def __init__(self, pages, source = LOCAL):
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
        master_base_uris = self.local_uris if self.source == LOCAL else self.remote_uris

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
        self.source = REMOTE if self.source == LOCAL else LOCAL
        # Update current uri
        self.update_current_uris()
        self.propagate_to_clubs(Club.toggle_source)
        self.propagate_to_players(Player.toggle_source)
        self.logger.info("{} source is {}".format(self.__class__.__name__, self.source))

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uris(self):
        self.current_uris = self.local_uris if self.source == LOCAL else self.remote_uris

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
