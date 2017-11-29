import logging
import os
import re
import urllib
import string
from bs4 import BeautifulSoup

from settings import *
from tfmktparser.Player import Player

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
        self.soup = None

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
            if player.soup is not None:
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

