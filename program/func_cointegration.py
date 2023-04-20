import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint
from constants import MAX_HALF_LIFE, WINDOW, ZSCORE_THRESH

# Calculate Half Life
# https://www.pythonforfinance.net/2016/05/09/python-backtesting-mean-reversion-part-2/

# Turn off SettingWithCopyWarning
pd.set_option("mode.chained_assignment", None)


def calculate_half_life(spread):
    df_spread = pd.DataFrame(spread, columns=["spread"])
    spread_lag = df_spread.spread.shift(1)
    spread_lag.iloc[0] = spread_lag.iloc[1]
    spread_ret = df_spread.spread - spread_lag
    spread_ret.iloc[0] = spread_ret.iloc[1]
    spread_lag2 = sm.add_constant(spread_lag)
    model = sm.OLS(spread_ret, spread_lag2)
    res = model.fit()
    halflife = round(-np.log(2) / res.params[1], 0)

    return halflife


def test_for_stationarity(spread):
    is_stationary = False

    # Perform Dickey-Fuller test
    result = adfuller(spread)

    # Extract test statistics and critical values
    test_statistic = result[0]
    critical_values = result[4]

    # Compare test statistic to critical values
    if test_statistic < critical_values["1%"]:
        is_stationary = True

    return is_stationary


# Calculate ZScore
def calculate_zscore(spread):
    spread_series = pd.Series(spread)
    mean = spread_series.rolling(center=False, window=WINDOW).mean()
    std = spread_series.rolling(center=False, window=WINDOW).std()
    x = spread_series.rolling(center=False, window=1).mean()
    zscore = (x - mean) / std

    return zscore


# Calculate Cointegration
def calculate_cointegration(series_1, series_2):
    series_1 = np.array(series_1).astype(np.float)
    series_2 = np.array(series_2).astype(np.float)

    coint_flag = 0
    coint_res = coint(series_1, series_2)
    coint_t = coint_res[0]
    p_value = coint_res[1]
    critical_value = coint_res[2][1]
    t_check = coint_t < critical_value
    coint_flag = 1 if p_value < 0.05 and t_check else 0

    return coint_flag


# Calculate hedge ratio and spread
def calculate_hedge_ratio_and_spread(series_1, series_2):
    series_1 = np.array(series_1).astype(np.float)
    series_2 = np.array(series_2).astype(np.float)

    model = sm.OLS(series_1, series_2).fit()
    hedge_ratio = model.params[0]
    spread = series_1 - (hedge_ratio * series_2)

    return hedge_ratio, spread


# Backtest pair for Sharpe Ratio
def backtest(spread, z_score):
    df_backtest = pd.DataFrame({"spread": spread, "z_score": z_score})

    entryZscore = ZSCORE_THRESH
    exitZscore = 0

    # Set up num units long
    df_backtest["long_entry"] = (df_backtest["z_score"] < -entryZscore) & (
        df_backtest["z_score"].shift(1) > -entryZscore
    )
    df_backtest["long_exit"] = (df_backtest["z_score"] > exitZscore) & (
        df_backtest["z_score"].shift(1) < exitZscore
    )
    df_backtest["num_units_long"] = np.nan
    df_backtest.loc[df_backtest["long_entry"], "num_units_long"] = 1
    df_backtest.loc[df_backtest["long_exit"], "num_units_long"] = 0
    df_backtest["num_units_long"][0] = 0
    df_backtest["num_units_long"] = df_backtest["num_units_long"].fillna(method="pad")

    # Set up num units short
    df_backtest["short_entry"] = (df_backtest["z_score"] > entryZscore) & (
        df_backtest["z_score"].shift(1) < entryZscore
    )
    df_backtest["short_exit"] = (df_backtest["z_score"] < -exitZscore) & (
        df_backtest["z_score"].shift(1) > -exitZscore
    )
    df_backtest.loc[df_backtest["short_entry"], "num_units_short"] = -1
    df_backtest.loc[df_backtest["short_exit"], "num_units_short"] = 0
    df_backtest["num_units_short"][0] = 0
    df_backtest["num_units_short"] = df_backtest["num_units_short"].fillna(method="pad")

    df_backtest["num_units"] = (
        df_backtest["num_units_long"] + df_backtest["num_units_short"]
    )
    df_backtest["spread_pct_ch"] = (
        df_backtest["spread"] - df_backtest["spread"].shift(1)
    ) / abs(df_backtest["spread"].shift(1))
    df_backtest["port_rets"] = df_backtest["spread_pct_ch"] * df_backtest[
        "num_units"
    ].shift(1)

    df_backtest["cum_rets"] = df_backtest["port_rets"].cumsum()
    df_backtest["cum_rets"] = df_backtest["cum_rets"] + 1

    # Calculate Sharpe Ratio
    sharpe = (
        df_backtest["port_rets"].mean() / df_backtest["port_rets"].std()
    ) * np.sqrt(365 * 6)

    return sharpe


# Store Cointegration Results
def store_cointegration_results(df_market_prices):
    # Initialize
    markets = df_market_prices.columns.to_list()
    criteria_met_pairs = []

    # Find cointegrated pairs
    # Start with our base pair
    for index_base, base_market in enumerate(markets[:-1]):
        series_1 = df_market_prices[base_market].values.astype(float).tolist()

        # Get Quote Pair
        for index_quote, quote_market in enumerate(markets[:-1]):
            if index_quote == index_base:
                continue

            series_2 = df_market_prices[quote_market].values.astype(float).tolist()

            # Check criteria
            coint_flag = calculate_cointegration(series_1, series_2)

            if coint_flag != 1:
                continue

            hedge_ratio, spread = calculate_hedge_ratio_and_spread(series_1, series_2)
            half_life = calculate_half_life(spread)
            stationary_flag = test_for_stationarity(spread)

            if half_life < 0 or half_life > MAX_HALF_LIFE or not stationary_flag:
                continue

            z_score = calculate_zscore(spread)
            sharpe = backtest(spread, z_score)

            # Log pair
            if sharpe >= 2.0:
                criteria_met_pairs.append(
                    {
                        "base_market": base_market,
                        "quote_market": quote_market,
                        "hedge_ratio": hedge_ratio,
                        "half_life": half_life,
                        "z_score": z_score.values.astype(float).tolist()[-1],
                        "sharpe_ratio": sharpe,
                    }
                )

    # Create and save DataFrame
    df_criteria_met = pd.DataFrame(criteria_met_pairs)
    df_criteria_met.sort_values(by="sharpe_ratio", ascending=False, inplace=True)
    df_criteria_met.to_csv("cointegrated_pairs.csv")
    del df_criteria_met

    # Return result
    print("Cointegrated pairs successfully saved")
    return "saved"
