# Import custom functions from 'R' folder
# Every new function needs to be defined in the
# functions.r file inside this folder
source("R/functions.R")

#####################################################
# Compute moving averages and add team ratings
#####################################################

# Imports
library(RMySQL)
library(tidyverse)
library(plyr)
library(fbRanks)
library(rpart)

# Connect to database
# Get 'raw' data
conn<-dbConnect(MySQL(), dbname = 'tfmkt', user = 'tfmkt', password = 'tfmkt', host = 'localhost')
season_data = dplyr::as_tibble(dbGetQuery(conn, "SELECT * FROM tfmkt.appearances"))
dbDisconnect(conn)

# Only for LaLiga appearanances
data =
  season_data %>%
  # Filter out minor leages. Only rows from:
  #  GB1 : Premier League
  #  ES1 : La Liga
  #  IT1 : Calccio
  #  L1 : Bundesliga
  #  FR1 : French league
  #  PO1 : Portuguese League
  #  UCL : Champions Leage
  #  EL : Europa League
  filter(`_C_` %in% c("ES1"))

movingAverages = 
  # Top = 1000 actually bring in all players, since La Liga has around 350 different players
  # Past = 1 means every player with at least 1 game played
  consolidateTopN(data, top = 1000, past = 1) #%>%
  #computeMovingPredictions(7, pFUN = mean, na.rm = TRUE)

# Module the raw data into a dataframe that can be the input to the rank.teams function
games =
  # From a season data dataframe (full 'appearances' table from the database)
  unnest(movingAverages) %>% 
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

# Get a vector with all games' dates
dates = games %>% distinct(date)

coefficients_as_dataframe = function(fitted) {
  # Extract coeficients object from the fitted model
  coef.list = coef(fitted)$coef.list
  return(data.frame(attack = coef.list$cluster.1$attack, defense = coef.list$cluster.1$defend))
}

fit_games = function(games, max_date) {
  fitted = rank.teams(games, max.date = max_date, silent = TRUE)
  return(coefficients_as_dataframe(fitted) %>% mutate(max_date = max_date))
}

# Get the matrix of team rating versus date limit
fitted = 
  apply(dates, 1, function(x){fit_games(games, x) %>% rownames_to_column(var = "name")}) %>%
  ldply() %>%
  # For a small number of samples, the ratings are inconsistent, filter those
  filter( max_date > '2017-10-01')

# Calculate attack and defense gain by subtracting attack and defense for home and away team
joined = 
  unnest(movingAverages) %>%
  mutate(`_ANAME_` = ifelse(`_H_`, `_AT_`, `_HT_`)) %>%
  left_join(fitted, by = c("_CNAME_" = "name", "_DATE_" = "max_date")) %>%
  left_join(fitted, by = c("_ANAME_" = "name", "_DATE_" = "max_date"), suffix = c(".my_team", ".their_team")) %>%
  mutate(attack.gain = attack.my_team - defense.their_team, defense.gain = defense.my_team + attack.their_team)

# Grow the tree
fit = rpart(scores.real.ary ~ `_POS_` + attack.gain + `_H_`, method = "anova", data = joined %>% filter(`_POS_` == 4))

# Plot
plot(fit, uniform=TRUE, 
     main="Regression Tree for score")
text(fit, use.n=TRUE, all=TRUE, cex=.8)

