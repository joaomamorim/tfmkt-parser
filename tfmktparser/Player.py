import os
import urllib
import sqlalchemy
from dateutil import parser as date_parser
import pandas as pd
from itertools import izip
from bs4 import BeautifulSoup

from settings import *

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
    def __init__(self, id, name, remote_uri, club_id, club_name, source=LOCAL):
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
        main_panel_figures = self.soup.\
            find('div', class_ = 'dataMain').\
            find_next_sibling('div', class_ = 'dataContent').\
            select('div div p span.dataItem')
        # The information about the position we will find it in the sibling node to the 'Postion' tag
        self.raw_position = filter(lambda x: "Position" in x.string.strip(),main_panel_figures)[0].\
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
