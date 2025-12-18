from micropython import const
import sys
import time
import supervisor
from displayio import Group,TileGrid,Palette,Bitmap
from adafruit_display_text.text_box import TextBox
from adafruit_fruitjam.peripherals import request_display_config
import random
import gc
import terminalio
from adafruit_display_text.bitmap_label import Label

# Setup display
request_display_config(320,240)
display = supervisor.runtime.display
ctrl_pad = supervisor.runtime.usb_connected

gc.collect()

# Game constants
MAX_BUCKETS = 3
MAX_LIFE_INTERVAL = 1000
STATE_PLAYING = const(0)
STATE_READY = const(1)
STATE_PAUSED = const(2)
STATE_GAME_OVER = const(3)
STATE_TITLE = const(4)
BTN_DPAD_UPDOWN_INDEX = const(4)
BTN_DPAD_RIGHTLEFT_INDEX = const(3)
BTN_ABXY_INDEX = const(5)
BTN_OTHER_INDEX = const(6)
DIR_IN = 0x80
 
# Game variables
nextExtraLife = MAX_LIFE_INTERVAL
row = 0
currentLevel = 8
bombs = []
params = []
drop_speed = None
directionChange = None
dropInterval = None
bombs_dropped = 0
bombScore = None
bombCount = None
bomberSpeed = None
baddy = None
successState = True
gameState = STATE_TITLE
bucket_count = 3
change_bucket = False
enemy_move_timer = 0
enemy_width = 16
enemy_step = 1
enemy_x = 10
enemy_direction = 1
enemy_change_timer = 0
bucket_x = display.width // 2 - 6
bucket_move = False
last_a_pressed = False
current_a_pressed = False
current_dpad_pressed = False
controller = None
push_left = False
push_right = False
push_a = False
bomber_start_x = 10
bomber_start_y = 4
bomb_start_x  = 7
bomb_start_y  = 17
drop_bomb_x = bomb_start_x
drop_bomb_y = bomb_start_y
bomb_drop_timer = 0
bomb_group_list = None
current_bomb = {}
splash = False
score = 0
scale = 2

# Setup Sprite Variables
sprites = []
bitmap = None
w = None
h = None
p = None
value_map = []
tile_grid = None
map_tg = None
tile_w = None
tile_h = None
grid_w = None
grid_h = None
x = None
y = None

# Levels parameter dictionary
LEVELS = {
    1: {
        'bomberSpeed': 3,
        'bombCount': 10,
        'bombScore': 1,
        'directionChangeLB': 150,
        'directionChangeUB': 250,
        'dropIntervalLB': 20,
        'dropIntervalUB': 30,
        'drop_speed': 2,
        'successState': 1,
        'enemy_step': 10
    },
    2: {
        'bomberSpeed': 3,
        'bombCount': 15,
        'bombScore': 2,
        'directionChangeLB': 140,
        'directionChangeUB': 220,
        'dropIntervalLB': 18,
        'dropIntervalUB': 28,
        'drop_speed': 3,
        'successState': 1,
        'enemy_step': 20
    },
    3: {
        'bomberSpeed': 2,
        'bombCount': 20,
        'bombScore': 3,
        'directionChangeLB': 130,
        'directionChangeUB': 200,
        'dropIntervalLB': 13,
        'dropIntervalUB': 18,
        'drop_speed': 4,
        'successState': 1,
        'enemy_step': 30
    },
    4: {
        'bomberSpeed': 2,
        'bombCount': 25,
        'bombScore': 4,
        'directionChangeLB': 120,
        'directionChangeUB': 180,
        'dropIntervalLB': 11,
        'dropIntervalUB': 16,
        'drop_speed': 5,
        'successState': 1,
        'enemy_step': 40
    },
    5: {
        'bomberSpeed': 2,
        'bombCount': 30,
        'bombScore': 5,
        'directionChangeLB': 110,
        'directionChangeUB': 160,
        'dropIntervalLB': 8,
        'dropIntervalUB': 12,
        'drop_speed': 7,
        'successState': 1,
        'enemy_step': 50
    },
    6: {
        'bomberSpeed': 1,
        'bombCount': 40,
        'bombScore': 6,
        'directionChangeLB': 100,
        'directionChangeUB': 140,
        'dropIntervalLB': 6,
        'dropIntervalUB': 10,
        'drop_speed': 9,
        'successState': 1,
        'enemy_step': 60
    },
    7: {
        'bomberSpeed': 1,
        'bombCount': 50,
        'bombScore': 7,
        'directionChangeLB': 80,
        'directionChangeUB': 120,
        'dropIntervalLB': 5,
        'dropIntervalUB': 9,
        'drop_speed': 11,
        'successState': 1,
        'enemy_step': 70
    },
    8: {
        'bomberSpeed': 1,
        'bombCount': 60,
        'bombScore': 8,
        'directionChangeLB': 50,
        'directionChangeUB': 100,
        'dropIntervalLB': 4,
        'dropIntervalUB': 7,
        'drop_speed': 14,
        'successState': 0,
        'enemy_step': 80
    }
}

# Sets game level parameters
def setLevelParams(currentLevel):
    global params, drop_speed, directionChange, dropInterval
    global bombsDropped, bombScore, bombCount, bomberSpeed
    params = LEVELS.get(currentLevel)
    drop_speed = params["drop_speed"]
    directionChange = random.randint(params["directionChangeLB"], params["directionChangeUB"])
    dropInterval = random.randint(params["dropIntervalLB"], params["dropIntervalUB"])
    bombsDropped = 0
    bombScore = params["bombScore"]
    bombCount = params["bombCount"]
    bomberSpeed = params["bomberSpeed"]
    enemy_step = params["enemy_step"]
    print("Level:", currentLevel, params)
    return params, drop_speed, directionChange, dropInterval, bombsDropped, bombScore, bombCount, bomberSpeed

setLevelParams(currentLevel)

gc.collect()

# Sprite functions

def setup_palette():
    # Setup color pallette
    pallette = Palette(16)
    pallette[0] = 0xFF00D0
    pallette[1] = 0xFFFFFF
    pallette[2] = 0x680303
    pallette[3] = 0x999999
    pallette[4] = 0x000000
    pallette[5] = 0xE38359
    pallette[6] = 0x14A5FF
    pallette[7] = 0x78DC52
    pallette[8] = 0x91463D
    pallette[9] = 0x14A5FF
    pallette[10] = 0xFFF700
    pallette[11] = 0x14A5FF
    pallette[12] = 0x14A5FF
    pallette[13] = 0xE5CDC4
    pallette[14] = 0x91463D
    pallette[15] = 0xFF7B00
    pallette.make_transparent(0)
    return pallette

pallette = setup_palette()

gc.collect()

def map_values_to_bitmap(bitmap, value_map, w, h):
    for y in range(h):
        for x in range(w):
            bitmap[x, y] = value_map[y * w + x]

def map_bitmap_to_tilegrid(tilegrid, item, w, h):
    for y in range(0, h):
        for x in range(0, w):
            tilegrid[x, y] = item

def create_sprite(bitmap, value_map, w, h, p, tile_grid, map_tg, tile_w, tile_h, grid_w, grid_h, x=0, y=0):
    bitmap = Bitmap(w, h, p)
    map_values_to_bitmap(bitmap, value_map, w, h)
    tile_grid = TileGrid(bitmap, pixel_shader=pallette,
                      width = grid_w, height = grid_h,
                      tile_width=tile_w, tile_height=tile_h,
                      x=x, y=y)
    if map_tg:
        map_bitmap_to_tilegrid(tile_grid, 0, grid_w-1, grid_h-1)

    return tile_grid

#Sprite definitions
SPRITES = {
    "top_wall": {
        "bitmap": 'top_wall',
        "w": 16,
        "h": 8, 
        "p": 16,
        "value_map": [3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,
                      4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,
                      4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4],
        "tile_grid": 'top_wall_sprite',
        "map_tg": True,
        "tile_w": 16,
        "tile_h": 8,
        "grid_w": 40,
        "grid_h": 1,
        "x": 0,
        "y": 25
        },
    "wall": {
        "bitmap": 'wall',
        "w": 14,
        "h": 6, 
        "p": 16,
        "value_map": [3,3,3,3,3,3,3,3,3,3,3,3,3,3,
                    2,2,2,3,2,2,2,2,2,2,3,2,2,2,
                    2,2,2,3,2,2,2,2,2,2,3,2,2,2,
                    3,3,3,3,3,3,3,3,3,3,3,3,3,3,
                    3,2,2,2,2,2,2,3,2,2,2,2,2,2,
                    3,2,2,2,2,2,2,3,2,2,2,2,2,2],
        "tile_grid": 'wall_sprite',
        "map_tg": True,
        "tile_w": 14,
        "tile_h": 6,
        "grid_w": 23,
        "grid_h": 40,
        "x": 0,
        "y": 32
        },
    "bomb":  {
        "bitmap": 'bomb',
        "w": 8,
        "h": 12, 
        "p": 16,
        "value_map": [
                        0,0,0,0,0,0,8,0,
                        0,0,0,0,0,14,0,0,
                        0,0,0,0,14,0,0,0,
                        0,0,0,14,0,0,0,0,
                        0,0,4,4,4,4,0,0,
                        0,4,4,4,4,4,4,0,
                        4,4,4,4,4,4,4,4,
                        14,14,14,14,14,14,14,14,
                        14,14,14,14,14,14,14,14,
                        4,4,4,4,4,4,4,4,
                        0,4,4,4,4,4,4,0,
                        0,0,4,4,4,4,0,0],
        "tile_grid": "bomb_sprite",
        "map_tg": False,
        "tile_w": 8,
        "tile_h": 12,
        "grid_w": 1,
        "grid_h": 1,
        "x" : 0,
        "y" : 0
        },
    "bucket3":  {
        "bitmap": 'bucket3',
        "w": 12,
        "h": 12, 
        "p": 16,
        "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,12,0,12,0,12,0,12,0,12,0,12,
                        12,0,12,0,12,0,12,0,12,0,12,0,
                        0,11,0,11,0,11,0,11,0,11,0,11,
                        11,0,11,0,11,0,11,0,11,0,11,0,
                        0,9,0,9,0,9,0,9,0,9,0,9,
                        9,0,9,0,9,0,9,0,9,0,9,0,
                        5,6,5,6,5,6,5,6,5,6,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0],
        "tile_grid": 'bucket_sprite_3',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 12,
        "grid_w": 1,
        "grid_h": 3,
        "x": 0,
        "y": 0
        },
        "bucket2":  {
        "bitmap": 'bucket2',
        "w": 12,
        "h": 12, 
        "p": 16,
        "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,12,0,12,0,12,0,12,0,12,0,12,
                        12,0,12,0,12,0,12,0,12,0,12,0,
                        0,11,0,11,0,11,0,11,0,11,0,11,
                        11,0,11,0,11,0,11,0,11,0,11,0,
                        0,9,0,9,0,9,0,9,0,9,0,9,
                        9,0,9,0,9,0,9,0,9,0,9,0,
                        5,6,5,6,5,6,5,6,5,6,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0],
        "tile_grid": 'bucket_sprite_2',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 12,
        "grid_w": 1,
        "grid_h": 2,
        "x": 0,
        "y": 0
        },
        "bucket1":  {
        "bitmap": 'bucket1',
        "w": 12,
        "h": 12, 
        "p": 16,
        "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,0,0,0,0,0,0,0,0,0,0,0,
                        0,12,0,12,0,12,0,12,0,12,0,12,
                        12,0,12,0,12,0,12,0,12,0,12,0,
                        0,11,0,11,0,11,0,11,0,11,0,11,
                        11,0,11,0,11,0,11,0,11,0,11,0,
                        0,9,0,9,0,9,0,9,0,9,0,9,
                        9,0,9,0,9,0,9,0,9,0,9,0,
                        5,6,5,6,5,6,5,6,5,6,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0,
                        5,5,5,5,5,5,5,5,5,5,5,0],
        "tile_grid": 'bucket_sprite_1',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 12,
        "grid_w": 1,
        "grid_h": 1,
        "x": 0,
        "y": 0
        },
    "sad_baddy":  {
        "bitmap": 'sad_baddy',
        "w": 12,
        "h": 23, 
        "p": 16,
        "value_map": [0,0,0,0,4,4,4,4,0,0,0,0,
                        0,0,0,4,4,4,4,4,4,0,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,4,4,7,4,4,7,4,4,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,13,13,13,13,13,13,13,13,0,0,
                        0,0,13,13,13,2,2,13,13,13,0,0,
                        0,0,13,13,2,13,13,2,13,13,0,0,
                        0,0,0,13,13,13,13,13,13,0,0,0,
                        0,0,0,0,0,13,13,0,0,0,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,1,1,1,1,1,1,1,1,1,1,0,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        1,1,3,1,1,1,1,1,1,3,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        13,13,3,1,1,1,1,1,1,3,13,13,
                        13,13,3,4,4,4,4,4,4,3,13,13],
        "tile_grid": 'tg_sad_pybomber',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 23,
        "grid_w": 1,
        "grid_h": 1,
        "x": 0,
        "y": 0
        },
    "happy_baddy":  {
        "bitmap": 'sad_baddy',
        "w": 12,
        "h": 23, 
        "p": 16,
        "value_map": [0,0,0,0,4,4,4,4,0,0,0,0,
                        0,0,0,4,4,4,4,4,4,0,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,4,4,7,4,4,7,4,4,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,13,13,13,13,13,13,13,13,0,0,
                        0,0,13,13,2,13,13,2,13,13,0,0,
                        0,0,13,13,13,2,2,13,13,13,0,0,
                        0,0,0,13,13,13,13,13,13,0,0,0,
                        0,0,0,0,0,13,13,0,0,0,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,1,1,1,1,1,1,1,1,1,1,0,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        1,1,3,1,1,1,1,1,1,3,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        13,13,3,1,1,1,1,1,1,3,13,13,
                        13,13,3,4,4,4,4,4,4,3,13,13],
        "tile_grid": 'tg_sad_pybomber',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 23,
        "grid_w": 1,
        "grid_h": 1,
        "x": 0,
        "y": 0
        },
    "surprised_baddy": {
        "bitmap": 'sad_baddy',
        "w": 12,
        "h": 23, 
        "p": 16,
        "value_map": [0,0,0,0,4,4,4,4,0,0,0,0,
                        0,0,0,4,4,4,4,4,4,0,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,4,4,7,4,4,7,4,4,0,0,
                        0,0,4,4,4,4,4,4,4,4,0,0,
                        0,0,13,13,13,13,13,13,13,13,0,0,
                        0,0,13,13,13,2,2,13,13,13,0,0,
                        0,0,13,13,13,2,2,13,13,13,0,0,
                        0,0,0,13,13,13,13,13,13,0,0,0,
                        0,0,0,0,0,13,13,0,0,0,0,0,
                        0,4,4,4,4,4,4,4,4,4,4,0,
                        0,1,1,1,1,1,1,1,1,1,1,0,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,4,4,4,4,4,4,4,4,4,4,
                        1,1,1,1,1,1,1,1,1,1,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        1,1,3,1,1,1,1,1,1,3,1,1,
                        4,4,3,4,4,4,4,4,4,3,4,4,
                        13,13,3,1,1,1,1,1,1,3,13,13,
                        13,13,3,4,4,4,4,4,4,3,13,13],
        "tile_grid": 'tg_sad_pybomber',
        "map_tg": False,
        "tile_w": 12,
        "tile_h": 23,
        "grid_w": 1,
        "grid_h": 1,
        "x": 0,
        "y": 0
        },
    "explosion":  {
        "bitmap": 'explosion',
        "w": 16,
        "h": 16,
        "p": 16,
        "value_map": [
            0, 0, 15, 15, 10, 10, 15, 15, 15, 15, 10, 10, 15, 15, 0, 0,
            0, 15, 10, 10, 15, 15, 10, 10, 10, 10, 15, 15, 10, 10, 15, 0,
            15, 10, 15, 15, 10, 10, 15, 15, 15, 15, 10, 10, 15, 15, 10, 15,
            15, 10, 15, 10, 15, 15, 10, 10, 10, 10, 15, 15, 10, 15, 10, 15,
            10, 15, 10, 15, 10, 15, 10, 15, 15, 10, 15, 10, 15, 10, 15, 10,
            10, 15, 10, 15, 15, 10, 15, 10, 10, 15, 10, 15, 15, 10, 15, 10,
            15, 10, 15, 10, 15, 10, 15, 10, 10, 15, 10, 15, 10, 15, 10, 15,
            15, 10, 10, 10, 15, 10, 15, 10, 10, 15, 10, 15, 10, 10, 10, 15,
            15, 10, 10, 10, 15, 10, 15, 10, 10, 15, 10, 15, 10, 10, 10, 15,
            15, 10, 15, 10, 15, 10, 15, 10, 10, 15, 10, 15, 10, 15, 10, 15,
            10, 15, 10, 15, 15, 10, 15, 10, 10, 15, 10, 15, 15, 10, 15, 10,
            10, 15, 10, 15, 10, 15, 10, 15, 15, 10, 15, 10, 15, 10, 15, 10,
            15, 10, 15, 10, 15, 15, 10, 10, 10, 10, 15, 15, 10, 15, 10, 15,
            15, 10, 15, 15, 10, 10, 15, 15, 15, 15, 10, 10, 15, 15, 10, 15,
            0, 15, 10, 10, 15, 15, 10, 10, 10, 10, 15, 15, 10, 10, 15, 0,
            0, 0, 15, 15, 10, 10, 15, 15, 15, 15, 10, 10, 15, 15, 0, 0,
        ],
        "tile_grid": 'explosion_sprite',
        "map_tg": False,
        "tile_w": 16,
        "tile_h": 16,
        "grid_w": 1,
        "grid_h": 1,
        "x": 0,
        "y": 0
    }
}

# Sets game level parameters
def sprite_prams(sprite_name, new_x, new_y):
    sprites = SPRITES.get(sprite_name)
    bitmap = sprites["bitmap"]
    w = sprites["w"]
    h = sprites["h"]
    p = sprites["p"]
    value_map = sprites["value_map"]
    tile_grid = sprites["tile_grid"]
    map_tg = sprites["map_tg"]
    tile_w = sprites["tile_w"]
    tile_h = sprites["tile_h"]
    grid_w = sprites["grid_w"]
    grid_h = sprites["grid_h"]
    if not new_x:
        x = sprites["x"]
    else:
        x = new_x
    if not new_y:
        y = sprites["y"]
    else:
        y = new_y
    return create_sprite(bitmap, value_map, w, h, p, tile_grid, map_tg, tile_w, tile_h, grid_w, grid_h, x, y)

top_wall_sprite = sprite_prams("top_wall",None,None)
wall_sprite = sprite_prams("wall",None,None)
sad_baddy_sprite = sprite_prams("sad_baddy",None,None)
happy_baddy_sprite = sprite_prams("happy_baddy",None,None)
surprised_baddy_sprite = sprite_prams("surprised_baddy",None,None)

gc.collect()

def bomb_flicker(): # pallette shifts 8 through 14, 10, and 15
    if pallette[8] == pallette[14]:
        pallette[8] = pallette[10]
    elif pallette[8] == pallette[10]:
        pallette[8] = pallette[15]
    elif pallette[8] == pallette[15]:
        pallette[8] = pallette[14]

def bucket_splash(is_splash): # pallet shifts 9, 11, 12 through transpearant
    global splash_count, splash
    if not is_splash:
        splash_count = 0
        pallette.make_transparent(9)
        pallette.make_transparent(11)
        pallette.make_transparent(12)
        return

    if is_splash:
        if splash_count < 3:
            pallette.make_opaque(9)
            splash_count += 1        
        elif splash_count < 6:
            pallette.make_transparent(9)
            pallette.make_opaque(11)
            splash_count += 1        
        elif splash_count < 9:
            pallette.make_transparent(11)
            pallette.make_opaque(12)
            splash_count += 1
        elif splash_count > 8:
            pallette.make_transparent(12)
            splash_count = 0
            splash = False


# initialize groups to hold visual elements
main_group = Group()
scaled_group = Group(scale=scale)
main_group.append(scaled_group)

# Setup background
bg_bmp = Bitmap(16, 12, 1)
bg_palette = Palette(1)
bg_palette[0] = 0x87F2FF  # light blue
bg_tilegrid = TileGrid(bg_bmp, pixel_shader=bg_palette)

# Group for the background scaled to 10x    
bg_group = Group(scale=10)

# add the background to it's group and add that to the scaled_group
bg_group.append(bg_tilegrid)
scaled_group.append(bg_group)

# Build wall
wall_group = Group(scale=scale)
wall_group.append(top_wall_sprite)
wall_group.append(wall_sprite)
main_group.append(wall_group)

# Setup PyBomber
pyBomber_group = Group(scale=scale) 
pyBomber_group.append(sad_baddy_sprite)
main_group.append(pyBomber_group)
pyBomber_group.x = bomber_start_x
pyBomber_group.y = bomber_start_y   

# Setup Bucket
def make_bucket(game_state, buckets, change_count):
    global bucket_group, main_group, splash, bucket_sprite, bucket_x
    
    # This fixed Y position ensures the top of the bucket remains stationary,
    # making it appear to build from the top down. It's calculated from 
    # the original position of the tallest (3-part) bucket so it still
    # sits near the bottom of the screen.
    BUCKET_TOP_Y = 164

    if game_state == STATE_TITLE:
        bucket_sprite = sprite_prams("bucket3",None,None)
        # center bucket horizontally and place it at a fixed top position
        bx = display.width // 2 - (bucket_sprite.tile_width * bucket_sprite.width * scale) // 2
        by = BUCKET_TOP_Y # Changed from original dynamic calculation
        bucket_group = Group(scale=scale, x = bx, y = by)
        bucket_group.append(bucket_sprite)
        main_group.append(bucket_group)
        bucket_x = bucket_group.x
        bucket_splash(splash)
    else:
        # Only remove and recreate if we need to change bucket count
        if change_count:
            if 'bucket_group' in globals() and bucket_group in main_group:
                main_group.remove(bucket_group)
            
            if buckets == 3:
                bucket_sprite = sprite_prams("bucket3",None,None)
            elif buckets == 2:
                bucket_sprite = sprite_prams("bucket2",None,None) 
            elif buckets == 1:
                bucket_sprite = sprite_prams("bucket1",None,None)
           
            # recreate and position bucket using the fixed top position
            bx = display.width // 2 - (bucket_sprite.tile_width * bucket_sprite.width * scale) // 2
            by = BUCKET_TOP_Y # Changed from original dynamic calculation
            bucket_group = Group(scale=scale, x=bx, y=by)
            bucket_group.append(bucket_sprite)
            main_group.append(bucket_group)
            bucket_x = bucket_group.x    

make_bucket(gameState, bucket_count, change_bucket)                   

# Setup Bomb Sprite and Groups
bomb_sprite = sprite_prams("bomb",bomb_start_x,bomb_start_y)
temp_bomb_group = Group(scale=scale)
temp_bomb_group.append(bomb_sprite)
main_group.append(temp_bomb_group)
temp_bomb_exists = True

# Setup Score Sprite
score_text = "       0"
font = terminalio.FONT
score_color = pallette[10]
score_area = Label(font, text=score_text, color=score_color,x=(display.width // 2) - 50,y=6)
text_group = Group(scale=2)
text_group.append(score_area)
main_group.append(text_group)

def make_bomb_name(bomb_dropped,name):
    global bomb_name
    bomb_name = f"{name}_{bomb_dropped}"
    print(bomb_name)
    return bomb_name

def drop_bomb(bomb_count):
    global bombs, bombs_dropped, bomb_name, bomb_start_x, drop_bomb_x, current_bomb

    # Update drop location
    drop_bomb_x = pyBomber_group.x // scale
    # print("bomb drop x: ", drop_bomb_x," pybomber x: ",pyBomber_group.x)
    drop_bomb_y = pyBomber_group.y + bomb_start_y // scale

    # Create the new displayio.TileGrid object for the bomb sprite
    bomb_spite_name = make_bomb_name(bomb_count,"bomb_sprite")
    bomb_group_name = make_bomb_name(bomb_count,"bomb_group")

    current_bomb[bomb_spite_name] = sprite_prams("bomb", 0, 0)
    current_bomb[bomb_group_name] = Group(scale=scale, x=drop_bomb_x * scale, y=drop_bomb_y * scale)

    bombs.append(bomb_group_name)

    # Add the sprite (from the Bomb object) to the display group
    current_bomb[bomb_group_name].append(current_bomb[bomb_spite_name])
    main_group.append(current_bomb[bomb_group_name])
    bombs_dropped += 1
    gc.collect()
    return bombs

def update_bombs(bombs):
    global splash, key, item, main_group, score, bombScore, bucket_sprite, item, bomb_sprite, drop_speed
    global bucket_count, gameState, successState
    if bombs:
        # Use a copy of the list to iterate over, so we can remove items from the original
        for key in list(bombs):
            item = current_bomb.get(key)
            if not item:
                continue

            # Move the whole group down by drop_speed (group.x/y are in screen pixels)
            item.y += drop_speed * 1  # drop_speed already in pixels per frame unit

            # Bomb dimensions in pixels (use bomb sprite tile size)
            bomb_left = item.x
            bomb_right = item.x + (bomb_sprite.tile_width * bomb_sprite.width * scale)
            bomb_top = item.y
            bomb_bottom = item.y + (bomb_sprite.tile_height * bomb_sprite.height * scale)

            # Bucket dimensions in pixels (use full tilegrid width/height)
            bucket_left = bucket_group.x
            bucket_right = bucket_group.x + (bucket_sprite.tile_width * bucket_sprite.width * scale)
            bucket_top = bucket_group.y + 20
            bucket_bottom = bucket_group.y + (bucket_sprite.tile_height * bucket_sprite.height * scale)

            # Check for collision
            x_collision = (bomb_right >= bucket_left and bomb_left <= bucket_right)
            y_collision = (bomb_bottom >= bucket_top and bomb_top <= bucket_bottom)

            # Handle collision
            if x_collision and y_collision:
                try:
                    bombs.remove(key)
                except ValueError:
                    pass
                if item in main_group:
                    main_group.remove(item)
                # Clean up the dictionary to free memory
                del current_bomb[key]
                sprite_key = key.replace("_group", "_sprite")
                if sprite_key in current_bomb:
                    del current_bomb[sprite_key]
                splash = True
                score += bombScore
                score_area.text = f"{int(score):>8}"
                continue

            # Check if bomb is off screen (use group y + sprite height)
            if item.y > (display.height - (12 * scale)):
                gameState = STATE_PAUSED
                successState = False
                
                # We only need to detect one bomb off screen to trigger the state change.
                # The main loop will handle the consequences.
                return
    
    gc.collect()


gc.collect()

# Show display
display.root_group = main_group 

gc.collect

while True:
    # if the player hasn't started yet
    if gameState in (STATE_READY, STATE_TITLE):
        while True:
            # check if any keys were pressed
            available = supervisor.runtime.serial_bytes_available

            # if one or more keys was pressed
            if available:
                # read the value
                cur_btn_val = sys.stdin.read(available)
            else:
                cur_btn_val = None

            # if spacebar was pressed
            if cur_btn_val == " ":
                gameState = STATE_PLAYING
                # Reset bucket count for a new game
                bucket_count = MAX_BUCKETS
                change_bucket = True
                make_bucket(gameState, bucket_count, change_bucket)
                change_bucket = False
                break

    if gameState == STATE_PAUSED:
        if not successState: # This is a failure state, not a user-initiated pause.
            # 1. Change all active bombs to explosions
            explosion_groups = []
            for bomb_key in list(bombs):
                bomb_item = current_bomb.get(bomb_key)
                if bomb_item and bomb_item in main_group:
                    # Create explosion at the bomb's location
                    explosion_sprite = sprite_prams("explosion", 0, 0)
                    explosion_group = Group(scale=scale, x=bomb_item.x, y=bomb_item.y)
                    explosion_group.append(explosion_sprite)
                    main_group.append(explosion_group)
                    explosion_groups.append(explosion_group)
                    
                    # Remove the original bomb
                    main_group.remove(bomb_item)
            
            # Clean up bomb tracking data structures
            bombs.clear()
            current_bomb.clear()

            # Change bomber to happy bomber after a miss
            if sad_baddy_sprite in pyBomber_group:
                pyBomber_group.remove(sad_baddy_sprite)
            pyBomber_group.append(happy_baddy_sprite)

            # 2. Show explosions for a moment
            display.refresh()
            time.sleep(1)

            # 3. Clean up explosions from the display
            for exp_group in explosion_groups:
                if exp_group in main_group:
                    main_group.remove(exp_group)
            
            # 4. Update game state: decrease buckets, check for game over
            bucket_count -= 1
            change_bucket = True

            if bucket_count <= 0:
                gameState = STATE_GAME_OVER
                # You could add a "Game Over" message display here
                continue

            # 5. Update the bucket display
            make_bucket(gameState, bucket_count, change_bucket)
            change_bucket = False

            # 6. Decrease level and reset level parameters
            currentLevel -= 1
            if currentLevel < 1:
                currentLevel = 1
            
            old_bomb_count = bombCount
            setLevelParams(currentLevel)
            bombCount = old_bomb_count // 2
            if bombCount < 5: # Ensure a minimum number of bombs
                bombCount = 5

            # 7. Reset for the next round
            successState = True # Reset for the new attempt

            # Change bomber back to sad for the new round
            if happy_baddy_sprite in pyBomber_group:
                pyBomber_group.remove(happy_baddy_sprite)
            pyBomber_group.append(sad_baddy_sprite)
            
            # Wait for user input to continue, without a message
            while True:
                available = supervisor.runtime.serial_bytes_available
                if available:
                    cur_btn_val = sys.stdin.read(available)
                else:
                    cur_btn_val = None

                if cur_btn_val == " ":
                    gameState = STATE_PLAYING
                    break # Exit the waiting loop
                time.sleep(0.01) # Small delay to prevent busy-looping


    if gameState == STATE_PLAYING:
        # Check if the level is complete (all bombs for the level have been dropped and
        # no bombs are left on the screen).
        level_complete = (bombs_dropped == bombCount) and not bombs

        # Only read input and move the bucket if the level is still in progress.
        if not level_complete:
            # if one or more keys was pressed
            available = supervisor.runtime.serial_bytes_available
            if available:
                  # read the value
                cur_btn_val = sys.stdin.read(available)
            else:
                cur_btn_val = None


            if cur_btn_val in ("a", "A"):
                bucket_x -= bucket_sprite.tile_width * scale
                bucket_move = True
            if cur_btn_val in ("d", "D"):
                bucket_x += bucket_sprite.tile_width * scale
                bucket_move = True

            # keep bucket on screen
            if bucket_move:
                if bucket_x <= 0:
                    bucket_x = 0
                    bucket_move = False
                elif bucket_x > display.width - (bucket_sprite.tile_width * scale):
                    bucket_x = display.width - (bucket_sprite.tile_width * scale)
                    bucket_move = False 
                else:
                    bucket_group.x = bucket_x
                    bucket_move = False
        else:
            # Level is complete. You could add logic here to transition to the next level.
            # For now, we just prevent the bucket from moving.
            pass

        # Update enemy movement (discrete steps)
        enemy_move_timer += 1 / 100  # Add frame time (since we sleep 0.01 each frame)
        enemy_change_timer += 1 / 100 # set the direction time change
        bomb_flicker()
        if enemy_move_timer >= bomberSpeed / 100:  # Time to move?
            enemy_move_timer = 0  # Reset timer

            # Move enemy one step
            enemy_x += enemy_step * enemy_direction

            # Check if enemy hits screen edge and is moving towards it
            if (enemy_x <= 8 and enemy_direction < 0) or \
               (enemy_x >= display.width - (enemy_width * scale) and enemy_direction > 0):
                enemy_direction *= -1  # Flip direction
                enemy_change_timer = 0 # Reset random change timer as well
        
            #Update change direction
            if enemy_change_timer >= directionChange / 100:
                enemy_direction = enemy_direction * -1
                enemy_change_timer = 0
                directionChange = random.randint(params["directionChangeLB"], params["directionChangeUB"])


        if not bombs_dropped == bombCount:
            bomb_drop_timer += 1 / 100  # Add frame time (since we sleep 0.01 each frame)
            # print("drop timer: ",bomb_drop_timer,"interval: ",dropInterval,"bombs dropped: ",bombs_dropped,"bomb to drop: ",bombCount)
            if bombs_dropped == 0 and temp_bomb_group in main_group:
                main_group.remove(temp_bomb_group)
                bomb_drop_timer = 0  # Reset timer
                drop_bomb(bombs_dropped)

            if bomb_drop_timer >= dropInterval / 100 and bombs_dropped < bombCount:  # Time to drop a bomb?
                bomb_drop_timer = 0  # Reset timer
                drop_bomb(bombs_dropped)
            
            # Update bomb locations
            update_bombs(bombs)

            # Update enemy position on display
            pyBomber_group.x = enemy_x
            bucket_splash(splash)
        else:
            # Update bomb locations
            update_bombs(bombs)
            bucket_splash(splash) 
            
        time.sleep(1/100)