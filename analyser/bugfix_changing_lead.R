# Definitions
memory = 4

# Calculate moving averages on numeric columns
predictions = 
  real_200 %>% 
  group_by(`_PNAME_`) %>%   # Group the tibble by player name. The player numeric id could also be used
  # but the name is better to understan the data
  filter(n() > 10) %>%      # Filter to those players where the number of rows (equivalent to appearances)
  arrange(desc(`_DATE_`)) %>%     # Order the rows inside the group by date. Default is ascending order
  # Select numeric rows. Moving averages can only be calculated over numeric rows
  select(`_PNAME_`, `_DATE_`, `_GS_`, `_GSS_`, `_AS_`, `_MIN_`, `_GC_` ,`_YC_`, `_RC_`, `_S_`) %>%
  # Mutate columns in 'vars' by using the functions in 'funs'
  # In this case we use the windowing function 'rollapply' to constaint the 'mean'
  # function to a few occurances in the past
  mutate_at(.vars = numeric_vars,
            # The 'rollapply' syntax requires that we pass the vector we want to apply the
            # function over in the 'data' parameter. Since we are inside a 'mutate_at' verb
            # we have to use the '.', placeholder character, to represent the changing column
            .funs = funs(rollapply(data = .,
                                   # The width parameter represents the memory of the moving average
                                   width = memory,
                                   # This is the function itself. Here we can insert an arbitrary function
                                   FUN = mean,
                                   # Remove NAs for the computaton? Yes, please
                                   na.rm = TRUE, 
                                   align = "right",
                                   fill = NA
            )
            )
  )