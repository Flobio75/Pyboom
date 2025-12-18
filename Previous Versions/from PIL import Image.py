from PIL import Image

# Image dimensions
IMG_WIDTH = 64
IMG_HEIGHT = 64
SCALE = 5 # How much to scale the bomb up

# Palette colors (RGB tuples) extracted from your game's setup_palette()
# Index 0 is transparent, so we don't need it here.
PALETTE = {
    # 0: (Transparent)
    # 1: (255, 255, 255), # White
    # 2: (104, 3, 3),    # Dark Red
    3: (153, 153, 153), # Gray (for background)
    4: (0, 0, 0),       # Black (Bomb body)
    # 5: (227, 131, 89),  # Light Brown
    # 6: (20, 165, 255),   # Light Blue
    # 7: (120, 220, 82),  # Green
    8: (145, 70, 61),   # Brown (Fuse)
    # 9: (20, 165, 255),   # Light Blue
    # 10: (255, 247, 0),   # Yellow
    # 11: (20, 165, 255),  # Light Blue
    # 12: (20, 165, 255),  # Light Blue
    # 13: (229, 205, 196), # Light Gray/Tan
    14: (145, 70, 61),  # Brown (Bomb Shading) - Same as 8
    # 15: (255, 123, 0)    # Orange
}

# Bomb sprite data from your game code
BOMB_W = 8
BOMB_H = 12
BOMB_VALUE_MAP = [
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
    0,0,4,4,4,4,0,0
]

# Create a new 64x64 image with a gray background (Palette index 3)
background_color = PALETTE[3]
img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), color=background_color)

# Calculate dimensions and position for the *scaled* bomb
scaled_bomb_w = BOMB_W * SCALE
scaled_bomb_h = BOMB_H * SCALE
start_x = (IMG_WIDTH - scaled_bomb_w) // 2
start_y = (IMG_HEIGHT - scaled_bomb_h) // 2

# Draw the scaled bomb sprite onto the image
for y in range(BOMB_H):
    for x in range(BOMB_W):
        map_index = y * BOMB_W + x
        palette_index = BOMB_VALUE_MAP[map_index]

        # Skip transparent pixels (index 0)
        if palette_index != 0:
            color = PALETTE.get(palette_index)
            if color:
                # Draw a SCALE x SCALE block for each original pixel
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        img_x = start_x + (x * SCALE) + dx
                        img_y = start_y + (y * SCALE) + dy
                        
                        # Check bounds just in case
                        if 0 <= img_x < IMG_WIDTH and 0 <= img_y < IMG_HEIGHT:
                            img.putpixel((img_x, img_y), color)

# Save the image as a BMP file
try:
    img.save("bomb_icon.bmp")
    print("Successfully created bomb_icon.bmp (64x64 with 6x scaled bomb)")
except Exception as e:
    print(f"Error saving bitmap: {e}")