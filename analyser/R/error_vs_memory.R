# Create figure: Error (between current score and averaged score) VS Memory (Memory in the moving average computation)
# Create figure: Error (between current score and score of averaged stats) vs Memory

# Functions
source("R/functions.R")

# Imports
library(RMySQL)
library(dplyr)
library(zoo) # Requirement for rollapply windowing function

# Definitions
Nmem = 8
Ntop = 200

# Connect to database
# Get 'raw' data
conn<-dbConnect(MySQL(), dbname = 'tfmkt', user = 'root', password = 'root', host = '192.168.56.102')
season_data = dplyr::as_tibble(dbGetQuery(conn, "SELECT * FROM tfmkt.appearances"))
dbDisconnect(conn)

# Calculated _S_ and _GC_
completed = completeData(season_data)

# Calculate moving averages on numeric columns.
# Predictions by the method of the 'moving average of scores' (method1) can be extracted from the
# 'rolling means' matrix (output of the computeMovingMeans function). We run the computations over
# a span of 'Nmem' samples in the past in order to observe the memory characteristics of the
# system (does it benefit from using many values in the past or it does not matter)
predictions_by_moving_mean_of_scores = 
  # Callculate the rolling means matrices for 1 to Nmem past samples.
  # Recall predicted and real value are denoted with a '.y' and '.x' respectivelly.
  lapply(1:Nmem, computeMovingPredictions, data = completed, top = Ntop, pFUN = mean, na.rm = TRUE) %>%
  # Union all 1 to Nmem matrices into one single data frame (or tibble in this
  # case). A new "memory" column is created indicating the number of ".x" samples in
  # the past used in order to compute the ".y" (predicted) value
  bind_rows(.id = "memory") %>%
  # Add a new column with the absolute error of the prediction
  mutate( E = abs(`_S_.x` - `_S_.y`))

# On the other hand, predictions by the method of the 'score of moving averages' (method2) uses the
# prediction of each individual statistic in order to calculate a predicted score. The matrix 
# 'predictions_by_moving_mean_of_scores' already contains these predictions from the individual
# statistics, therefore we can use this matrix to produce the scores by the second method
predictions_by_score_of_moving_means =
    predictions_by_moving_mean_of_scores %>%
    # Use the individual moving averages to compute the predictions
    mutate( 
            S = (function(pos,min,gc,gs,gss,as,yc,y2,rc){
              apply(data.frame(pos,min,gc,gs,gss,as,yc,y2,rc), 1, computeScore)
            }
            )(`_POS_`,`_MIN_.y`, `_GC_.y`, `_GS_.y`, `_GSS_.y`, `_AS_.y`, `_YC_.y`, `_Y2_.y`, `_RC_.y`)
            ) %>%
  # Add new column with the error
  mutate( E = abs(`_S_.x` - S) )
# Bind rows from methods 1 and 2 together in the same tibble, identifying the method used by a new
# column "method". We are putting everithing in the same dataframe here since it is easier for plotting
predictions = predictions_by_moving_mean_of_scores %>% bind_rows(predictions_by_moving_mean_of_scores, .id = "method")
# Creates a plot showing the average error, breaking down by memory and position
plot = 
  ggplot() + 
  geom_bar(data = predictions, 
           aes(x = factor(memory), y = E, fill = factor(method)), 
           stat = "summary", 
           fun.y = "mean", 
           na.rm = TRUE, 
           position = "dodge") +
  facet_wrap( ~ `_POS_`, ncol = 2 )