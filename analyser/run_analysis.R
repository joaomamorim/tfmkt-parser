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
library(dplyr)
library(zoo) # Requirement for rollapply windowing function

# Definitions
numeric_vars = vars(`_GS_`, `_GSS_`, `_AS_`, `_MIN_`, `_GC_` ,`_YC_`, `_RC_`)
relcolumns_prev = vars(`_PNAME_`, `_DATE_`, `_POS_`,`_MIN_`, `_GC_`, `_GS_`, `_GSS_`, `_AS_`, `_YC_`, `_Y2_`, `_RC2_`)
relcolumns_real = vars(`_PNAME_`, `_DATE_`, `_POS_`,`_MIN_.x`, `_GC_.x`, `_GS_.x`, `_GSS_.x`, `_AS_.x`, `_YC_.x`, `_Y2_.x`, `_RC2_.x`)
relcolumns_pred = vars(`_PNAME_`, `_DATE_`, `_POS_`,`_MIN_.y`, `_GC_.y`, `_GS_.y`, `_GSS_.y`, `_AS_.y`, `_YC_.y`, `_Y2_.y`, `_RC2_.y`)

# Connect to database
# Get 'raw' data
conn<-dbConnect(MySQL(), dbname = 'tfmkt', user = 'root', password = 'root', host = '192.168.56.102')
season_data = dplyr::as_tibble(dbGetQuery(conn, "SELECT * FROM tfmkt.appearances"))
dbDisconnect(conn)

# Clean out invalid rows and generate updated GC (Goals Condeeded)
# and S (Score) columns. Sub-set the input data to a given conditions
consolidated = consolidateTopN(season_data, top = 200, past = 10)

movedWAvg = 
  consolidated %>% 
  computeMovingPredictions(10, top = 200, pFUN = weighted.mean, na.rm = TRUE, w = c(10,10,10,8,8,8,5,5,5,2)/71)
eWAvg = 
  movedAvg %>%
  mutate(
    err.wma.tbl = map2(stats.real.tbl, stats.pred.tbl, ~ (as.matrix(.x) - as.matrix(.y)) %>% abs() %>% dplyr::as_tibble())
  )
# Calculate average error in scores
#(abs((movedWAvg %>% unnest())$scores.real.ary - (movedWAvg %>% unnest())$scores.pred.ary)) %>% mean(na.rm = TRUE)
movedAvg = 
  consolidated %>% 
  computeMovingPredictions(10, top = 200, pFUN = mean, na.rm = TRUE)
eAvg =
  movedAvg %>%
  mutate(
    err.ma.tbl = map2(stats.real.tbl, stats.pred.tbl, ~ (as.matrix(.x) - as.matrix(.y)) %>% abs() %>% dplyr::as_tibble())
  )
#eAvg %>% unnest() %>% select(-(name)) %>% as.matrix() %>% colMeans(na.rm = TRUE)
movedEts =
  consolidated %>%
  computeMovingPredictions(10, top = 200, pFUN = function(x){
      fitted = ets(x)
      prediction = forecast(fitted, h=1) %>% as.data.frame()
      return(prediction$`Point Forecast`)
   }
  )
