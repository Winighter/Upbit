import ccxt, math, time, requests, threading

from config import *
from indicator import *


class Upbit:
    def __init__(self, access:str, secret:str):

        print("Upbit Starting...")

        self.access = access
        self.secret = secret

        Upbit.exchange = ccxt.upbit(config={
        'apiKey': access,
        'secret': secret,
        'enableRateLimit': True
        })

        Upbit.매수 = False
        Upbit.buy_list = []
        Upbit.sell_list = []
        Upbit.correct_list = []
        self.balance_dict = {}
        self.not_balance_dict = {}
        Upbit.percent_to_be_used = 50 # (%)
        self.symbol_cross_dict = {}
        self.test_count = 0

        self.symbol = []
        self.get_balance()
        self.get_symbol()
        self.min_candle_chart()
        ws_all = WebSocketAll(access, secret, self.symbol)
        while True:
            data = ws_all.get()
            self.on_ws_private_data(data)
        ws_all.terminate()

    def get_hoka(_symbol): # KRW-BTC
        url = "https://api.upbit.com/v1/orderbook"
        querystring = {"markets":_symbol,"level":"0"}
        response = requests.request("GET", url, params=querystring)
        data = response.json()

        for i in data:
            for h in i["orderbook_units"]:
                bid_price = float(h["bid_price"])
                break

        return bid_price

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
            else:
                balance = format(balance, '.8f')
                balance = float(balance)
                locked = format(locked, '.8f')
                locked = float(locked)

            if locked > 0:
                print("미체결 내역 조회")

            self.balance_dict.update({symbol:{"balance":balance,"locked":locked}})

    # 심볼 및 현재가 조회 KRW-BTC
    def get_symbol(self):
        sList = []
        symbol_dict = {}
        black_list = ["KRW-TRX","KRW-USDT","KRW-BTC","KRW-STPT"]

        tickers = Upbit.exchange.fetch_tickers()
        symbols = tickers.keys()

        for s in symbols:
            if s.endswith("KRW"):
                s_info = tickers[s]["info"]
                symbol = s_info['market']
                acc_trade_price_24h = float(s_info['acc_trade_price_24h'])
                trade_price = float(s_info['trade_price'])
                if acc_trade_price_24h >= 100000000000: # 천억
                    symbol_dict.update({acc_trade_price_24h:symbol})

        symbol_list = list(symbol_dict.keys())
        symbol_list.sort(reverse=True)

        for i in range(len(symbol_list)):
            key = symbol_list[i]
            value = symbol_dict[key]
            if value not in black_list:
                sList.append(value)

        if len(self.balance_dict.keys()) > 1:
            for i in self.balance_dict.keys():
                if i != "KRW-KRW" and i not in sList:
                    sList.append(i)

        self.symbol = sList

        threading.Timer(1, self.get_symbol).start()

    # 주문
    def order(bsc, symbol:str, amount:float, price:float, id:str):

        # 주문취소
        if bsc == "CANCLE":
            if id != "":
                Upbit.exchange.cancel_order(id)
                # Upbit.correct_list.append(symbol)
        else:
            if price != 0:

                # 매수 지정가
                if bsc == "BUY":
                    Upbit.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=amount,
                        price=price
                    )
                    # Upbit.buy_list.append(symbol)

                # 매도 지정가
                else:
                    Upbit.exchange.create_limit_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                        price=price        # 매도가격(KRW)
                    )
                    # Upbit.sell_list.append(symbol)
            else:
                # 매수 시장가
                if bsc == "BUY":
                    Upbit.exchange.create_market_buy_order(
                        symbol=symbol,
                        amount=amount,
                    )
                    Upbit.buy_list.append(symbol)

                # 매도 시장가
                else:
                    Upbit.exchange.create_market_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                    )
                    Upbit.sell_list.append(symbol)

        time.sleep(0.5)

    ### Quotation ###
    def min_candle_chart(self): # KRW-BTC

        for _symbol in self.symbol:
            
            url = "https://api.upbit.com/v1/candles/minutes/1" # n분차트
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

            #####################################
            if ema12 != None and ema26 != None:

                # 하락 추세
                if close < ema12 and ema12 < ema26:

                    self.symbol_cross_dict.update({_symbol:True})

                    if _symbol in self.balance_dict.keys():
                        Log(f"{_symbol} SELL")
                        _sAmount = self.balance_dict[_symbol]['balance']
                        Upbit.order("SELL", _symbol, _sAmount, 0, "")

                # 상승 추세
                if close > ema12 and ema12 > ema26:

                    if _symbol in self.symbol_cross_dict.keys():

                        symbol_cross = self.symbol_cross_dict[_symbol]

                        if symbol_cross == True:

                            if len(self.balance_dict.keys()) == 1: # 현재로서는 종목 1개만 매매

                                if _symbol not in self.balance_dict.keys():

                                    sym_list = []
                                    for n in self.not_balance_dict.keys():
                                        symbol = self.not_balance_dict[n]['symbol']
                                        sym_list.append(symbol)

                                    if _symbol not in sym_list:
                                        Log(f"{_symbol} BUY")
                                        bid_price = float(Upbit.get_hoka(_symbol))
                                        balance = int(self.balance_dict["KRW-KRW"]["balance"])
                                        deposit = math.trunc(balance*(Upbit.percent_to_be_used/100/len(self.symbol)))
                                        amount = float(format(deposit/bid_price,'.8f'))
                                        if deposit*amount > balance:
                                            pass
                                        else:
                                            Upbit.order("BUY", _symbol, amount, bid_price, "")

                # 취소 및 재주문(재주문은 안되는 것 같음)
                if self.not_balance_dict != {}:

                    for nb in self.not_balance_dict.keys():
                        short_not = self.not_balance_dict[nb]
                        symbol = short_not['symbol']
                        ask_bid = short_not['ask_bid']
                        order_type = short_not['order_type']
                        price = short_not['price']
                        remaining_volume = short_not['remaining_volume']
                        new_hoka = float(Upbit.get_hoka(_symbol))
                        if price < new_hoka and remaining_volume > 0:
                            Upbit.order("CANCLE", symbol, remaining_volume, new_hoka, nb)

        threading.Timer(1,self.min_candle_chart).start()

    # 주문 및 체결내역 & 잔고
    def on_ws_private_data(self,data):

        if data["type"] == "myOrder":
            '''
            {
            'code': 'KRW-XRP', 'uuid': '3f23d426-cc72-4dd7-923b-1d1b19716ce1', 
            'ask_bid': 'BID', 'order_type': 'limit', 'state': 'wait', 'trade_uuid': None, 
            'price': 500, 'avg_price': 0, 'volume': 10, 'remaining_volume': 10, 'executed_volume': 0, 
            'trades_count': 0, 'reserved_fee': 2.5, 'remaining_fee': 2.5, 'paid_fee': 0, 'locked': 5002.5,
            'executed_funds': 0, 'time_in_force': None, 'trade_fee': None, 'is_maker': None, 'identifier': None,
            }
            '''
            state = data["state"]
            symbol = data['code'] # KRW-BTC
            uuid = data["uuid"] # 주문번호
            ask_bid = data['ask_bid']
            order_type = data['order_type']
            price = data['price']
            remaining_volume = data['remaining_volume']

            if state != "done":
                self.not_balance_dict.update({uuid:{'symbol':symbol,'ask_bid':ask_bid,'order_type':order_type,'price':price,'remaining_volume':remaining_volume}})

            if state == "wait": # 체결 대기
                pass

            if state == "watch": # 예약 주문 대기
                pass

            if state == "trade": # 체결 발생

                if remaining_volume == 0:
                    if uuid in self.not_balance_dict.keys():
                        self.not_balance_dict.pop(uuid)

            if state == "cancel": # 주문 취소

                if uuid in self.not_balance_dict.keys():
                    self.not_balance_dict.pop(uuid)

            if state == "done": # 전체 체결 완료
                pass
        else:
            assets = data["assets"] # assets values
            for s in assets:
                currency = s["currency"] # 종목 ex) KRW, XRP
                symbol = f"KRW-{currency}" # KRW-???
                locked = float(s["locked"]) # 미체결
                balance = float(s["balance"]) # 주문가능

                if symbol == "KRW-KRW":
                    locked = math.trunc(locked)
                    balance = math.trunc(balance)
                else:
                    locked = float(format(locked, '.8f'))
                    balance = float(format(balance, '.8f'))

                self.balance_dict.update({symbol:{"balance":balance,"locked":locked}})

                if balance == 0 and locked == 0:
                    self.balance_dict.pop(symbol)

                if symbol in self.symbol_cross_dict.keys():

                    if self.symbol_cross_dict[symbol] == True and balance > 0 and locked == 0:
                        self.symbol_cross_dict.pop(symbol)

if __name__ == "__main__":

    with open("./upbit.key") as f:
        lines = f.readlines()
        access = lines[0].strip()
        secret = lines[1].strip()
        # slack_token = lines[2].strip()
        upbit = Upbit(access, secret)
