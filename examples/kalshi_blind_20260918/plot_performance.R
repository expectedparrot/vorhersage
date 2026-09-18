# Rebuild the faceted slope graph from the frozen comparison; no network calls.
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(jsonlite))

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
stopifnot(length(script_arg) == 1L)
root <- dirname(normalizePath(sub("^--file=", "", script_arg)))
out <- file.path(root, "figures")
dir.create(out, showWarnings = FALSE)
comparison <- fromJSON(file.path(root, "run", "comparison.json"))
cases <- comparison$pairs
stopifnot(nrow(cases) == 6L, length(comparison$exclusions) == 0L)

# Check the underlying numerical results independently before plotting.
for (arm in names(comparison$metrics)) {
  gaps <- cases[[arm]] - cases$target
  actual <- c(mae_pp = 100 * mean(abs(gaps)),
              rmse_pp = 100 * sqrt(mean(gaps^2)),
              mean_outside_spread_pp = 100 * mean(pmax(
                cases$bid - cases[[arm]], cases[[arm]] - cases$ask, 0)))
  expected <- unlist(comparison$metrics[[arm]][names(actual)])
  stopifnot(all(abs(actual - expected) < 1e-10))
}

# Readable questions preserve the event definitions, including the Netflix
# settlement date rather than its ambiguous headline date.
questions <- c(
  weather = "Will LAX's high be 74\u201375\u00b0F\non September 18, 2026?",
  employment = "Will US unemployment (U-3)\nexceed 4.4% in September 2026?",
  fed = "Will the Fed hold rates at its\nOctober 28, 2026 meeting?",
  neutron = "Will Rocket Lab launch Neutron\nbefore January 1, 2027?",
  netflix = "Will \u201cWhy Did I Get Married Again?\u201d\nrank first on the September 22, 2026\nUS Netflix film chart?",
  baseball = "Will Milwaukee beat Baltimore\non September 20, 2026?"
)
stopifnot(identical(cases$id, names(questions)))
plot_data <- rbind(
  data.frame(id = cases$id, condition = "Question only",
             probability = 100 * cases$question_only, target = 100 * cases$target),
  data.frame(id = cases$id, condition = "Outside research",
             probability = 100 * cases$outside_research, target = 100 * cases$target)
)
plot_data$condition <- factor(plot_data$condition,
                              levels = c("Question only", "Outside research"))
plot_data$question <- factor(questions[plot_data$id], levels = unname(questions))
plot_data$label <- sprintf("%g%%", plot_data$probability)
plot_data$x <- as.integer(plot_data$condition) - 1
# Place annotations away from the benchmark, leaving the forecast-to-market
# distances visible. No data points or reference lines are displaced.
plot_data$label_vjust <- ifelse(plot_data$probability >= plot_data$target, -0.9, 1.5)
targets <- data.frame(
  question = factor(questions[cases$id], levels = unname(questions)),
  probability = 100 * cases$target,
  label = sprintf("Kalshi: %g%%", 100 * cases$target),
  label_vjust = ifelse(cases$target < pmin(cases$question_only, cases$outside_research),
                       1.3, -0.4)
)

# Improvement is a reduction in absolute market deviation, not the percentage
# change in the forecast itself. Relative improvement uses the initial gap.
initial_gap <- 100 * abs(cases$question_only - cases$target)
research_gap <- 100 * abs(cases$outside_research - cases$target)
improvement_pp <- initial_gap - research_gap
stopifnot(all(abs(improvement_pp - cases$absolute_gap_improvement_pp) < 1e-10))
improvement_pct <- ifelse(initial_gap > 0, 100 * improvement_pp / initial_gap, NA_real_)
slope_midpoint <- 50 * (cases$question_only + cases$outside_research)
improvements <- data.frame(
  question = targets$question,
  midpoint = slope_midpoint,
  label_y = slope_midpoint + ifelse(slope_midpoint >= targets$probability, 18, -18),
  label = ifelse(is.na(improvement_pct), sprintf("%.1f pp (relative n/a)", improvement_pp),
                 sprintf("%.1f pp (%.1f%%)", improvement_pp, improvement_pct))
)

figure <- ggplot() +
  geom_hline(data = targets, aes(yintercept = probability),
              linetype = "dashed", colour = "#333333", linewidth = 0.55) +
  geom_line(data = plot_data, aes(x = x, y = probability, group = question),
             colour = "#7E8589", linewidth = 0.7) +
  geom_point(data = plot_data, aes(x = x, y = probability,
                                  colour = condition, shape = condition), size = 2.6) +
  geom_text(data = plot_data, aes(x = x, y = probability, label = label,
                                  vjust = label_vjust, colour = condition),
            size = 3.5, family = "serif", show.legend = FALSE) +
  geom_label(data = targets, aes(x = 0.5, y = probability, label = label,
                                 vjust = label_vjust),
             size = 3.4, family = "serif", colour = "#222222", fill = "white",
             label.size = NA, label.padding = grid::unit(1.5, "pt")) +
  geom_segment(data = improvements,
               aes(x = 0.5, xend = 0.5, y = midpoint, yend = label_y),
               colour = "#999999", linewidth = 0.3) +
  geom_label(data = improvements, aes(x = 0.5, y = label_y, label = label),
             size = 3.4, family = "serif", colour = "#222222", fill = "white",
             label.size = 0.15, label.padding = grid::unit(3, "pt"),
             label.r = grid::unit(0, "pt")) +
  facet_wrap(~question, ncol = 2, scales = "fixed", axes = "all",
             axis.labels = "all") +
  scale_colour_manual(name = NULL, values = c("Question only" = "#426D8A",
                                              "Outside research" = "#317663")) +
  scale_shape_manual(name = NULL, values = c("Question only" = 16, "Outside research" = 15)) +
  scale_x_continuous(limits = c(-0.35, 1.35), breaks = c(0, 1),
                     labels = c("Question only", "Outside research"), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0, 100), breaks = seq(0, 100, 25),
                     expand = expansion(mult = c(0.15, 0.04))) +
  labs(x = NULL, y = "Probability of the YES event (%)") +
  theme_bw(base_size = 12, base_family = "serif") +
  theme(
    legend.position = "none",
    strip.background = element_rect(fill = "#F4F4F4", colour = "#BBBBBB",
                                    linewidth = 0.35),
    strip.text = element_text(size = 11.5, lineheight = 1.02,
                              margin = margin(7, 5, 7, 5)),
    panel.border = element_rect(colour = "#BBBBBB", linewidth = 0.35),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "#E8E8E8", linewidth = 0.3),
    panel.grid.minor = element_blank(),
    panel.spacing = grid::unit(13, "pt"),
    axis.ticks = element_blank(),
    axis.text = element_text(colour = "#333333", size = 10.5),
    axis.title.y = element_text(size = 11.5, margin = margin(r = 9)),
    plot.margin = margin(9, 12, 9, 9)
  )

ggsave(file.path(out, "performance.pdf"), figure, width = 8.4, height = 7.6,
       units = "in", device = cairo_pdf, bg = "white")
ggsave(file.path(out, "performance.png"), figure, width = 8.4, height = 7.6,
       units = "in", dpi = 300, bg = "white")
cat("Verified frozen metrics and rendered six question-labeled facets with ggplot2.\n")
