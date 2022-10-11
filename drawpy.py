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
    CURSOR = '⌄'

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

    '''Marks the current cursor position for a given color'''
    ENUM_CURSOR = {
        'WHITE': '🤍',
        'BLACK': '🖤',
        'BLUE': '💙',
        'ORANGE': '🧡',
        'PURPLE': '💜',
        'GREEN': '💚',
        'YELLOW': '💛',
        'RED': '❤️',
        'BROWN': '🤎'
    }

    DIRECTION_COMPONENT = [
        {
            'type': 1,
            'components': [
                {
                    'type': 2,
                    'style': 1,
                    'emoji': { 
                        'id': None,
                        'name': '⬅️'
                    },
                    'custom_id': 'left'
                },
                {
                    'type': 2,
                    'style': 1,
                    'emoji': {
                        'id': None,
                        'name': '➡️'
                    },
                    'custom_id': 'right'
                },
                {
                    'type': 2,
                    'style': 1,
                    'emoji': {
                        'id': None,
                        'name': '⬆️'
                    },
                    'custom_id': 'up'
                },
                {
                    'type': 2,
                    'style': 1,
                    'emoji': {
                        'id': None,
                        'name': '⬇️'
                    },
                    'custom_id': 'down'
                }
            ]
        }
    ]

    def canvas(w: int, h: int, fill=None):
        fill_color = Canvas.ENUM_COLORS[fill if fill else 'WHITE']
        return (fill_color * w + '\n') * h

    '''
    Parses a canvas to determine the cursor position, width, and height
    '''
    def load_canvas(content):
        w = 0
        h = 1
        cur = -1
        linebreak = None
        for i in range(len(content)):
            if content[i] == '\n':
                h += 1
                linebreak = True
            elif not linebreak:
                w+=1
            for color in Canvas.ENUM_CURSOR:
                if content[i] == Canvas.ENUM_CURSOR[color]:
                    cur = i
        return cur, w, h

    '''
    Returns the key 'Color' of the cursor or pixel object for use with ENUM_COLORS/ENUM_CURSOR
    '''
    def color_from_char(c):
        for color in Canvas.ENUM_COLORS:
            if c == Canvas.ENUM_COLORS[color] or c == Canvas.ENUM_CURSOR[color]:
                return color

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
            'max_value': 14
        },
        {
            'type': OP_INTEGER,
            'name': 'height',
            'description': 'The height of the canvas',
            'required': True,
            'min_value': 1,
            'max_value': 14
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
    image = Canvas.canvas(w, h, fill)
    bot.reply_interaction(command_response['id'], command_response['token'], image, components=Canvas.DIRECTION_COMPONENT)

'''
Callback function for moving the drawing cursor
'''
def move(command_response):
    direction = command_response['data']['custom_id']
    image = command_response['message']['content']
    cur, w, h = Canvas.load_canvas(image)
    print(cur, w, h)
    new_cur = 0
    
    if cur == -1:
        cur = 0
    row = int(cur / (w+1))

    if direction == 'left' and cur > 0 and image[cur - 1] != '\n':
        new_cur = cur - 1
    elif direction == 'left':
        new_cur = cur + w-1
    elif direction == 'right' and cur < len(image) - 1 and image[cur + 1] != '\n':
        new_cur = cur + 1
    elif direction == 'right':
        new_cur = cur - w+1
    elif direction == 'up' and cur > w:
        new_cur = cur - (w+1)
    elif direction == 'up':
        new_cur = (h-1)*(w+1) + cur
    elif direction == 'down' and row < h - 1:
        new_cur = cur + w+1
    elif direction == 'down':
        new_cur = cur%(w+1)
    print(new_cur, w, h)
    
    image = image[:cur] + Canvas.ENUM_COLORS[Canvas.color_from_char(image[cur])] + image[cur+1:]
    print(image + '\n')
    image = image[:new_cur] + Canvas.ENUM_CURSOR[Canvas.color_from_char(image[new_cur])] + image[new_cur+1:]
    print(image)
    bot.reply_interaction(command_response['id'], command_response['token'], image, components=Canvas.DIRECTION_COMPONENT, edit=True)
    

bot.register_command(canvas_command, canvas, '--reg' in sys.argv)
bot.register_command({'name': 'up'}, move, False)
bot.register_command({'name': 'down'}, move, False)
bot.register_command({'name': 'left'}, move, False)
bot.register_command({'name': 'right'}, move, False)

bot.start()
