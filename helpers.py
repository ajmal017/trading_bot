import datetime
import talib
import pandas as pd
import pandas_datareader as pdr
import numpy as np
import statsmodels.api as sm
import copy
from stocktrends import Renko

import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades

from alpha_vantage.timeseries import TimeSeries

class AlphaVantageData:

    def __init__(self):
        return    

    def getAlphaTimeSeries(self, ticker, interval, key,):
        ts = TimeSeries(key=key, output_format='pandas')
        data, meta_data, r = ts.get_intraday(symbol=ticker,interval=interval, outputsize='full')
        data.columns = ["open", "high", "low", "close", "volume"]
        return data

class Indicators:

    def __init__(self):
        return

    #PD must have the format["date, open, high, low, close"]
    def atr(self, DF, n):
        df = DF.copy()
        df["H-L"] = abs(df["high"] - df["low"])
        df["H-PC"] = abs(df["high"] - df["close"].shift(1))
        df["L-PC"] = abs(df["low"] - df["close"].shift(1))
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis = 1, skipna = False)
        df["ATR"] = df["TR"].rolling(n).mean()
        df2 = df.drop(["H-L", "H-PC", "L-PC"], axis = 1)
        return df2

    def atr_talib(self, DF, n):
        df = DF.copy()
        df["ATR"] = talib.ATR(DF["high"], DF["low"], DF["close"], timeperiod = n)
        return df

    def bollinger_bands(self, DF, n):
        df = DF.copy()
        df["MA"] = df["close"].rolling(n).mean()
        df["BB_up"] = df["MA"] + 2 * df["MA"].rolling(n).std() 
        df["BB_dn"] = df["MA"] - 2 * df["MA"].rolling(n).std()
        df["BB_range"] = df["BB_up"] - df["BB_dn"]
        df.dropna(inplace = True)
        return df

    def macd(self, DF, fastN, slowN, macdN) :
        df = DF.copy()
        df["MA_FAST"] = df["close"].ewm(span = fastN, min_periods = fastN).mean()
        df["MA_SLOW"] = df["close"].ewm(span = slowN, min_periods = slowN).mean()
        df["MACD"] = df["MA_FAST"] - df["MA_SLOW"]
        df["Signal"] = df["MACD"].ewm(span = macdN, min_periods = macdN).mean()
        df.dropna(inplace = True)
        return df

    def obv(self, DF):
        df = DF.copy()
        df['daily_ret'] = df['close'].pct_change()
        df['direction'] = np.where(df['daily_ret']>=0,1,-1)
        df['direction'][0] = 0
        df['vol_adj'] = df['volume'] * df['direction']
        df['obv'] = df['vol_adj'].cumsum()
        df2 = df.drop(["daily_ret", "direction", "vol_adj"], axis = 1)
        return df2

    def obv_talib(self, DF):
        df = DF.copy()
        df['obv'] = talib.OBV(df['close'], df['volume'])
        return df

    def renko_bars(self, DF, n, instrument):
        df = DF.copy()
        df2 = Renko(df)
        real = talib.ATR(df["high"], df["low"], df["close"], timeperiod = n)
        brick_sizing = round(real[len(real) - 1], 5)
        print("BRICK_SIZE: ", brick_sizing)
        df2.brick_size = brick_sizing
        renko_df = df2.get_bricks()
        renko_df["bar_num"] = np\
            .where(renko_df["uptrend"]==True,1,np\
                .where(renko_df["uptrend"]==False,-1,0))
        for i in range(1,len(renko_df["bar_num"])):
            if renko_df["bar_num"][i]>0 and renko_df["bar_num"][i-1]>0:
                renko_df["bar_num"][i]+=renko_df["bar_num"][i-1]
            elif renko_df["bar_num"][i]<0 and renko_df["bar_num"][i-1]<0:
                renko_df["bar_num"][i]+=renko_df["bar_num"][i-1]
        renko_df.drop_duplicates(subset="date",keep="last",inplace=True)
        return renko_df, brick_sizing

    def rsi(self, DF, n):
        df = DF.copy()
        df["RSI"] = talib.RSI(df["close"], timeperiod = n)

    def slope(self, series, n):
        slopes = [i*0  for i in range(n - 1)]
        for i in range(n, len(series) + 1):
            y = series[i-n: i]
            x = np.array(range(n))
            #scaling, similar to standardization
            y_scaled = (y - y.min())/(y.max() - y.min())
            x_scaled = (x - x.min())/(x.max() - x.min())
            x_scaled = sm.add_constant(x_scaled)
            model = sm.OLS(y_scaled, x_scaled)
            results = model.fit()
            slopes.append(results.params[-1])
        slope_angle = (np.rad2deg(np.arctan(np.array(slopes))))
        return np.array(slope_angle)

    def slope_talib(self, series, n):
        return talib.LINEARREG_SLOPE(series, timeperiod = n)

    def angle_talib(self, series, n):
        return talib.LINEARREG_SLOPE(series, timeperiod = n)

    def sma(self, df, n):
        df['sma']= df['close'].rolling(n).mean()
        return df

    def ema_n(self, df, n):
        df["ema" + str(n)]= talib.EMA(df['close'], timeperiod=n)
        return df


class YahooData:

    def __init__(self):
        return

    def GetYahooOhlcv(self, ticker, days):
        return pdr.get_data_yahoo(ticker, datetime.date.today() - datetime.timedelta(days), datetime.date.today())

class Oanda:

    def __init__(self, account_id, access_token, environment):
        self.account_id = account_id
        self.access_token = access_token
        self.environment = environment
        self.client = oandapyV20.API(access_token= self.access_token, environment=self.environment)

    def getLiveEndpoint(self, ticker,):
        params = {"instruments": ticker}
        r = pricing.PricingInfo(accountID=self.account_id, params=params)
        rv = self.client.request(r)
        return {"date": rv["time"], "bid": rv["prices"][0]["closeoutBid"],"ask": rv["prices"][0]["closeoutAsk"]}

    def getAccountDetails(self):
        return self.client.request(accounts.AccountDetails(accountID=self.account_id))

    def getAccountSummary(self):
        return self.client.request(accounts.AccountSummary(accountID=self.account_id))

    #returns a dataframe formatted [date, open, high, low, close, volume]
    #granularity can be in seconds S5 - S30, minutes M1 - M30, hours H1 - H12, days D, weeks W or months M
    def getCandles(self, ticker, count, granularity):
        try:
            params = {"count": count,"granularity": granularity}
            candles = instruments.InstrumentsCandles(instrument=ticker,params=params)
            self.client.request(candles)
            ohlc_dict = candles.response["candles"]
            ohlc = pd.DataFrame(ohlc_dict)
        
            ohlc_df = ohlc["mid"].dropna().apply(pd.Series)
            ohlc_df["volume"] = ohlc["volume"]
            ohlc_df.index = ohlc["time"]
            ohlc_df = ohlc_df.apply(pd.to_numeric)
            ohlc_df.reset_index(inplace=True)
            ohlc_df = ohlc_df.iloc[:,[0,1,2,3,4,5]]
            ohlc_df.columns = ["date","open","high","low","close","volume"]
            ohlc_df['date'] = ohlc_df['date'].apply(lambda x: str(x).split('T'))
            ohlc_df['date'] = ohlc_df['date'].apply(lambda x: x[0] + " " + x[1].split('.')[0])
            return ohlc_df

        except:
            raise ConnectionError("Candle Error")
        
            


class Performance:

    def __init__(self):
        return

    #cumulative annual growth rate. need col with "ret" signifying return.
    def cagr(self, DF, n_periods_in_day):
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        n = len(df)/(253 * n_periods_in_day)
        CAGR = (df["cum_return"].tolist()[-1])**(1/n) - 1
        return CAGR

    #need col with "ret" signifying return.
    def annnualized_volatility(self, DF, n_periods_in_day):
        df = DF.copy()
        vol = df["ret"].std() * np.sqrt(253 * n_periods_in_day)
        return vol

    def sharpe(self, DF, rfr, n_periods_in_day):
        df = DF.copy()
        sr = (self.cagr(df, n_periods_in_day) - rfr) / self.annnualized_volatility(df, n_periods_in_day)
        return sr   

    def max_dd(self, DF):
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        df["cum_roll_max"] = df["cum_return"].cummax()
        df["drawdown"] = df["cum_roll_max"] - df["cum_return"]
        df["drawdown_pct"] = df["drawdown"]/df["cum_roll_max"]
        max_dd = df["drawdown_pct"].max()
        return max_dd
    
class DataFormatter:

    def __init__(self):
        return

    def merge_renko_timeframe(self, renko_df, ohlc_df):
        df = ohlc_df.merge(renko_df.loc[:,["date","bar_num"]],how="outer",on="date")
        df["bar_num"].fillna(method='ffill',inplace=True)
        return df