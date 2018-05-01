# Import custom functions from 'R' folder
# Every new function needs to be defined in the
# functions.r file inside this folder
source("R/functions.R")

#####################################################
# MAIN
# Analyse appearances
#####################################################

# Imports
library(RMySQL)
library(tidyverse)

# Connect to database
# Get 'raw' data
conn<-dbConnect(MySQL(), dbname = 'tfmkt', user = 'tfmkt', password = 'tfmkt', host = 'localhost')
season_data = dplyr::as_tibble(dbGetQuery(conn, "SELECT * FROM tfmkt.appearances"))
dbDisconnect(conn)

data =
  season_data %>%
  # Filter to valid rows (rows with real appearances)
  filter(`_V_` == TRUE) %>%
  # Add H/A information
  mutate(`_H_` = ifelse(`_CID_` == `_HTID_`, TRUE, FALSE)) %>%
  # Filter out minor leages. Only rows from:
  #  GB1 : Premier League
  #  ES1 : La Liga
  #  IT1 : Calccio
  #  L1 : Bundesliga
  #  FR1 : French league
  #  PO1 : Portuguese League
  #  UCL : Champions Leage
  #  EL : Europa League
  #filter(`_C_` %in% c("GB1", "ES1", "IT1", "L1", "FR1", "PO1", "UCL", "EL")) %>%
  filter(`_C_` %in% c("GB1", "ES1", "IT1", "L1", "FR1", "CL"))

# Clean out invalid rows and generate updated GC (Goals Condeeded)
# and S (Score) columns. Sub-set the input data to a given conditions
consolidated = consolidateTopN(data, top = 200, past = 10)

movedWAvg = 
  consolidated %>% 
  computeMovingPredictions(2, pFUN = weighted.mean, na.rm = TRUE, w = c(0.5,0.5))
# Calculate average error in scores
#(abs((movedWAvg %>% unnest())$scores.real.ary - (movedWAvg %>% unnest())$scores.pred.ary)) %>% mean(na.rm = TRUE)
movedAvg = 
  consolidated %>% 
  computeMovingPredictions(7, pFUN = mean, na.rm = TRUE)

withStd = 
  movedAvg %>%
  mutate(err.std.ary = 0)
