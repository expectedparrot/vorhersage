suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(jsonlite))
arg <- grep('^--file=', commandArgs(FALSE), value=TRUE)
root <- dirname(normalizePath(sub('^--file=', '', arg)))
a <- fromJSON(file.path(root, 'arithmetic.json'))
w <- read.csv(file.path(root, 'measles-weekly.csv'))
w$week_start <- as.Date(w$week_start)
n <- read.csv(file.path(root, 'nasa-predictions.csv'))
n$method <- factor(n$method, levels=rev(n$method))
base <- theme_minimal(base_size=11, base_family='serif') +
  theme(panel.grid.minor=element_blank(), plot.title=element_text(face='bold'),
        plot.caption=element_text(hjust=0, size=9))
p1 <- ggplot(w, aes(week_start, cases)) +
  annotate('rect', xmin=as.Date('2026-09-06'), xmax=as.Date('2026-09-20'),
           ymin=-Inf, ymax=Inf, fill='#EEEEEE') +
  geom_col(fill='#326A8C', width=5) +
  geom_hline(yintercept=a$measles$required_cases_per_week, linetype='dashed', colour='#A44626') +
  geom_hline(yintercept=a$measles$calendar_ytd_cases_per_week, linetype='dotted', colour='#555555') +
  annotate('text', x=as.Date('2026-04-18'), y=184, label='Needed through year-end: 169/week',
           family='serif', colour='#A44626', size=3.4) +
  annotate('text', x=as.Date('2026-04-18'), y=106, label='Year-to-date average: 93/week',
           family='serif', colour='#555555', size=3.4) +
  scale_x_date(date_breaks='1 month', date_labels='%b', expand=expansion(mult=c(.01,.02))) +
  labs(title='A. Measles: recent incidence was much higher than the annual average',
       subtitle='Four weeks ending September 5: 178 cases/week; previous four weeks: 85/week',
       x=NULL, y='Cases by week of rash onset',
       caption='CDC data retrieved after reveal from the September 18 page. Recent weeks (shaded) are especially incomplete.\nThe required rate uses approximately 15 remaining weeks; maintaining a rate is a scenario, not a probability forecast.') + base
p2 <- ggplot(n, aes(mean_1850_1900, method)) +
  geom_vline(xintercept=1.475, linetype='dashed', colour='#A44626') +
  geom_segment(aes(x=mean_1850_1900-published_95_interval_halfwidth,
                   xend=mean_1850_1900+published_95_interval_halfwidth, yend=method),
               linewidth=.7, colour='#326A8C') +
  geom_point(size=2.6, colour='#326A8C') +
  labs(title='B. Temperature: forward-looking models differed from extrapolating the year so far',
       subtitle='All seven NASA September predictions for 2026; points and published 95% uncertainty bars',
       x='Annual anomaly relative to 1850–1900 (°C)', y=NULL,
       caption='Dashed line: approximate equivalent of 1.285°C on the contract baseline (using NASA FAQ offset of +0.19°C).\nBaseline conversion and interval interpretation require reconciliation before estimating a contract probability.\nSources: CDC weekly cases; NASA GISTEMP GMSTA September 2026 CSV. Post-reveal diagnosis; original scores unchanged.') + base
draw <- function() {
  grid::grid.newpage()
  grid::pushViewport(grid::viewport(layout=grid::grid.layout(2,1)))
  print(p1, vp=grid::viewport(layout.pos.row=1,layout.pos.col=1))
  print(p2, vp=grid::viewport(layout.pos.row=2,layout.pos.col=1))
}
cairo_pdf(file.path(root,'diagnosis.pdf'),width=11,height=9)
draw()
dev.off()
png(file.path(root,'diagnosis.png'),width=1760,height=1440,res=160,type='cairo')
draw()
dev.off()
