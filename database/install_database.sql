create database if not exists tfmkt;
# Main entity. Holds the information of all the appearances parsed witht the web-scrapping tool
# There are some views and tables which are complementary to this
drop table if exists tfmkt.appearances;
create table tfmkt.appearances (
	_PID_ int not null comment 'A number identifying the player in the tfmkt system. Its supposed to be unique',
    _PNAME_ varchar(50) not null comment 'The name of the player in a dns compatible format (no special characters or spaces)',
    _RPOS_ varchar(50) not null comment 'Position of the player in extended format as parsed from the main player webpage',
    _POS_ int comment 'Position of the player in reduced format (either Goalkeeper-1, Defense-2, Midfielder-3, Forward-4). Inferred mapping RPOS through POS_DEFS table',
    _D_ int comment 'Player number in the team. Messi is number 10',
    _CID_ int not null comment 'A number identifying the club in the tfmkt system. Its supposed to be unique',
    _CNAME_ varchar(50) not null comment 'The name of the club in the tfmkt system. Again here they use a dns compliant string',
    _V_ boolean not null comment 'Flags wether the row holds player statistics or its mereley keeps the games figures. Rows should only be active (with _V_ = TRUE) when the player actually participated in the game',
    _C_ varchar(5) not null comment 'A short string giving information about the competition where the appearance actually took playe. It maps to COMP_DEFS table, where further information is available',
    _DATE_ date not null comment 'Contains the date of the appearance. Only the information about the year, month and day is relevant (discart the time if present)',
    _HT_ varchar(50) not null comment 'Contains the name of the club which played home this game',
    _HTID_ int not null comment 'Contains a number idetifying the club which played home this game. It is supposed to be unique',
    _AT_ varchar(50) not null comment 'Contains the name of the club which played away this game',
    _ATID_ int not null comment 'Contains a number idetifying the club which played away this game. It is supposed to be unique',
    _GID_ int not null comment 'Contains a number idetifying the club which played away this game. It is supposed to be unique',
    _GSH_ int not null comment 'Number of goals scored by the team which played home',
    _GSA_ int not null comment 'Number of goals scored by the team which played away',
    _ON_ int comment 'Number of shots on target shot by the player',
    _OFF_ int comment 'Number of shots off target shot by the player',
    _GS_ int comment 'Number of goals scored by the player',
    _GC_ int comment 'Number of goals conceeded by the player',
    _AS_ int comment 'Number of assistances given by the player',
    _GSP_ int comment 'Number of goals scored by penalty',
    _GSS_ int comment 'Number of own-goals',
    _PSA_ int comment 'Number of penlaties saved by the player, if he is a goalkeeper',
    _GMP_ int comment 'Number of pelaties missed by the player',
    _SAV_ int comment 'Number of total saves done by the goalkeeper',
    _PEN_ int comment 'Number of penalties suffered by the player',
    _OF_ int comment 'Number of off-sides commited',
    _FC_ int comment 'Fouls commited',
    _CP_ int comment '?',
    _FS_ int comment 'Fouls suffered',
    _AP_ int comment '?',
    _PC_ int comment '?',
	_AW_ int comment '?',
    _YC_ int comment 'Minute of the game the first yellow card was received',
    _Y2_ int comment 'Minute of the game the second yellow card was received',
    _RC_ int comment 'Minute of the game a straight red card was received',
    _MIN_ int comment 'Minutes played',
    CONSTRAINT APP_ID PRIMARY KEY(_DATE_, _PID_)
);

# Create a view with only some relevant fields from the appearences table