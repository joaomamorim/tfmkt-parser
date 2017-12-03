import os
import urllib
from dateutil import parser as date_parser
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

    ##########################################################################################################
    # MAGIC                                                                                                  #
    ##########################################################################################################
    """
    Class constructor...
    """
    def __init__(self, id, name, remote_uri, club_id, club_name, source=LOCAL):
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
        self.stats = None
        self.source = source

        # Set local and remote uri attributes
        self.local_uri = "file:" + urllib.pathname2url(HOME_RAW + 'raw\\clubs\\CL_2017_%05d_%s\\PL_%05d_%s.html' % (club_id, club_name, self.id, self.name))
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
            self.logger.error("{} error creating soup. We can try again later with 'soup_season'".format(self.__repr__()))
            return
            # Create a the BeautifulSoup object containing the html for the master
        self.logger.debug("Player URI is {}, creating soup".format(self.current_uri))
        self.soup = BeautifulSoup(html, "html5lib")
        self.logger.debug("{} soup is ready".format(self.__repr__()))

    def set_position(self, position):
        try:
            self.position = self.POSITION_MAPPER[position]
            self.logger.debug("Setted {0} ({1}) position to {2}".format(self.name, self.id, position))
        except:
            self.position = self.UNK

    def init_tables(self, force=False):
        # Avoid double initialization of tables
        if len(self.tables) > 0 and not force:
            self.logger.warning("{} avoided unintended initialization of tables, use 'force' flag to force it".format(self.__repr__()))
            return
        else:
            self.tables = {}
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
            if id not in ("gesamt"):
                self.tables[id] = self.parse_table(id, table)
                self.tables[id].set_index('_DATE_', inplace=True)
                #self.tables[id]
            else:
                self.logger.warning("{} found invalid table with id {}".format(self.__repr__(), id))
            self.logger.debug("Finished parsing table {}".format(id))
        # Regenerate stats attribute (simply a merging of all tables)
        self.stats = pd.concat(self.tables.values()) if len(self.tables) > 0 else None

    def parse_table(self, id,  table):
        self.logger.debug("{} raw table dump {}".format(self.__repr__(), table.find("tbody")))
        all_rows = table.find("tbody").find_all("tr")
        #self.logger.debug("{} all rows in list form: {}".find(self.__repr__(), sall_rows)))
        #rows = [row for row in table.find("tbody").find_all("tr") if row.has_attr('class') and not row['class'][0] in ("bg_rot_20", "bg_gelb_20", "bg_blau_20")]
        rows = [row for row in table.find("tbody").find_all("tr")]
        self.logger.debug("Found {} rows in this table".format(len(rows)))
        parsed_rows = [self.parse_row(id, row) for row in rows]
        return pd.DataFrame.from_dict([row for row in parsed_rows if row is not None], orient='columns')

    def parse_row(self, id, row):
        self.logger.debug("%s parsing row \n{\n %s \n}" % (self.__repr__(), row))
        # If the row is of class 'bg_blau_20' then it's a dummy row and we wont be able to parse anything from it
        # Skip it
        if row.find('td').has_attr('class') and "bg_blau_20" in row.find('td')['class']:
            self.logger.debug("{} found blue row, skipping".format(self.__repr__()))
            return None
        # Assume at least the game information is present in the row
        figures = row.select("td")
        # if len(figures) < 13 :
        #     self.logger.warning("{} unexpected number of elements in a table row, requires checking".format(self.__repr__()))
        #     return

        # Init row
        appearance = {}
        # The appearance is 'invalid' unless this is changed down in the flow
        appearance['_V_'] = False
        # Assign the competition 'id'. This is passed as a parameter to the parse_row function by the parse_table
        # which actually extracts out the current competition id from the html
        appearance['_C_'] = id
        # Date in the 'detailed' view table is an a format such as 'Sep 30, 2017'. We extract the element and parse it
        # into datetime value. We use the date_parser third party library, which automatically detects the correct
        # format in the date string
        appearance['_DATE_'] = date_parser.parse(figures[1].string.strip())
        # Extract the name of the club. Normally it should be easy to find the team name in the 'href' attribute in the
        # vereinprofil class
        try:
            href_with_teamn_name = figures[2].find("a", class_="vereinprofil_tooltip")['href']
            appearance['_HT_'] = re.match(r"/([\w\-]+)/.*",href_with_teamn_name).group(1)
        # but it can happen that the href has strange characteres. In such case the regex match
        # fails and we run into a 'AttributeError'. We capture this exception, give a warning and assign 'None' to
        # the 'HT' element for this appearance.
        # Example: 'jan-bednarek' from 'fc-southampton' has an 'href' for the first game of the Europa Leage Qualifiers
        # in 2017 of '/lech-pozna%C5%84/spielplan/verein/238/saison_id/2017'.
        except AttributeError:
            appearance['_HT_'] = None
            self.logger.warning("{} was not able to extract 'HT' name from 'href' '{}', assign none".format(self.__repr__(), href_with_teamn_name))
        appearance['_HTID_'] = (figures[2].find("a", class_="vereinprofil_tooltip"))['id']
        appearance['_AT_'] = re.match("/([\w\-]+)/.*", figures[4].find("a", class_="vereinprofil_tooltip")['href']).group(1)
        appearance['_ATID_'] = (figures[4].find("a", class_="vereinprofil_tooltip"))['id']
        # The game is usually an attribute in row number 6 (inside de 'a' tag)
        # Try to extract it by querying this 'id' inside of 'a'
        try:
            appearance['_GID_'] = int(figures[6].find("a")['id'])
        # It can happen that the attribute 'id' is not present in some row, in such case fallback to extract
        # the game id from the 'href' of the game
        except KeyError:
            self.logger.warning("{} missing attribute game 'id' for the row, attepting extraction from 'href'".format(self.__repr__()))
            appearance['_GID_'] = int(re.search(r".*/([0-9]+)$", figures[6].find("a")['href']).group(1))
        parsed_result = re.search("([0-9]+):([0-9]+)", figures[6].find("span").text.strip())
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
        appearance['_GS_'] = int(figures[8].string) if figures[8].string is not None else 0
        appearance['_AS_'] = int(figures[9].string) if figures[9].string is not None else 0
        appearance['_GSS_'] = int(figures[10].string) if figures[10].string is not None else 0
        appearance['_YC_'] = int(figures[11].string[:-1:]) if figures[11].string is not None else None
        appearance['_RC_'] = int(figures[12].string[:-1:]) if figures[12].string is not None else None
        # try:
        #     appearance['_RC_'] = int(figures[12].string) if figures[12].string is not None else 0
        # except:
        #     self.logger.error("Unable to assign _RC_ for {}".format(self.name))
        return appearance

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
        self.source = REMOTE if self.source == LOCAL else LOCAL
        # Update current uri
        self.update_current_uri()
        self.logger.debug("{} source is {}".format(self.__class__.__name__, self.source))

    """
    Update the pointer to the current URI of the player, either to the transfermarket server or to a local file
    """
    def update_current_uri(self):
        self.current_uri = self.local_uri if self.source == LOCAL else self.remote_uri

    """
    Triggers updating from remote
    """
    def update_soup_if(self, matcher):
        #print matcher
        condition, argument = matcher[0]
        if condition(self, argument):
            self.logger.info("{} matches condition {} for updating, refreshing".format(self.__repr__(), matcher[0]))
            if self.source == LOCAL:
                self.toggle_source()
                self.create_soup(force=True)
                self.init_tables(force=True)
                self.toggle_source()
            else:
                self.create_soup(force=True)
                self.init_tables(force=True)
        else:
            self.logger.debug("{} does not match condition for updating".format(self.__repr__()))

    """
    Conditions
    """
    def has_table(self, table):
        return True if table in self.tables.keys() else False

    # def is_fr1(self):
    #     return True if "FR1" in self.tables.keys() else False

