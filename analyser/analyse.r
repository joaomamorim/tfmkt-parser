#Clear workspace
rm(list=ls())

#Function definitions
killDbConnections <- function () {
  
  all_cons <- dbListConnections(MySQL())
  
  print(all_cons)
  
  for(con in all_cons)
    +  dbDisconnect(con)
  
  print(paste(length(all_cons), " connections killed."))
  
}

dbGetReferenceDB <- function() {
  return(dbConnect(MySQL(),
                   dbname = 'tfmkt',
                   user = 'david',
                   password = 'david',
                   host = 'localhost')
  )
}

dbGetPredictionsDB <- function() {
  return(dbConnect(MySQL(),
                   dbname = 'predictions',
                   user = 'david',
                   password = 'david',
                   host = 'localhost')
  )db
}

dbUpdateAppearance <- function(pApp, conn, isTransient) {
  pName<-(splitPID(pApp[1]))[1]; pTeam<-(splitPID(pApp[1]))[2]; pDorsal<-(splitPID(pApp[1]))[3] 
  query<-paste(
    #c('_GS_', '_PC_', '_AP_', '_FS_', '_OFF_','_OF_','_AS_','_CP_','_FC_','_ON_' )
    "REPLACE INTO APPEARANCES SET ",
    "_GS_ = ", pApp[3], ", ",
    "_PC_ = ", ifelse(is.na(pApp[4]), "NULL", pApp[4]), ", ",
    "_AP_ = ", ifelse(is.na(pApp[5]), "NULL", pApp[5]), ", ",
    "_FS_ = ", pApp[6], ", ",
    "_OFF_ = ", pApp[7], ", ",
    "_OF_ = ", pApp[8], ", ",
    "_AS_ = ", ifelse(is.na(pApp[9]), "NULL", pApp[9]), ", ",
    "_CP_ = ", ifelse(is.na(pApp[10]), "NULL", pApp[10]), ", ",
    "_FC_ = ", ifelse(is.na(pApp[11]), "NULL", pApp[11]), ", ",
    "_ON_ = ", pApp[12], ", ",
    "_S2_ = ", ifelse(is.na(pApp[13]), "NULL", pApp[13]), ", ",
    "_NAME_ = \"", pName, "\", ",
    "_TEAM_ = ", pTeam, ", ",
    "_D_ = ", pDorsal, ", ",
    "_P_ = ", ifelse(isTransient, "0","1"), ", ",
    "_GID_ = ",
    "(",
    " SELECT _ID_ FROM GAMES ",
    " WHERE _DATE_ = \"", pApp[2], "\" ",
    " AND ",
    "  (",
    "   _HTID_ = ", pTeam, " OR ",
    "   _ATID_ = ", pTeam,
    "  )",
    ")",
    sep = ""
  )
  #print(query)
  dbGetQuery(conn, query)
}

dbUpdateAllAppearances <- function(conn, pIDs, pDates, transient, A) {
  
  for (pIndex in 1:length(pIDs)) {
    pID<-pIDs[pIndex]
    pApps<-A[pIndex, which(apply(!is.na(A[pIndex,,]), 1, any)),]
    pAppsD<-pDates[which(apply(!is.na(A[pIndex,,]), 1, any))]

    stopifnot((dim(pApps))[1] == length(pAppsD))
    
    pAppU<-data.frame(pid = array(pID, (dim(pApps))[1]), 
                      pd = pAppsD,
                      pstat = pApps)
    # print(paste("Index is ", pIndex))
    # print(pID)
    # print(pAppU)
    if((dim(pAppU))[1] > 0) {
      apply(pAppU, 1, dbUpdateAppearance, conn, ifelse(pIndex<transient, TRUE, FALSE))
    }
    else{
      print(paste("Found no appearances for player ", pID))
    }
  }
  dbDisconnect(conn)
}

dbGetPIDs <- function(conn, start, end, transient, nsamples = 10, conditions = "(1 = 1)") {
  
  query<-paste (
    "SELECT DISTINCT(_PID_) as _PID_, _PNAME_ FROM",
    "(",
    " SELECT  _PID_, _PNAME_, count(*) AS _NAPP_ FROM appearances ",
    " WHERE (_DATE_ BETWEEN \"", start, "\" AND \"", end, "\") ",
    " AND ", conditions,
    " GROUP BY _PID_ ",
    ") grp ",
    "WHERE _NAPP_ > ", transient + nsamples,
    sep = ""
  )
  #print(query)
  return(dbGetQuery(conn,query))
}

dbGetPDates <- function(conn, start, end, transient, nsamples = 10, conditions = "(1 = 1)") {
  pIDs<-dbGetPIDs(conn, start, end, transient, nsamples, conditions)
  allDates<-dbGetQuery(conn, "SELECT _PID_, _DATE_ FROM appearances")
  return(unique((merge(pIDs,allDates, by = "_PID_"))[c("_DATE_")]))
}



splitPID <- function(pID) {
  return(unlist(splittedID<-strsplit(pID, "|", fixed = TRUE)))
}

dbGetPAppearances <- function(conn, pID, startDate, endDate) {
  #Split pID into pName, pTeam and pDorsal
  pName<-(splitPID(pID))[1]; pTeam<-(splitPID(pID))[2]; pDorsal<-(splitPID(pID))[3] 
  
  #Query the database for the records belonging in this one player
  #Hint: print(query) to debug the query itself
  query<-paste("SELECT _DATE_, _TEAM_, _NAME_, _GS_, _PC_, _AW_, _AP_, _FS_, _OFF_, _OF_, _AS_, _FC_, _ON_, _CP_, _S_ ", 
               "FROM APPEARANCES a JOIN GAMES g ON a._GID_ = g._ID_ ",
               "WHERE _NAME_ = \"", pName, "\" ",
               "AND (_DATE_ BETWEEN \"", startDate, "\" AND \"", endDate, "\") ",
               "AND _TEAM_ = ", pTeam, " ",
               "AND _D_ = ", pDorsal, " ",
               "ORDER BY _DATE_ ASC",
               sep = "")
  #print(query)
  pApp_DF<-dbGetQuery(conn,query)
  return(pApp_DF)
}

dbGetAppearancesBox <- function(conn, startDate, endDate, transient, nsamples,
                                stats = c('_GS_', '_PC_', '_AP_', '_FS_', '_OFF_','_OF_','_AS_','_CP_','_FC_','_ON_','_S_' ),
                                conditions = "(1 = 1)"){
  pIDs<-dbGetPIDs(conn, startDate, endDate, transient, nsamples, conditions)[[1]]
  pDates<-dbGetPDates(conn, startDate, endDate, transient, nsamples)
  NStat<-length(stats)
  M<-array(NA,c(length(pIDs), length(pDates), NStat))
  for(pID in pIDs){
    #Get all appearances for this player
    pApp_DF<-dbGetPAppearances(conn, pID, startDate, endDate)
    #print(query)
    
    #Get the dates vector for this particular player. We must update de rows according
    #to the relative position of this dates. We use 'which' to find the indices where
    #such dates and pID appear in pIDs and pDates reference vectors.
    pApp_Dates_DF<-pApp_DF[c('_DATE_')]
    
    for(date in pApp_Dates_DF[,1]) {
      #Convert the data frame into a numeric matrix for computations
      pApp_Stats_V<-data.matrix(pApp_DF[,stats])
      
      #We shouldnt be finding histories shorter than length(C), since we required
      #that the players we bring from the database have a longer history than 'memory' = lenght(C)
      #If anyways we find one, stop execution
      stopifnot((dim(pApp_Stats_V))[1] >= length(transient+nsamples))
      
      #Store history and predictions in the M matrices, having into accound the dates each
      #record is refering to keep relative positions inside the matrices
      M[which(pIDs == pID), which(pDates == date),]<-
        pApp_Stats_V[which(pApp_Dates_DF == date),]
    }
    
  }
  dbDisconnect(conn)
  return(M)
}

applyMovingAverage <- function(X, C) {
  positions<-c(which(apply(!is.na(X),1,any)), nrow(X)+1)
  X_tilde<-array(NA, dim(X) + c(1, 0))
  X_without_NAs<-X[(positions[-length(positions)]),]
  X_tilde_woNAs<-filter(X_without_NAs, C, method = 'convolution', sides = 1)
  X_tilde[positions[-1],]<-X_tilde_woNAs
  return(X_tilde)
}

computeMovingAverage <- function(M, transient) {
  C<-array(1/transient, c(transient))
  M_tilde<-t(apply(M,1,applyMovingAverage, C))
  dim(M_tilde)<-dim(M)+c(0,1,0)
  return(M_tilde)
}


computeError <- function(lM) {
  M<-lM[[1]]; M_tilde<-lM[[2]]
  #Now we can start checking how good our predictions were by checking the difference
  #between M and M_tilde
  M_tilde_aligned = M_tilde[,-(dim(M_tilde))[2],]
  return(E<-abs(M-M_tilde_aligned))
}

applyByChunks <- function(x, fun, chunk) {
  NChunks<-ceiling(dim(x)[1]/chunk)
  mod<-(dim(x)[1])%%chunk
  y<-array(NA,NChunks*chunk)
  
  for (i in c(1:NChunks)){
    if(i<NChunks) {
      y[((i-1)*chunk)+1:i*chunk]<-apply(x[(((i-1)*chunk)+1):(i*chunk),],1,fun)
    }
    else{
      lastChunk<-apply(x[(((i-1)*chunk)+1):mod,],1,fun)
      length(lastChunk)<-chunk
      y[(((i-1)*chunk)+1):(i*chunk)]<-lastChunk
    }
  }
  
  length(y)<-dim(x)[1]
  return(y)
}

computeOptimalCombinantion<-function(threshold, C, M){
  C_indices<-t(combn(which(M > threshold), C))
  C_scores<-t(combn(M[which(M > threshold)],C))
  C_scores_total<-rowSums(C_scores,1)
  C_score_max<-max(C_scores_total)
  index_optimal<-(which(C_scores_total == C_score_max))[1]
  indices_optimal<-C_indices[index_optimal,]
  return(list(indices_optimal, C_score_max))
}

compute10OptimalCombinantion<-function(threshold, C, M, delta){
  C_indices<-t(combn(which(M > threshold), C))
  C_scores<-t(combn(M[which(M > threshold)],C))
  C_scores_total<-rowSums(C_scores,1)
  C_score_max<-max(C_scores_total)
  index_optimal<-which(C_scores_total > C_score_max-delta)
  indices_optimal<-C_indices[index_optimal,]
  #result<-c(indices_optimal, C_scores[indices_optimal])
  return(list(indices_optimal,  C_scores[index_optimal,]))
}

printTeam<-function(indices, pIDs) {
  print(paste(pIDs[indices],collapse=" "))
}

indexToPID<-function(indices, pIDs) {
  return(pIDs[indices])
}

printOptimalPlayers<-function(opt, pIDs) {
  apply(opt[[1]],1,printTeam,pIDs)
}

#Returns the last not null value for a given statistic (Stat) up to date index 'index'
lastValue<-function(M,Stat) {
  isNotNA<-!is.na(M[,,Stat])
  return(apply(isNotNA,1,function(x) max(which(x))))
}

#####################################################
# MAIN
# Analyse appearances
#####################################################

#Load MySQL connector
library(RMySQL)

startDate<-"2000-05-01"
endDate<-"2018-01-01"
transient<-c(7)
nsamples<-20

#Connect to database
#conn<-dbConnect(MySQL(), dbname = 'datamine', user = 'david', password = 'david', host = 'localhost')

# lM<-lapply(transient, 
#                  computeMovingAverage, 
#                  conn = conn, 
#                  startDate = startDate, 
#                  endDate = endDate, 
#                  nsamples = nsamples)

# lM<-computeMovingAverage(conn, startDate, endDate, transient, nsamples)
# 
# lE<-lapply(lM, computeError)
# lE_means_by_player<-lapply(lE, function(E) apply(E, 1, colMeans, na.rm = TRUE))
# E_means_by_transient_length<-sapply(
#   lapply(lE_means_by_player, rowMeans, na.rm = TRUE),
#   unlist
# )
# 
# E_scaled<-scale(t(E_means_by_transient_length), center = TRUE, scale = TRUE)
# 
# 
# M_tilde<-lM[[2]]
# M_tilde_aligned = M_tilde[,-(dim(M_tilde))[2],]
# 
# 
#   
# 
#   
# 
# conn2<-dbConnect(MySQL(), dbname = 'predictions', user = 'david', password = 'david', host = 'localhost')


#We are done with the database for now, we can disconnect
# dbUpdateAllAppearances(conn2,
#                        dbGetPIDs(conn, startDate, endDate, transient, nsamples)[[1]],
#                        dbGetPDates(conn, startDate, endDate, transient, nsamples),
#                        startDate,
#                        endDate,
#                        transient,
#                        M_tilde_aligned)

#dbDisconnect(conn2)


#Check the usage of this of function 'apply' like it is suggested in this post -> 
#https://stackoverflow.com/questions/13519717/cumulative-sum-in-a-matrix
#Also consider its usage in the load and filter stage


#E_scaled = scale(E_plot, center = TRUE, scale = TRUE)
#matplot(rowMeans(E_scaled), type = 'l')
#matplot(E_scaled, type = 'l')

M_for<-dbGetAppearancesBox(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 4)")
M_mid<-dbGetAppearancesBox(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 3)")
M_def<-dbGetAppearancesBox(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 2)")

M_for_tilde<-computeMovingAverage(M_for,7)
M_mid_tilde<-computeMovingAverage(M_mid,7)
M_def_tilde<-computeMovingAverage(M_def,7)

I_for<-dbGetPIDs(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 4)")
I_mid<-dbGetPIDs(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 3)")
I_def<-dbGetPIDs(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, conditions = "(_POS_ = 2)")

# dbUpdateAllAppearances(dbGetPredictionsDB(),
#                        I_for[[1]],
#                        dbGetPDates(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1),
#                        7, 
#                        M_for_tilde[,-length(M_for_tilde[1,,1]),])
# 
# dbUpdateAllAppearances(dbGetPredictionsDB(),
#                        I_mid[[1]],
#                        dbGetPDates(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1),
#                        7, 
#                        M_mid_tilde[,-length(M_mid_tilde[1,,1]),])
# 
# dbUpdateAllAppearances(dbGetPredictionsDB(),
#                        I_def[[1]],
#                        dbGetPDates(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1),
#                        7, 
#                        M_def_tilde[,-length(M_def_tilde[1,,1]),])

O_for<-compute10OptimalCombinantion(3,3,M_for_tilde[,dim(M_for_tilde)[2],11],1.5)
O_mid<-compute10OptimalCombinantion(3,5,M_mid_tilde[,dim(M_mid_tilde)[2],11],1)
O_def<-compute10OptimalCombinantion(3.3,5,M_def_tilde[,dim(M_def_tilde)[2],11],0.5)


P_for<-apply(O_for[[1]],1,indexToPID, I_for[[1]])
P_mid<-apply(O_mid[[1]],1,indexToPID, I_mid[[1]])
P_def<-apply(O_def[[1]],1,indexToPID, I_def[[1]])

W_for<-paste(P_for, O_for[[2]], sep = "|"); dim(W_for)<-c(dim(P_for))
W_mid<-paste(P_mid, O_mid[[2]], sep = "|"); dim(W_mid)<-c(dim(P_mid))
W_def<-paste(P_def, O_def[[2]], sep = "|"); dim(W_def)<-c(dim(P_def))

write.table(t(W_for), file = "for2.csv", sep = " ", row.names = FALSE, col.names = FALSE)
write.table(t(W_mid), file = "mid2.csv", sep = " ", row.names = FALSE, col.names = FALSE)
write.table(t(W_def), file = "def2.csv", sep = " ", row.names = FALSE, col.names = FALSE)

# 
# optimalAttack_tilde<-computeOptimalCombinantion(3,5,M_forw_tilde[,dim(M_forw_tilde)[2],11])
# optimalAttack_tilde2<-computeOptimalCombinantion(3,5,M_forw_tilde[cbind(c(1:nrow(M_forw_tilde)),
#                                                                          lastValue(M_forw_tilde,11),
#                                                                          11
#                                                                        )
#                                                                  ]
#                                                  )
# 
# optimalAttack3<-computeOptimalCombinantion(3,5,M_forw[cbind(c(1:nrow(M_forw)),
#                                                              lastValue(M_forw,11),
#                                                              11
#                                                             )
#                                                       ]
#                                           )
# Sthr<-4
# Stat<-11
# 
# M<-dbGetAppearancesBox(dbGetReferenceDB(), startDate, endDate, transient, nsamples, conditions)
# lM2<-computeMovingAverage(dbGetReferenceDB(), "2014-05-01", "2018-01-01", 7, 1, "(_POS_ = 3)")
# printOptimalTeam(3, 11, lM2, 5, pIDs = dbGetPIDs(
#                                                   dbGetReferenceDB(),
#                                                   "2014-05-01",
#                                                   "2018-01-01",
#                                                   7,
#                                                   1,
#                                                   "(_POS_ = 3)"
#   )[[1]]
# )

#dbDisconnect(conn)

#print(colMeans(E_means, na.rm = TRUE))
#write.csv(t(colMeans(E_means, na.rm = TRUE)), file="", sep = '|', row.names = FALSE, col.names = FALSE)
