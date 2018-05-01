# Transfermakt Scrapper
Webscrapper for the player statistics in [transfermarkt](www.transfermarkt.com)

# Scrapping target
The library is targeted to collect the [individual player statistics](https://www.transfermarkt.es/lionel-messi/leistungsdaten/spieler/28003) in the website for each game. It is mainly based on the [bs4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) Python 2.7 package.

# Requiremtents
Altough it is possible to scrape the website without saving the data for a later use, normally it is more useful to save it into a persistet structred/semi-structured format. In order to do so, a running MySQL instance is required for the data to be output. The required schema can be installed by executing the `install_database.sql` script.

# Example
```python
# Import module
from tfmktparser import *
# Initialize season object
seas = Season([1], Mode.REMOTE)
# Most of functions come with a 'on-demand' flavor, which make a more 
# efficient memory use
seas.propagate_to_clubs(Club.init_players_on_demand)
# For each player call on initialize tables
seas.propagate_to_players(Player.init_tables_on_demand)
# Get Lewandowski's goals scored in the Champions League. We can use regular expressions to locate 'bayern-munich' in the 
# teams collection and 'lewandowski' in the players collection
seas[".*bayern-mu.*"]['.*lewan.*']["CL"]['_GS_']
```
Would produce an output like this
```console
>>> seas[".*bayern-mu.*"]['.*lewan.*']["CL"]['_GS_']
_DATE_
2017-09-12    1.0
2017-09-27    0.0
2017-10-18    0.0
2017-10-31    NaN
2017-11-22    1.0
2017-12-05    1.0
2018-02-20    2.0
2018-03-14    0.0
2018-04-03    0.0
2018-04-11    0.0
2018-04-25    0.0
Name: _GS_, dtype: float64
```

The `update_data.py` script shows another use case where we update the local cache of data for a subset of players.

# Analytical module
The project ships with an R module that can be used to perform some analysis with the data obtained with the scrapping module.
In the script `with_team_ratings.R` we fit a regression tree to the players data to predict performance based on historic data.

![alt text](https://raw.githubusercontent.com/dcaribou/tfmkt-parser/master/analyser/score_tree_strikers.png)
