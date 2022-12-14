from stats import Stats
from multiprocessing.dummy import Pool
import websocket
import threading
import requests
import threading
import signal
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

    RESPOND_MSG = 4
    RESPOND_DEFERED = 6
    RESPOND_EDIT = 7

    #Dispatch types
    TYPE_READY = 'READY'
    TYPE_INTERACTION = 'INTERACTION_CREATE'

    #Websocket close event codes in which a resume is not possible.
    #The bot must reconnect with the original gateway url and re-identify itself.
    UNRECOVERABLE_EXIT = [1000, 1001, 4004, 4010, 4011, 4012, 4013, 4014]


    def __init__(self, app_id: str, token: str, shard_id: int, shard_total: int, log):
        self.app_id = app_id
        self.token = token
        self.session = requests.Session()
        self.session.stream = False
        self.session.headers.update({'Authorization': 'Bot {}'.format(token)})
        self.shard = [shard_id, shard_total] #The shard id is a single instance 0 to n-1, shard total is a number n of total instances running
        self.command_registry = {}   #A map of discord command names to there respective function callback
        self.tpool = Pool(8)         #Thread pool for asynchorously running requests

        '''Data for websocket maintenence'''
        self.ws = None               #Websocket for which data is exchanged.
        self.ack = 1                 #Determines if an ack was recieved. If 0 when sending heartbeat, connection is bad. 
        self.sequence = 0            #The last sequence 's' sent by Discord.
        self.dispatch_sequence = 0   #The last sequence 's' sent by Discord with an opcode of DISPATCH. Used for resuming a connection.
        self.heartbeat_flag = 0      # 1: force heartbeat
        self.heartbeat_thread = None #Thread on which heartbeating runs.

        '''Data related to websocket connection'''
        self.gateway_url = None      #Url used to open the initial gateway. May be needed to reconnect if a resume is not possible.
        self.resume_gateway_url = '' #Url used to resume a disconnected gateway.
        self.resume_session_id = ''  #Session id used to resume a disconnected gateway.
        self.resume_flag = 0         #Indicates wether a resume (1) or identify (0) should be sent on connection open.
        
        '''General Setup'''
        self.log = log
        signal.signal(signal.SIGINT, self.terminate)
    
    '''
    Opens a websocket with the discord server so that the bot can begin exchanging data.
    Takes a resume flag as a paramater
    0 - Fresh start
    1 - Resumable start
    Returns the resume flag on exit. 1 - resumable restart, 0 - irrecoverable restart, -1 - Terminated
    NOTE: This command blocks indefinitley and should therefore only be called after bot
          initialization is complete.
    '''
    def start(self, resume=0):
        self.log.info('Starting pixgs instance')
        wss_url = ''

        if resume:
            wss_url = self.resume_gateway_url
        elif not resume and self.gateway_url:
            wss_url = self.gateway_url
        else:
            res = self.session.get(
                url=Discbot.API_URL + '/gateway/bot',
                params = {'v': 10, 'encoding': 'json'}
            )
            if(Discbot.raise_for_status(res)):
                data = res.json()
                wss_url = data['url']
                self.gateway_url = wss_url
            else:
                return -1            

        self.ws = websocket.WebSocketApp(
                wss_url,
                on_open=self._on_open,
                on_close=self._on_close,
                on_message=self._on_msg,
                on_error=self._on_err,
            )
        self.ws.run_forever(skip_utf8_validation=True)
        return self.resume_flag

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
            res = self.session.post(url, json=command)
            Discbot.raise_for_status(res)
        self.command_registry[command['name']] = callback

    '''
    Runs once after calling ws.run_forever(). Connection has been established
    and the bot must identify itself with Discord.
    '''
    def _on_open(self, ws):
        self.log.info('Connection was opened.')
        payload = None

        if self.resume_flag == 1:
            self.resume_flag = 0
            payload = {
                'op': Discbot.OP_RESUME,
                'd': {
                    'token': self.token,
                    'session_id': self.resume_session_id,
                    'seq': self.dispatch_sequence
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
                        'status': 'online',
                        'afk': False,
                    },
                    'shard': self.shard,
                    'intents': 0
                }
            }
        ws.send(json.dumps(payload))

    def _on_close(self, ws, close_status_code, close_msg):
        self.log.warning('Connection to Discord was closed with status code: {}, and message: {}'.format(
            close_status_code,
            close_msg
        ))
        self.clean_up(restart=True, resumable=(close_status_code not in Discbot.UNRECOVERABLE_EXIT))

    def _on_err(self, ws, error):
        self.log.error('The following error was encountered with the websocket: {}'.format(str(error)))

    def _on_msg(self, ws, msg):
        res = json.loads(msg)
        self.sequence = res['s']
        match res['op']:
            case Discbot.OP_DISPATCH:
                self.dispatch_sequence = res['s']
                if res['t'] == Discbot.TYPE_READY:
                    self.log.info('Handshake successful! Connection with Discord was established.')
                    self.resume_gateway_url = res['d']['resume_gateway_url']
                    self.resume_session_id = res['d']['session_id']
                elif res['t'] == Discbot.TYPE_INTERACTION:
                    self.log.info('Got Interaction Command: {}'.format(res))
                    callback = None
                    if 'name' in res['d']['data']:
                        callback = res['d']['data']['name']
                    elif 'custom_id' in res['d']['data']:
                        callback = res['d']['data']['custom_id']
                    if callback in self.command_registry:
                        self.command_registry[callback](res['d'])
            case Discbot.OP_HEARTBEAT:
                self.log.info('Immediate heartbeat required')
                self.heartbeat_flag = 1
            case Discbot.OP_RECONNECT:
                self.log.info('Reconnect requested.')
                self.clean_up(restart=True, resumable=True)
                ws.close()
            case Discbot.OP_HELLO:
                interval = res['d']['heartbeat_interval']
                self.log.info('Starting heartbeat with interval: %dms', interval)
                self._heartbeat(ws, interval)
            case Discbot.OP_ACK:
                self.ack = 1
                self.log.info("Recieved Ack")
            case Discbot.OP_INVALID:
                self.log.info('Invalid state. Closing the websocket')
                self.clean_up(restart=True, resumable=res['d'])
                ws.close()

    '''
    Sends a periodic 'heartbeat' with the last recieved sequence number to keep the websocket alive.
    '''
    def _heartbeat(self, ws: websocket.WebSocketApp, interval: int):
        def run():
            start_time = time.time()
            while 1:
                delta = (time.time() - start_time) * 1000
                if not ws.sock: #Case if thread should terminate
                    return 
                elif self.heartbeat_flag == 1 or ( delta > interval and self.ack ): #Case if heartbeat should be sent
                    self.log.info('Sending Heartbeat')
                    start_time = time.time()
                    self.heartbeat_flag = 0
                    self.ack = 0

                    ws.send(json.dumps({
                        'op': Discbot.OP_HEARTBEAT,
                        'd': self.sequence
                    }))
                    Stats.out(self.log)
                elif delta > interval: #Case if heartbeat should be sent but an ack was never gotten
                    self.clean_up(restart=True, resumable=False)
                    ws.close()
                    return
                time.sleep(.5) #Time precision is not super important so we can deschedule the thread

        threading.Thread(target=run, daemon=True).start()

    '''
    Stops Heartbeat thread and restarts the websocket if requested.
    '''
    def clean_up(self, restart=False, resumable=False):
        if restart:
            if resumable:
                self.log.info('Websocket resume flag set.')
                self.resume_flag = 1
            else:
                self.log.info('Websocket restart flag set.')
        else:
            self.resume_flag = -1
            self.tpool.close()
            self.ws.close()

    '''
    Replies to a TYPE_INTERACT event. This function is required to be called
    during a TYPE_INTERACT event otherwise the user will see an error message.
    interaction_id - The interaction if of the command being responded to.
    interaction_token - The token of the interaction being responded to.
    msg - A string message.
    components (optional) - An array of Discord component objects.
    edit - If true a message is edited instead of creating a new one. Default: False.
    hidden - If true a message is only visible to the user who started the interaction. Default: False.
    '''
    def reply_interaction(self, interaction_id: str, interaction_token: str, msg: str, components=None, edit=False, hidden=False):
        url = '{}/v10/interactions/{}/{}/callback'.format(Discbot.API_URL, interaction_id, interaction_token)
        data = {
            'type': Discbot.RESPOND_EDIT if edit else Discbot.RESPOND_MSG,
            'data': {
                'content': msg,
                'components': components,
                'flags': 1 << 6 if hidden else 0
            }
        }
        self.tpool.apply_async(self.session.post, args=[url], kwds={'json': data, 'timeout': 2}, callback=Discbot.raise_for_status)

    '''
    Edits a previously sent message. If editing when responding to a TYPE_INTERACTION
    event, reply_interaction should be used instead.
    '''
    def edit_message(self, channel_id: str, message_id: str, msg: str, components=None):
        uri = '{}/channels/{}/messages/{}'.format(Discbot.API_URL, channel_id, message_id)
        reply = {
            'content': msg
        }
        self.tpool.apply_async(self.session.patch, args=[uri], kwds={'json': reply, 'timeout': 2}, callback=Discbot.raise_for_status)

    '''
    Returns a message's content given the channel id and message id
    '''
    def get_message(self, channel_id: str, message_id: str):
        uri = '{}/channels/{}/messages/{}'.format(Discbot.API_URL, channel_id, message_id)
        res = self.session.get(uri)
        Discbot.raise_for_status(res)
        return res.json()

    '''
    Calls raise_for_status with logging on error
    '''
    def raise_for_status(res: requests.Response):
        try:
            res.raise_for_status()
            return 1
        except Exception as e:
            self.log.error(e)
            raise Exception("Bad request")
        
    def terminate(self, signal, frame):
        self.clean_up(restart=False)
