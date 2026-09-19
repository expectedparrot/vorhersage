# Price-blind expanded experiment: registered accepted forecasts, never repaired.
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(jsonlite))
arg <- grep("^--file=", commandArgs(FALSE), value=TRUE)
root <- dirname(normalizePath(sub("^--file=", "", arg)))
dir.create(file.path(root, "figures"), showWarnings=FALSE)
comparison <- fromJSON(file.path(root, "run/comparison.json"), simplifyVector=FALSE)
questions <- c(
  "candidate-01"="Will Q3 2026 real GDP\ngrowth exceed 2% annualized?",
  "candidate-02"="Will Q4 2026 real GDP\ngrowth exceed 2% annualized?",
  "candidate-03"="Will September payroll\ngrowth exceed 30,000?",
  "candidate-04"="Will October payroll\ngrowth exceed 30,000?",
  "candidate-05"="Will October monthly CPI\ngrowth exceed 0.4%?",
  "candidate-06"="Will November monthly CPI\ngrowth exceed 0.2%?",
  "candidate-07"="Will October unemployment\nexceed 4.3%?",
  "candidate-08"="Will the Fed hold rates\nat its December meeting?",
  "candidate-12"="Will 2026 Atlantic major\nhurricanes exceed three?",
  "candidate-15"="Will Cincinnati beat Houston\non September 20?",
  "candidate-16"="Will Cleveland beat Tampa Bay\non September 20?",
  "candidate-17"="Will Denver beat Jacksonville\non September 20?",
  "candidate-18"="Will the Chargers beat Las Vegas\non September 20?",
  "candidate-19"="Will Miami beat San Francisco\non September 20?",
  "candidate-20"="Will Arizona beat Seattle\non September 20?"
)
models <- c(astra="GPT-6 Astra", fable="Claude Fable 5.1", gemini="Gemini 3.1 Pro")
panels <- do.call(rbind, lapply(comparison$pairs, function(p) do.call(rbind, lapply(names(models), function(k) {
  f <- p$forecasts[[k]]
  data.frame(id=p$id, question=questions[[p$id]], model=models[[k]],
             q=if (is.null(f$question_only)) NA_real_ else 100*f$question_only,
             r=if (is.null(f$outside_research)) NA_real_ else 100*f$outside_research, target=100*p$target)
}))))
panels$question <- factor(panels$question, levels=unname(questions))
panels$model <- factor(panels$model, levels=unname(models))
panels$gain <- abs(panels$q-panels$target)-abs(panels$r-panels$target)
panels$relative <- 100*panels$gain/abs(panels$q-panels$target)
panels$gain_label <- ifelse(is.na(panels$gain), "Incomplete accepted pair",
                          ifelse(abs(panels$q-panels$target)<1e-8, sprintf("Gap reduction: %+.1f pp (n/a)",panels$gain),
                          sprintf("Gap reduction: %+.1f pp (%+.1f%%)",panels$gain,panels$relative)))

make_figure <- function(data, part) {
  points <- rbind(data.frame(data,x=0,probability=data$q,condition="Question only"),
                  data.frame(data,x=1,probability=data$r,condition="Outside research"))
  points <- points[!is.na(points$probability),]
  points$vjust <- ifelse(points$probability>=points$target,-.75,1.4)
  ggplot() +
    geom_hline(data=data,aes(yintercept=target),linetype="dashed",colour="#555555",linewidth=.45) +
    geom_segment(data=data[!is.na(data$gain),],aes(x=0,xend=1,y=q,yend=r),colour="#7E8589",linewidth=.6) +
    geom_point(data=points,aes(x,probability,colour=condition,shape=condition),size=2.5) +
    geom_text(data=points,aes(x,probability,label=paste0(probability,"%"),colour=condition,vjust=vjust),family="serif",size=3.1,show.legend=FALSE) +
    geom_label(data=data,aes(x=.5,y=target,label=sprintf("Kalshi %g%%",target)),family="serif",size=2.8,fill="white",label.size=NA,label.padding=grid::unit(1.5,"pt")) +
    geom_text(data=data,aes(x=.5,y=105,label=gain_label),family="serif",size=2.65) +
    facet_grid(question~model,switch="y",axes="all_x") +
    scale_x_continuous(breaks=c(0,1),labels=c("Question only","Research"),limits=c(-.18,1.18)) +
    scale_y_continuous(breaks=c(0,25,50,75,100),labels=function(x) paste0(x,"%"),limits=c(-5,114)) +
    scale_colour_manual(values=c("Question only"="#28658A","Outside research"="#17816E")) +
    scale_shape_manual(values=c("Question only"=16,"Outside research"=15)) +
    labs(x=NULL,y="Forecast probability",colour=NULL,shape=NULL,
         title=paste0("New contracts, shared evidence: part ",part," of 3"),
         subtitle="Question-only → outside research; dashed line: sealed opening midpoint",
         caption="Registered acceptance rule; excluded responses are omitted, never set to zero. One draw per cell.\nGap reduction is the decrease in absolute distance from the midpoint; negative values indicate deterioration.\nNFL ties have fractional payouts. Related economic releases and games are not independent observations.") +
    theme_minimal(base_size=11,base_family="serif") +
    theme(panel.grid.minor=element_blank(),panel.grid.major.x=element_blank(),
          panel.grid.major.y=element_line(colour="#EEEEEE"),strip.text.y.left=element_text(angle=0,hjust=1,size=10),
          strip.text.x=element_text(face="bold",size=12),strip.placement="outside",
          panel.spacing=grid::unit(.6,"lines"),legend.position="bottom",
          plot.caption=element_text(hjust=0,size=9),plot.title=element_text(size=18,face="bold"),axis.text.x=element_text(size=9))
}
figures <- list()
for (i in 1:3) {
  ids <- names(questions)[((i-1)*5+1):(i*5)]
  fig <- make_figure(panels[panels$id %in% ids,],i)
  figures[[i]] <- fig
  ggsave(file.path(root,"figures",paste0("performance-",i,".pdf")),fig,width=12.5,height=11.3,device=cairo_pdf,bg="white")
  ggsave(file.path(root,"figures",paste0("performance-",i,".png")),fig,width=12.5,height=11.3,dpi=160,bg="white")
}
cairo_pdf(file.path(root,"figures/performance.pdf"),width=12.5,height=11.3)
for (fig in figures) print(fig)
dev.off()
