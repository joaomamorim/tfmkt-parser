# Python external modules
import logging
import urllib
import re
import time
import os
from bs4 import BeautifulSoup

# Module specific imports
from settings import *
from tfmktparser.Club import Club

class Season:

    """
    Constructor for the Season class looks for the master html file, either on the filesystem or on the transfer
    market server, and loads it into a BeautifulSoup object for a convenient parsing thereafter. The most important
    attribute in the class is the 'clubs' attribute. This is a list of Club objects representing the clubs found
    for this season. The 'clubs' list gets filled up when a call to the class method 'init_clubs' is made.
    The 'persist' method saves the season to filesystem using a known structure.
    """
    def __init__(self, source = LOCAL):
        # Get a logger reference for all objects of Season class to use
        self.logger = logging.getLogger(__name__)
        self.logger.info("Started season!")

        # Season initialization
        self.year = 2017
        self.clubs = []
        self.clubs_desc = []
        self.source = source

        # Load master html from either a local file of from the remote server
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + "raw/sub-master_2017.html".replace('/', '\\'))
        self.remote_uri = "https://www.transfermarkt.co.uk/vereins-statistik/wertvollstemannschaften/marktwertetop"
        master_uri = self.local_uri if self.source == LOCAL else self.remote_uri

        # Create a the BeautifulSoup object containing the html for the master
        html = safe_url_getter(master_uri)
        if html is not None:
            self.soup = BeautifulSoup(html, "html5lib")
            self.logger.debug("Master soup is ready")
        else:
            self.logger.error("Unable to obtain html from master")

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
            self.clubs.append(Club(int(uri_re[1]), uri_re[0], remote_url, self.source))
        elapsed_time = time.time() - start_time
        self.logger.info("Finished initializing clubs (%.2f seconds)" % (elapsed_time))
        #self.logger.info("Finished initializing clubs ({} seconds)".format(elapsed_time))

    """
    Triggers the souping of all clubs in the season, and propagates it down to players also.
    It is equivalent to as full download of the season when source is REMOTE
    """
    def soup_season(self):
        if self.clubs is None or self.size == 0:
            self.init_clubs()
        for club in self.clubs:
            club.soup_club()

    """
    Force all players in a season to load their respective htmls from either local or remote and parse it into
    a BeautifulSoup object. If 'init_players' ends correctly, the season object is ready to call on the 'parse_tables'
    method
    """
    def init_players(self):
        self.logger.info("Initializing players")
        start_time = time.time()
        # Clubs need to be initialized before we call on player for initialization
        if self.size is not None and self.size == self.size_souped:
            # Call for initialization of all reason players
            for club in self.clubs:
                club.init_players()
            elapsed_time = time.time() - start_time
            self.logger.info("Finished initializing players ({} seconds)".format(elapsed_time))
        else:
            self.logger.error("State of 'clubs' does not allow for players initialization")

    """
    Persists the season to disk. It recursively saves the in-memory representation of the season to a directory tree with all the
    necessary html files needed to recover the state. All soup attributes from the Season, Clubs and Players need to be populated
    before we call this method
    """
    def persist(self):
        self.logger.debug("Persisting season {}".format(self.__repr__()))
        if not os.path.exists("raw"):
            os.makedirs("raw")
        with open("raw/sub-master_2017.html", 'w') as f:
            f.write(str(self.soup))
        for club in self.clubs:
            if club.soup is not None:
                self.logger.info("Persisting {}".format(club.__repr__()))
                club.persist()

    """
    Toggle mode form LOCAL to REMOTE or viceversa. It propagates the change all over the season clubs and players
    """
    def toggle_source(self):
        self.logger.info("{} source is {}, toggling...".format(self.__class__.__name__, self.source))
        # Toggle source attribute
        self.source = REMOTE if self.source == LOCAL else LOCAL
        # Update current uri
        self.update_current_uri()
        self.logger.info("{} source is {}".format(self.__class__.__name__, self.source))
        for club in self.clubs:
            club.toggle_source()

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uri(self):
        self.current_uri = self.local_uri if self.source == LOCAL else self.remote_uri

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
    Total number of club objects currently in the season which have loaded their html soup
    """
    @property
    def size_souped(self):
        return len(filter(lambda x: x.soup is not None, self.clubs))



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
