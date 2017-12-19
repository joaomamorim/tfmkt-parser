function [ playerID ] = getPlayerID( playerName)
%Returns the player ID
global appearances_2017;
global M;

pidArray = M((find(strcmp(playerName,table2array(appearances_2017(:,{'x_NAME_'}))))),24);
if isequal(pidArray, pidArray)
    playerID = pidArray(1);
else
    playerID = 0;
end

end

