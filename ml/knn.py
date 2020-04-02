import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import numpy as np
import pandas as pd
import helpers
import talib

import matplotlib.pyplot as plt

from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error 
from math import sqrt

data = {
    "account_id": "101-003-13732651-001",
    "access_token": "ced47fd0c66657dc093c0a120479a74f-7211869c73c94f3ebb02ea88c0eede79",
    "environment": "practice"
}

pair = "USD_JPY"

client = oandapyV20.API(access_token= data["access_token"],environment= data["environment"])
account_id = data["account_id"]
oanda = helpers.Oanda(account_id, data["access_token"], data["environment"])
indicators = helpers.Indicators()
formatters = helpers.DataFormatter()

def getIndepIndicators(DF, rsi_n, bollinger_n):
    #get rsi
    df = DF.copy()
    df["rsi"] = talib.RSI(df["close"], timeperiod = rsi_n)
    #get ema
    df["ema50"] = df["ema50"]= talib.EMA(df['close'], timeperiod=50)
    df["ema100"] = df["ema100"]= talib.EMA(df['close'], timeperiod=100)
    df["ema150"] = df["ema150"]= talib.EMA(df['close'], timeperiod=150)
    #get bollingers
    upperband, middleband, lowerband = talib.BBANDS(df["close"], timeperiod=bollinger_n, nbdevup=2, nbdevdn=2, matype=0)
    df["BB_up"] = upperband
    df["BB_dn"] = upperband
    df["BB_range"] = upperband - middleband
    #obv
    df['obv'] = talib.OBV(df['close'], df['volume'])
    df.dropna(inplace = True)
    #angles
    df["angle50"] = talib.LINEARREG_SLOPE(df["ema50"], timeperiod = 5)
    df["angle100"] = talib.LINEARREG_SLOPE(df["ema100"], timeperiod = 5)
    df["angle150"] = talib.LINEARREG_SLOPE(df["ema150"], timeperiod = 5)
    #future_close
    df["future_close"] = df["close"].shift(-1)
    df.dropna(inplace = True)
    return df

#obtain data
data = oanda.getCandles(pair, 5000, "D")
data = getIndepIndicators(data, 14, 20)
data = data.reset_index().drop(["index"], axis = 1)
data.to_excel("data/USD_JPY_h.xlsx", index=False)


#defining independent variables
X = data.drop(["date", "future_close"], axis=1)

#define dependent variable
Y = data["future_close"]

scaler = MinMaxScaler(feature_range=(0, 1))

# x_train, x_test = train_test_split(X, test_size = 0.4)
# y_train, y_test = train_test_split(Y, test_size = 0.4)

train_percentage = 0.6
split = int(train_percentage*len(data))
x_train = X[:split]
x_test = X[split:]

y_train = Y[:split]
y_test = Y[split:]

x_train_scaled = scaler.fit_transform(x_train)
x_train = pd.DataFrame(x_train_scaled)
x_test_scaled = scaler.fit_transform(x_test)
x_test = pd.DataFrame(x_test_scaled)

knn = KNeighborsRegressor(n_neighbors=7)
knn.fit(x_train, y_train)
predicted = knn.predict(x_test)
error = sqrt(mean_squared_error(y_test,predicted))
predicted_df = pd.DataFrame(predicted)
len_test = len(predicted_df)
test_df = data.tail(len_test)
test_df["Real Ret"] = test_df["future_close"] / test_df["close"] - 1
test_df["pred_close"] = predicted
test_df["Predictive Ret"] = test_df["pred_close"] / test_df["close"] - 1

m, b = np.polyfit(test_df["Real Ret"], test_df["Predictive Ret"], 1)
plt.plot(test_df["Real Ret"], m*test_df["Real Ret"] + b, '-', color='r')

plt.scatter(test_df["Real Ret"], test_df["Predictive Ret"])
plt.title('Predictive Correlation by K-Nearest Neighbours')
plt.xlabel('Real Returns')
plt.ylabel('Predictive Returns')
plt.show()

corr_examine = test_df[["Real Ret", "Predictive Ret"]]
print("Corr: ", str(corr_examine.corr(method="pearson")))

f= open("knn_pred.txt","w+")
f.write(test_df.to_string())
f.close()

