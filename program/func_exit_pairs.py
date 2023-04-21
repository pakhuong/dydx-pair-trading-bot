from constants import CLOSE_AT_ZSCORE_CROSS
from func_utils import format_number
from func_public import get_candles_recent
from func_cointegration import calculate_zscore
from func_private import place_market_order
import json
import time

from func_messaging import send_message


# Manage trade exits
def manage_trade_exits(client):
    """
    Manage exiting open positions
    Based upon criteria set in constants
    """

    # Initialize saving output
    save_output = []

    # Opening JSON file
    try:
        open_positions_file = open("bot_agents.json")
        open_positions_dict = json.load(open_positions_file)

    except:
        return "complete"

    # Guard: Exit if no open positions in file
    if len(open_positions_dict) < 1:
        return "complete"

    # Get all open positions per trading platform
    exchange_pos = client.private.get_positions(status="OPEN")
    all_exc_pos = exchange_pos.data["positions"]
    markets_live = []

    for p in all_exc_pos:
        markets_live.append(p)

    # Protect API
    time.sleep(0.5)

    # Get markets for reference of tick size
    markets = client.public.get_markets().data["markets"]

    # Protect API
    time.sleep(0.2)

    # Check all saved positions match order record
    # Exit trade according to any exit trade rules
    for position in open_positions_dict:
        # Initialize is_close trigger
        is_close = False

        # Extract position matching information from file - market 1
        position_market_m1 = position["market_1"]
        position_size_m1 = position["order_m1_size"]
        position_side_m1 = position["order_m1_side"]

        # Extract position matching information from file - market 2
        position_market_m2 = position["market_2"]
        position_size_m2 = position["order_m2_size"]
        position_side_m2 = position["order_m2_side"]

        # Protect API
        time.sleep(0.5)

        # Get order info m1 per exchange
        order_m1 = client.private.get_order_by_id(position["order_id_m1"])
        order_market_m1 = order_m1.data["order"]["market"]
        order_size_m1 = order_m1.data["order"]["size"]
        order_side_m1 = order_m1.data["order"]["side"]

        # Protect API
        time.sleep(0.5)

        # Get order info m2 per exchange
        order_m2 = client.private.get_order_by_id(position["order_id_m2"])
        order_market_m2 = order_m2.data["order"]["market"]
        order_size_m2 = order_m2.data["order"]["size"]
        order_side_m2 = order_m2.data["order"]["side"]

        # Perform matching checks
        check_m1 = (
            position_market_m1 == order_market_m1
            and position_size_m1 == order_size_m1
            and position_side_m1 == order_side_m1
        )
        check_m2 = (
            position_market_m2 == order_market_m2
            and position_size_m2 == order_size_m2
            and position_side_m2 == order_side_m2
        )

        check_m1_live = False

        for m in markets_live:
            if m["market"] == position_market_m1:
                check_m1_live = True

        check_m2_live = False

        for m in markets_live:
            if m["market"] == position_market_m2:
                check_m2_live = True

        check_live = check_m1_live and check_m2_live

        # Guard: If not all match exit with error
        if not check_m1 or not check_m2 or not check_live:
            print(
                f"Warning: Not all open positions match exchange records for {position_market_m1} and {position_market_m2}"
            )
            continue

        # Get prices
        series_1 = get_candles_recent(client, position_market_m1)
        time.sleep(0.2)
        series_2 = get_candles_recent(client, position_market_m2)
        time.sleep(0.2)

        # Trigger close based on Z-Score
        if CLOSE_AT_ZSCORE_CROSS:
            # Initialize z_scores
            hedge_ratio = position["hedge_ratio"]
            z_score_traded = position["z_score"]
            half_life = position["half_life"]

            if len(series_1) > 0 and len(series_1) == len(series_2):
                spread = series_1 - (hedge_ratio * series_2)
                z_score_current = calculate_zscore(
                    spread, int(half_life)
                ).values.tolist()[-1]
                position["spread_current"] = spread[-1]
                position["z_score_current"] = z_score_current

            # Determine trigger
            z_score_level_check = abs(z_score_current) >= 0
            z_score_cross_check = (z_score_current < 0 and z_score_traded > 0) or (
                z_score_current > 0 and z_score_traded < 0
            )

            # Close trade
            if z_score_level_check and z_score_cross_check:
                # Initiate close trigger
                is_close = True

        ###
        # Add any other close logic you want here
        # Trigger is_close
        ###

        # Close positions if triggered
        if is_close:
            # Determine side - m1
            side_m1 = "SELL"
            if position_side_m1 == "SELL":
                side_m1 = "BUY"

            # Determine side - m2
            side_m2 = "SELL"
            if position_side_m2 == "SELL":
                side_m2 = "BUY"

            # Get and format Price
            price_m1 = float(series_1[-1])
            price_m2 = float(series_2[-1])
            accept_price_m1 = price_m1 * 1.05 if side_m1 == "BUY" else price_m1 * 0.95
            accept_price_m2 = price_m2 * 1.05 if side_m2 == "BUY" else price_m2 * 0.95
            tick_size_m1 = markets[position_market_m1]["tickSize"]
            tick_size_m2 = markets[position_market_m2]["tickSize"]
            accept_price_m1 = format_number(accept_price_m1, tick_size_m1)
            accept_price_m2 = format_number(accept_price_m2, tick_size_m2)

            # Close positions
            try:
                # Close position for market 1
                print(">>> Closing market 1 <<<")
                print(f"Closing position for {position_market_m1}")

                close_order_m1 = place_market_order(
                    client,
                    market=position_market_m1,
                    side=side_m1,
                    size=position_size_m1,
                    price=accept_price_m1,
                    reduce_only=True,
                )

                print(close_order_m1["order"]["id"])
                print(">>> Closing <<<")

                # Protect API
                time.sleep(1)

                # Close position for market 2
                print(">>> Closing market 2 <<<")
                print(f"Closing position for {position_market_m2}")

                close_order_m2 = place_market_order(
                    client,
                    market=position_market_m2,
                    side=side_m2,
                    size=position_size_m2,
                    price=accept_price_m2,
                    reduce_only=True,
                )

                print(close_order_m2["order"]["id"])
                print(">>> Closing <<<")

            except Exception as e:
                print(f"Exit failed for {position_market_m1} with {position_market_m2}")
                save_output.append(position)

        # Keep record if items and save
        else:
            save_output.append(position)

        # Remove position from list `market_lives` after processing
        markets_live = [
            m
            for m in markets_live
            if m["market"] != position_market_m1 and m["market"] != position_market_m2
        ]

    # Close remaining live positions that are not being tracked
    if len(markets_live) > 0:
        print(f"{len(markets_live)} markets not being tracked. Closing...")

        for m in markets_live:
            market = m["market"]

            print(f">>> Closing {m['market']} <<<")

            price_series = get_candles_recent(client, market)
            time.sleep(0.2)
            price = float(price_series[-1])
            side = "SELL" if m["side"] == "LONG" else "BUY"
            # Position side will be negative in case of short position
            size = m["size"] if side == "SELL" else m["size"][1:]
            tick_size = markets[market]["tickSize"]
            accept_price = price * 1.05 if side == "BUY" else price * 0.95
            accept_price = format_number(accept_price, tick_size)

            try:
                close_order = place_market_order(
                    client,
                    market=market,
                    side=side,
                    size=size,
                    price=accept_price,
                    reduce_only=True,
                )

                print(close_order["order"]["id"])
                print(">>> Closing <<<")

                time.sleep(1)

            except Exception as e:
                print(f"Exit failed for market {market}:", e)
                send_message(f"Exit failed for market {market}: {e}")

    # Save remaining items
    print(f"{len(save_output)} Items remaining. Saving file...")

    with open("bot_agents.json", "w") as f:
        json.dump(save_output, f)
