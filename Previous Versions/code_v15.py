from micropython import const
import sys
import time
import supervisor
from displayio import Group,TileGrid,Palette,Bitmap
from adafruit_display_text.text_box import TextBox
from adafruit_fruitjam.peripherals import request_display_config, Peripherals
import random
import gc
import terminalio
from adafruit_display_text.bitmap_label import Label
import array
import math
import audiocore

# Setup display
request_display_config(320,240)
display = supervisor.runtime.display
ctrl_pad = supervisor.runtime.usb_connected

# --- v1.5 Audio Setup (Reverted) ---
try:
    fruit_jam = Peripherals()
    fruit_jam.dac.headphone_output = True
    fruit_jam.dac.dac_volume = 0 
    sample_rate = fruit_jam.dac.sample_rate
    
    # Simplified generate_wave for sine only
    def generate_wave(frequency, duration_seconds):
        length = int(duration_seconds * sample_rate)
        if frequency == 0: # For silence
             return array.array("h", [0] * length)
        
        # Generate one cycle
        period = sample_rate / frequency
        if period == 0:
            return array.array("h", [0] * length)
            
        sine_wave_cycle = array.array("h", [0] * int(period))
        for i in range(int(period)):
            sine_wave_cycle[i] = int((math.sin(math.pi * 2 * i / period)) * 0.5 * (2**15 - 1))
        
        # Repeat the cycle to fill the duration
        sine_wave = array.array("h", [0] * length)
        for i in range(length):
            sine_wave[i] = sine_wave_cycle[i % int(period)]
            
        return sine_wave

    def play_sound(sample, loop=False):
        if fruit_jam.audio.playing:
            fruit_jam.audio.stop()
        fruit_jam.audio.play(sample, loop=loop)

    # Reverted sound samples to original sine waves
    wave_start = generate_wave(440, 0.1) # 100ms A4
    sound_start = audiocore.RawSample(wave_start, sample_rate=sample_rate)
    
    wave_catch = generate_wave(880, 0.05) # 50ms A5
    sound_catch = audiocore.RawSample(wave_catch, sample_rate=sample_rate)

    wave_miss = generate_wave(165, 0.3) # 300ms E3
    sound_miss = audiocore.RawSample(wave_miss, sample_rate=sample_rate)
    
    wave_level_up = generate_wave(523, 0.2) # 200ms C5
    sound_level_up = audiocore.RawSample(wave_level_up, sample_rate=sample_rate)
    
    wave_game_over = generate_wave(110, 1.0) # 1s A2
    sound_game_over = audiocore.RawSample(wave_game_over, sample_rate=sample_rate)

except ImportError:
    print("Fruit Jam peripherals not found. Running without sound.")
    # Create dummy functions if hardware isn't present
    def play_sound(sample, loop=False):
        pass
    # Create dummy samples
    sound_start = None
    sound_catch = None
    sound_miss = None
    sound_level_up = None
    sound_game_over = None

gc.collect()

# Game constants
MAX_BUCKETS = const(3)
MAX_LIFE_INTERVAL = const(1000)
STATE_PLAYING = const(0)
STATE_READY = const(1)
STATE_PAUSED = const(2)
STATE_GAME_OVER = const(3)
STATE_TITLE = const(4)
BUCKET_TOP_Y = const(164)
DEBUG_START_LEVEL = const(3) # Set this to 1 for normal play, or any level to test
 
# Game variables
next_extra_life = MAX_LIFE_INTERVAL
current_level = DEBUG_START_LEVEL
bombs = []
params = []
drop_speed = None
direction_change = None
drop_interval = None
bombs_dropped = 0
bomb_score = None
bomb_count = None
bomber_speed = None
success_state = True
game_state = STATE_TITLE
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
bomber_start_x = 10
bomber_start_y = 4
bomb_start_x  = 7
bomb_start_y  = 17
drop_bomb_x = bomb_start_x
drop_bomb_y = bomb_start_y
bomb_drop_timer = 0
current_bomb = {}
splash = False
score = 0
scale = 2
surprised_baddy_triggered = False
high_score = 0
game_win = False

gc.collect()

# Levels parameter dictionary
LEVELS = {
    1: {
        'bomberSpeed': 1,
        'bombCount': 10,
        'bombScore': 1,
        'directionChangeLB': 80,
        'directionChangeUB': 150,
        'dropIntervalLB': 12,
        'dropIntervalUB': 22,
        'drop_speed': 4,
        'successState': 1,
        'enemy_step': 2
    },
    2: {
        'bomberSpeed': 1,
        'bombCount': 15,
        'bombScore': 2,
        'directionChangeLB': 70,
        'directionChangeUB': 140,
        'dropIntervalLB': 10,
        'dropIntervalUB': 20,
        'drop_speed': 5,
        'successState': 1,
        'enemy_step': 2
    },
    3: {
        'bomberSpeed': 1,
        'bombCount': 20,
        'bombScore': 3,
        'directionChangeLB': 60,
        'directionChangeUB': 120,
        'dropIntervalLB': 8,
        'dropIntervalUB': 18,
        'drop_speed': 5,
        'successState': 1,
        'enemy_step': 2
    },
    4: {
        'bomberSpeed': 1,
        'bombCount': 25,
        'bombScore': 4,
        'directionChangeLB': 50,
        'directionChangeUB': 100,
        'dropIntervalLB': 7,
        'dropIntervalUB': 16,
        'drop_speed': 6,
        'successState': 1,
        'enemy_step': 2
    },
    5: {
        'bomberSpeed': 1,
        'bombCount': 30,
        'bombScore': 5,
        'directionChangeLB': 40,
        'directionChangeUB': 80,
        'dropIntervalLB': 6,
        'dropIntervalUB': 13,
        'drop_speed': 7,
        'successState': 1,
        'enemy_step': 2
    },
    6: {
        'bomberSpeed': 1,
        'bombCount': 40,
        'bombScore': 6,
        'directionChangeLB': 30,
        'directionChangeUB': 70,
        'dropIntervalLB': 5,
        'dropIntervalUB': 10,
        'drop_speed': 9,
        'successState': 1,
        'enemy_step': 2
    },
    7: {
        'bomberSpeed': 1,
        'bombCount': 50,
        'bombScore': 7,
        'directionChangeLB': 25,
        'directionChangeUB': 60,
        'dropIntervalLB': 4,
        'dropIntervalUB': 8,
        'drop_speed': 11,
        'successState': 1,
        'enemy_step': 2
    },
    8: {
        'bomberSpeed': 1,
        'bombCount': 60,
        'bombScore': 8,
        'directionChangeLB': 20,
        'directionChangeUB': 50,
        'dropIntervalLB': 3,
        'dropIntervalUB': 6,
        'drop_speed': 13,
        'successState': 0,
        'enemy_step': 2
    }
}

gc.collect()

# Sets game level parameters
def set_level_params(level):
    global params, drop_speed, direction_change, drop_interval
    global bombs_dropped, bomb_score, bomb_count, bomber_speed, enemy_step
    
    # Handle looping level 8
    level_key = level
    if level > 8:
        level_key = 8
        
    params = LEVELS.get(level_key)
    drop_speed = params["drop_speed"]
    direction_change = random.randint(params["directionChangeLB"], params["directionChangeUB"])
    drop_interval = random.randint(params["dropIntervalLB"], params["dropIntervalUB"])
    bombs_dropped = 0
    bomb_score = params["bombScore"]
    bomb_count = params["bombCount"]
    bomber_speed = params["bomberSpeed"]
    enemy_step = params["enemy_step"]
    print("Level:", level, params)
    gc.collect()
    return params, drop_speed, direction_change, drop_interval, bombs_dropped, bomb_score, bomb_count, bomber_speed

set_level_params(current_level)

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
    gc.collect()
    return pallette

pallette = setup_palette()

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

gc.collect()

# Renamed from sprite_prams
def sprite_params(sprite_name, new_x, new_y):
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

top_wall_sprite = sprite_params("top_wall",None,None)
wall_sprite = sprite_params("wall",None,None)
sad_baddy_sprite = sprite_params("sad_baddy",None,None)
happy_baddy_sprite = sprite_params("happy_baddy",None,None)
surprised_baddy_sprite = sprite_params("surprised_baddy",None,None)

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
        if splash_count < 10:
            pallette.make_opaque(9)
            splash_count += 1        
        elif splash_count < 20:
            pallette.make_transparent(9)
            pallette.make_opaque(11)
            splash_count += 1        
        elif splash_count < 30:
            pallette.make_transparent(11)
            pallette.make_opaque(12)
            splash_count += 1
        elif splash_count > 29:
            pallette.make_transparent(12)
            splash_count = 0
            splash = False

# initialize groups to hold visual elements
main_group = Group()
scaled_group = Group(scale=scale)
main_group.append(scaled_group)
gc.collect()

# Setup background
bg_bmp = Bitmap(16, 12, 1)
bg_palette = Palette(1)
bg_palette[0] = 0x87F2FF  # light blue
bg_tilegrid = TileGrid(bg_bmp, pixel_shader=bg_palette)
gc.collect()

# Group for the background scaled to 10x    
bg_group = Group(scale=10)

# add the background to it's group and add that to the scaled_group
bg_group.append(bg_tilegrid)
scaled_group.append(bg_group)
gc.collect()

# Build wall
wall_group = Group(scale=scale)
wall_group.append(top_wall_sprite)
wall_group.append(wall_sprite)
main_group.append(wall_group)
gc.collect()

# Setup PyBomber
pyBomber_group = Group(scale=scale) 
pyBomber_group.append(sad_baddy_sprite)
main_group.append(pyBomber_group)
pyBomber_group.x = bomber_start_x
pyBomber_group.y = bomber_start_y   
gc.collect()

# Setup Bucket
def make_bucket(game_state_val, buckets, change_count):
    global bucket_group, main_group, splash, bucket_sprite, bucket_x, BUCKET_TOP_Y
    
    # This fixed Y position ensures the top of the bucket remains stationary,
    # making it appear to build from the top down. It's calculated from 
    # the original position of the tallest (3-part) bucket so it still
    # sits near the bottom of the screen.

    if game_state_val == STATE_TITLE:
        bucket_sprite = sprite_params("bucket3",None,None)
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
                bucket_sprite = sprite_params("bucket3",None,None)
            elif buckets == 2:
                bucket_sprite = sprite_params("bucket2",None,None) 
            elif buckets == 1:
                bucket_sprite = sprite_params("bucket1",None,None)
           
            # recreate and position bucket using the fixed top position
            bx = display.width // 2 - (bucket_sprite.tile_width * bucket_sprite.width * scale) // 2
            by = BUCKET_TOP_Y # Changed from original dynamic calculation
            bucket_group = Group(scale=scale, x=bx, y=by)
            bucket_group.append(bucket_sprite)
            main_group.append(bucket_group)
            bucket_x = bucket_group.x

make_bucket(game_state, bucket_count, change_bucket)                   

gc.collect()

# Create a global bomb_sprite to reference its dimensions
# This object is not displayed; it's just for getting tile_width/height
bomb_sprite = sprite_params("bomb", 0, 0)
gc.collect()

# Setup Score Sprite
score_text = "       0"
font = terminalio.FONT
score_color = pallette[10]
score_area = Label(font, text=score_text, color=score_color,x=(display.width // 2) - 50,y=6)
text_group = Group(scale=2)
text_group.append(score_area) # score_area is always element 0
main_group.append(text_group)
gc.collect()

def make_bomb_name(bombs_dropped_count, name):
    global bomb_name
    bomb_name = f"{name}_{bombs_dropped_count}"
    print(bomb_name)
    return bomb_name

def drop_bomb(bombs_dropped_count):
    global bombs, bombs_dropped, bomb_name, bomb_start_x, drop_bomb_x, current_bomb

    # Update drop location
    drop_bomb_x = pyBomber_group.x // scale
    # print("bomb drop x: ", drop_bomb_x," pybomber x: ",pyBomber_group.x)
    drop_bomb_y = pyBomber_group.y + bomb_start_y // scale

    # Create the new displayio.TileGrid object for the bomb sprite
    bomb_sprite_name = make_bomb_name(bombs_dropped_count,"bomb_sprite")
    bomb_group_name = make_bomb_name(bombs_dropped_count,"bomb_group")

    current_bomb[bomb_sprite_name] = sprite_params("bomb", 0, 0)
    current_bomb[bomb_group_name] = Group(scale=scale, x=drop_bomb_x * scale, y=drop_bomb_y * scale)

    bombs.append(bomb_group_name)

    # Add the sprite (from the Bomb object) to the display group
    current_bomb[bomb_group_name].append(current_bomb[bomb_sprite_name])
    main_group.append(current_bomb[bomb_group_name])
    bombs_dropped += 1
    return bombs

def update_bombs(bombs_list):
    global splash, key, item, main_group, score, bomb_score, bucket_sprite, drop_speed
    global bucket_count, game_state, success_state, next_extra_life, change_bucket
    global surprised_baddy_triggered, game_win, current_level
    
    if bombs_list:
        # Use a copy of the list to iterate over, so we can remove items from the original
        for key in list(bombs_list):
            item = current_bomb.get(key)
            if not item:
                continue

            # Move the whole group down by drop_speed (group.x/y are in screen pixels)
            item.y += drop_speed * 1  # drop_speed already in pixels per frame unit

            # Bomb dimensions in pixels (use bomb sprite tile size)
            bomb_left = item.x
            bomb_right = item.x + (bomb_sprite.tile_width * scale)
            bomb_top = item.y
            bomb_bottom = item.y + (bomb_sprite.tile_height * scale)

            # Bucket dimensions in pixels (use full tilegrid width/height)
            bucket_left = bucket_group.x
            bucket_right = bucket_group.x + (bucket_sprite.tile_width * scale)
            bucket_top = bucket_group.y + 20
            bucket_bottom = bucket_group.y + (bucket_sprite.tile_height * bucket_sprite.height * scale)

            # Check for collision
            x_collision = (bomb_right >= bucket_left and bomb_left <= bucket_right)
            y_collision = (bomb_bottom >= bucket_top and bomb_top <= bucket_bottom)

            # Handle collision
            if x_collision and y_collision:
                try:
                    bombs_list.remove(key)
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
                score += bomb_score
                score_area.text = f"{int(score):>8}"
                play_sound(sound_catch) # Reverted to simple catch sound

                # Check for 100,000 point win condition
                if score >= 100000:
                    game_win = True
                    game_state = STATE_GAME_OVER
                    return # Exit update_bombs, go to game over
                
                # Award an extra bucket every 1000 points
                if score >= next_extra_life:
                    next_extra_life += MAX_LIFE_INTERVAL
                    if bucket_count < MAX_BUCKETS:
                        bucket_count += 1
                        change_bucket = True
                        make_bucket(STATE_PLAYING, bucket_count, change_bucket)
                        change_bucket = False
                
                # Change bomber to surprised at 10000 points
                if not surprised_baddy_triggered and score >= 10000:
                    if sad_baddy_sprite in pyBomber_group:
                        pyBomber_group.remove(sad_baddy_sprite)
                    if happy_baddy_sprite in pyBomber_group:
                        pyBomber_group.remove(happy_baddy_sprite)
                    if surprised_baddy_sprite not in pyBomber_group:
                        pyBomber_group.append(surprised_baddy_sprite)
                    surprised_baddy_triggered = True
                
                continue

            # Check if bomb is off screen (use group y + sprite height)
            if bomb_bottom > (display.height): # Check bottom of bomb
                play_sound(sound_miss) # Reverted to simple miss sound
                game_state = STATE_PAUSED
                success_state = False
                # We only need to detect one bomb off screen to trigger the state change.
                # The main loop will handle the consequences.
                return

def reset_game():
    global score, current_level, bucket_count, change_bucket, bombs_dropped
    global bomb_drop_timer, enemy_x, next_extra_life, surprised_baddy_triggered
    global game_state, game_win

    # Reset game variables
    score = 0
    current_level = DEBUG_START_LEVEL # Use the debug start level
    set_level_params(current_level)
    bucket_count = MAX_BUCKETS
    change_bucket = True
    make_bucket(STATE_PLAYING, bucket_count, change_bucket)
    change_bucket = False
    
    bombs.clear()
    current_bomb.clear()
    bombs_dropped = 0
    bomb_drop_timer = 0
    
    enemy_x = bomber_start_x
    pyBomber_group.x = enemy_x
    pyBomber_group.y = bomber_start_y
    
    next_extra_life = MAX_LIFE_INTERVAL
    surprised_baddy_triggered = False
    game_win = False
    
    # Restore default bomber sprite
    if happy_baddy_sprite in pyBomber_group:
        pyBomber_group.remove(happy_baddy_sprite)
    if surprised_baddy_sprite in pyBomber_group:
        pyBomber_group.remove(surprised_baddy_sprite)
    if sad_baddy_sprite not in pyBomber_group:
        pyBomber_group.append(sad_baddy_sprite)

    # Clean up all text labels except the original score_area
    while len(text_group) > 1:
        text_group.pop()
        
    # Restore score display
    score_area.text = f"{int(score):>8}"
    score_area.hidden = False
    
    # Restore bucket
    bucket_group.hidden = False
    
    gc.collect()

gc.collect()

# Show display
display.root_group = main_group 

gc.collect()

while True:
    # if the player hasn't started yet
    if game_state in (STATE_READY, STATE_TITLE):
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
                # Reset game if starting from title
                if game_state == STATE_TITLE:
                    reset_game()
                # Set state to playing (either from Title or Ready)
                play_sound(sound_start) # Reverted to simple start sound
                game_state = STATE_PLAYING
                break

    if game_state == STATE_PAUSED:
        if not success_state: # This is a failure state, not a user-initiated pause.
            try:
                fruit_jam.audio.stop() # Stop any playing sound
            except NameError: # Handle case where fruit_jam wasn't initialized
                pass
            # 1. Change all active bombs to explosions
            explosion_groups = []
            for bomb_key in list(bombs):
                bomb_item = current_bomb.get(bomb_key)
                if bomb_item and bomb_item in main_group:
                    # Create explosion at the bomb's location
                    explosion_sprite = sprite_params("explosion", 0, 0)
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
            if surprised_baddy_triggered:
                if surprised_baddy_sprite in pyBomber_group:
                     pyBomber_group.remove(surprised_baddy_sprite)
            elif sad_baddy_sprite in pyBomber_group:
                pyBomber_group.remove(sad_baddy_sprite)
            
            if happy_baddy_sprite not in pyBomber_group:
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
                game_win = False # Explicitly set to false for a loss
                game_state = STATE_GAME_OVER
                continue

            # 5. Update the bucket display
            make_bucket(game_state, bucket_count, change_bucket)
            change_bucket = False

            # 6. Decrease level and reset level parameters
            
            # Store the bomb count of the level we just failed
            previous_bomb_count = bomb_count
            
            current_level -= 1
            if current_level < 1:
                current_level = 1

            set_level_params(current_level) # This sets the new level's params

            # Now, set the bombCount based on the failed level's count
            if current_level == 1 and previous_bomb_count == LEVELS.get(1)['bombCount']:
                # If we failed at level 1, just set to 5
                bomb_count = 5
            else:
                bomb_count = previous_bomb_count // 2
            
            if bomb_count < 5: # Ensure a minimum number of bombs
                bomb_count = 5

            # 7. Reset for the next round
            success_state = True # Reset for the new attempt
            
            # Change bomber back to sad/surprised for the new round
            if happy_baddy_sprite in pyBomber_group:
                pyBomber_group.remove(happy_baddy_sprite)
                
            if surprised_baddy_triggered:
                if surprised_baddy_sprite not in pyBomber_group:
                    pyBomber_group.append(surprised_baddy_sprite)
            elif sad_baddy_sprite not in pyBomber_group:
                pyBomber_group.append(sad_baddy_sprite)
            
            # Wait for user input to continue, without a message
            while True:
                available = supervisor.runtime.serial_bytes_available
                if available:
                    cur_btn_val = sys.stdin.read(available)
                else:
                    cur_btn_val = None
                if cur_btn_val == " ":
                    game_state = STATE_PLAYING
                    play_sound(sound_start) # Play simple start sound
                    bomb_drop_timer = 0 # Reset bomb drop timer
                    break # Exit the waiting loop
                time.sleep(0.01) # Small delay to prevent busy-looping

    if game_state == STATE_GAME_OVER:
        try:
            fruit_jam.audio.stop() # Stop any playing sound
        except NameError:
            pass
        # Hide active game elements
        bucket_group.hidden = True
        score_area.hidden = True
        
        game_over_labels = []

        if game_win:
            win_text = "YOU WIN!"
            font_width = 6
            text_pixel_width = len(win_text) * font_width * scale
            label_x = (display.width - text_pixel_width) // (2 * scale)
            label_y = (display.height // 2) // scale - 10
            win_label = Label(font, text=win_text, color=pallette[10], x=label_x, y=label_y)
            text_group.append(win_label)
            game_over_labels.append(win_label)
        else:
            # Show "GAME OVER"
            play_sound(sound_game_over)
            game_over_text = "GAME OVER"
            font_width = 6
            text_pixel_width = len(game_over_text) * font_width * scale
            label_x = (display.width - text_pixel_width) // (2 * scale)
            label_y = (display.height // 2) // scale - 10
            game_over_label = Label(font, text=game_over_text, color=pallette[10], x=label_x, y=label_y) # Changed color from 2 (red) to 10 (yellow)
            text_group.append(game_over_label)
            game_over_labels.append(game_over_label)

            # Create explosions over the wall
            explosion_groups = []
            wall_y_start = top_wall_sprite.y * scale
            wall_height = display.height - wall_y_start
            for _ in range(30):
                exp_x = random.randint(0, display.width - (16 * scale))
                exp_y = random.randint(wall_y_start, display.height - (16 * scale))
                explosion_sprite = sprite_params("explosion", 0, 0)
                explosion_group = Group(scale=scale, x=exp_x, y=exp_y)
                explosion_group.append(explosion_sprite)
                main_group.append(explosion_group)
                explosion_groups.append(explosion_group)
            
            display.refresh()
            time.sleep(2)
            
            # Clear explosions
            for exp_group in explosion_groups:
                if exp_group in main_group:
                    main_group.remove(exp_group)
                    
            # Animate bomber running off screen
            while pyBomber_group.x < display.width:
                pyBomber_group.x += 5
                display.refresh()
                time.sleep(0.01)

        # Handle Score Display
        score_label_y = (display.height // 2) // scale + 10
        if score > high_score:
            high_score = score
            score_text = f"New High: {score}"
            score_label = Label(font, text=score_text, color=pallette[10], x=10, y=score_label_y)
        else:
            score_text = f"Score: {score}"
            score_label = Label(font, text=score_text, color=pallette[1], x=10, y=score_label_y)
        
        text_group.append(score_label)
        game_over_labels.append(score_label)
        
        # Show "Press R to Restart"
        reset_text = "Press 'R' to Restart"
        font_width = 6
        text_pixel_width = len(reset_text) * font_width * scale
        label_x = (display.width - text_pixel_width) // (2 * scale)
        label_y = score_label_y + 20
        reset_label = Label(font, text=reset_text, color=pallette[1], x=label_x, y=label_y)
        text_group.append(reset_label)
        game_over_labels.append(reset_label)

        # Wait for reset key
        while True:
            available = supervisor.runtime.serial_bytes_available
            if available:
                cur_btn_val = sys.stdin.read(available)
            else:
                cur_btn_val = None

            if cur_btn_val in ("r", "R"):
                # Clean up labels and reset game
                reset_game()
                game_state = STATE_READY # Go to ready, not playing
                break # Exit the waiting loop
            time.sleep(0.01) # Small delay
        
        continue # Go back to the top of the main game loop

    if game_state == STATE_PLAYING:
        # Check if the level is complete (all bombs for the level have been dropped and
        # no bombs are left on the screen, and splash animation is done).
        level_complete = (bombs_dropped == bomb_count) and not bombs and not splash
        
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
            # Level is complete. Transition to the next level.
            try:
                fruit_jam.audio.stop() # Stop any playing sound
            except NameError:
                pass
            play_sound(sound_level_up)
            current_level += 1
            
            # Clear any remaining bomb data structures
            bombs.clear()
            current_bomb.clear()
            bombs_dropped = 0
            
            if current_level > 8: # 8 is the max level
                # Loop back to level 8
                pyBomber_group.x = enemy_x
            
            # Set params for the next level
            set_level_params(current_level)
            bomb_drop_timer = 0
            
            # Set state to READY to wait for player
            game_state = STATE_READY
            continue # Go back to top of loop to enter STATE_READY

        # Update enemy movement (discrete steps)
        enemy_move_timer += 1 / 100  # Add frame time (since we sleep 0.01 each frame)
        enemy_change_timer += 1 / 100 # set the direction time change
        bomb_flicker()
        if enemy_move_timer >= bomber_speed / 100:  # Time to move?
            enemy_move_timer = 0  # Reset timer

            # Move enemy one step
            enemy_x += enemy_step * enemy_direction
            # Check if enemy hits screen edge and is moving towards it
            if (enemy_x <= 8 and enemy_direction < 0) or \
               (enemy_x >= display.width - (enemy_width * scale) and enemy_direction > 0):
                enemy_direction *= -1  # Flip direction
                enemy_change_timer = 0 # Reset random change timer as well
        
            #Update change direction
            if enemy_change_timer >= direction_change / 100:
                enemy_direction = enemy_direction * -1
                enemy_change_timer = 0
                direction_change = random.randint(params["directionChangeLB"], params["directionChangeUB"])

        if not bombs_dropped == bomb_count:
            bomb_drop_timer += 1 / 100  # Add frame time (since we sleep 0.01 each frame)

            if bombs_dropped == 0: # Drop first bomb immediately
                drop_bomb(bombs_dropped)
                bomb_drop_timer = 0
            elif bomb_drop_timer >= drop_interval / 100 and bombs_dropped < bomb_count:  # Time to drop a bomb?
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