global appearances_2017;


G = findgroups(appearances_2017(:,{'x_NAME_'}));

relevantColumns = appearances_2017;
relevantColumns(:,{'x_NAME_', 'x_GID_', 'x_TEAM_', 'x_POS_'}) = [];
relevantColumns = table2array(relevantColumns);
M = [relevantColumns G];
global M;

A = arrayfun(@(x) M(M(:,24) == x, :), unique(M(:,24)), 'uniformoutput', false);

for A
    


