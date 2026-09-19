# Contract-definition audit

This note uses only the frozen official terms and primary source documentation. It does not use market prices.

## Measles

The binding terms are preserved in `definitions/measles-terms.pdf`. The underlying is the number of measles cases in the United States in the specified year according to CDC; revisions made after expiration are excluded. The payout criterion is an expiration value above the threshold, so “above 6000” means at least 6001 cases.

The last trading date is the sooner of 10:00 a.m. ET after occurrence of the payout event or the last day of the year; last trading time is 11:59 p.m. ET. The expiration date is the sooner of 10:00 a.m. ET after occurrence, 10:00 a.m. ET after CDC releases data for the entire year, or one year after the year. Expiration time is 10:00 a.m. ET. Therefore the scheduled January 1 close is not necessarily the ascertainment or settlement deadline.

CDC’s primary page is <https://www.cdc.gov/measles/data-research/index.html>. It says the data are confirmed cases reported to CDC as of noon Thursday; 2026–27 counts are preliminary and subject to change. Counts include international visitors. Cases are assigned by epidemiological week of rash onset, not report date (the last 2025 epidemiological week, Dec 28 2025–Jan 3 2026, is assigned to 2025). “New outbreaks” are cumulative outbreaks of at least three related cases, not active outbreaks. The weekly chart is by rash-onset date and recent weeks are incomplete/reporting-lagged.

The main forecasting traps are conflating market close with data ascertainment, using the annual average without recent trajectory, treating new outbreaks as active outbreaks, ignoring visitor inclusion and epidemiological-week assignment, and treating preliminary counts as final.

## Global temperature

NASA’s official LOTI table is <https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.txt>. It defines the global land–ocean temperature index in hundredths of a degree Celsius relative to the 1951–1980 base period, based on GHCN v4 and ERSST v5. The annual value is the J–D annual mean. NASA’s overview (<https://data.giss.nasa.gov/gistemp/>) says analyses are updated around the tenth of each month and incorporate late reports and corrections to earlier months.

The contract requires the **unsmoothed** 2026 LOTI reported by GISS to be strictly above both the 2025 value and 1.28°C. It closes at 11:59 p.m. ET on December 31, 2026, and expires at the earlier of 10:00 a.m. ET after release of 2026 data or 10:00 a.m. ET April 1, 2027. The headline “hottest year” is therefore shorthand for a two-part threshold, not merely a record comparison.

NASA’s FAQ (<https://data.giss.nasa.gov/gistemp/faq/>) gives uncertainty context (roughly ±0.05°C for annual means after 1960; larger monthly uncertainty) and explains LOTI. NASA’s new GMSTA page (<https://data.giss.nasa.gov/gistemp/gmsta/>) uses a 1850–1900 preindustrial baseline and NMME/statistical forecasts; those forecasts require baseline conversion and are not the same metric as the contract’s 1951–1980 LOTI.

The main traps are strict “above” semantics, confusing the unsmoothed LOTI with a smoothed series or GMSTA, mixing the 1951–80 and preindustrial baselines, mishandling hundredths/annual averaging and rounding, overlooking monthly data revisions, and confusing the December 31 close with the later data-release expiration.
