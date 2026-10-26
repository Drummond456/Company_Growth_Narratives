from pvgo_history import format_points_table, write_outputs
from pvgo_history_series import collect_history

# --- Set these before running -----------------------------------------------
TICKER = "COST"  # one stock ticker (US listing; e.g. a class-B share as "XXX.B")
YEARS = 5  # chart period in years, counting back from today (e.g. 0.5, 1, 2)
ERP_PCT = 4.60  # equity risk premium in percent (e.g. 4.3); None = default 4.14% (Damodaran ERP Jan. 2026).
# For an explanation run: the average of Damodaran's January estimates for the run's years (2024: 4.60), as main.py sets it
ERP_BY_YEAR = False  # True = Damodaran's implied ERP at each date (damodaran_implied_erp.csv); needs ERP_PCT = None.
# Off for explanation runs: mid-year values interpolate toward the next January's estimate (METHODOLOGY 7)
MARKET_BETA = False  # True = beta 1.0 instead of the industry bet; False = use Damodaran industry beta
OWN_BETA = True  # True = the company's own beta at each date (60 monthly returns vs the S&P 500, Blume-adjusted),
# instead of the industry beta; needs MARKET_BETA = False. Much closer to Counterpoint's charts (METHODOLOGY.md 7)
BLUME_ADJUST = True  # True = own beta Blume-adjusted (0.67 x slope + 0.33, pulled toward 1.0); False = the raw
# regression slope. Needs OWN_BETA = True
# EPS versions to plot: turn on one or more (the same readings as pvgo_growth_share.py).
# Each gets its own no-growth line and growth-share line on the same chart.
PLOT_TTM_ADJUSTED = True  # adjusted TTM EPS, the standard: TTM without the realized and
# unrealized gains and losses on investments, less 25% tax, so a mark-to-market swing isn't capitalized as
# permanent earnings; other one-time items still enter at their release and leave four quarters later, and
# explain_run.py explains each step. Outputs: <TICKER>_pvgo_history_ttm_adjusted_*.csv
PLOT_TTM = False  # raw TTM diluted EPS, for comparison. Keep it on while
# an explanation run on the "ttm" basis may still be updated. Its outputs keep the unsuffixed file names
PLOT_TWO_YEAR = False  # 2-year EPS, for comparisons with Counterpoint: the last 8 quarters without the highest and
# lowest, x 4/6. Keep it on while an explanation run on the 2-year basis may still be updated. Not a check on the
# adjusted TTM's one-time charges: it's built on raw GAAP EPS, so investment marks move it
PLOT_SIX_MONTH = False  # 6-month EPS: the last 2 quarters x 2 (annualized); reacts soonest, but one-time items
# weigh double and seasonal quarters make it swing within the year
PLOT_RD_ADJUSTED = False  # R&D-adjusted EPS: the TTM EPS with R&D capitalized
RELEASE_ITEMS = False  # True = also save each release's press-release EPS reconciliation (the GAAP-to-adjusted
# table naming one-time items: legal charges, investment gains/losses, restructuring) to
# Outputs_CSV_data/<TICKER>_pvgo_history_release_items.csv. One SEC request per release, cached; read by
# Company_Narrative_Aggregation/explain_run.py
# Smoother lines on the chart only (the tables and CSVs keep the daily values):
SMOOTHING = "monthly"  # None = daily; "weekly", "monthly" or "yearly" = a 1-week, 1-month or 1-year moving average


def main():
    if not TICKER.strip() or TICKER.strip() == "<ticker>":
        raise SystemExit("Set TICKER at the top of pvgo_history_run.py first.")
    if YEARS * 365 < 30:
        raise SystemExit("Set YEARS to at least 0.1 (about a month).")
    bases = [basis for basis, on in (("ttm_adjusted", PLOT_TTM_ADJUSTED), ("ttm", PLOT_TTM),
                                     ("two_year", PLOT_TWO_YEAR), ("six_month", PLOT_SIX_MONTH),
                                     ("rd_adjusted", PLOT_RD_ADJUSTED)) if on]
    if not bases:
        raise SystemExit("Turn on at least one of PLOT_TTM_ADJUSTED, PLOT_TTM, PLOT_TWO_YEAR, PLOT_SIX_MONTH and "
                         "PLOT_RD_ADJUSTED.")
    if OWN_BETA and MARKET_BETA:
        raise SystemExit("Choose one beta: set OWN_BETA or MARKET_BETA to False.")
    if not BLUME_ADJUST and not OWN_BETA:
        raise SystemExit("BLUME_ADJUST = False needs OWN_BETA = True: only the company's own beta is Blume-adjusted.")
    if SMOOTHING not in (None, "weekly", "monthly", "yearly"):
        raise SystemExit('Set SMOOTHING to None, "weekly", "monthly" or "yearly".')
    if ERP_BY_YEAR and ERP_PCT is not None:
        raise SystemExit("ERP_BY_YEAR replaces ERP_PCT: set ERP_PCT = None, or turn ERP_BY_YEAR off.")

    # The daily share price vs. the no-growth value per share (EPS / cost of
    # equity) for each EPS version turned on, stepping at each earnings
    # release, with the growth share on a right-hand axis (PVGO shaded when
    # one version is plotted). Saves the chart in PVGO_Collection/ plus two
    # CSVs per version in PVGO_Collection/Outputs_CSV_data/. With a year-end
    # in the window, also the growth share at each year-end (a CSV per
    # version, and a chart of them from two year-ends): the unit of
    # Counterpoint's charts. Needs SEC_EDGAR_USER_AGENT in .env.
    versions = collect_history([TICKER], market_beta=MARKET_BETA, erp_pct=ERP_PCT,
                               window_days=round(YEARS * 365), eps_basis=bases, erp_by_year=ERP_BY_YEAR,
                               own_beta=OWN_BETA, blume=BLUME_ADJUST, release_items=RELEASE_ITEMS)

    for v in versions:  # one per EPS version; empty if the ticker was skipped (the reason is printed)
        print(format_points_table(v))
        print()
    if versions:
        try:
            written = write_outputs(versions, smoothing=SMOOTHING)
            print(f"Chart saved to {written[0]}")
            if written[1].endswith("_year_end.png"):
                print(f"Year-end chart saved to {written[1]}")
        except OSError as exc:  # Windows refuses to overwrite a file that's open in another program
            print(f"Couldn't write {exc.filename} -- is it open in Excel or an image viewer? Close it and rerun.")


if __name__ == "__main__":
    main()
