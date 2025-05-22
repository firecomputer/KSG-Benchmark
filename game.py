import pygame
import sys
import json
import random
from copy import copy

# Conquest parameters
CONQUEST_POPULATION_THRESHOLD = 5000 # Minimum population required to attempt conquest
CONQUEST_GDP_COST = 3000 # GDP cost per conquered tile

# 0.33x of Total Image width and height
SCREEN_WIDTH = 551
SCREEN_HEIGHT = 964

REAL_LENGTH_FACTOR = 4

COUNTRY_COUNT = 4

REAL_WIDTH = round(SCREEN_WIDTH/REAL_LENGTH_FACTOR)
REAL_HEIGHT = round(SCREEN_HEIGHT/REAL_LENGTH_FACTOR)

white = (255, 255, 255)
black = (0, 0, 0)

pygame.init()
pygame.display.set_caption("Simple PyGame Example")
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

# Load black dot coordinates from the JSON file
try:
    with open('../KSG Benchmark/black_dot_coordinates.json', 'r') as f:
        black_dots_data = json.load(f)
except FileNotFoundError:
    print("Error: black_dot_coordinates.json not found.")
    black_dots_data = []
except json.JSONDecodeError:
    print("Error: Could not decode JSON from black_dot_coordinates.json.")
    black_dots_data = []

# Classes (Will be moved to another file)

class Tile:
    def __init__(self, screen, x, y, is_black_dot=False):
        self.screen = screen # Getting Pygame Screen
        self.x = x
        self.y = y
        self.is_black_dot = is_black_dot
        self.color = (0,0,0)
        self.owner = None # Add owner attribute, None initially
        # Add other tile properties here later, e.g., unit, terrain type, etc.
        self.border_country = []

    def changeColor(self, color):
        self.is_black_dot = False
        self.color = color
        # Change the color of tile
    def change_border_country(self, countries):
        for country in countries:
            self.border_country.append(country)

class Country:
    # Defining the Country
    def __init__(self, start_tile_coords, color, start_population, start_gdp):
        self.color = color # Store the Tuple of Color RGB
        self.population = start_population
        self.gdp = start_gdp
        self.time_elapsed = 0 # Add a counter for time/frames
        self.owned_tiles = [start_tile_coords] # List to store owned tiles
        start_tile_coords.owner = self # Set the owner of the starting tile
        start_tile_coords.changeColor(self.color)

    def add_tile(self, tile):
        tile.owner = self
        tile.changeColor(self.color)
        self.owned_tiles.append(tile)

    def remove_tile(self, tile):
        tile.owner = None
        tile.changeColor((0,0,0)) # Reset color to black or default
        if tile in self.owned_tiles:
            self.owned_tiles.remove(tile)
        

# Create a 2D grid of Tile instances
# Initialize all tiles as not black dots
tile_grid = [[Tile(screen, x, y) for y in range(REAL_HEIGHT)] for x in range(REAL_WIDTH)]

# Mark tiles that correspond to black dots
# Scale the black dot coordinates and mark the corresponding tile in the grid
for dot in black_dots_data:
    # Calculate the scaled coordinates, rounding to the nearest integer for tile mapping
    scaled_x = int(round(dot["x"] / (3*REAL_LENGTH_FACTOR)))
    scaled_y = int(round(dot["y"] / (3*REAL_LENGTH_FACTOR)))

    # Check if the scaled coordinates are within the screen bounds
    if 0 <= scaled_x < REAL_WIDTH and 0 <= scaled_y < REAL_HEIGHT:
        tile_grid[scaled_x][scaled_y].is_black_dot = True

# Instantiate a random country
# Choose a random black dot tile as the starting position
if black_dots_data:
    random_dot = random.choice(black_dots_data)
    # Scale the black dot coordinates to match the tile grid
else:
    # Fallback to a random tile if no black dots are loaded
    start_x = random.randint(0, REAL_WIDTH - 1)
    start_y = random.randint(0, REAL_HEIGHT - 1)
    start_tile_coords = Tile(screen, start_x, start_y)
    # print("Warning: No black dots loaded, starting country on a random tile.")


# Initial population and GDP
initial_population = 10000
initial_gdp = 1000000

countries = []

for i in range(COUNTRY_COUNT):
    random_dot = random.choice(black_dots_data)
    start_x = int(round(random_dot["x"] / (3*REAL_LENGTH_FACTOR)))
    start_y = int(round(random_dot["y"] / (3*REAL_LENGTH_FACTOR)))
    start_tile_coords = tile_grid[start_x][start_y]
    start_r, start_g, start_b = (int(round(random.randint(0,256))),int(round(random.randint(0,256))),int(round(random.randint(0,256))))
    start_color = (start_r, start_g, start_b)

    countries.append(Country(start_tile_coords, start_color, initial_population, initial_gdp))

# Game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    for country in countries:
    # Update country stats over time
        country.time_elapsed += 50
        # Increase population and GDP based on time elapsed (e.g., every 60 frames)
        if country.time_elapsed % 60 == 0: # Update every second (assuming 60 FPS)
            country.population += int(country.population * 0.01) # 1% growth
            country.gdp += int(country.gdp * 0.05) # 5% growth
            print(f"Time: {country.time_elapsed // 60}s, Population: {country.population}, GDP: {country.gdp}") # Print for debugging

        former_gdp = copy(country.gdp)
        if country.population >= CONQUEST_POPULATION_THRESHOLD:
            # Check neighbors of owned tiles
            dx_all = [-1,0,1]
            dy_all = [-1,0,1]
            random.shuffle(dx_all)
            random.shuffle(dy_all)
            while True:
                conquerable_neighbors = None
                owned_tile = random.choice(country.owned_tiles)
                for dx in dx_all:
                    for dy in dy_all:
                        if dx == 0 and dy == 0:
                            continue # Skip the tile itself

                        nx, ny = owned_tile.x + dx, owned_tile.y + dy

                        # Check if neighbor is within bounds
                        if 0 <= nx < SCREEN_WIDTH and 0 <= ny < SCREEN_HEIGHT:
                            neighbor_tile = tile_grid[nx][ny]

                            # Check if the neighbor is not owned by the current country and is not a black dot (black dots are boundaries)
                            if neighbor_tile.owner != country and neighbor_tile.is_black_dot:
                                conquerable_neighbors = neighbor_tile
                                break
                if conquerable_neighbors:
                    break
            # Attempt to conquer a random conquerable neighbor if available and affordable
            if conquerable_neighbors and country.gdp >= CONQUEST_GDP_COST:
                # If gdp is lower than threshold percent of initial gdp, break
                tile_to_conquer = conquerable_neighbors
                country.add_tile(tile_to_conquer)
                country.gdp -= CONQUEST_GDP_COST
                # print(f"Conquered tile at ({tile_to_conquer.x}, {tile_to_conquer.y}). Remaining GDP: {country.gdp}")
            # If country cannot pay conquest gdp, break
            # --- End Conquest Logic ---
        # Clear the screen
        screen.fill(white)

        # --- Modified Drawing Loop ---
        # Draw tiles based on their properties
        for x in range(REAL_WIDTH):
            for y in range(REAL_HEIGHT):
                tile = tile_grid[x][y]
                if tile.owner:
                    pygame.draw.rect(screen, tile.color, (tile.x*REAL_LENGTH_FACTOR, tile.y*REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR)) # Draw a red pixel at the tile
                elif tile.is_black_dot:
                    # Draw a black pixel or a small circle for the black dot tile
                    # Drawing a 1x1 pixel is equivalent to setting the pixel color
                    pygame.draw.rect(screen, black, (tile.x*REAL_LENGTH_FACTOR, tile.y*REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR)) # Draw a red pixel at the tile
                # else:
                    # Optionally draw other tile types/colors here (e.g. unowned tiles)

        # --- End Modified Drawing Loop ---

        # Update the display
        pygame.display.update()

pygame.quit()
sys.exit()
