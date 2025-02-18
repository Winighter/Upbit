import ccxt, math, requests, threading

from config import *
from indicator import *


class Upbit:
    def __init__(self, access:str, secret:str):

        self.access = access
        self.secret = secret

        Upbit.exchange = ccxt.upbit(config={
        'apiKey': access,
        'secret': secret,
        'enableRateLimit': True
        })

        Upbit.매수 = False
        Upbit.cross = False
        Upbit.balance_dict = {}
        Upbit.not_balance_dict = {}
        Upbit.black_list = ["KRW-TRX"]
        Upbit.percent_to_be_used = 50 # (%)
        self.get_balance()
        self.symbol = "KRW-BTC"
        # self.get_symbol()
        self.min_candle_chart()
        ws_all = WebSocketAll(access, secret, self.symbol)

        while True:
            data = ws_all.get()
            Upbit.on_ws_private_data(data)
        ws_all.terminate()

    def on_ws_private_data(data):

        if data["type"] == "myOrder":

            state = data["state"] # wait: 체결 대기, watch: 예약 주문 대기, trade: 체결 발생, cancel: 주문 취소

            if state != "done":

                code = data["code"] # (ex. KRW-XRP
                uuid = data["uuid"] # 주문 고유 아이디 아마도 주문번호
                ask_bid = data["ask_bid"] # ASK : 매도 / BID : 매수
                order_type = data["order_type"] # limit: 지정가 ,price: 시장가 매수 ,market: 시장가 매도
                price = data["price"] # 주문 가격, 체결 가격 (state: trade 일 때)
                volume = data["volume"] # 주문 수량, 체결량 (state: trade 일 때)
                remaining_volume = data["remaining_volume"] # 체결 후 아직 미체결된 주문 양

                if state != "cancel":
                    Upbit.not_balance_dict.update({uuid:{"code":code,"ask_bid":ask_bid,"price":price,"volume":volume, "remaining_volume":remaining_volume}})

                    if state == "trade":

                        if uuid in Upbit.not_balance_dict.keys():

                            if remaining_volume == 0 and volume > 0:

                                Upbit.not_balance_dict.pop(uuid)

                    if state == "wait" and remaining_volume > 0:

                        if code in Upbit.order_buy_list and ask_bid == "BID":
                            Upbit.order_buy_list.remove(code)

                        if code in Upbit.order_sell_list and ask_bid == "ASK":
                            Upbit.order_sell_list.remove(code)


                elif state == "cancel":

                    if uuid in Upbit.not_balance_dict.keys():
                        Upbit.not_balance_dict.pop(uuid)

        else:
            assets = data["assets"]
            for s in assets:
                currency = s["currency"] # 종목 ex) KRW, XRP
                currency = f"KRW-{currency}"
                balance = s["balance"] # 주문가능
                locked = s["locked"] # 미체결

                if currency == "KRW-KRW":
                    balance = math.trunc(balance)
                    locked = math.trunc(locked)
                Upbit.balance_dict.update({currency:{"balance":balance,"locked":locked}})

                if balance == 0 and locked == 0:
                    Upbit.balance_dict.pop(currency)

                Upbit.매수 = False

    # 심볼 및 현재가 조회 KRW-BTC
    def get_symbol(self):
        sList = []
        symbol_dict = {}
        tickers = Upbit.exchange.fetch_tickers()
        symbols = tickers.keys()
        for s in symbols:
            if s.endswith("KRW"):
                s_info = tickers[s]["info"]
                close = float(s_info['trade_price'])
                if close < 2000: # 
                    symbol = s_info['market']
                    signed_change_rate = float(s_info['signed_change_rate'])*100
                    if signed_change_rate > 0:
                        symbol_dict.update({signed_change_rate:symbol})

        for i in list(symbol_dict.keys()):
            max_price = max(list(symbol_dict))
            if symbol_dict[max_price] not in Upbit.black_list:
                sList.append(symbol_dict[max_price])
                symbol_dict.pop(max_price)
                if len(sList) == 1:
                    break

        for i in Upbit.balance_dict.keys():
            if i != "KRW-KRW" and i not in sList:
                sList.append(i)
        self.symbol = sList

        threading.Timer(1, self.get_symbol).start()

    # 잔고 조회
    def get_balance(self): # KRW-BTC

        balance = Upbit.exchange.fetch_balance()
        balance_info = balance["info"]

        for i in balance_info:
            symbol = i["currency"] # BTC
            unit_currency = i["unit_currency"] # KRW
            symbol = f"{unit_currency}-{symbol}"
            balance = float(i["balance"])
            locked = float(i["locked"])

            if symbol == "KRW-KRW":
                balance = math.trunc(balance)
                locked = math.trunc(locked)

            Upbit.balance_dict.update({symbol:{"balance":balance,"locked":locked}})

    # 주문
    def order(bsc, symbol:str, amount:float, price:float, id:str):

        # 주문취소
        if bsc == "CANCLE":
            if id != "":
                Upbit.exchange.cancel_order(id)
        else:
            if price != 0:

                # 매수 지정가
                if bsc == "BUY":
                    Upbit.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=amount,
                        price=price
                    )

                # 매도 지정가
                else:
                    Upbit.exchange.create_limit_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                        price=price        # 매도가격(KRW)
                    )
            else:
                # 매수 시장가
                if bsc == "BUY":
                    Upbit.exchange.create_market_buy_order(
                        symbol=symbol,
                        amount=amount,
                    )

                # 매도 시장가
                else:
                    Upbit.exchange.create_market_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                    )

    ### Quotation ###
    def min_candle_chart(self): # KRW-BTC

        _symbol = "KRW-BTC"

        url = "https://api.upbit.com/v1/candles/minutes/5" # n분차트
        querystring = {"market":_symbol,"count":"51"} # count = 필요한 봉 갯수
        response = requests.request("GET", url, params=querystring)
        data = response.json()

        close_list = []
        for i in data:
            a = float(i['trade_price'])
            close_list.append(a)

        close = close_list[0]
        ema12 = Ema.ema(close_list, 12)
        ema26 = Ema.ema(close_list, 26)

        # 매수
        if Upbit.매수 == False:

            # 정정 및 재주문
            if Upbit.not_balance_dict != {}:

                for i in Upbit.not_balance_dict.copy().keys():
                    nbdata = Upbit.not_balance_dict[i]
                    bid = nbdata["ask_bid"]
                    price = nbdata["price"]
                    매수호가 = Upbit.hoka(_symbol)
                    remaining_volume = nbdata["remaining_volume"]

                    if bid == "BID" and remaining_volume > 0 and price < 매수호가:
                        Upbit.order("CANCLE",_symbol, remaining_volume, 매수호가, i)

            # 하락 추세
            if close < ema12 and ema12 < ema26:

                if Upbit.cross == False:
                    Upbit.cross = True

                if _symbol in Upbit.balance_dict.keys():
                    sAmount = Upbit.balance_dict[_symbol]['balance']

                    Upbit.매수 = True
                    Upbit.order("SELL", _symbol, sAmount, 0, "")

            # 상승 추세
            if close > ema12 and ema12 >= ema26:

                if _symbol not in Upbit.balance_dict.keys() and Upbit.not_balance_dict == {}:
                    bBalance = Upbit.balance_dict["KRW-KRW"]["balance"]
                    deposit = math.trunc(bBalance*(Upbit.percent_to_be_used/100))
                    bid_price = int(Upbit.hoka(_symbol))
                    bAmount = format(deposit/bid_price,'.8f')

                    if Upbit.cross == True:
                        Upbit.매수 = True
                        Upbit.cross = False
                        Upbit.order("BUY", _symbol, bAmount, bid_price, "")
   
        threading.Timer(1,self.min_candle_chart).start()

    def hoka(_symbol): # KRW-BTC
        url = "https://api.upbit.com/v1/orderbook"
        querystring = {"markets":_symbol,"level":"0"}
        response = requests.request("GET", url, params=querystring)
        data = response.json()
        bid_price = 0

        for i in data:
            for h in i["orderbook_units"]:
                bid_price = h["bid_price"]
                break

        return bid_price

if __name__ == "__main__":

    with open("./upbit.key") as f:
        lines = f.readlines()
        access = lines[0].strip()
        secret = lines[1].strip()
        # slack_token = lines[2].strip()
        upbit = Upbit(access, secret)
