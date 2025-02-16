import multiprocessing as mp
import jwt, json, uuid, asyncio, websockets


class WebSocketAll(mp.Process):
    def __init__(self, access: str, secret: str, codes:list, qsize: int = 1000):
        
        self.__q = mp.Queue(qsize)
        self.alive = False
        self.codes = codes
        self.headers = self.auth_token(access, secret)

        super().__init__()

    async def __connect_public_socket(self):
        url = "wss://api.upbit.com/websocket/v1"
        sc = self.codes
        async for websocket in websockets.connect(url):
            try:
                data = [
                    {"ticket":"public websocket"},
                    {"type": "ticker","codes":sc},
                    {"type": "trade","codes":sc},
                    {"type": "orderbook","codes":sc},
                    {"type":"candle.1s","codes":sc}
                    ]
                await websocket.send(json.dumps(data))
                while self.alive:
                    recv_data = await websocket.recv()
                    recv_data = recv_data.decode('utf8')
                    self.__q.put(json.loads(recv_data))
            except websockets.ClientConnection:
                continue

    async def __connect_private_socket(self):
        url = "wss://api.upbit.com/websocket/v1/private"
        async for websocket in websockets.connect(url, additional_headers=self.headers):
            try:
                data = [
                    {"ticket":"private websocket"},
                    {"type": "myOrder"},
                    {"type":"myAsset"}
                    ]
                await websocket.send(json.dumps(data))
                while self.alive:
                    recv_data = await websocket.recv()
                    recv_data = recv_data.decode('utf8')
                    self.__q.put(json.loads(recv_data))
            except websockets.ClientConnection:
                continue

    async def __connect_all_socket(self):
        results = await asyncio.gather(self.__connect_private_socket()) # self.__connect_public_socket(),

    def auth_token(self, access, secret):
        payload = {'access_key': access,'nonce': str(uuid.uuid4())}
        jwt_token = jwt.encode(payload, secret)
        authorization_token = 'Bearer {}'.format(jwt_token)
        result = {"Authorization": authorization_token}
        return result

    def run(self):
        # Method 1
        # self.__aloop = asyncio.get_event_loop()
        # self.__aloop.run_until_complete(self.__connect_all_socket())

        # Method 2
        asyncio.run(self.__connect_all_socket())

    def get(self):
        if self.alive is False:
            self.alive = True
            self.start()
        return self.__q.get()

    def terminate(self):
        self.alive = False
        super().terminate()
