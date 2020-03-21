import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import time
import json
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

pairs = ["AUD_CAD", 
    "AUD_USD",
    "CAD_JPY",
    "EUR_CHF",
    "EUR_GBP",
    "EUR_JPY",
    "EUR_USD",
    "GBP_CAD",
    "GBP_USD",
    "USD_CAD",
    "USD_JPY",
    "USD_CHF"]

pos_size = int(input("POSITION_SIZE(DEFAULT=600): "))
granularity = input("GRANULARITY: ") 
candle_count = int(input("CANDLE_COUNT(DEFAULT=800): "))
script_duration = float(input("SCRIPT RUNS FOR(HR): "))
atr_n = int(input("ATR_N(DEFAULT=14): "))

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
    "USD_JPY": 3,
    "USD_CHF": 5
}

def market_order(instrument,units,account_id, close, atr):
    if units > 0:
        profit_price = round(close + atr * 4, decimal[instrument])
        loss_price = round(close - atr * 2, decimal[instrument])
    elif units < 0:
        profit_price = round(close - atr * 4, decimal[instrument])
        loss_price = round(close + atr * 2, decimal[instrument])
    data = {
        "order": {
            "price": "",
            'stopLossOnFill': {
                "timeInForce": "GTC",
                'price': str(loss_price),
            },
            "takeProfitOnFill": {
                "timeInForce": "GTC",
                "price": str(profit_price)
            },
            "timeInForce": "FOK",
            "instrument": str(instrument),
            "units": str(units),
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }
    r = orders.OrderCreate(accountID=account_id, data=data)

    play_obj = wave_obj.play()
    play_obj.wait_done()
    return client.request(r)

def signalIntoPosition(df):
    signal = ""
    angle50 = df['angle50'].iloc[-1]
    angle100 = df['angle100'].iloc[-1]
    angle150 = df['angle150'].iloc[-1]
    
    ema50 = df['ema50'].iloc[-1]
    ema100 = df['ema100'].iloc[-1]
    ema150 = df['ema150'].iloc[-1]

    close = df['close'].iloc[-1]
    close_prev = df['close'].iloc[-2]

    concavity50 = df['concavity50'].iloc[-1]
    concavity100 = df['concavity100'].iloc[-1]

    if angle50 >= 30 and angle100 >= 30 and angle150 >= 30 and angle50 <= 60 and angle100 <= 60 and angle150 <= 60:
        if close > ema50 and close_prev < ema50:
            play_obj = wave_obj.play()
            play_obj.wait_done()
            print("CHECKING d^2y/dx^2")
            signal = "Buy" if concavity50 > 0 and concavity100 > 0 else ""
    if angle50 <= -30 and angle100 <= -30 and angle150 <= -30 and angle50 >= -60 and angle100 >= -60 and angle150 >= -60:
        if close < ema50 and close_prev > ema50:
            play_obj = wave_obj.play()
            play_obj.wait_done()
            print("CHECKING d^2y/dx^2")
            signal = "Sell" if concavity50 < 0 and concavity100 < 0 else ""

    print(colored("Signal " + signal, 'blue'))
    if signal == "Buy" or signal == "Sell":
        play_obj = wave_obj.play()
        play_obj.wait_done()
        print(colored(df.tail(2).drop(["open", "high", "low", "volume"], axis = 1).to_string(), "blue"))
    return signal, close

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
            print("analyzing currency not in position: ",currency)
            data = oanda.getCandles(currency, candle_count, granularity)
          
            data = indicators.ema_n(data, 50)
            data = indicators.ema_n(data, 100)
            data = indicators.ema_n(data, 150)
            data = indicators.atr_talib(data, 14)
          
            data["angle50"] = indicators.slope(data["ema50"], 5)
            data["angle100"] = indicators.slope(data["ema100"], 5)
            data["angle150"] = indicators.slope(data["ema150"], 5)

            data["concavity50"] = indicators.slope(data["angle50"], 5)
            data["concavity100"] = indicators.slope(data["angle100"], 5)

            data = data.dropna()
            signal, close = signalIntoPosition(data)
            if signal == "Buy":
                market_order(currency,pos_size, account_id, close, data["ATR"].iloc[-1])
                print(colored("New long position initiated for " + str(currency), 'green'))

            elif signal == "Sell":
                market_order(currency,-1*pos_size, account_id, close, data["ATR"].iloc[-1])
                print(colored("New short position initiated for " + str(currency), 'red'))
            show_data = data.tail(4).drop(["open", "high", "low", "volume"], axis = 1)
            print(colored(show_data.to_string() + "\n\n", 'yellow'))
            print("======================\n")

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
        print(colored("RETRYING CANDLE", 'magenta'))
        continue
    except:
        print(colored("RETRYING CANDLE", 'magenta'))
        continue
