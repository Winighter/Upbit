import ccxt, math, time, requests, threading

from config import *
from indicator import *


class Upbit:
    def __init__(self, access:str, secret:str):

        # EXCHAGE CCXT
        self.exchange = ccxt.upbit(config={
        'apiKey': access,
        'secret': secret,
        'enableRateLimit': True
        })

        # DEFAULT SETTINGS
        self.balance_dict = {}
        self.not_balance_dict = {}
        self.symbol_signal_dict = {}
        self.buy_order_list = []
        self.sell_order_list = []
        self.sell_cnt = False

        # CUSTOM SETTINGS
        self.symbol = "KRW-XRP"
        self.position = 20 # 10 ~ 20 %
        self.risk = 1.5 # [0.25-1] [0.5-1.5] %
        self.balance = 0
        self.locked = 0
        self.deposit = 0

        # RUN
        self.get_balance()
        self.min_candle_chart()
        ws_all = WebSocketAll(access, secret, self.symbol)
        while True:
            data = ws_all.get()
            self.on_ws_private_data(data)
        ws_all.terminate()

    def get_hoka(self,_symbol):
        url = "https://api.upbit.com/v1/orderbook"
        querystring = {"markets":_symbol,"level":"0"}
        response = requests.request("GET", url, params=querystring)
        data = response.json()

        for i in data:
            for h in i["orderbook_units"]:
                bid_price = float(h["bid_price"])
                break

        return bid_price

    def get_balance(self):

        balance = self.exchange.fetch_balance()

        for i in balance["info"]:

            locked = float(i["locked"])
            balance = float(i["balance"])
            avg_buy_price = float(i['avg_buy_price'])
            symbol = f"{i["unit_currency"]}-{i["currency"]}"

            if symbol == "KRW-KRW":
                self.locked = math.trunc(locked)
                self.balance = math.trunc(balance)
            else:
                locked = float(format(locked,'.8f'))
                balance = float(format(balance,'.8f'))

                self.balance_dict.update({symbol:{"balance":balance,"locked":locked,"avg_buy_price":avg_buy_price}})

    def order(self, side:str, symbol:str, amount:float, price:float, id:str):

        # 주문취소
        if side == "CANCLE":
            if id != "":
                self.exchange.cancel_order(id)
                # Upbit.correct_list.append(symbol)
        else:
            if price != 0:

                # 매수 지정가
                if side == "BUY":
                    self.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=amount,
                        price=price
                    )
                    self.buy_order_list.append(symbol)

                # 매도 지정가
                else:
                    self.exchange.create_limit_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                        price=price        # 매도가격(KRW)
                    )
            else:
                # 매수 시장가
                if side == "BUY":
                    self.exchange.create_market_buy_order(
                        symbol=symbol,
                        amount=amount,
                    )

                # 매도 시장가
                else:
                    self.exchange.create_market_sell_order(
                        symbol=symbol,
                        amount=amount,       # 주문수량(XRP)
                    )
                    self.sell_order_list.append(symbol)

    def min_candle_chart(self):
        # self.balance = 300000
        deposit = math.trunc(self.balance*(self.position/100))
        risk = math.trunc(self.balance*(self.risk/100))*-1

        url = "https://api.upbit.com/v1/candles/minutes/60" # n분차트
        querystring = {"market":self.symbol,"count":"200"} # count = 필요한 봉 갯수
        response = requests.request("GET", url, params=querystring)
        data = response.json()

        close_list = []
        for i in data:
            a = float(i['trade_price'])
            close_list.append(a)

        close = close_list[0]

        # EMA 5
        ema10 = Ema.ema(close_list, 10)
        ema12 = Ema.ema(close_list, 12)
        ema20 = Ema.ema(close_list, 20)
        ema26 = Ema.ema(close_list, 26)
        ema50 = Ema.ema(close_list, 50)
        #####################################

        if (ema10 and ema20 and ema50) != None:

            if ema10 > ema20 and ema20 > ema50:
                pass

            elif ema10 < ema20 and ema20 < ema50:
                pass

        if (ema12 and ema26) != None:

            if close > ema12 and ema12 > ema26:

                if self.symbol in self.balance_dict.keys():
                    sbala = self.balance_dict[self.symbol]['balance']
                    sig = self.symbol_signal_dict[self.symbol]
                    if sbala > 0 and sig == True:
                        self.symbol_signal_dict.update({self.symbol:False})

            if close < ema12 and ema12 < ema26:
                self.symbol_signal_dict.update({self.symbol:True})

        # 매수
        if self.symbol not in self.balance_dict.keys():

            if self.symbol not in self.not_balance_dict.keys():

                if self.symbol in self.symbol_signal_dict.keys():

                    signal = self.symbol_signal_dict[self.symbol]

                    if signal == True:

                        if close > ema12 and ema12 > ema26:

                            bid_price = self.get_hoka(self.symbol)
                            amount = float(format(deposit/bid_price, '.8f'))
                            print("매수")
                            self.order("BUY", self.symbol, amount, bid_price, "")

        # 매도
        if self.symbol in self.balance_dict.keys():

            보유수량 = self.balance_dict[self.symbol]['balance']
            locked = self.balance_dict[self.symbol]['locked']
            매수평균가 = self.balance_dict[self.symbol]['avg_buy_price']
            손실가 = math.trunc((close - 매수평균가) * 보유수량)

            # 최우선1순위 손절 주문 (손실 허용 범위 조건 매도)
            if self.symbol not in self.sell_order_list:
                if 손실가 <= risk:
                    print("전량 손절 매도")
                    self.order("SELL", self.symbol, 보유수량, 0, "")

            # 최우선2순위 12 26 교차(데드크로스) 또는 26 침범시 2차(마지막) 익절 주문
            if self.symbol not in self.sell_order_list:
                if (close < ema26 and ema12 > ema26) or (ema12 <= ema26):
                    print("전량 익절 매도",self.balance_dict)
                    self.order("SELL", self.symbol, 보유수량, 0, "")

            # 12 이평선 하향시 1차 익절 주문
            if self.symbol not in self.sell_order_list:
                if self.sell_cnt == False:
                    if ema12 > close and close > ema26:
                        amnt = float(보유수량/2)
                        self.sell_cnt = True
                        print("절반 익절 매도",amnt,self.balance_dict)
                        self.order("SELL", self.symbol, amnt, 0, "")

        # print(f"\n{self.symbol_signal_dict} {deposit} {risk}\n{self.balance_dict}\n{self.not_balance_dict}")

        threading.Timer(1,self.min_candle_chart).start()

    def on_ws_private_data(self, data):

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
                if currency != "KRW":
                    symbol = f"KRW-{currency}" # KRW-???
                    locked = float(s["locked"]) # 미체결
                    locked = float(format(locked, '.8f'))
                    balance = float(s["balance"]) # 주문가능
                    balance = float(format(balance, '.8f'))

                    if balance > 0:
                        self.get_balance()

                    if symbol in self.balance_dict.keys():
                        if balance == 0 and locked == 0:
                            self.balance_dict.pop(symbol)

if __name__ == "__main__":

    with open("./upbit.key") as f:
        lines = f.readlines()
        access = lines[0].strip()
        secret = lines[1].strip()
        upbit = Upbit(access, secret)
