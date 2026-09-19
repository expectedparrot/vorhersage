suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(jsonlite))
arg <- grep('^--file=',commandArgs(FALSE),value=TRUE)
root <- dirname(normalizePath(sub('^--file=','',arg)))
dir.create(file.path(root,'figures'),showWarnings=FALSE)
d <- fromJSON(file.path(root,'run/comparison.json'),simplifyVector=FALSE)
questions <- c(mortgage='Will the September 24 mortgage\nrate exceed 7.01%?',
 housing='Will September housing starts\nexceed 1.300 million SAAR?',
 measles='Will 2026 U.S. measles cases\nexceed 6,000?',
 global_heat='Will the 2026 NASA temperature\nindex exceed 1.28°C and 2025?',
 miami='Will Miami reach a maximum\nof 88–89°F on September 19?',
 austin='Will Austin reach a maximum\nof 98–99°F on September 19?',
 dune='Will Dune: Part Three be\ndelayed past December 18?')
models <- c(astra='GPT-6 Astra',fable='Claude Fable 5.1',gemini='Gemini 3.1 Pro')
rows <- list(); points <- list(); n <- 0
for(p in d$pairs) for(k in names(models)) {
 n <- n+1
 q <- 100*unlist(p$draws[[k]]$question_only); r <- 100*unlist(p$draws[[k]]$outside_research)
 rows[[n]] <- data.frame(id=p$id,question=questions[[p$id]],model=models[[k]],q=mean(q),r=mean(r),target=100*p$target,
                         qmin=min(q),qmax=max(q),rmin=min(r),rmax=max(r))
 points[[n]] <- rbind(data.frame(id=p$id,question=questions[[p$id]],model=models[[k]],x=seq(-.06,.06,length.out=length(q)),p=q,condition='Question only'),
                      data.frame(id=p$id,question=questions[[p$id]],model=models[[k]],x=1+seq(-.06,.06,length.out=length(r)),p=r,condition='Research'))
}
rows <- do.call(rbind,rows); points <- do.call(rbind,points)
for(v in c('rows','points')) {
 x <- get(v); x$question <- factor(x$question,levels=unname(questions));x$model <- factor(x$model,levels=unname(models));assign(v,x)
}
rows$gain <- abs(rows$q-rows$target)-abs(rows$r-rows$target)
rows$label <- ifelse(abs(rows$q-rows$target)<1e-8,sprintf('Mean gap reduction: %+.1f pp (n/a)',rows$gain),
                     sprintf('Mean gap reduction: %+.1f pp (%+.1f%%)',rows$gain,100*rows$gain/abs(rows$q-rows$target)))
make_plot <- function(ids,part) {
 a <- rows[rows$id %in% ids,]; b <- points[points$id %in% ids,]
 centers <- rbind(data.frame(a,x=0,p=a$q,low=a$qmin,high=a$qmax,condition='Question only'),
                   data.frame(a,x=1,p=a$r,low=a$rmin,high=a$rmax,condition='Research'))
 centers$label_y <- ifelse(centers$p>=centers$target,centers$high+6,centers$low-6)
 ggplot()+
 geom_hline(data=a,aes(yintercept=target),linetype='dashed',colour='#555555',linewidth=.45)+
 geom_segment(data=a,aes(x=0,xend=1,y=q,yend=r),colour='#6D777C',linewidth=.65)+
 geom_errorbar(data=centers,aes(x=x,ymin=low,ymax=high,colour=condition),width=.10,linewidth=.5)+
 geom_point(data=b,aes(x=x,y=p,colour=condition),size=1.3,alpha=.55,show.legend=FALSE)+
 geom_point(data=centers,aes(x=x,y=p,colour=condition,shape=condition),size=2.5)+
 geom_text(data=centers,aes(x=x,y=label_y,label=sprintf('%.1f%%',p),colour=condition),family='serif',size=3.2,show.legend=FALSE)+
 geom_label(data=a,aes(x=.5,y=target,label=sprintf('Kalshi %g%%',target)),family='serif',size=3,fill='white',label.size=NA,label.padding=grid::unit(1.5,'pt'))+
 geom_text(data=a,aes(x=.5,y=108,label=label),family='serif',size=2.8)+
 facet_grid(question~model,switch='y',axes='all_x')+
 scale_x_continuous(breaks=c(0,1),labels=c('Question only','Research'),limits=c(-.18,1.18))+
 scale_y_continuous(breaks=c(0,25,50,75,100),labels=function(x)paste0(x,'%'),limits=c(-11,118))+
 scale_colour_manual(values=c('Question only'='#28658A','Research'='#17816E'))+
 scale_shape_manual(values=c('Question only'=16,'Research'=15))+
 labs(x=NULL,y='Forecast probability',colour=NULL,shape=NULL,title=paste0('Research and repeated forecasts: part ',part,' of 2'),
      subtitle='Three fresh calls per condition; lines join means; small points and bars show draws and their range',
      caption='Dashed line: opening midpoint, sealed before research. Bars are observed ranges, not confidence intervals.\nAnnotations score the mean forecast; the primary table averages losses across calls within each question.\nQuestion-only and research calls are separate; replicate numbers do not imply matched random draws.')+
 theme_minimal(base_size=11,base_family='serif')+
 theme(panel.grid.minor=element_blank(),panel.grid.major.x=element_blank(),panel.grid.major.y=element_line(colour='#EEEEEE'),
       strip.text.y.left=element_text(angle=0,hjust=1,size=11),strip.text.x=element_text(face='bold',size=12),strip.placement='outside',
       panel.spacing=grid::unit(.7,'lines'),legend.position='bottom',plot.caption=element_text(hjust=0,size=9),
       plot.title=element_text(size=18,face='bold'),axis.text.x=element_text(size=10))
}
plots <- list(make_plot(names(questions)[1:4],1),make_plot(names(questions)[5:7],2))
for(i in 1:2) {
 ggsave(file.path(root,'figures',paste0('performance-',i,'.pdf')),plots[[i]],width=13,height=10,device=cairo_pdf,bg='white')
 ggsave(file.path(root,'figures',paste0('performance-',i,'.png')),plots[[i]],width=13,height=10,dpi=160,bg='white')
}
cairo_pdf(file.path(root,'figures/performance.pdf'),width=13,height=10)
for(p in plots)print(p)
dev.off()
