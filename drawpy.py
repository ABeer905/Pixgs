from discord_service.discbot import Discbot
from dotenv import load_dotenv
import sys
import os

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TOKEN = os.getenv("TOKEN")
bot = Discbot(CLIENT_ID, TOKEN)

MESSAGE_COMMAND = 1
OP_STRING = 3
OP_INTEGER = 4
OP_BOOL = 5

class Canvas:
    CURSOR = '🖍️'
    CURSOR_UNICODE = '\u3164'

    ENUM_COLORS = {
        'WHITE': '⬜',
        'BLACK': '⬛',
        'BLUE': '🟦',
        'ORANGE': '🟧',
        'PURPLE': '🟪',
        'GREEN': '🟩',
        'YELLOW': '🟨',
        'RED': '🟥',
        'BROWN': '🟫'
    }

    def canvas(w: int, h: int, fill=None):
        fill_color = Canvas.ENUM_COLORS[fill if fill else 'WHITE']
        return Canvas.CURSOR_UNICODE + (fill_color * w + '\n') * h

    '''
    Converts the Color ENUM to a Discord choice array
    '''
    def colors_to_list():
        color_list = []
        for color in Canvas.ENUM_COLORS.keys():
            color_list.append({
                'name': color,
                'value': color
            })
        return color_list

#Discord application command structure for command 'canvas'
canvas_command = {
    'name': 'canvas',
    'type': MESSAGE_COMMAND,
    'description': 'Create a new empty drawing board',
    'options': [
        {
            'type': OP_INTEGER,
            'name': 'width',
            'description': 'The width of the canvas',
            'required': True,
            'min_value': 1,
            'max_value': 20
        },
        {
            'type': OP_INTEGER,
            'name': 'height',
            'description': 'The height of the canvas',
            'required': True,
            'min_value': 1,
            'max_value': 20
        },
        {
            'type': OP_STRING,
            'name': 'fill',
            'description': 'The initial color of the canvas (default: white)',
            'required': False,
            'choices': Canvas.colors_to_list()
        }
    ]
}

'''
Callback function for the command '/canvas'. Creates a blank canvas of w x h in the Discord chat box.
'''
def canvas(command_response):
    w = command_response['data']['options'][0]['value']
    h = command_response['data']['options'][1]['value']
    fill = command_response['data']['options'][2]['value'] if len(command_response['data']['options']) == 3 else None
    canvas = Canvas.canvas(w, h, fill)
    bot.reply_interaction(command_response['id'], command_response['token'], canvas)

bot.register_command(canvas_command, canvas, '--reg' in sys.argv)

bot.start()
