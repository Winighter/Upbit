import ccxt, math, requests, threading

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

        ### DEFAULT SETTINGS ###

        # DICTIONALY
        self.balance_dict = {}
        self.not_balance_dict = {}

        # LIST
        self.buy_order_list = []
        self.sell_order_list = []

        # BOOLEAN
        self.sell_cnt = False
        self.ORDER_LOCK = False

        # CUSTOM SETTINGS
        self.symbol = "KRW-XRP"
        # self.deposit = 0 
        self.일차손절가격 = 0.0
        self.전량손절가격 = 0.0

        # RUN
        self.get_balance()
        self.min_candle_chart()
        ws_all = WebSocketAll(access, secret, self.symbol)
        while True:
            data = ws_all.get()
            self.on_ws_private_data(data)
        ws_all.terminate()

    def get_hoka(self, _symbol):
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

        position = 20 # 10 ~ 20 전체자산 기준 투자할 금액 비율 (%)
        risk = 1.5 # [0.25-1] [0.5-1.5] 투자금액 기준 손절할 금액 비율 (%)

        balance = self.exchange.fetch_balance()

        for i in balance["info"]:

            locked = float(i["locked"])
            balance = float(i["balance"])
            avg_buy_price = float(i['avg_buy_price'])
            symbol = f"{i["unit_currency"]}-{i["currency"]}"

            if symbol == "KRW-KRW":
                balance = math.trunc(balance)
                self.deposit = math.trunc(balance*(position/100))
                self.risk = math.trunc(balance*(risk/100))*-1
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
                        amount=amount,
                        price=price
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
                        amount=amount,
                    )
                    self.sell_order_list.append(symbol)

    def min_candle_chart(self):
        deposit = self.deposit
        risk = self.risk
        # "https://api.upbit.com/v1/candles/days
        url = "https://api.upbit.com/v1/candles/minutes/60" # n분차트 1, 3, 5, 10, 15, 30, 60, 240
        querystring = {"market":self.symbol,"count":"200"} # count = 필요한 봉 갯수
        response = requests.request("GET", url, params=querystring)
        data = response.json()

        low_list = []
        high_list = []
        open_list = []
        close_list = []
        for i in data:
            low = float(i['low_price'])
            high = float(i['high_price'])
            close = float(i['trade_price'])
            open = float(i['opening_price'])

            open_list.append(open)
            low_list.append(low)
            high_list.append(high)
            close_list.append(close)

        close = close_list[0]

        # EMA 5
        ema10 = Ema.ema(close_list, 10)
        ema20 = Ema.ema(close_list, 20)
        ema50 = Ema.ema(close_list, 50)

        ema10_1 = Ema.ema(close_list, 10, 1)
        #####################################

        if (ema10 and ema20 and ema50) != None:
        
            if (ema10 > ema20 and ema20 > ema50 and close > ema50):
                print("정배열")

                if high_list[2] < close and high_list[1] < close:
                    print("눌림목 구간")

                    if low_list[1] <= ema10_1 or low_list[0] <= ema10:
                        print("10 이평선 하향 돌파")

                        if self.ORDER_LOCK == False:
                            # 매수
                            if self.symbol not in self.balance_dict.keys():

                                if self.symbol not in self.not_balance_dict.keys():

                                    if self.symbol not in self.buy_order_list:

                                        print("매수")
                                        self.일차손절가격 = min(open_list[0],open_list[1],open_list[2])
                                        self.전량손절가격 = min(low_list[0],low_list[1],low_list[2])
                                        bid_price = self.get_hoka(self.symbol)
                                        amount = float(format(deposit/bid_price, '.8f'))
                                        self.order("BUY", self.symbol, amount, bid_price, "")

            # 매도
            if self.symbol in self.balance_dict.keys():

                보유수량 = self.balance_dict[self.symbol]['balance']
                locked = self.balance_dict[self.symbol]['locked']
                매수평균가 = self.balance_dict[self.symbol]['avg_buy_price']
                손실가 = math.trunc((close - 매수평균가) * 보유수량)

                # 최우선1순위 손절 주문 (손실 허용 범위 조건 매도)
                if self.symbol not in self.sell_order_list:
                    if (손실가 <= risk) or (close <= ema50) or (close <=self.전량손절가격):
                        print("전량 손절 매도",(손실가 <= risk) , (close <= ema50) , (close <=self.전량손절가격))
                        self.sell_cnt = False
                        self.order("SELL", self.symbol, 보유수량, 0, "")

                    elif close <= self.일차손절가격:
                        print("전량 손절 매도")
                        self.order("SELL", self.symbol, 보유수량, 0, "")
                    else:
                        # 최우선2순위 10 20 데드크로스
                        if self.symbol not in self.sell_order_list:
                            if ema10 < ema20:
                                print("전량 익절 매도",close ,ema10, ema20, self.balance_dict)
                                self.sell_cnt = False
                                self.order("SELL", self.symbol, 보유수량, 0, "")

                        # 10 이평선 하향시 1차 익절 주문
                        if self.symbol not in self.sell_order_list:
                            if self.sell_cnt == False:
                                if close < ema10:
                                    print("절반 익절 매도",amnt,self.balance_dict)
                                    amnt = float(보유수량/2)
                                    self.sell_cnt = True
                                    self.order("SELL", self.symbol, amnt, 0, "")


        # print(f"\n{deposit} {risk} {close} {ema10} {ema20}\n{self.balance_dict}\n{self.not_balance_dict}")

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

                        if ask_bid == 'bid' and symbol in self.buy_order_list:
                            self.buy_order_list.remove(symbol)

                        if ask_bid == 'ask' and symbol in self.sell_order_list:
                            self.sell_order_list.remove(symbol)

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
