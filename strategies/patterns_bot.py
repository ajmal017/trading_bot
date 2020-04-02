import oandapyV20
import time
import json
import helpers
import sys
import talib
import pandas as pd

with open('keys.json') as f:
    data = json.load(f)

f = open("patterns_log.txt", "a+")

candle_names = [
    "CDL3STARSINSOUTH", #bullish reversal
    #"CDL3WHITESOLDIERS", #bullish reversal
    "CDLINVERTEDHAMMER", #bear continuation #100 -> SELL
    "CDLRISEFALL3METHODS", #bear continuation
    #"CDLSEPARATINGLINES" #bullish continuation
]
#candle_names = talib.get_function_groups()['Pattern Recognition'] returns all the patterns

client = oandapyV20.API(access_token= data["access_token"],environment= data["environment"])
account_id = data["account_id"]
oanda = helpers.Oanda(account_id, data["access_token"], data["environment"])
indicators = helpers.Indicators()
formatters = helpers.DataFormatter()

pairs = ["AUD_CAD","AUD_CHF","AUD_HKD","AUD_USD","CAD_CHF","CAD_JPY","EUR_CHF","EUR_GBP","EUR_JPY","EUR_USD","GBP_CAD","GBP_USD","USD_CAD","USD_JPY"]

granularity = input("GRANULARITY: ") 
candle_count = int(input("CANDLE_COUNT(DEFAULT=800): "))

def main():
    global pairs
    try:
        for currency in pairs:
            print("analyzing currency not in position: ",currency)
            data = oanda.getCandles(currency, candle_count, granularity)
            for pattern in candle_names:
                data[pattern] = getattr(talib, pattern)(data["open"], data["high"], data["low"], data["close"])

            f.write(data.to_string())
            f.close()

    except ValueError as error:
        print(format(error))


# Continuous execution        
starttime=time.time()
timeout = time.time() + 60 * 60 * 1

while time.time() <= timeout:
    try:
        print("passthrough at ",time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        main()
        time.sleep(300 - ((time.time() - starttime) % 300.0))
    except KeyboardInterrupt:
        print('\n\nKeyboard exception received. Exiting.')
        exit()
