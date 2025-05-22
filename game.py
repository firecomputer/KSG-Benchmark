import pygame
import sys
import json
import random

# 0.33x of Total Image width and height
SCREEN_WIDTH = 551
SCREEN_HEIGHT = 964

white = (255, 255, 255)
black = (0, 0, 0)

pygame.init()
pygame.display.set_caption("Simple PyGame Example")
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

# Load black dot coordinates from the JSON file
try:
    with open('black_dot_coordinates.json', 'r') as f:
        black_dots_data = json.load(f)
except FileNotFoundError:
    print("Error: black_dot_coordinates.json not found.")
    black_dots_data = []
except json.JSONDecodeError:
    print("Error: Could not decode JSON from black_dot_coordinates.json.")
    black_dots_data = []

# Classes (Will be moved to another file)

class Tile:
    def __init__(self, x, y, is_black_dot=False):
        self.x = x
        self.y = y
        self.is_black_dot = is_black_dot
        # Add other tile properties here later, e.g., unit, terrain type, etc.


class Country:
    def __init__(self, tile_grid):
        self.startPos = random.randint(0, len(tile_grid))
        
        

# Create a 2D grid of Tile instances
# Initialize all tiles as not black dots
tile_grid = [[Tile(x, y) for y in range(SCREEN_HEIGHT)] for x in range(SCREEN_WIDTH)]

# Mark tiles that correspond to black dots
# Scale the black dot coordinates and mark the corresponding tile in the grid
for dot in black_dots_data:
    # Calculate the scaled coordinates, rounding to the nearest integer for tile mapping
    scaled_x = int(round(dot["x"] / 3))
    scaled_y = int(round(dot["y"] / 3))

    # Check if the scaled coordinates are within the screen bounds
    if 0 <= scaled_x < SCREEN_WIDTH and 0 <= scaled_y < SCREEN_HEIGHT:
        tile_grid[scaled_x][scaled_y].is_black_dot = True

# --- End New Code ---

# Game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Clear the screen
    screen.fill(white)

    # --- Modified Drawing Loop ---
    # Draw tiles based on their properties
    for x in range(SCREEN_WIDTH):
        for y in range(SCREEN_HEIGHT):
            tile = tile_grid[x][y]
            if tile.is_black_dot:
                # Draw a black pixel or a small circle for the black dot tile
                # Drawing a 1x1 pixel is equivalent to setting the pixel color
                screen.set_at((tile.x, tile.y), black)
            # else:
                # Optionally draw other tile types/colors here

    # --- End Modified Drawing Loop ---

    # Update the display
    pygame.display.flip()

pygame.quit()
sys.exit()
