from discord_service.discbot import Discbot
from cache_service.image_cache import ImgCache
from stats import Stats
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import copy
import time
import sys
import os

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TOKEN = os.getenv("TOKEN")
SHARD_ID = os.getenv("SHARD_ID")
SHARD_TOTAL = os.getenv("SHARD_TOTAL")

handle = RotatingFileHandler('pixgs-s%s.log' % SHARD_ID, mode='a', maxBytes=1024*1024*1024, encoding='utf-8')
handle.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(lineno)d %(message)s'))
handle.setLevel(logging.INFO)

log = logging.getLogger('logger')
log.setLevel(logging.INFO)
log.addHandler(handle)

bot = Discbot(CLIENT_ID, TOKEN, int(SHARD_ID), int(SHARD_TOTAL), log)
imgcache = ImgCache(65536)

MESSAGE_COMMAND = 1
OP_STRING = 3
OP_INTEGER = 4
OP_BOOL = 5

CONTAINER = 1
BUTTON = 2
DROPDOWN = 3

STYLE_PRIMARY = 1
STYLE_SECONDARY = 2
STYLE_SUCCESS = 3

class Canvas:

    ENUM_COLORS = {
        'WHITE': 'โฌ',
        'BLACK': 'โฌ',
        'BLUE': '๐ฆ',
        'ORANGE': '๐ง',
        'PURPLE': '๐ช',
        'GREEN': '๐ฉ',
        'YELLOW': '๐จ',
        'RED': '๐ฅ',
        'BROWN': '๐ซ'
    }

    '''Marks the current cursor position for a given color'''
    ENUM_CURSOR = {
        'WHITE': '๐ค',
        'BLACK': '๐ค',
        'BLUE': '๐',
        'ORANGE': '๐งก',
        'PURPLE': '๐',
        'GREEN': '๐',
        'YELLOW': '๐',
        'RED': 'โค',
        'BROWN': '๐ค'
    }

    '''
    A Discord component object used to initiate editing of a canvas
    '''
    EDIT_COMPONENT = [
        {
            'type': CONTAINER,
            'components': [
                {
                    'type': BUTTON,
                    'style': STYLE_PRIMARY,
                    'emoji': {
                        'id': None,
                        'name': '๐๏ธ'
                    },
                    'label': 'Edit Canvas',
                    'custom_id': 'edit'
                }
            ]
        }
    ]

    '''
    A Discord component object used to describe the drawing controls
    '''
    CONTROLLER_COMPONENT = [
        {
            'type': CONTAINER,
            'components': [
                {
                    'type': BUTTON,
                    'style': STYLE_SECONDARY,
                    'emoji': { 
                        'id': None,
                        'name': 'โฌ๏ธ'
                    },
                    'custom_id': 'left'
                },
                {
                    'type': BUTTON,
                    'style': STYLE_SECONDARY,
                    'emoji': {
                        'id': None,
                        'name': 'โก๏ธ'
                    },
                    'custom_id': 'right'
                },
                {
                    'type': BUTTON,
                    'style': STYLE_SECONDARY,
                    'emoji': {
                        'id': None,
                        'name': 'โฌ๏ธ'
                    },
                    'custom_id': 'up'
                },
                {
                    'type': BUTTON,
                    'style': STYLE_SECONDARY,
                    'emoji': {
                        'id': None,
                        'name': 'โฌ๏ธ'
                    },
                    'custom_id': 'down'
                },
                {
                    'type': BUTTON,
                    'style': STYLE_SUCCESS,
                    'emoji': {
                        'id': None,
                        'name': '๐๏ธ'
                    },
                    'label': 'Fill Color',
                    'custom_id': 'draw'
                }
            ]
        },
        {
            'type': CONTAINER,
            'components': [
                {
                    'type': DROPDOWN,
                    'custom_id': 'color_select',
                    'options': None,
                }
            ]
        },
        {
            'type': CONTAINER,
            'components': [
                {
                    'type': BUTTON,
                    'style': STYLE_PRIMARY,
                    'custom_id': 'cursor',
                    'emoji': {
                        'id': None,
                        'name': 'โค'
                    },
                    'label': 'Toggle Cursor'
                },
                #The following components are disabled buttons.
                #Instead of a real id, button 0 stores a channel id for the original canvas
                #Instead of a real id, button 1 stores a message id for the original canvas 
                #This is useful for calling back to edit the original canvas without having to locally store any data
                #These components will be returned with each edit, and while hacky appears to work
                {
                    'type': BUTTON,
                    'style': STYLE_PRIMARY,
                    'custom_id': '',
                    'label': ' ',
                    'disabled': True
                },
                {
                    'type': BUTTON,
                    'style': STYLE_PRIMARY,
                    'custom_id': '',
                    'label': ' ',
                    'disabled': True
                }
            ]
        }
    ]

    '''
    Creates a w x h canvas string with the fill color if specified, otherwise white
    '''
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
        lock = -1
        linebreak = None
        for i in range(len(content)):
            if content[i] == '\0':
                break
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
    Attempts to gets an image from the cache with the id (guild_id, message_id).
    If the image is not cached a request is made to discord for the image,
    and then the image is stored in cache. 
    Optional paramater no_cache:
        if True, returns 0 on a cache miss
        if False, the standard behavior as described above occurs 
    '''
    def get_image(guild_id, message_id, no_cache=False):
        image = imgcache.get((guild_id, message_id))
        if image:
            return image
        elif no_cache:
            return 0
        else:
            image = bot.get_message(guild_id, message_id)['content']
            imgcache.put((guild_id, message_id), image)
            return image

    '''
    Returns the key 'Color' of the cursor or pixel object for use with ENUM_COLORS/ENUM_CURSOR
    '''
    def color_from_char(c):
        for color in Canvas.ENUM_COLORS:
            if c == Canvas.ENUM_COLORS[color] or c == Canvas.ENUM_CURSOR[color]:
                return color

    '''
    Converts the Color ENUM to a Discord object of type
    type: 0 - A Discord choice array
          1 - A Discord dropdown array
    '''
    def colors_to_list(obj_type):
        color_list = []
        for color in Canvas.ENUM_COLORS.keys():
            if obj_type:
                color_list.append({
                    'label': 'Color: ' + color.title(),
                    'value': color,
                    'default': color == 'BLACK',
                    'emoji': {
                        'id': None,
                        'name': Canvas.ENUM_COLORS[color]
                    }
                }) 
            else:
                color_list.append({
                    'name': color.title(),
                    'value': color
                })
        return color_list

    '''
    Returns a deep copy of the controller component where the dropdown has the
    select menu set to the desired color.
    color - A key from ENUM_COLORS
    '''
    def set_controller_color(controller: dict, color: str):
        for op in controller[1]['components'][0]['options']:
            if op['value'] == color:
                op['default'] = True
            else:
                op['default'] = False
        return controller

    '''
    Returns a deep copy of the controller component where the dropdown is copied
    from the current command response.
    command_response - The interaction object taken as a paramater to a webhook callback
    '''
    def copy_controller(command_response: dict):
        controller = copy.deepcopy(Canvas.CONTROLLER_COMPONENT)
        dropdown = command_response['message']['components'][1]
        data = command_response['message']['components'][2]
        controller[1] = dropdown
        controller[2] = data
        return controller

    '''
    Extracts data stored in discord components.
    Returns channel_id, message_id
    '''
    def unpack_data(command_response: dict):
        tk_args = command_response['message']['components'][2]['components']
        channel_id = tk_args[1]['custom_id']
        message_id = tk_args[2]['custom_id']
        return channel_id, message_id

#Set color select dropdown options
Canvas.CONTROLLER_COMPONENT[1]['components'][0]['options'] = Canvas.colors_to_list(1)

#Discord application command structure for command '/canvas'
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
            'choices': Canvas.colors_to_list(0)
        },
        {
            'type': OP_BOOL,
            'name': 'private',
            'description': 'Only you can see and edit the image (default: false)',
            'required': False
        }
    ]
}

#Discord application command structure for command '/help'
help_command = {
    'name': 'help',
    'type': MESSAGE_COMMAND,
    'description': 'View command refrence guide.'
}

'''
Callback function for the command '/canvas'. Creates a blank canvas of w x h in the Discord chat box.
'''
def canvas(command_response):
    w = command_response['data']['options'][0]['value']
    h = command_response['data']['options'][1]['value']
    optional_args = {'fill': None, 'private': False}

    if len(command_response['data']['options']) >= 3:
        optional_args[command_response['data']['options'][2]['name']] = command_response['data']['options'][2]['value']
    if len(command_response['data']['options']) == 4:
        optional_args[command_response['data']['options'][3]['name']] = command_response['data']['options'][3]['value']

    image = Canvas.canvas(w, h, optional_args['fill'])
    controller = copy.deepcopy(Canvas.CONTROLLER_COMPONENT)
    controller[2]['components'][1]['custom_id'] = 'none'
    controller[2]['components'][2]['custom_id'] = 'none-1'
    bot.reply_interaction(
        command_response['id'],
        command_response['token'],
        image,
        components=controller if optional_args['private'] else Canvas.EDIT_COMPONENT,
        hidden=optional_args['private']
    )
    Stats.canvases += 1

'''
Callback function to enter 'edit mode', where a user can begin editing a canvas
'''
def edit_mode(command_response):
    image = command_response['message']['content']
    controller = copy.deepcopy(Canvas.CONTROLLER_COMPONENT)
    #Split the token into chunks and store it into disabled button
    controller[2]['components'][1]['custom_id'] = command_response['message']['channel_id']
    controller[2]['components'][2]['custom_id'] = command_response['message']['id']

    bot.reply_interaction(
      command_response['id'],
      command_response['token'],
      image,
      components=controller,
      hidden=True
    )
    Stats.edit += 1

'''
Callback function for moving the drawing cursor
'''
def move(command_response):
    direction = command_response['data']['custom_id']
    channel_id, message_id = Canvas.unpack_data(command_response)
    private = channel_id == None
    image = command_response['message']['content']
    #Attempt to load updated copy of public image if it exists in cache, otherwise we just use our edit copy
    image_public = None
    if not private:
        image_public = Canvas.get_image(channel_id, message_id, no_cache=True)

    cur, w, h = Canvas.load_canvas(image)
    new_cur = 0
    
    if cur == -1:
        cur = 0
    if image_public: #Refresh edit copy of image in case of cache hit
        image = image_public[:cur] + Canvas.ENUM_CURSOR[Canvas.color_from_char(image_public[cur])] + image_public[cur+1:]

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
        new_cur = cur % (w+1)
    
    image = image[:cur] + Canvas.ENUM_COLORS[Canvas.color_from_char(image[cur])] + image[cur+1:]
    image = image[:new_cur] + Canvas.ENUM_CURSOR[Canvas.color_from_char(image[new_cur])] + image[new_cur+1:]
    controller = Canvas.copy_controller(command_response)
    bot.reply_interaction(command_response['id'], command_response['token'], image, components=controller, edit=True)
    Stats.move += 1

'''
Callback function where the user selects the drawing color
'''
def choose_color(command_response):
    image = command_response['message']['content']
    color = command_response['data']['values'][0]
    controller = Canvas.copy_controller(command_response)
    controller = Canvas.set_controller_color(controller, color)

    bot.reply_interaction(command_response['id'], command_response['token'], image, components=controller, edit=True)
    Stats.color += 1

'''
Callback function for setting a pixel to the selected color
'''
def draw(command_response):
    channel_id, message_id = Canvas.unpack_data(command_response)
    private = channel_id == 'none'

    image_edit = command_response['message']['content']
    image_public = command_response['message']['content'] if private else Canvas.get_image(channel_id, message_id)
    controller = Canvas.copy_controller(command_response)

    cur, w, h = Canvas.load_canvas(image_edit)
    if cur == -1:
        cur = 0

    fill_color = 'WHITE'
    for op in command_response['message']['components'][1]['components'][0]['options']:
        if 'default' in op and op['default']:
            fill_color = op['value']
            break
    
    image_edit = image_public[:cur] + Canvas.ENUM_CURSOR[fill_color] + image_public[cur+1:]
    image_public = image_public[:cur] + Canvas.ENUM_COLORS[fill_color] + image_public[cur+1:]

    bot.reply_interaction(command_response['id'], command_response['token'], image_edit, components=controller, edit=True)
    if not private:
        imgcache.put((channel_id, message_id), image_public)
        bot.edit_message(channel_id, message_id, image_public)
    Stats.draw += 1

'''
Toggles the cursor to make it visible/invisible
'''
def toggle_cursor(command_response):
    image = command_response['message']['content']
    cur, w, h = Canvas.load_canvas(image)
    controller = Canvas.copy_controller(command_response)
    
    show_c = 0
    if cur == -1:
        cur = 0
        show_c = 1
    
    color = Canvas.color_from_char(image[cur])
    image = image[:cur] + (Canvas.ENUM_CURSOR[color] if show_c else Canvas.ENUM_COLORS[color]) + image[cur+1:]
    bot.reply_interaction(command_response['id'], command_response['token'], image, components=controller, edit=True)
    Stats.cur += 1

'''
Callback method for /help. Returns the url for command refrence
'''
def help(command_response):
    bot.reply_interaction(
        command_response['id'],
        command_response['token'],
        'For information on using Pixgs visit: https://pix-gs.github.io/commands.html',
        hidden=True
    )
    Stats.help += 1

bot.register_command(canvas_command, canvas, '--reg' in sys.argv)
bot.register_command(help_command, help, '--reg' in sys.argv)
bot.register_command({'name': 'edit'}, edit_mode, False)
bot.register_command({'name': 'up'}, move, False)
bot.register_command({'name': 'down'}, move, False)
bot.register_command({'name': 'left'}, move, False)
bot.register_command({'name': 'right'}, move, False)
bot.register_command({'name': 'color_select'}, choose_color, False)
bot.register_command({'name': 'draw'}, draw, False)
bot.register_command({'name': 'cursor'}, toggle_cursor, False)

exitcode = 0
while exitcode >= 0:
    exitcode = bot.start(resume=exitcode)
    print(exitcode)
log.info("Bot terminated")
