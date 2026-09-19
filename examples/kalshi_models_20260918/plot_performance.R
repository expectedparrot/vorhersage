# Exact original midpoints; accepted forecasts only. No network access.
suppressPackageStartupMessages(library(ggplot2))
suppressPackageStartupMessages(library(jsonlite))
arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
root <- dirname(normalizePath(sub("^--file=", "", arg)))
out <- file.path(root, "figures")
dir.create(out, showWarnings = FALSE)
comparison <- fromJSON(file.path(root, "run", "comparison.json"), simplifyVector = FALSE)
questions <- c(
  weather = "Will LAX's high be 74–75°F\non September 18, 2026?",
  employment = "Will US unemployment exceed\n4.4% in September 2026?",
  fed = "Will the Fed hold rates\non October 28, 2026?",
  neutron = "Will Neutron launch\nbefore January 1, 2027?",
  netflix = "Will ‘Why Did I Get Married Again?’\nrank first on the September 22\nUS Netflix film chart?",
  baseball = "Will Milwaukee beat Baltimore\non September 20, 2026?"
)
models <- c(astra = "GPT-6 Astra", fable = "Claude Fable 5.1", gemini = "Gemini 3.1 Pro (new)")
panels <- do.call(rbind, lapply(comparison$pairs, function(p) {
  do.call(rbind, lapply(names(models), function(k) {
    f <- p$forecasts[[k]]
    data.frame(question = questions[[p$id]], model = models[[k]],
               q = if (is.null(f$question_only)) NA_real_ else 100 * f$question_only,
               r = if (is.null(f$outside_research)) NA_real_ else 100 * f$outside_research,
               target = 100 * p$target)
  }))
}))
panels$question <- factor(panels$question, levels = unname(questions))
panels$model <- factor(panels$model, levels = unname(models))
panels$gain <- abs(panels$q - panels$target) - abs(panels$r - panels$target)
panels$relative <- 100 * panels$gain / abs(panels$q - panels$target)
panels$gain_label <- ifelse(is.na(panels$gain), "Question-only excluded",
  sprintf("Gap reduction: %+.1f pp (%+.1f%%)", panels$gain, panels$relative))
points <- rbind(data.frame(panels, x = 0, probability = panels$q, condition = "Question only"),
                data.frame(panels, x = 1, probability = panels$r, condition = "Outside research"))
points <- points[!is.na(points$probability), ]
points$vjust <- ifelse(points$probability >= points$target, -0.65, 1.3)
panels$market_label <- sprintf("Kalshi %g%%", panels$target)
figure <- ggplot() +
  geom_hline(data = panels, aes(yintercept = target), linetype = "dashed", colour = "#555555", linewidth = .45) +
  geom_segment(data = panels[!is.na(panels$gain), ], aes(x = 0, xend = 1, y = q, yend = r),
               colour = "#7E8589", linewidth = .6) +
  geom_point(data = points, aes(x, probability, colour = condition, shape = condition), size = 2.5) +
  geom_text(data = points, aes(x, probability, label = paste0(probability, "%"), colour = condition, vjust = vjust),
            size = 3.1, family = "serif", show.legend = FALSE) +
  geom_label(data = panels, aes(x = .5, y = target, label = market_label),
             family = "serif", size = 2.9, fill = "white", label.size = NA,
             label.padding = grid::unit(1.5, "pt")) +
  geom_text(data = panels, aes(x = .5, y = 103, label = gain_label), family = "serif", size = 2.7) +
  facet_grid(question ~ model, switch = "y", axes = "all_x") +
  scale_x_continuous(breaks = c(0, 1), labels = c("Question only", "Research"), limits = c(-.18, 1.18)) +
  scale_y_continuous(breaks = c(0, 25, 50, 75, 100), labels = function(x) paste0(x, "%"), limits = c(-5, 111)) +
  scale_colour_manual(values = c("Question only" = "#28658A", "Outside research" = "#17816E")) +
  scale_shape_manual(values = c("Question only" = 16, "Outside research" = 15)) +
  labs(x = NULL, y = "Forecast probability", colour = NULL, shape = NULL,
       title = "The same evidence, different forecasting models",
       subtitle = "Question-only → outside research; dashed line: original Kalshi midpoint",
       caption = "One draw per model × question × condition. Unaccepted forecasts are omitted, not imputed.\nGap reduction is the decrease in absolute distance to the midpoint; negative values indicate deterioration.\nInputs frozen September 18, 2026, 11:19 UTC; model calls executed later. No new research or prices supplied.") +
  theme_minimal(base_size = 11, base_family = "serif") +
  theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
        panel.grid.major.y = element_line(colour = "#EEEEEE"),
        strip.text.y.left = element_text(angle = 0, hjust = 1, size = 9.2),
        strip.text.x = element_text(face = "bold", size = 12),
        strip.placement = "outside", panel.spacing = grid::unit(.6, "lines"),
        legend.position = "bottom", plot.caption = element_text(hjust = 0, size = 9),
        plot.title = element_text(size = 18, face = "bold"), axis.text.x = element_text(size = 9))
ggsave(file.path(out, "performance.pdf"), figure, width = 12.5, height = 13.5, device = cairo_pdf, bg = "white")
ggsave(file.path(out, "performance.png"), figure, width = 12.5, height = 13.5, dpi = 170, bg = "white")
