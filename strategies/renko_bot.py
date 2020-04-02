import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import json
import matplotlib.pyplot as plt
import time
import simpleaudio as sa
import helpers
import sys
from termcolor import colored, cprint

with open('keys.json') as f:
    data = json.load(f)

wave_obj = sa.WaveObject.from_wave_file("noti.wav")
f = open("log.txt", "a+")

client = oandapyV20.API(access_token= data["access_token"],environment= data["environment"])
account_id = data["account_id"]
oanda = helpers.Oanda(account_id, data["access_token"], data["environment"])
indicators = helpers.Indicators()
formatters = helpers.DataFormatter()

pairs = ["AUD_CAD","AUD_CHF","AUD_HKD","AUD_USD","CAD_CHF","CAD_JPY","EUR_CHF","EUR_GBP","EUR_JPY","EUR_USD","GBP_CAD","GBP_USD","USD_CAD","USD_JPY"]

pos_size = int(input("POSITION_SIZE(DEFAULT=600): "))
granularity = input("GRANULARITY: ") 
candle_count = int(input("CANDLE_COUNT(DEFAULT=800): "))
script_duration = float(input("SCRIPT RUNS FOR(HR): "))
atr_n = int(input("ATR_N(DEFAULT=14): "))

regression_slope_n = int(input("REGRESSION_SLOPE_N(DEFAULT=5): "))
rolling_sma_n = int(input("ROLLING_SMA_N(DEFAULT=12): "))

decimal = {
    "AUD_CAD" : 5,
    "AUD_CHF" : 5,
    "AUD_HKD": 5,
    "AUD_USD": 5,
    "CAD_CHF": 5,
    "CAD_JPY": 3,
    "EUR_CHF": 5,
    "EUR_GBP" : 5,
    "EUR_JPY": 3,
    "EUR_USD": 5,
    "GBP_CAD": 5,
    "GBP_USD": 5,
    "USD_CAD": 5,
    "USD_JPY": 3
}

positions_sl = {}
with open("positions_sl.json", "r") as jsonFile:
    positions_sl = json.load(jsonFile)
    jsonFile.close()

def market_order(instrument,units,account_id, brick_size, close, bar_num):
    if units > 0:
        price = round(close - brick_size * 2, decimal[instrument])
    elif units < 0:
        price = round(close + brick_size * 2, decimal[instrument])
    data = {
        "order": {
            "price": "",
            'stopLossOnFill': {
                'price': str(price),
            },
            "timeInForce": "FOK",
            "instrument": str(instrument),
            "units": str(units),
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    r = orders.OrderCreate(accountID=account_id, data=data)

    #update bar_num
    positions_sl[instrument] = bar_num
    update_positions()

    #notification
    play_obj = wave_obj.play()
    play_obj.wait_done()
    return client.request(r)

def order_edit(trade_id, account_id, new_sl, currency):
    print(colored("NEW_SL: " + str(new_sl), 'green'))
    edit = {
        "stopLoss": {
            "timeInForce": "GTC",
            "price": str(round(new_sl, decimal[currency])),
        }
    }
    play_obj = wave_obj.play()
    play_obj.wait_done()
    r = trades.TradeCRCDO(accountID = account_id, tradeID= trade_id, data = edit)
    return client.request(r)

def signalIntoPosition(df):
    signal = ""
    bar_num = df['bar_num'].iloc[-1]
    obv_slope = df['obv_slope'].iloc[-1]
    sma = df['sma'].iloc[-1]
    sma_slope = df['sma_slope'].iloc[-1]
    close = df['close'].iloc[-1]

    print(colored("BarNum: " + str(bar_num), 'white'))
    print(colored("OBVSlope: " + str(obv_slope), 'white'))
    print(colored("SMA: " + str(sma), 'white'))
    print(colored("Close: " + str(close), 'white'))
    print(colored("SMASlope: " + str(sma_slope), 'white'))

    if bar_num == 2 and sma_slope > 0 and obv_slope >= 30 and close > sma:
        signal = "Buy"
    if bar_num == -2 and sma_slope < 0 and obv_slope <= -30 and close < sma:
        signal = "Sell"

    print(colored("Signal " + signal, 'blue'))
    return signal, close, bar_num

def signal_edit_sl(df, isLong, currency, brick_size):
    bar_num = df['bar_num'].iloc[-1]
    close = df['close'].iloc[-1]
    signal = ""
    new_sl = close
    if isLong and bar_num > positions_sl[currency]:
        signal = "Edit"
        new_sl = close - 2 * brick_size
        positions_sl[currency] = bar_num
        update_positions()

    elif not isLong and bar_num < positions_sl[currency]:
        signal = "Edit"
        new_sl  = close + 2 * brick_size
        positions_sl[currency] = bar_num
        update_positions()
        
    return signal, new_sl

def update_positions():
    with open("positions_sl.json", "w") as jsonFile:
        json.dump(positions_sl, jsonFile)
        jsonFile.close()

def main():
    global pairs
    try:
        r = trades.OpenTrades(accountID=account_id)
        open_trades = client.request(r)['trades']
        
        curr_ls = []
        for i in range(len(open_trades)):
            curr_ls.append(open_trades[i]['instrument'])
        pairsNotInPosition = [i for i in pairs if i not in curr_ls]

        for currency in pairsNotInPosition:
            positions_sl.pop(currency, None)
            print("analyzing currency not in position: ",currency)
            data = oanda.getCandles(currency, candle_count, granularity)
            renkobars, brick_size = indicators.renko_bars(data, atr_n, currency)
            scaledRenko = formatters.merge_renko_timeframe(renkobars, data)
            scaledRenko = indicators.obv_talib(scaledRenko)
            scaledRenko = indicators.sma(scaledRenko, rolling_sma_n)
            scaledRenko["obv_slope"]= indicators.slope(scaledRenko["obv"], regression_slope_n)
            scaledRenko["sma_slope"] = indicators.slope(scaledRenko["sma"], regression_slope_n)
            scaledRenko = scaledRenko.dropna()
            signal, close, bar_num = signalIntoPosition(scaledRenko)
            if signal == "Buy":
                market_order(currency,pos_size, account_id, brick_size, close, bar_num)
                f.write("BUY" + currency + "\n"+ scaledRenko.to_string() + "\n")
                print(colored("New long position initiated for " + str(currency), 'green'))
            elif signal == "Sell":
                market_order(currency,-1*pos_size, account_id, brick_size, close, bar_num)
                f.write("SELL" + currency + "\n"+ scaledRenko.to_string() + "\n")
                print(colored("New short position initiated for " + str(currency), 'red'))

            show_data = scaledRenko.tail(20)
            print(colored(show_data.to_string() + "\n\n", 'yellow'))

        for positions in open_trades:
            id = positions['id']
            currency = positions['instrument']
            units = int(positions['currentUnits'])
            print("analyzing currency already in position: ", currency)
            data = oanda.getCandles(currency, candle_count, granularity)
            renkobars, brick_size = indicators.renko_bars(data, atr_n, currency)
            scaledRenko = formatters.merge_renko_timeframe(renkobars, data)
            scaledRenko = indicators.sma(scaledRenko, rolling_sma_n)
            scaledRenko["sma_slope"] = indicators.slope(scaledRenko["sma"], regression_slope_n)
            scaledRenko = scaledRenko.dropna()
            show_data = scaledRenko.tail(20)
            print(colored(show_data.to_string() + "\n\n", 'yellow'))
            signal, new_sl = signal_edit_sl(scaledRenko, units > 0, currency, brick_size)

            if signal == "Edit":
                order_edit(id, account_id, new_sl, currency)
                print(colored("Edited stop loss for " + currency, 'cyan'))

    except ValueError as error:
        print(format(error))


# Continuous execution        
starttime=time.time()
timeout = time.time() + 60 * 60 * script_duration

while time.time() <= timeout:
    try:
        print(granularity)
        print(candle_count)
        print(atr_n)
        print(regression_slope_n)
        print(rolling_sma_n)
        print("passthrough at ",time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        main()
        time.sleep(300 - ((time.time() - starttime) % 300.0))
    except KeyboardInterrupt:
        print('\n\nKeyboard exception received. Exiting.')
        exit()
    except ConnectionResetError:
        print(colored("RETRYING", 'magenta'))
        continue
    except ConnectionError:
        print(colored("RETRYING", 'magenta'))
        continue
