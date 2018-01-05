# Definitions
numeric_vars = vars(`_GS_`, `_GSS_`, `_AS_`, `_MIN_`, `_GC_` ,`_YC_`, `_Y2_`, `_RC_`)

# Auxiliar function to calculate an appearance score based on the
# stats. It takes one vector as the only parameter, where each
# position in the vector contains a different type of statistic
computeScore = function(x) {
  # All values in the input vector are required. If any is NA
  # then the computed score is also NA
  #print(x)
  if(any(is.na(x[1:6]))) return(NA)
  # Variable unpack
  pos = x[1]
  min = x[2]
  gc = x[3]
  gs = x[4]
  gss = x[5]
  as = x[6]
  yc = x[7]
  y2 = x[8]
  rc = x[9]
  # Calculate position based coeficients
  cgc_below = if(pos == 1 || pos == 2) 4 else if(pos == 3) 1 else 0
  cgc_above = if(pos == 1 || pos == 2) 1 else 0
  # Calculate score
  return(
    # MINUTES
    # More than 60 minutes gives 2 points. More than 0 gives 1 point
    (if(min>60) 2
    else 1) +
    # GOALS SCORED
    # The reward can be calculated detracting the position
    # number to 8:
    # DEF: 8 - 2(DEF) = 6 points
    # MID: 8 - 3(MID) = 5 points
    # FOR: 8 - 4(FOR) = 4 points
    gs * (8 - pos) +
    # ASSISTS
    # Every assist rewards 3 points for every player
    as * 3 +
    # GOALS CONCEEDED
    if ( gc <= 1) {
      # If goals conceeded are under 1, use cgc_below coeficient
      (1-gc)*cgc_below
    } else {
      # If goals are above 1, we use cgc_above coeficient
      (1-gc)*cgc_above
    } +
    # CARDS
    # We only use information about yellow cards (one and two)
    # It is difficult to combine with the information about red
    # cards in continuous mode
    (yc + y2)*(-1)
    )
}

# Compute predictions by the pFUN method and return a joined tibble real vs predicted values
# As the first parameter accepts a tibble with the raw data, a parameter 'memory' for the width of the
# moving average and 
computeMovingPredictions = function(data, memory, pFUN, ...){
  # Calculate moving averages on numeric columns
  predictions = 
    data %>%
    mutate(
      stats.pred.tbl = 
        map(
          stats.real.tbl,
          function(x){
            rolled_aplied = x %>%
            # Mutate columns in 'vars' by using the functions in 'funs'
            # In this case we use the windowing function 'rollapply' to constaint the 'mean'
            # function to a few occurances in the past
            mutate_at(
              .vars = numeric_vars,
              # The 'rollapply' syntax requires that we pass the vector we want to apply the
              # function over in the 'data' parameter. Since we are inside a 'mutate_at' verb
              # we have to use the '.', placeholder character, to represent the changing column
              .funs = funs(
                 rollapply(data = .,
                 # The width parameter represents the memory of the moving average
                 width = memory,
                 # This is the function itself. Here we can insert an arbitrary function
                 FUN = pFUN,
                 # Parameters to pFUN are passed on
                 ...,
                 align = "right",
                 fill = NA
               )
              )
            ) %>%
            # Lag numeric variables by 1 sample. This make sure windowing affects only to rows in the past
            mutate_at(.vars = numeric_vars, .funs = funs(dplyr::lag(x = ., n = 1)))
            return(rolled_aplied)
          }
        )
      ) %>%
    updatePredScores()
  # Return predictions together with a new column holding the 'mean' predicted score
  return(predictions %>% mutate(scores.pred.mean = map_dbl(scores.pred.ary, mean, na.rm = TRUE)))
}

# Clean out invalid rows and generate updated GC (Goals Condeeded)
# and S (Score) columns. Sub-set the input data to a given conditions
consolidateTopN = function(data, top = 200, past = 10){
  cleanedSeason =
    data %>%
    # Filter to valid rows (rows with real appearances)
    filter(`_V_` == TRUE) %>% 
    # Filter out minor leages. Only rows from:
    #  GB1 : Premier League
    #  ES1 : La Liga
    #  IT1 : Calccio
    #  L1 : Bundesliga
    #  FR1 : French league
    #  PO1 : Portuguese League
    #  UCL : Champions Leage
    #  EL : Europa League
    filter(`_C_` %in% c("GB1", "ES1", "IT1", "L1", "FR1", "PO1", "UCL", "EL")) %>%
    # Update GC column with the goals conceeded by the player
    mutate(`_GC_` = ifelse(`_CID_` == `_HTID_`, `_GSA_`, `_GSH_`)) %>%
    # YC and RC columns are more useful when they represent 'number of occurances'
    # rather than 'minute of the match the player saw the card'. We transform them
    # in this way
    mutate(`_YC_` = ifelse(is.na(`_YC_`), 0, 1), 
           `_Y2_` = ifelse(is.na(`_Y2_`), 0, 1),
           `_RC_` = ifelse(is.na(`_RC_`), 0, 1))
  # Comment
  withScores =
    cleanedSeason %>%
    select(`_PNAME_`, `_DATE_`, `_POS_`,`_MIN_`, `_GC_`, `_GS_`, `_GSS_`, `_AS_`, `_YC_`, `_Y2_`, `_RC_`) %>%
    # Group by player name and consolidate for each player in a nested table
    group_by(`_PNAME_`) %>%
    arrange(`_DATE_`) %>%
    nest(.key = 'stats.real.tbl') %>%
    # Prepare nested tables as pure numeric matrix splitting out the dates column
    mutate(
      stats.dates.ary = map(stats.real.tbl,~.$`_DATE_`),
      stats.real.tbl = map(stats.real.tbl, ~ select(., -(`_DATE_`)))
    ) %>%
    # Calculate scores
    updateRealScores() %>%
    # Generate average score and N (number of samples)
    mutate(
      scores.real.mean = map_dbl(scores.real.ary, mean, na.rm = TRUE),
      Nsamples = map_int(stats.real.tbl, nrow)
    )
    
  # Take a sample of the top N scorers
  # Firstly, find out the top N scorers
  top_n_players = 
    withScores %>%
    select(`_PNAME_`, scores.real.mean, Nsamples) %>% 
    #unnest() %>%
    filter(Nsamples >= past) %>%
    top_n(n = top, wt = scores.real.mean)
  # Secondly, filter the original sample to contain only rows from this players
  all_n_players = 
    withScores %>% 
    filter(`_PNAME_` %in% top_n_players$`_PNAME_`)
  return(all_n_players %>% select(-Nsamples))
}

# Update real scores
# The score is calculated by passing to a custom function 'computeScore' the
# relevant columns
updateRealScores = function(data) {
  return(
    data %>% 
      mutate(scores.real.ary = map(stats.real.tbl, ~ apply(., 1, computeScore)))
  )
}
updatePredScores = function(data) {
  return(
    data %>% 
      mutate(scores.pred.ary = map(stats.pred.tbl, ~ apply(., 1, computeScore)))
  )
}