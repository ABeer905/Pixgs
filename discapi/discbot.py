import websocket
import threading
import requests
import threading
import logging
import json
import sys

class Discbot:

    API_URL = 'https://discord.com/api'

    #Websocket Opcodes
    OP_HEARTBEAT = 1
    OP_IDENTIFY = 2
    OP_RESUME = 6
    OP_RECONNECT = 7
    OP_INVALID = 9
    OP_HELLO = 10
    OP_ACK = 11


    def __init__(self, token):
        self.token = token
        self.auth = {'Authorization': 'Bot {}'.format(token)}
        logging.basicConfig(filename='drawpy.log', encoding='utf-8', level=logging.DEBUG)

    '''
    Opens a websocket with the discord server so that the bot can begin exchanging data.
    NOTE: This command blocks indefinitley and should therefore only be called after bot
          initialization is complete. Commands will arrive on seperate threads.
    '''
    def start(self):
        logging.info('Starting Drawpy instance')

        res = requests.get(
            url=Discbot.API_URL + '/gateway/bot',
            headers=self.auth,
            params = {'v': 10, 'encoding': 'json'}
        )

        if(Discbot.raise_for_status(res)):
            data = res.json()
            ws = websocket.WebSocketApp(
                    data['url'],
                    on_open=self._on_open,
                    on_close=self._on_close,
                    on_message=self._on_msg,
                    on_error=self._on_err
                )
            ws.run_forever()

    '''
    Runs once after calling ws.run_forever(). Connection has been established
    and the bot must identify itself with Discord.
    '''
    def _on_open(self, ws):
        logging.info('Connection was opened.')
        identity = {
            'op': Discbot.OP_IDENTIFY,
            'd': {
                'token': self.token,
                'properties': {
                    'os': None,
                    'browser': None,
                    'device': None
                },
                'presence': {
                    'status': None,
                    'status': 'online',
                    'afk': False,
                },
                'intents': 0
            }
        }
        ws.send(json.dumps(identity))

    def _on_close(self, ws, close_status_code, close_msg):
        pass

    def _on_err(self, ws, error):
        pass

    def _on_msg(self, ws, msg):
        pass
    
    '''
    Calls raise_for_status with logging on error
    '''
    def raise_for_status(res):
        try:
            res.raise_for_status()
            return 1
        except Exception as e:
            logging.error(e)
