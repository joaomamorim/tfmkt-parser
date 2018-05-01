import logging.config
import yaml

from tfmktparser import *

logging.config.dictConfig(yaml.load(open('conf/logging.yaml')))
# Initialize all pages
seas = Season([1, 2, 3, 4], Mode.LOCAL)
# Load club names from htmls
seas.init_clubs()
# For every club, call on initialize players
seas.propagate_to_clubs(Club.init_players_on_demand)
# For each player call on initialize tables
seas.propagate_to_players(Player.init_tables_on_demand)
# Update player html if a condition is matched (the player has a table for champions league games)
# A call on update_player_soup_on_demand will additionally persist the newly downloaded players to local
seas.update_players_soup_on_demand(Player.has_table, "CL")
# Update data in mysql too
seas.update_mysql()
