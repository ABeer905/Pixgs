import websocket
import threading
import requests
import threading
import logging
import json
import time
import sys

class Discbot:

    API_URL = 'https://discord.com/api'

    #Websocket Opcodes
    OP_DISPATCH = 0
    OP_HEARTBEAT = 1
    OP_IDENTIFY = 2
    OP_RESUME = 6
    OP_RECONNECT = 7
    OP_INVALID = 9
    OP_HELLO = 10
    OP_ACK = 11

    RESPOND_PING = 1
    RESPOND_MSG = 4
    RESPOND_EDIT = 7

    #Dispatch types
    TYPE_READY = 'READY'
    TYPE_INTERACTION = 'INTERACTION_CREATE'

    #Websocket close event codes in which a resume is not possible.
    #The bot must reconnect with the original gateway url and re-identify itself.
    UNRECOVERABLE_EXIT = [1000, 1001, 4004, 4010, 4011, 4012, 4013, 4014]


    def __init__(self, app_id: str, token: str):
        self.app_id = app_id
        self.token = token
        self.auth = {'Authorization': 'Bot {}'.format(token)}

        self.ws = None               #Websocket for which data is exchanged.
        self.ack = 1                 #Determines if an ack was recieved. If 0 when sending heartbeat, connection is bad. 
        self.sequence = 0            #The last sequence 's' sent by Discord.
        self.heartbeat_flag = 0      # 1: force heartbeat, regardless of current interval. 2: Terminates thread.
        self.heartbeat_thread = None #Thread on which heartbeating runs.
        self.command_registry = {}   #A map of discord command names to there respective function callback

        self.gateway_url = ''        #Url used to open the initial gateway. May be needed to reconnect if a resume is not possible.
        self.resume_gateway_url = '' #Url used to resume a disconnected gateway.
        self.resume_session_id = ''  #Session id used to resume a disconnected gateway.
        self.resume_flag = 0         #Indicates wether a resume or identify should be sent on connection open.
        
        logging.basicConfig(
            format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
            filename='drawpy.log',
            encoding='utf-8',
            filemode='w',
            level=logging.DEBUG)
    
    '''
    Opens a websocket with the discord server so that the bot can begin exchanging data.
    NOTE: This command blocks indefinitley and should therefore only be called after bot
          initialization is complete.
    '''
    def start(self, wss_url=None):
        logging.info('Starting Drawpy instance')

        if not wss_url:
            res = requests.get(
                url=Discbot.API_URL + '/gateway/bot',
                headers=self.auth,
                params = {'v': 10, 'encoding': 'json'}
            )
            if(Discbot.raise_for_status(res)):
                data = res.json()
                wss_url = data['url']
                self.gateway_url = wss_url
            else:
                return

        self.ws = websocket.WebSocketApp(
                wss_url,
                on_open=self._on_open,
                on_close=self._on_close,
                on_message=self._on_msg,
                on_error=self._on_err
            )
        self.ws.run_forever()

    '''
    Registers a Discord command. Used to callback to command functions when recieved by the websocket.
    @command - A dictionary that follows the Application Command Structure as specified by Discord docs
    @callback - A pointer to the function to run when the command is run.
    @post - Wether the command should be posted to Discord. This should be set to True to initialize the command
              or each time you make an edit to the command paramater. Discord will store a copy once you
              post it, therefore, it is not necesary to post more than once.
    '''
    def register_command(self, command: dict, callback, post: bool):
        if post:
            url = '{}/v10/applications/{}/commands'.format(Discbot.API_URL, self.app_id)
            res = requests.post(url, headers=self.auth, json=command)
            Discbot.raise_for_status(res)
        self.command_registry[command['name']] = callback

    '''
    Runs once after calling ws.run_forever(). Connection has been established
    and the bot must identify itself with Discord.
    '''
    def _on_open(self, ws):
        logging.info('Connection was opened.')
        paylaod = None

        if self.resume_flag:
            self.resume_flag = 0
            payload = {
                'op': Discbot.OP_RESUME,
                'd': {
                    'token': self.token,
                    'session_id': self.resume_session_id,
                    'seq': self.sequence
                }
            }
        else:
            payload = {
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
        ws.send(json.dumps(payload))

    def _on_close(self, ws, close_status_code, close_msg):
        logging.warning('Connection to Discord was closed with status code: {}, and message: {}'.format(
            close_status_code,
            close_msg
        ))
        self.resume_flag = close_status_code not in Discbot.UNRECOVERABLE_EXIT
        self.clean_up(restart=True, resumable=self.resume_flag)

    def _on_err(self, ws, error):
        logging.error('The following error was encountered with the websocket: {}'.format(str(error)))

    def _on_msg(self, ws, msg):
        res = json.loads(msg)
        self.sequence = res['s']
        match res['op']:
            case Discbot.OP_DISPATCH:
                if res['t'] == Discbot.TYPE_READY:
                    logging.info('Handshake successful! Connection with Discord was established.')
                    self.resume_gateway_url = res['d']['resume_gateway_url']
                    self.resume_session_id = res['d']['session_id']
                elif res['t'] == Discbot.TYPE_INTERACTION:
                    logging.info('Got Interaction Command: {}'.format(res))
                    callback = None
                    if 'name' in res['d']['data']:
                        callback = res['d']['data']['name']
                    elif 'custom_id' in res['d']['data']:
                        callback = res['d']['data']['custom_id']
                    if callback in self.command_registry:
                        self.command_registry[callback](res['d'])
            case Discbot.OP_HEARTBEAT:
                self.heartbeat_flag = 1
            case Discbot.OP_RECONNECT:
                ws.close(0)
            case Discbot.OP_HELLO:
                interval = res['d']['heartbeat_interval']
                logging.info('Starting heartbeat with interval: %dms', interval)
                self._heartbeat(ws, interval)
            case Discbot.OP_ACK:
                self.ack = 1
                logging.info("Recieved Ack")
            case Discbot.OP_INVALID:
                if res['d'] == True:
                    ws.close(0)
                else:
                    ws.close(1000)

    '''
    Sends a periodic 'heartbeat' with the last recieved sequence number to keep the websocket alive.
    '''
    def _heartbeat(self, ws: websocket.WebSocketApp, interval: int):
        def run():
            start_time = time.time()
            while 1:
                delta = (time.time() - start_time) * 1000
                if self.heartbeat_flag == 2: #Case if thread should terminate
                    self.heartbeat_flag = 0
                    return #Exit heartbeat
                elif self.heartbeat_flag == 1 or ( delta > interval and self.ack ): #Case if heartbeat should be sent
                    logging.info('Sending Heartbeat')
                    start_time = time.time()
                    self.force_heartbeat = 0
                    self.ack = 0

                    ws.send(json.dumps({
                        'op': Discbot.OP_HEARTBEAT,
                        'd': self.sequence
                    }))
                elif delta > interval: #Case if heartbeat should be sent but an ack was never gotten
                    self.ws.close(0)

        threading.Thread(target=run, daemon=True).start()

    '''
    Stops Heartbeat thread and restarts the websocket if requested.
    '''
    def clean_up(self, restart=False, resumable=False):
        self.heartbeat_flag = 2
        if restart:
            if resumbale:
                logging.info('Attempting to resume websocket connection.')
                self.start(wss_url=self.resume_gateway_url)
            else:
                logging.info('Attempting to restart websocket connection.')
                self.start(wss_url=self.gateway_url)

    '''
    Replies to a slash '/' command.
    interaction_id - The interaction if of the command being responded to.
    interaction_token - The token of the interaction being responded to.
    msg - A string message
    components - A list of Discord Component objects
    '''
    def reply_interaction(self, interaction_id: str, interaction_token: str, msg: str, components=None, edit=False):
        url = '{}/v10/interactions/{}/{}/callback'.format(Discbot.API_URL, interaction_id, interaction_token)
        data = {
            'type': Discbot.RESPOND_EDIT if edit else Discbot.RESPOND_MSG,
            'data': {
                'content': msg,
                'components': components
            }
        }
        res = requests.post(url, headers=self.auth, json=data)
        Discbot.raise_for_status(res)

    '''
    Calls raise_for_status with logging on error
    '''
    def raise_for_status(res: requests.Response):
        try:
            res.raise_for_status()
            return 1
        except Exception as e:
            logging.error(e)
