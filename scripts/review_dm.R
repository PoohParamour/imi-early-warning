args <- commandArgs(trailingOnly=FALSE)
script <- sub('^--file=', '', args[grep('^--file=', args)][1])
setwd(normalizePath(file.path(dirname(script), '..')))
dir.create('reports/review', recursive=TRUE, showWarnings=FALSE)
source(url('https://raw.githubusercontent.com/robjhyndman/forecast/master/R/DM2.R'))
p <- read.csv('logs/metrics/04_predictions.csv', colClasses=c(commodity_code='character',feature_set='character'))
p$series <- paste(p$model,p$feature_set,sep='/')
p$error <- p$y_pred-p$y_true
p <- p[p$split=='test',]
checks <- rbind(read.csv('logs/metrics/05_dm_main_comparisons.csv',colClasses=c(commodity_code='character'))[,c('commodity_code','horizon','model_1','model_2','dm_hln','p_value')],
                read.csv('logs/metrics/05_sensitivity_cutoff24.csv',colClasses=c(commodity_code='character'))[,c('commodity_code','horizon','model_1','model_2','dm_hln','p_value')],
                read.csv('logs/metrics/05_rq4_horizon_skill.csv',colClasses=c(commodity_code='character'))[,c('commodity_code','horizon','model_1','model_2','dm_hln','p_value')])
ref <- function(a,b,h) {
  d <- abs(a)-abs(b)
  ac <- as.numeric(acf(d,lag.max=h-1,type='covariance',plot=FALSE)$acf)
  variance <- (ac[1]+2*sum(ac[-1]))/length(d)
  method <- if(variance>0) 'acf' else 'bartlett'
  dm.test(a,b,h=h,power=1,varestimator=method)
}
for(i in seq_len(nrow(checks))) {
  c <- checks[i,]
  a <- p[p$commodity_code==c$commodity_code & p$horizon==c$horizon & p$series==c$model_1,]
  b <- p[p$commodity_code==c$commodity_code & p$horizon==c$horizon & p$series==c$model_2,]
  stopifnot(identical(a$month_ce,b$month_ce))
  r <- ref(a$error,b$error,c$horizon)
  checks$r_dm[i] <- as.numeric(r$statistic); checks$r_p[i] <- r$p.value
}
cat('comparisons=',nrow(checks),'max_dm_error=',max(abs(checks$dm_hln-checks$r_dm)),
    'max_p_error=',max(abs(checks$p_value-checks$r_p)),'\n')
write.csv(checks,'reports/review/dm_reference.csv',row.names=FALSE)
main <- read.csv('logs/metrics/05_dm_main_comparisons.csv',colClasses=c(commodity_code='character'))
main <- main[main$commodity_code %in% c('318','402'),]
cat('Holm family=',nrow(main),'max_error=',max(abs(main$p_holm-p.adjust(main$p_value,'holm'))),'\n')
# ACF variance < 0: explicit Bartlett fallback prescribed by Scope, not R's default h=1 recursion.
a <- rep(c(2,0),20); b <- rep(1,40)
r <- ref(a,b,2)
cat('synthetic Bartlett stat=',r$statistic,'p=',r$p.value,'method=',r$varestimator,'\n')
p2 <- read.csv('logs/metrics/05b_predictions.csv',colClasses=c(commodity_code='character'))
results <- read.csv('logs/metrics/05b_results.csv',colClasses=c(commodity_code='character'))
delta <- c()
for(i in seq_len(nrow(results))) {
  c <- results[i,]
  panel <- p2[p2$split=='test' & p2$commodity_code==c$commodity_code & p2$horizon==c$horizon,]
  panel <- panel[order(panel$month_ce),]
  new <- panel[panel$series=='ridge/3+commodity','error']
  for(old in c('ridge/3','no_change/none')) {
    r <- ref(new,panel[panel$series==old,'error'],c$horizon)
    expected <- if(old=='ridge/3') c$p_vs_ridge3 else c$p_vs_no_change
    delta <- c(delta, abs(r$p.value-expected))
  }
}
cat('iteration2 comparisons=',length(delta),'max_p_error=',max(delta),'\n')
