# Imports
library(RMySQL)
library(dplyr)
library(fbRanks)

# Connect to database
# Get 'raw' data
conn<-dbConnect(MySQL(), dbname = 'tfmkt', user = 'root', password = 'root', host = '192.168.56.102')
season_data = dplyr::as_tibble(dbGetQuery(conn, "SELECT * FROM tfmkt.appearances"))
dbDisconnect(conn)

# Module the raw data into a dataframe that can be the input to the rank.teams function
games =
  # From a season data dataframe (full 'appearances' table from the database)
  season_data %>% 
  # Filter to spanish league games only
  filter(`_C_` == 'ES1') %>% 
  group_by(`_DATE_`, `_GID_`) %>%
  # I beleive this call to distinct is not really necessary
  distinct() %>%
  # Create the columns date, home.team, away.team and scores as they are
  # expected in the fbRanks.rank_teams function
  mutate( 
    date = as.Date(`_DATE_`, format="%Y-%m-%d"), 
    home.team = `_HT_`, home.score = `_GSH_`, 
    away.team = `_AT_`, away.score = `_GSA_`) %>% 
  # Take only the first row, since we are interested in the score of the
  # game this is enough
  filter(row_number() == 1) %>%
  # Remove the grouping
  ungroup() %>% ungroup() %>%
  # order rows by date
  arrange(desc(date)) %>%
  # Drop unnecesary rows
  select(date, home.team, home.score, away.team, away.score)

# Fits the 'fbRanks' model into a fbRanks object
rank.teams(games) -> ranked_teams

# Calculates predictions for the upcoming matches
predictions = fbRanks::predict.fbRanks(ranked_teams)