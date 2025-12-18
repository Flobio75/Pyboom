from micropython import const
import sys
import time
import supervisor
from displayio import Group,TileGrid,Palette,Bitmap,OnDiskBitmap
from adafruit_display_text.text_box import TextBox
from adafruit_fruitjam.peripherals import request_display_config, Peripherals
import random
import gc
import terminalio
from adafruit_display_text.bitmap_label import Label
import array
import math
import audiocore

# --- Game Constants ---
MAX_BUCKETS = const(3)
MAX_LIFE_INTERVAL = const(1000)
STATE_PLAYING = const(0)
STATE_READY = const(1)
STATE_PAUSED = const(2)
STATE_GAME_OVER = const(3)
STATE_TITLE = const(4)
BUCKET_TOP_Y = const(164)
DEBUG_START_LEVEL = const(1) # Set this to 1 for normal play, or any level to test

# Title animation states
TITLE_ANIM_START = const(0)
TITLE_ANIM_DROPPING = const(1)
TITLE_ANIM_EXPLODING = const(2)
TITLE_ANIM_DONE = const(3)

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
        'enemy_step': 4 # This is P2's move speed in 2P, AI speed in 1P
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
        'enemy_step': 4
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
        'enemy_step': 5
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
        'enemy_step': 5
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
        'enemy_step': 6
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
        'enemy_step': 6
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
        'enemy_step': 7
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
        'enemy_step': 8
    }
}

# --- Audio Class ---
class Audio:
    def __init__(self):
        try:
            self.fruit_jam = Peripherals()
            self.fruit_jam.dac.headphone_output = True
            self.fruit_jam.dac.dac_volume = 0
            self.sample_rate = self.fruit_jam.dac.sample_rate

            # Generate sound samples
            self.sound_start = self._generate_sample(440, 0.1) # 100ms A4
            self.sound_catch = self._generate_sample(880, 0.05) # 50ms A5
            self.sound_miss = self._generate_sample(165, 0.3) # 300ms E3
            self.sound_level_up = self._generate_sample(523, 0.2) # 200ms C5
            self.sound_game_over = self._generate_sample(110, 1.0) # 1s A2

        except (ImportError, AttributeError, OSError):
            print("Fruit Jam peripherals not found. Running without sound.")
            # Create dummy functions if hardware isn't present
            self.play = self._dummy_play
            self.stop = self._dummy_play

    def _generate_wave(self, frequency, duration_seconds):
        length = int(duration_seconds * self.sample_rate)
        if frequency == 0: # For silence
             return array.array("h", [0] * length)

        period = self.sample_rate / frequency
        if period == 0:
            return array.array("h", [0] * length)

        sine_wave_cycle = array.array("h", [0] * int(period))
        for i in range(int(period)):
            sine_wave_cycle[i] = int((math.sin(math.pi * 2 * i / period)) * 0.5 * (2**15 - 1))

        sine_wave = array.array("h", [0] * length)
        for i in range(length):
            sine_wave[i] = sine_wave_cycle[i % int(period)]

        return sine_wave

    def _generate_sample(self, frequency, duration):
        wave = self._generate_wave(frequency, duration)
        return audiocore.RawSample(wave, sample_rate=self.sample_rate)

    def play(self, sample, loop=False):
        if hasattr(self, 'fruit_jam') and self.fruit_jam.audio.playing:
            self.fruit_jam.audio.stop()
        if hasattr(self, 'fruit_jam'):
             self.fruit_jam.audio.play(sample, loop=loop)

    def stop(self):
        if hasattr(self, 'fruit_jam') and self.fruit_jam.audio.playing:
            self.fruit_jam.audio.stop()

    def _dummy_play(self, sample, loop=False):
        pass # Do nothing if audio hardware fails

# --- SpriteManager Class ---
class SpriteManager:
    def __init__(self):
        self.palette = self._setup_palette()
        self.SPRITES = {
            "top_wall": {
                "bitmap": 'top_wall', "w": 16, "h": 8, "p": 16,
                "value_map": [3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,3,2,2,2,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4],
                "tile_grid": 'top_wall_sprite', "map_tg": True, "tile_w": 16, "tile_h": 8, "grid_w": 40, "grid_h": 1, "x": 0, "y": 25
            },
            "wall": {
                "bitmap": 'wall', "w": 14, "h": 6, "p": 16,
                "value_map": [3,3,3,3,3,3,3,3,3,3,3,3,3,3,2,2,2,3,2,2,2,2,2,2,3,2,2,2,2,2,2,3,2,2,2,2,2,2,3,2,2,2,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,2,2,2,2,2,2,3,2,2,2,2,2,2,3,2,2,2,2,2,2,3,2,2,2,2,2,2],
                "tile_grid": 'wall_sprite', "map_tg": True, "tile_w": 14, "tile_h": 6, "grid_w": 23, "grid_h": 40, "x": 0, "y": 32
            },
            "bomb":  {
                "bitmap": 'bomb', "w": 8, "h": 12, "p": 16,
                "value_map": [0,0,0,0,0,0,8,0,0,0,0,0,0,14,0,0,0,0,0,0,14,0,0,0,0,0,0,14,0,0,0,0,0,0,4,4,4,4,0,0,0,4,4,4,4,4,4,0,4,4,4,4,4,4,4,4,14,14,14,14,14,14,14,14,14,14,14,14,14,14,14,14,4,4,4,4,4,4,4,4,0,4,4,4,4,4,4,0,0,0,4,4,4,4,0,0],
                "tile_grid": "bomb_sprite", "map_tg": False, "tile_w": 8, "tile_h": 12, "grid_w": 1, "grid_h": 1, "x" : 0, "y" : 0
            },
            "bucket3":  {
                "bitmap": 'bucket3', "w": 12, "h": 12, "p": 16,
                "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,12,0,12,0,12,0,12,0,12,0,12,12,0,12,0,12,0,12,0,12,0,12,0,0,11,0,11,0,11,0,11,0,11,0,11,11,0,11,0,11,0,11,0,11,0,11,0,0,9,0,9,0,9,0,9,0,9,0,9,9,0,9,0,9,0,9,0,9,0,9,0,5,6,5,6,5,6,5,6,5,6,5,0,5,5,5,5,5,5,5,5,5,5,5,0,5,5,5,5,5,5,5,5,5,5,5,0],
                "tile_grid": 'bucket_sprite_3', "map_tg": False, "tile_w": 12, "tile_h": 12, "grid_w": 1, "grid_h": 3, "x": 0, "y": 0
            },
            "bucket2":  {
                "bitmap": 'bucket2', "w": 12, "h": 12, "p": 16,
                "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,12,0,12,0,12,0,12,0,12,0,12,12,0,12,0,12,0,12,0,12,0,12,0,0,11,0,11,0,11,0,11,0,11,0,11,11,0,11,0,11,0,11,0,11,0,11,0,0,9,0,9,0,9,0,9,0,9,0,9,9,0,9,0,9,0,9,0,9,0,9,0,5,6,5,6,5,6,5,6,5,6,5,0,5,5,5,5,5,5,5,5,5,5,5,0,5,5,5,5,5,5,5,5,5,5,5,0],
                "tile_grid": 'bucket_sprite_2', "map_tg": False, "tile_w": 12, "tile_h": 12, "grid_w": 1, "grid_h": 2, "x": 0, "y": 0
            },
            "bucket1":  {
                "bitmap": 'bucket1', "w": 12, "h": 12, "p": 16,
                "value_map": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,12,0,12,0,12,0,12,0,12,0,12,12,0,12,0,12,0,12,0,12,0,12,0,0,11,0,11,0,11,0,11,0,11,0,11,11,0,11,0,11,0,11,0,11,0,11,0,0,9,0,9,0,9,0,9,0,9,0,9,9,0,9,0,9,0,9,0,9,0,9,0,5,6,5,6,5,6,5,6,5,6,5,0,5,5,5,5,5,5,5,5,5,5,5,0,5,5,5,5,5,5,5,5,5,5,5,0],
                "tile_grid": 'bucket_sprite_1', "map_tg": False, "tile_w": 12, "tile_h": 12, "grid_w": 1, "grid_h": 1, "x": 0, "y": 0
            },
            "sad_baddy":  {
                "bitmap": 'sad_baddy', "w": 12, "h": 23, "p": 16,
                "value_map": [0,0,0,0,4,4,4,4,0,0,0,0,0,0,0,4,4,4,4,4,4,0,0,0,0,0,4,4,4,4,4,4,4,4,0,0,0,4,4,4,4,4,4,4,4,4,4,0,0,0,4,4,4,4,4,4,4,4,0,0,0,0,4,4,7,4,4,7,4,4,0,0,0,0,4,4,4,4,4,4,4,4,0,0,0,0,13,13,13,13,13,13,13,13,0,0,0,0,13,13,13,2,2,13,13,13,0,0,0,0,13,13,2,13,13,2,13,13,0,0,0,0,0,13,13,13,13,13,13,0,0,0,0,0,0,0,0,13,13,0,0,0,0,0,0,4,4,4,4,4,4,4,4,4,4,0,0,1,1,1,1,1,1,1,1,1,1,0,4,4,4,4,4,4,4,4,4,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,4,4,4,4,4,4,4,4,4,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,4,4,3,4,4,4,4,4,4,3,4,4,1,1,3,1,1,1,1,1,1,3,1,1,4,4,3,4,4,4,4,4,4,3,4,4,13,13,3,1,1,1,1,1,1,3,13,13,13,13,3,4,4,4,4,4,4,3,13,13],
                "tile_grid": 'tg_sad_pybomber', "map_tg": False, "tile_w": 12, "tile_h": 23, "grid_w": 1, "grid_h": 1, "x": 0, "y": 0
            },
            "happy_baddy":  {
                "bitmap": 'happy_baddy', "w": 12, "h": 23, "p": 16,
                "value_map": [0,0,0,0,4,4,4,4,0,0,0,0,0,0,0,4,4,4,4,4,4,0,0,0,0,0,4,4,4,4,4,4,4,4,0,0,0,4,4,4,4,4,4,4,4,4,4,0,0,0,4,4,4,4,4,4,4,4,0,0,0,0,4,4,7,4,4,7,4,4,0,0,0,0,4,4,4,4,4,4,4,4,0,0,0,0,13,13,13,13,13,13,13,13,0,0,0,0,13,13,2,13,13,2,13,13,0,0,0,0,13,13,13,2,2,13,13,13,0,0,0,0,0,13,13,13,13,13,13,0,0,0,0,0,0,0,0,13,13,0,0,0,0,0,0,4,4,4,4,4,4,4,4,4,4,0,0,1,1,1,1,1,1,1,1,1,1,0,4,4,4,4,4,4,4,4,4,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,4,4,4,4,4,4,4,4,4,4,4,4,1,1,1,1,1,1,1,1,1,1,1,1,4,4,3,4,4,4,4,4,4,3,4,4,1,1,3,1,1,1,1,1,1,3,1,1,4,4,3,4,4,4,4,4,4,3,4,4,13,13,3,1,1,1,1,1,1,3,13,13,13,13,3,4,4,4,4,4,4,3,13,13],
                "tile_grid": 'tg_happy_pybomber', "map_tg": False, "tile_w": 12, "tile_h": 23, "grid_w": 1, "grid_h": 1, "x": 0, "y": 0
            },
            "surprised_baddy": {
                "bitmap": 'surprised_baddy', "w": 12, "h": 23, "p": 16,
                "value_map": [
                    0,0,0,0,4,4,4,4,0,0,0,0,
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
                    13,13,3,4,4,4,4,4,4,3,13,13
                ],
                "tile_grid": 'tg_surprised_pybomber', "map_tg": False, "tile_w": 12, "tile_h": 23, "grid_w": 1, "grid_h": 1, "x": 0, "y": 0
            },
            "explosion":  {
                "bitmap": 'explosion', "w": 16, "h": 16, "p": 16,
                "value_map": [0,0,15,15,10,10,15,15,15,15,10,10,15,15,0,0,0,15,10,10,15,15,10,10,10,10,15,15,10,10,15,0,15,10,15,15,10,10,15,15,15,15,10,10,15,15,10,15,15,10,15,10,15,15,10,10,10,10,15,15,10,15,10,15,10,15,10,15,10,15,15,10,15,10,15,10,15,10,10,15,10,15,15,10,15,10,10,15,10,15,15,10,15,10,15,10,15,10,15,10,15,10,10,15,10,15,10,15,10,15,15,10,10,10,15,10,15,10,10,15,10,15,10,10,10,15,15,10,10,10,15,10,15,10,10,15,10,15,10,10,10,15,15,10,15,10,15,10,15,10,15,10,10,15,10,15,10,15,10,15,10,15,10,15,15,10,15,10,10,15,10,15,15,10,15,10,10,15,10,15,10,15,10,15,15,10,15,10,15,10,15,10,15,10,15,10,15,15,10,10,10,10,15,15,10,15,10,15,15,10,15,15,10,10,15,15,15,15,10,10,15,15,10,15,0,15,10,10,15,15,10,10,10,10,15,15,10,10,15,0,0,0,15,15,10,10,15,15,15,15,10,10,15,15,0,0],
                "tile_grid": 'explosion_sprite', "map_tg": False, "tile_w": 16, "tile_h": 16, "grid_w": 1, "grid_h": 1, "x": 0, "y": 0
            }
        }
        gc.collect()

    def _setup_palette(self):
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
        
        # Fix for splash bug: Make splash palette entries transparent by default
        pallette.make_transparent(9)
        pallette.make_transparent(11)
        pallette.make_transparent(12)
        
        gc.collect()
        return pallette

    def _map_values_to_bitmap(self, bitmap, value_map, w, h):
        for y in range(h):
            for x in range(w):
                idx = y * w + x
                if idx < len(value_map):
                    try:
                        value = int(value_map[idx])
                    except (ValueError, TypeError):
                        value = 0
                else:
                    # Fall back to transparent / empty if the value_map is shorter than w*h
                    value = 0
                bitmap[x, y] = value

    def _map_bitmap_to_tilegrid(self, tilegrid, item, w, h):
        # iterate full grid width/height (0..w-1, 0..h-1)
        for y in range(h):
            for x in range(w):
                tilegrid[x, y] = item

    def create_sprite(self, sprite_name, new_x=None, new_y=None):
        sprite_data = self.SPRITES.get(sprite_name)
        if not sprite_data:
            raise ValueError(f"Sprite '{sprite_name}' not found.")

        w, h, p = sprite_data["w"], sprite_data["h"], sprite_data["p"]
        value_map = sprite_data["value_map"]
        map_tg = sprite_data["map_tg"]
        tile_w, tile_h = sprite_data["tile_w"], sprite_data["tile_h"]
        grid_w, grid_h = sprite_data["grid_w"], sprite_data["grid_h"]

        x = new_x if new_x is not None else sprite_data["x"]
        y = new_y if new_y is not None else sprite_data["y"]

        bitmap = Bitmap(w, h, p)
        self._map_values_to_bitmap(bitmap, value_map, w, h)
        tile_grid = TileGrid(bitmap, pixel_shader=self.palette,
                             width=grid_w, height=grid_h,
                             tile_width=tile_w, tile_height=tile_h,
                             x=x, y=y)
        if map_tg:
            # pass the full grid dimensions (not -1) to fill the tile grid
            self._map_bitmap_to_tilegrid(tile_grid, 0, grid_w, grid_h)
        return tile_grid

# --- Player Class (P1 - Bucket) ---
class Player:
    def __init__(self, sprite_manager, main_group, scale, display):
        self.sprite_manager = sprite_manager
        self.main_group = main_group
        self.scale = scale
        self.display = display
        self.bucket_count = MAX_BUCKETS

        self.sprite = self.sprite_manager.create_sprite("bucket3")

        bx = self.display.width // 2 - (self.sprite.tile_width * self.sprite.width * self.scale) // 2
        by = BUCKET_TOP_Y

        self.group = Group(scale=self.scale, x=bx, y=by)
        self.group.append(self.sprite)
        self.main_group.append(self.group)

    def set_buckets(self, count):
        self.bucket_count = count
        if self.sprite in self.group:
            self.group.remove(self.sprite)

        if self.bucket_count == 3:
            self.sprite = self.sprite_manager.create_sprite("bucket3")
        elif self.bucket_count == 2:
            self.sprite = self.sprite_manager.create_sprite("bucket2")
        elif self.bucket_count == 1:
            self.sprite = self.sprite_manager.create_sprite("bucket1")

        self.group.append(self.sprite)

        # Recenter
        bx = self.display.width // 2 - (self.sprite.tile_width * self.sprite.width * self.scale) // 2
        self.group.x = bx

    def move(self, direction_char):
        bucket_move = False
        bucket_x = self.group.x

        if direction_char in ("a", "A"):
            bucket_x -= self.sprite.tile_width * self.scale
            bucket_move = True
        if direction_char in ("d", "D"):
            bucket_x += self.sprite.tile_width * self.scale
            bucket_move = True

        if bucket_move:
            if bucket_x <= 0:
                bucket_x = 0
            elif bucket_x > self.display.width - (self.sprite.tile_width * self.scale):
                bucket_x = self.display.width - (self.sprite.tile_width * self.scale)

            self.group.x = bucket_x

    def get_rect(self):
        # Return collision rectangle
        bucket_left = self.group.x
        bucket_right = self.group.x + (self.sprite.tile_width * self.sprite.width * self.scale)
        bucket_top = self.group.y + 20
        bucket_bottom = self.group.y + (self.sprite.tile_height * self.sprite.height * self.scale)
        return (bucket_left, bucket_top, bucket_right, bucket_bottom)

    def hide(self):
        self.group.hidden = True

    def show(self):
        self.group.hidden = False

    def reset(self):
        self.set_buckets(MAX_BUCKETS)
        self.hide() # Was self.show()

# --- Bomber Class (P2 - Bomber) ---
class Bomber:
    def __init__(self, sprite_manager, main_group, scale, display):
        self.sprite_manager = sprite_manager
        self.main_group = main_group
        self.scale = scale
        self.display = display

        self.sad_sprite = self.sprite_manager.create_sprite("sad_baddy")
        self.happy_sprite = self.sprite_manager.create_sprite("happy_baddy")
        self.surprised_sprite = self.sprite_manager.create_sprite("surprised_baddy")

        self.start_x = 10
        self.start_y = 4

        self.group = Group(scale=self.scale)
        self.group.append(self.sad_sprite)
        self.main_group.append(self.group)

        self.width = 16 # From old enemy_width
        self.move_step = 2 # Default move speed, will be set by level
        
        # --- Add back AI variables ---
        self.direction = 1
        self.move_timer = 0
        self.change_timer = 0
        # self.direction_change is set in update()

        self.reset()

    def reset(self):
        self.group.x = self.start_x
        self.group.y = self.start_y
        self.set_state("sad")
        # --- Reset AI variables ---
        self.direction = 1
        self.move_timer = 0
        self.change_timer = 0

    def set_state(self, state):
        if self.sad_sprite in self.group:
            self.group.remove(self.sad_sprite)
        if self.happy_sprite in self.group:
            self.group.remove(self.happy_sprite)
        if self.surprised_sprite in self.group:
            self.group.remove(self.surprised_sprite)

        if state == "sad":
            self.group.append(self.sad_sprite)
        elif state == "happy":
            self.group.append(self.happy_sprite)
        elif state == "surprised":
            self.group.append(self.surprised_sprite)

    def move(self, direction_key):
        """Move the bomber based on player input."""
        bomber_x = self.group.x
        
        if direction_key == 'left':
            bomber_x -= self.move_step
        elif direction_key == 'right':
            bomber_x += self.move_step
            
        # Clamp position to screen edges
        if bomber_x <= 8: # Left wall
            bomber_x = 8
        elif bomber_x >= self.display.width - (self.width * self.scale): # Right wall
            bomber_x = self.display.width - (self.width * self.scale)
            
        self.group.x = bomber_x

    def update(self, speed, step, change_lb, change_ub):
        """AI update logic for 1-Player mode."""
        self.move_timer += 1 / 100
        self.change_timer += 1 / 100

        # Initialize direction_change if it hasn't been set yet
        if not hasattr(self, 'direction_change') or self.direction_change == 0:
            if change_lb >= change_ub:
                 self.direction_change = change_lb # Avoid error if lb >= ub
            else:
                 self.direction_change = random.randint(change_lb, change_ub)


        if self.move_timer >= speed / 100:
            self.move_timer = 0

            self.group.x += step * self.direction

            if (self.group.x <= 8 and self.direction < 0) or \
               (self.group.x >= self.display.width - (self.width * self.scale) and self.direction > 0):
                self.direction *= -1
                self.change_timer = 0
                # Also reset direction_change when hitting wall
                if change_lb >= change_ub:
                    self.direction_change = change_lb
                else:
                    self.direction_change = random.randint(change_lb, change_ub)

            # Correctly use self.direction_change, not the parameter
            if self.change_timer >= self.direction_change / 100:
                self.direction *= -1
                self.change_timer = 0
                # Update self.direction_change with a new random value
                if change_lb >= change_ub:
                    self.direction_change = change_lb
                else:
                    self.direction_change = random.randint(change_lb, change_ub)

    def run_off_screen(self):
        while self.group.x < self.display.width:
            self.group.x += 5
            self.display.refresh()
            time.sleep(0.01)

# --- Bomb Class ---
class Bomb:
    def __init__(self, sprite_manager, main_group, x, y, scale):
        self.main_group = main_group
        self.sprite = sprite_manager.create_sprite("bomb", 0, 0)
        self.group = Group(scale=scale, x=x, y=y)
        self.group.append(self.sprite)
        self.main_group.append(self.group)
        self.scale = scale

    def update(self, drop_speed):
        self.group.y += drop_speed

    def get_rect(self):
        bomb_left = self.group.x
        bomb_right = self.group.x + (self.sprite.tile_width * self.scale)
        bomb_top = self.group.y
        bomb_bottom = self.group.y + (self.sprite.tile_height * self.scale)
        return (bomb_left, bomb_top, bomb_right, bomb_bottom)

    def is_off_screen(self, display_height):
        bomb_bottom = self.group.y + (self.sprite.tile_height * self.scale)
        return bomb_bottom > display_height

    def destroy(self):
        if self.group in self.main_group:
            self.main_group.remove(self.group)

# --- Main Game Class ---
class Game:
    def __init__(self, display):
        self.display = display
        self.scale = 2

        # Init core systems
        gc.collect()
        self.audio = Audio()
        self.sprite_manager = SpriteManager()
        self.font = terminalio.FONT
        
        # Create display groups
        self.main_group = Group()
        self.scaled_group = Group(scale=self.scale)
        self.main_group.append(self.scaled_group)

        self.text_group = Group(scale=2)
        
        self.title_text_group = Group(scale=1) # New group for small text
        self.main_group.append(self.title_text_group)
        self.title_text_group.hidden = True

        # Setup background (BLUE)
        bg_bmp = Bitmap(16, 12, 1)
        bg_palette = Palette(1)
        bg_palette[0] = 0x87F2FF
        bg_tilegrid = TileGrid(bg_bmp, pixel_shader=bg_palette)
        self.bg_group = Group(scale=10) # Store as self.bg_group
        self.bg_group.append(bg_tilegrid)
        self.scaled_group.append(self.bg_group) # Add to scaled_group
        self.bg_group.hidden = True # Hide by default

        # Setup wall (GAMEPLAY)
        self.wall_group = Group(scale=self.scale) # Store as self.wall_group
        self.wall_group.append(self.sprite_manager.create_sprite("top_wall"))
        self.wall_group.append(self.sprite_manager.create_sprite("wall"))
        self.main_group.append(self.wall_group)
        self.wall_group.hidden = True # Hide by default

        # Setup Title Screen Background (FULLSCREEN WALL)
        self.title_bg_group = Group(scale=self.scale) # Apply scale
        try:
            # Manually create the wall bitmap
            wall_sprite_data = self.sprite_manager.SPRITES.get("wall")
            wall_w, wall_h, wall_p = wall_sprite_data["w"], wall_sprite_data["h"], wall_sprite_data["p"]
            wall_value_map = wall_sprite_data["value_map"]
            wall_tile_w, wall_tile_h = wall_sprite_data["tile_w"], wall_sprite_data["tile_h"]
            
            wall_bitmap = Bitmap(wall_w, wall_h, wall_p)
            self.sprite_manager._map_values_to_bitmap(wall_bitmap, wall_value_map, wall_w, wall_h)
            
            # Calculate tiles needed to fill 320x240
            scaled_tile_w = wall_tile_w * self.scale
            scaled_tile_h = wall_tile_h * self.scale
            bg_tiles_w = (self.display.width + scaled_tile_w - 1) // scaled_tile_w
            bg_tiles_h = (self.display.height + scaled_tile_h - 1) // scaled_tile_h
            
            title_wall_tg = TileGrid(wall_bitmap, pixel_shader=self.sprite_manager.palette,
                                     width=bg_tiles_w, height=bg_tiles_h,
                                     tile_width=wall_tile_w, tile_height=wall_tile_h,
                                     x=0, y=0)
            
            self.sprite_manager._map_bitmap_to_tilegrid(title_wall_tg, 0, bg_tiles_w, bg_tiles_h)
            
            self.title_bg_group.append(title_wall_tg)
            self.main_group.append(self.title_bg_group)
            self.title_bg_group.hidden = False # Show by default
        
        except Exception as e:
            print(f"Error creating title background: {e}")
            # Fallback in case "wall" sprite is missing
            self.main_group.append(self.title_bg_group) # Add empty group


        # Setup score display
        self.score_area = Label(self.font, text="       0", color=self.sprite_manager.palette[10], x=(display.width // 2) - 50, y=6)
        self.text_group.append(self.score_area)
        
        # --- Setup Ready Labels ---
        self.p1_ready_label = Label(self.font, text="P1: PRESS START", color=0xFFFFFF, x=10, y=60)
        self.p1_ready_label.hidden = True
        self.text_group.append(self.p1_ready_label)

        self.p2_ready_label = Label(self.font, text="P2: PRESS START", color=0xFFFFFF, x=10, y=80)
        self.p2_ready_label.hidden = True
        self.text_group.append(self.p2_ready_label)
        
        # --- Setup Mode Select Labels ---
        # Centered x for 24 chars at scale 1: (320 - (24 * 6)) // 2 = 88
        self.p1_mode_label = Label(self.font, text="PRESS '1' FOR 1-PLAYER", color=0xFFF700, x=88, y=190)
        self.p1_mode_label.hidden = True
        self.title_text_group.append(self.p1_mode_label) # Add to new group

        self.p2_mode_label = Label(self.font, text="PRESS '2' FOR 2-PLAYER", color=0xFFF700, x=88, y=205)
        self.p2_mode_label.hidden = True
        self.title_text_group.append(self.p2_mode_label) # Add to new group

        self.main_group.append(self.text_group)
        self.text_group.hidden = True # Hide by default

        # Create game objects
        self.player = Player(self.sprite_manager, self.main_group, self.scale, self.display)
        self.player.hide() # Hide by default
        self.bomber = Bomber(self.sprite_manager, self.main_group, self.scale, self.display)
        self.bomber.group.hidden = True # Hide by default

        # --- Setup Title Screen Logo ---
        self.title_group = Group()
        try:
            # Load the bitmap from the file
            title_bitmap = OnDiskBitmap('pyboom.bmp') # Use the new filename

            # Create a palette to key out the green background
            # 0x00FF00 is the bright green in the image
            title_palette = Palette(2)
            title_palette[1] = 0xFF00D0 # The green background
            title_palette[0] = 0x78DC52 # The NEW bright green text (was 0xFF0000)
            title_palette.make_transparent(1) # Make the green transparent

            # Create the sprite
            title_sprite = TileGrid(title_bitmap,
                                      pixel_shader=title_palette,
                                      x=0, y=0) # We set x/y later
            
            # Calculate position to center the 160x120 bitmap
            center_x = (self.display.width - title_bitmap.width) // 2
            center_y = (self.display.height - title_bitmap.height) // 2
            
            self.title_group.x = center_x
            self.title_group.y = center_y
            self.title_group.append(title_sprite)
            self.title_group.hidden = True # Hide by default for animation

        except (OSError, TypeError) as e:
            # This is a fallback in case the 'pyboom.bmp' file is missing
            print(f"Failed to load title screen: {e}")
            fallback_label = Label(self.font, text="PYBOOM!", color=0x78DC52, scale=5)
            fallback_label.x = (self.display.width - fallback_label.bounding_box[2]) // (2 * self.scale) # Adjust for text_group scale
            fallback_label.y = (self.display.height - fallback_label.bounding_box[3]) // (2 * self.scale) # Adjust for text_group scale
            self.text_group.append(fallback_label) # Add to text_group as fallback
            # We don't hide the text_group here, so fallback is visible

        self.main_group.append(self.title_group)
        gc.collect()

        # --- Title Animation ---
        self.title_animation_state = TITLE_ANIM_START
        self.title_anim_bomb = None
        self.title_anim_explosion = None
        self.title_explosion_timer = 0
        
        # Pre-calculate target X/Y
        # Target X: Center of screen minus half of 5x scaled bomb width (8px)
        self.title_target_x = (self.display.width // 2) - ((8 * 5) // 2)
        # Target Y: Center of screen minus half of 5x scaled bomb height (12px)
        self.title_target_y = (self.display.height // 2) - ((12 * 5) // 2)

        # Init game state variables
        self.game_state = STATE_TITLE # Start at the title screen
        self.game_mode = 0 # 0 = Not Selected, 1 = 1P, 2 = 2P
        self.bombs = []
        self.params = {}
        self.splash = False
        self.splash_count = 0

        self.high_score = 0
        self.game_win = False

        # Set level params from attributes
        self.drop_speed = 0
        self.bombs_dropped = 0
        self.bomb_score = 0
        self.bomb_count = 0
        # --- Add back AI variables ---
        self.bomber_speed = 0
        self.drop_interval = 0
        self.enemy_step = 0 # Now P2 move speed
 
        # 2-Player Ready State
        self.p1_ready = False
        self.p2_ready = False
        
        # ANSI escape sequence buffer for arrow keys
        self.key_buffer = ""

        self.reset_game()
        gc.collect()

    def set_level_params(self, level):
        level_key = level
        if level > 8:
            level_key = 8

        self.params = LEVELS.get(level_key)
        self.drop_speed = self.params["drop_speed"]
        self.bombs_dropped = 0
        self.bomb_score = self.params["bombScore"]
        self.bomb_count = self.params["bombCount"]
        self.enemy_step = self.params["enemy_step"]
        
        # --- Add back AI variables ---
        self.bomber_speed = self.params["bomberSpeed"]
        if self.params["dropIntervalLB"] >= self.params["dropIntervalUB"]:
            self.drop_interval = self.params["dropIntervalLB"]
        else:
            self.drop_interval = random.randint(self.params["dropIntervalLB"], self.params["dropIntervalUB"])
        
        # Set bomber (P2) speed
        self.bomber.move_step = self.enemy_step
        
        print("Level:", level, self.params)
        gc.collect()

    def reset_game(self):
        self.score = 0
        self.current_level = DEBUG_START_LEVEL
        self.set_level_params(self.current_level)

        self.player.reset()
        self.bomber.reset()

        for bomb in self.bombs:
            bomb.destroy()
        self.bombs.clear()

        self.bombs_dropped = 0
        self.bomb_drop_timer = 0 # Used for P2 bomb drop rate limiting / AI

        self.next_extra_life = MAX_LIFE_INTERVAL
        self.surprised_baddy_triggered = False
        self.game_win = False
        self.title_text_group.hidden = True # Hide new group
        
        # Reset ready state
        self.p1_ready = False
        self.p2_ready = False
        self.p1_ready_label.text = "P1: PRESS START"
        self.p1_ready_label.color = 0xFFFFFF
        self.p2_ready_label.text = "P2: PRESS START"
        self.p2_ready_label.color = 0xFFFFFF
        self.p1_ready_label.hidden = True
        self.p2_ready_label.hidden = True
        
        # Hide mode select labels
        self.p1_mode_label.hidden = True
        self.p2_mode_label.hidden = True
        
        # Clear old game over/win labels
        # This is safer than popping
        for i in range(len(self.text_group) - 1, -1, -1):
            item = self.text_group[i]
            if item not in (self.score_area, self.p1_ready_label, self.p2_ready_label, self.p1_mode_label, self.p2_mode_label):
                self.text_group.pop(i)

        self.score_area.text = f"{int(self.score):>8}"
        # We don't make score_area visible here,
        # we do it when the game starts
        gc.collect()

    def spawn_bomb(self):
        # --- Simplified: AI and P2 logic will check *before* calling ---
        if self.bombs_dropped >= self.bomb_count:
            return

        drop_bomb_x = self.bomber.group.x
        drop_bomb_y = self.bomber.group.y * self.scale + 17 # 17 was bomb_start_y

        new_bomb = Bomb(self.sprite_manager, self.main_group, drop_bomb_x, drop_bomb_y, self.scale)
        self.bombs.append(new_bomb)
        self.bombs_dropped += 1
        print(f"bomb_sprite_{self.bombs_dropped - 1}") # Match log output
            
    def update_bombs(self):
        player_rect = self.player.get_rect()
        player_l, player_t, player_r, player_b = player_rect

        for bomb in self.bombs[:]: # Iterate over a copy
            bomb.update(self.drop_speed)

            bomb_l, bomb_t, bomb_r, bomb_b = bomb.get_rect()

            # Check for collision
            x_collision = (bomb_r >= player_l and bomb_l <= player_r)
            y_collision = (bomb_b >= player_t and bomb_t <= player_b)

            if x_collision and y_collision:
                bomb.destroy()
                self.bombs.remove(bomb)
                self.splash = True
                self.score += self.bomb_score
                self.score_area.text = f"{int(self.score):>8}"
                self.audio.play(self.audio.sound_catch)

                if self.score >= 100000:
                    self.game_win = True
                    self.game_state = STATE_GAME_OVER
                    return

                if self.score >= self.next_extra_life:
                    self.next_extra_life += MAX_LIFE_INTERVAL
                    if self.player.bucket_count < MAX_BUCKETS:
                        new_count = self.player.bucket_count + 1
                        self.player.set_buckets(new_count)

                if not self.surprised_baddy_triggered and self.score >= 10000:
                    self.bomber.set_state("surprised")
                    self.surprised_baddy_triggered = True

                continue # Go to next bomb

            if bomb.is_off_screen(self.display.height):
                self.audio.play(self.audio.sound_miss)
                self.game_state = STATE_PAUSED
                self.success_state = False
                return # Exit update_bombs

    def bomb_flicker(self):
        pal = self.sprite_manager.palette
        if pal[8] == pal[14]:
            pal[8] = pal[10]
        elif pal[8] == pal[10]:
            pal[8] = pal[15]
        elif pal[8] == pal[15]:
            pal[8] = pal[14]

    def bucket_splash(self, is_splash):
        pal = self.sprite_manager.palette
        if not is_splash:
            self.splash_count = 0
            # Note: We no longer need to modify the palette here
            # because it's set to transparent by default in _setup_palette
            return

        if is_splash:
            if self.splash_count < 10:
                pal.make_opaque(9)
                self.splash_count += 1
            elif self.splash_count < 20:
                pal.make_transparent(9)
                pal.make_opaque(11)
                self.splash_count += 1
            elif self.splash_count < 30:
                pal.make_transparent(11)
                pal.make_opaque(12)
                self.splash_count += 1
            elif self.splash_count > 29:
                pal.make_transparent(12)
                self.splash_count = 0
                self.splash = False
    
    def process_keyboard_input(self, cur_btn_val):
        """Processes raw keyboard input, including ANSI for arrow keys."""
        if not cur_btn_val:
            return

        self.key_buffer += cur_btn_val

        # --- Simple Keys (P1) ---
        if 'a' in self.key_buffer or 'A' in self.key_buffer:
            if self.game_state == STATE_PLAYING:
                self.player.move('a')
        
        if 'd' in self.key_buffer or 'D' in self.key_buffer:
             if self.game_state == STATE_PLAYING:
                self.player.move('d')
        
        if ' ' in self.key_buffer:
            if self.game_state == STATE_TITLE:
                pass # P1 'start' (space) no longer used on title
            elif self.game_state == STATE_READY:
                self.p1_ready = True
            elif self.game_state == STATE_PAUSED:
                self.resume_game_from_pause()

        if '\r' in self.key_buffer or '\n' in self.key_buffer: # Enter key (Check for \r and \n)
            if self.game_state == STATE_TITLE:
                pass # P2 'start' (enter) no longer used on title
            elif self.game_state == STATE_READY and self.game_mode == 2:
                self.p2_ready = True
        
        if 'r' in self.key_buffer or 'R' in self.key_buffer:
             if self.game_state == STATE_GAME_OVER:
                self.reset_game_from_game_over()

        # --- Mode Select Keys ---
        if '1' in self.key_buffer and self.game_state == STATE_TITLE:
            self.game_mode = 1
            self.start_game_from_title()

        if '2' in self.key_buffer and self.game_state == STATE_TITLE:
            self.game_mode = 2
            self.start_game_from_title()

        # --- Arrow Keys (P2) ---
        # Look for escape sequences
        
        # Left: \x1b[D
        if '\x1b[D' in self.key_buffer and self.game_mode == 2:
            if self.game_state == STATE_PLAYING:
                self.bomber.move('left')
            self.key_buffer = self.key_buffer.replace('\x1b[D', '')
            
        # Right: \x1b[C
        if '\x1b[C' in self.key_buffer and self.game_mode == 2:
            if self.game_state == STATE_PLAYING:
                self.bomber.move('right')
            self.key_buffer = self.key_buffer.replace('\x1b[C', '')
        
        # Down: \x1b[B
        if '\x1b[B' in self.key_buffer and self.game_mode == 2:
            if self.game_state == STATE_PLAYING:
                # P2 bomb drop logic
                if self.bombs_dropped < self.bomb_count and self.bomb_drop_timer <= 0:
                    self.spawn_bomb()
                    self.bomb_drop_timer = 50 # Set P2 rate limit
            self.key_buffer = self.key_buffer.replace('\x1b[B', '')
        
        # Up: \x1b[A (unused, but good to clear)
        if '\x1b[A' in self.key_buffer:
            self.key_buffer = self.key_buffer.replace('\x1b[A', '')

        # Clear buffer if it gets too large or has no escape chars
        if (len(self.key_buffer) > 10 and '\x1b' not in self.key_buffer) or \
           len(self.key_buffer) > 20:
            self.key_buffer = ""
        
        # Clean out non-escape-related parts
        if '\x1b' not in self.key_buffer:
            self.key_buffer = ""


    def handle_gameplay_input(self):
        """Handles input only for the PLAYING state."""
        available = supervisor.runtime.serial_bytes_available
        cur_btn_val = sys.stdin.read(available) if available else None
        self.process_keyboard_input(cur_btn_val)
            
    def handle_title_input(self):
        """Handles input for the TITLE screen (non-blocking).."""
        available = supervisor.runtime.serial_bytes_available
        cur_btn_val = sys.stdin.read(available) if available else None
        self.process_keyboard_input(cur_btn_val)
        # Action is handled by ' ' or '\r' in process_keyboard_input

    def start_game_from_title(self):
        """Transition from TITLE to READY."""
        self.audio.play(self.audio.sound_start)
        self.title_group.hidden = True # Hide title logo
        self.title_bg_group.hidden = True # Hide title wall background
        
        # Hide mode select labels
        self.title_text_group.hidden = True
        
        # Show all game elements for the "Ready" state
        self.bg_group.hidden = False # Show blue background
        self.wall_group.hidden = False # Show gameplay walls
        self.text_group.hidden = False # Ensure group is visible
        self.score_area.hidden = False # Show score
        self.player.show()
        self.bomber.group.hidden = False
        
        # Show ready labels
        self.p1_ready_label.hidden = False
        if self.game_mode == 2:
            self.p2_ready_label.hidden = False

        self.game_state = STATE_READY

    def handle_ready_input(self):
        """Handles input for the READY screen (non-blocking)."""
        available = supervisor.runtime.serial_bytes_available
        cur_btn_val = sys.stdin.read(available) if available else None
        self.process_keyboard_input(cur_btn_val)
        
        # Update UI based on ready state
        if self.p1_ready:
            self.p1_ready_label.text = "P1: READY!"
            self.p1_ready_label.color = 0x78DC52 # Green
            
        if self.game_mode == 2 and self.p2_ready:
            self.p2_ready_label.text = "P2: READY!"
            self.p2_ready_label.color = 0x78DC52 # Green
        
        # Check if ready to start
        start_game = False
        if self.game_mode == 1 and self.p1_ready:
            start_game = True
        elif self.game_mode == 2 and self.p1_ready and self.p2_ready:
            start_game = True
            
        if start_game:
            self.audio.play(self.audio.sound_start)
            
            # Hide ready labels
            self.p1_ready_label.hidden = True
            self.p2_ready_label.hidden = True
            
            self.game_state = STATE_PLAYING


    def handle_title_animation(self):
        """Runs the title screen animation sequence."""
        if self.title_animation_state == TITLE_ANIM_START:
            # Create a 5x scaled bomb
            bomb_sprite = self.sprite_manager.create_sprite("bomb", 0, 0)
            self.title_anim_bomb = Group(scale=5, x=self.title_target_x, y=-100) # Start off-screen
            self.title_anim_bomb.append(bomb_sprite)
            self.main_group.append(self.title_anim_bomb)
            self.title_animation_state = TITLE_ANIM_DROPPING
        
        elif self.title_animation_state == TITLE_ANIM_DROPPING:
            # Move the bomb down
            if self.title_anim_bomb.y < self.title_target_y:
                self.title_anim_bomb.y += 8 # Drop speed
            else:
                # Reached target, switch to exploding
                self.title_anim_bomb.y = self.title_target_y
                if self.title_anim_bomb in self.main_group:
                    self.main_group.remove(self.title_anim_bomb)
                self.title_anim_bomb = None
                
                # Create 5x scaled explosion
                exp_sprite = self.sprite_manager.create_sprite("explosion", 0, 0)
                # Target X: Center of screen minus half of 5x scaled explosion width (16px)
                exp_x = (self.display.width // 2) - ((16 * 5) // 2)
                # Target Y: Center of screen minus half of 5x scaled explosion height (16px)
                exp_y = (self.display.height // 2) - ((16 * 5) // 2)
                
                self.title_anim_explosion = Group(scale=5, x=exp_x, y=exp_y)
                self.title_anim_explosion.append(exp_sprite)
                self.main_group.append(self.title_anim_explosion)
                
                self.audio.play(self.audio.sound_miss) # Re-use a sound
                
                self.title_explosion_timer = 0
                self.title_animation_state = TITLE_ANIM_EXPLODING
        
        elif self.title_animation_state == TITLE_ANIM_EXPLODING:
            self.title_explosion_timer += 1
            if self.title_explosion_timer >= 60: # Show explosion for ~1 second (60 frames)
                # Clean up explosion
                if self.title_anim_explosion in self.main_group:
                    self.main_group.remove(self.title_anim_explosion)
                self.title_anim_explosion = None
                
                # Show the logo
                self.title_group.hidden = False
                
                # Show mode select labels
                self.text_group.hidden = True # Hide score/ready labels
                self.title_text_group.hidden = False # Show small text group
                self.p1_mode_label.hidden = False
                self.p2_mode_label.hidden = False
                
                # Animation is done
                self.title_animation_state = TITLE_ANIM_DONE

    def resume_game_from_pause(self):
        """Action to resume from pause (called by input)."""
        self.game_state = STATE_PLAYING
        self.audio.play(self.audio.sound_start)
        self.bomb_drop_timer = 0 # Reset bomb drop timer

    def handle_pause_state(self):
        if not self.success_state: # This is a failure (P1 miss) state
            self.audio.stop()

            # 1. Show explosions for all active bombs
            explosion_groups = []
            for bomb in self.bombs:
                exp_sprite = self.sprite_manager.create_sprite("explosion", 0, 0)
                exp_group = Group(scale=self.scale, x=bomb.group.x, y=bomb.group.y)
                exp_group.append(exp_sprite) # <-- THE FIX IS HERE
                self.main_group.append(exp_group)
                explosion_groups.append(exp_group)
                bomb.destroy() # Remove original bomb

            self.bombs.clear()

            # 2. Change bomber (P2) state to happy
            self.bomber.set_state("happy")

            # 3. Show explosions
            self.display.refresh()
            time.sleep(1)

            # 4. Clean up explosions
            for exp_group in explosion_groups:
                if exp_group in self.main_group:
                    self.main_group.remove(exp_group)

            # 5. Update game state
            new_bucket_count = self.player.bucket_count - 1
            if new_bucket_count <= 0:
                self.game_win = False # P1 loses
                self.game_state = STATE_GAME_OVER
                return # Exit to main loop

            self.player.set_buckets(new_bucket_count)

            # 6. Decrease level
            previous_bomb_count = self.bomb_count
            self.current_level -= 1
            if self.current_level < 1:
                self.current_level = 1

            self.set_level_params(self.current_level)

            # 7. Reset for next round
            self.success_state = True

            if self.surprised_baddy_triggered:
                self.bomber.set_state("surprised")
            else:
                self.bomber.set_state("sad")

            # Wait for user input to continue
            # This is still a blocking loop, which is fine for a pause state
            while True:
                available = supervisor.runtime.serial_bytes_available
                cur_btn_val = sys.stdin.read(available) if available else None
                self.process_keyboard_input(cur_btn_val)
                                
                # resume_game_from_pause() sets the state
                if self.game_state == STATE_PLAYING:
                    break
                    
                time.sleep(0.01)

    def handle_game_over(self):
        self.audio.stop()
        self.player.hide()
        self.bomber.group.hidden = True # Hide bomber
        self.score_area.hidden = True # Hide score, not the whole text_group

        # --- MOVED ---
        # Hide gameplay backgrounds
        self.bg_group.hidden = True
        self.wall_group.hidden = True
        
        # Show title background
        self.title_bg_group.hidden = False
        # --- END MOVE ---

        game_over_labels = []

        if self.game_win:
            win_text = "P1 (BUCKET) WINS!"
            label_x = (self.display.width - (len(win_text) * 6 * self.scale)) // (2 * self.scale)
            label_y = (self.display.height // 2) // self.scale - 10
            win_label = Label(self.font, text=win_text, color=self.sprite_manager.palette[10], x=label_x, y=label_y)
            self.text_group.append(win_label)
            game_over_labels.append(win_label)
        else:
            self.audio.play(self.audio.sound_game_over)
            
            if self.game_mode == 2:
                game_over_text = "P2 (BOMBER) WINS!"
            else:
                game_over_text = "GAME OVER"
                
            label_x = (self.display.width - (len(game_over_text) * 6 * self.scale)) // (2 * self.scale)
            label_y = (self.display.height // 2) // self.scale - 10
            game_over_label = Label(self.font, text=game_over_text, color=self.sprite_manager.palette[10], x=label_x, y=label_y)
            self.text_group.append(game_over_label)
            game_over_labels.append(game_over_label)

            # Create explosions
            explosion_groups = []
            wall_y_start = 25 * self.scale # From top_wall_sprite.y
            for _ in range(30):
                exp_x = random.randint(0, self.display.width - (16 * self.scale))
                exp_y = random.randint(wall_y_start, self.display.height - (16 * self.scale))
                exp_sprite = self.sprite_manager.create_sprite("explosion", 0, 0)
                exp_group = Group(scale=self.scale, x=exp_x, y=exp_y)
                exp_group.append(exp_sprite) # <-- ***** THE REAL FIX IS HERE *****
                self.main_group.append(exp_group)
                explosion_groups.append(exp_group)

            # Show explosions for 2 seconds using a non-blocking loop
            # to allow auto-refresh
            explosion_timer = 200 # 200 * (1/100) = 2 seconds
            while explosion_timer > 0:
                # We still need to poll for 'R' here in case
                # the user wants to skip the explosion display
                available = supervisor.runtime.serial_bytes_available
                cur_btn_val = sys.stdin.read(available) if available else None
                self.process_keyboard_input(cur_btn_val)
                if self.game_state != STATE_GAME_OVER:
                    break # User reset during explosions

                self.display.refresh()
                time.sleep(0.01) # THIS IS THE FIX
                explosion_timer -= 1
                
            
            if self.game_state != STATE_GAME_OVER:
                # Clean up explosions and exit if user reset
                for exp_group in explosion_groups:
                    if exp_group in self.main_group:
                        self.main_group.remove(exp_group)
                return # Exit handle_game_over

            for exp_group in explosion_groups:
                if exp_group in self.main_group:
                    self.main_group.remove(exp_group)

            # self.bomber.run_off_screen() # No longer run off screen

        # Handle Score Display
        score_label_y = (self.display.height // 2) // self.scale + 10
        if self.score > self.high_score:
            self.high_score = self.score
            score_text = f"New High: {self.score}"
            score_label = Label(self.font, text=score_text, color=self.sprite_manager.palette[10], x=10, y=score_label_y)
        else:
            score_text = f"Score: {self.score}"
            score_label = Label(self.font, text=score_text, color=self.sprite_manager.palette[1], x=10, y=score_label_y)

        self.text_group.append(score_label)
        game_over_labels.append(score_label)

        reset_text = "Press 'R' to Restart"
        label_x = (self.display.width - (len(reset_text) * 6 * self.scale)) // (2 * self.scale)
        label_y = score_label_y + 20
        reset_label = Label(self.font, text=reset_text, color=self.sprite_manager.palette[1], x=label_x, y=label_y)
        self.text_group.append(reset_label)
        game_over_labels.append(reset_label)

        # Make sure the game over text is visible
        self.text_group.hidden = False
        
        # Hide gameplay backgrounds
        # self.bg_group.hidden = True # <-- MOVED
        # self.wall_group.hidden = True # <-- MOVED
        
        # Show title background
        # self.title_bg_group.hidden = False # <-- MOVED
        
        self.display.refresh() # <-- ADDED REFRESH CALL

        # Wait for reset key
        while True:
            available = supervisor.runtime.serial_bytes_available
            cur_btn_val = sys.stdin.read(available) if available else None
            self.process_keyboard_input(cur_btn_val)

            # reset action is in process_keyboard_input
            if self.game_state == STATE_TITLE:
                break
            time.sleep(0.01) # Keep polling
            
    def reset_game_from_game_over(self):
        """Action to reset from game over (called by input)."""
        self.reset_game() # Resets scores, levels, and hides player
        
        # --- Reset for TITLE State ---
        self.game_state = STATE_TITLE
        self.game_mode = 0 # Reset mode selection
        
        # Hide all game over/gameplay elements
        self.title_group.hidden = False
        self.title_bg_group.hidden = False
        self.text_group.hidden = False # Show text group
        self.score_area.hidden = True  # Hide score
        self.player.hide()
        self.bomber.group.hidden = True
        self.bg_group.hidden = True
        self.wall_group.hidden = True
        
        # Show mode select labels
        self.title_text_group.hidden = False
        self.p1_mode_label.hidden = False
        self.p2_mode_label.hidden = False
        
        # We don't need to reset the animation, as we are not returning to Title


    def run(self):
        self.display.root_group = self.main_group

        while True:
            if self.game_state == STATE_TITLE:
                if self.title_animation_state != TITLE_ANIM_DONE:
                    self.handle_title_animation()
                else:
                    self.handle_title_input()

            elif self.game_state == STATE_READY:
                self.handle_ready_input() # This now handles P1/P2 ready state

            elif self.game_state == STATE_PAUSED:
                self.handle_pause_state()

            elif self.game_state == STATE_GAME_OVER:
                self.handle_game_over()

            elif self.game_state == STATE_PLAYING:
                # Level complete = Bomber ran out of bombs and all are off-screen
                level_complete = (self.bombs_dropped == self.bomb_count) and not self.bombs and not self.splash

                if not level_complete:
                    self.handle_gameplay_input() # Handles P1 and P2 (if 2P) input
                else:
                    # P1 (Bucket) WINS the round
                    self.audio.stop()
                    self.audio.play(self.audio.sound_level_up)
                    self.current_level += 1

                    for bomb in self.bombs:
                        bomb.destroy()
                    self.bombs.clear()
                    self.bombs_dropped = 0

                    self.set_level_params(self.current_level)
                    self.bomb_drop_timer = 0
                    
                    # Go back to READY state, reset player ready status
                    self.p1_ready = False
                    self.p2_ready = False
                    self.p1_ready_label.text = "P1: PRESS START"
                    self.p1_ready_label.color = 0xFFFFFF
                    self.p2_ready_label.text = "P2: PRESS START"
                    self.p2_ready_label.color = 0xFFFFFF
                    self.p1_ready_label.hidden = False
                    if self.game_mode == 2:
                        self.p2_ready_label.hidden = False
                    
                    self.game_state = STATE_READY 
                    continue

                # Update game logic
                if self.game_mode == 1:
                    # Call AI update
                    self.bomber.update(self.bomber_speed, self.enemy_step, self.params["directionChangeLB"], self.params["directionChangeUB"])
                
                self.bomb_flicker()
                
                # Tick down bomb drop rate limiter (for P2)
                if self.game_mode == 2:
                    if self.bomb_drop_timer > 0:
                        self.bomb_drop_timer -= 1
                elif self.game_mode == 1:
                    # AI Bomb Spawning Logic
                    if not self.bombs_dropped == self.bomb_count:
                        self.bomb_drop_timer += 1 / 100
                        if self.bombs_dropped == 0:
                            self.spawn_bomb()
                            self.bomb_drop_timer = 0
                            if self.params["dropIntervalLB"] >= self.params["dropIntervalUB"]:
                                self.drop_interval = self.params["dropIntervalLB"]
                            else:
                                self.drop_interval = random.randint(self.params["dropIntervalLB"], self.params["dropIntervalUB"])
                        elif self.bomb_drop_timer >= self.drop_interval / 100 and self.bombs_dropped < self.bomb_count:
                            self.bomb_drop_timer = 0
                            self.spawn_bomb()
                            if self.params["dropIntervalLB"] >= self.params["dropIntervalUB"]:
                                self.drop_interval = self.params["dropIntervalLB"]
                            else:
                                self.drop_interval = random.randint(self.params["dropIntervalLB"], self.params["dropIntervalUB"])

                # Spawn bombs (now handled by P2 input in process_keyboard_input or AI logic above)
 
                # Update bombs and splash
                self.update_bombs()
                self.bucket_splash(self.splash)

            #self.display.refresh() # <-- This was the slowdown, now commented out
            time.sleep(1/100)

# --- Main execution ---
if __name__ == "__main__":
    try:
        request_display_config(320,240)
        main_display = supervisor.runtime.display
    except (ImportError, AttributeError, OSError) as e:
        print(f"Could not request display: {e}")
        # Create a dummy display object if hardware fails
        class DummyDisplay:
            width = 320
            height = 240
            root_group = None
            def refresh(self):
                pass
        main_display = DummyDisplay()


    game = Game(main_display)
    game.run()

