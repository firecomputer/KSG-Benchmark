from PIL import Image
import json
import os

def extract_black_dots(image_path, output_json_path):
    """
    Extracts the top-left coordinates of all 3x3 black pixel clusters
    from an image and saves them to a JSON file.

    Args:
        image_path (str): The path to the input image file.
        output_json_path (str): The path to the output JSON file.
    """
    try:
        img = Image.open(image_path).convert("RGB")
        pixels = img.load()
        width, height = img.size
        black_dots = []

        # Iterate through the image, stopping 1 pixel before the edge
        # to allow checking for a 3x3 block.
        for y in range(height - 2):
            for x in range(width - 2):
                # Check if the current pixel and its neighbors form a 2x2 black square
                # A pixel is considered black if its RGB values are all 0.
                is_black = (
                    pixels[x, y] == (0, 0, 0) and
                    pixels[x + 1, y] == (0, 0, 0) and
                    pixels[x, y + 1] == (0, 0, 0) and
                    pixels[x + 1, y + 1] == (0, 0, 0)
                )

                if is_black:
                    black_dots.append({"x": x, "y": y})

        # Save the coordinates to a JSON file
        with open(output_json_path, 'w') as f:
            json.dump(black_dots, f, indent=4)

        print(f"Found {len(black_dots)} 2x2 black dots.")
        print(f"Coordinates saved to {output_json_path}")

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Assuming the image is in the current working directory
    image_file = "Map_of_Korea-blank.png"
    output_file = "black_dot_coordinates.json"

    # Check if the image file exists before proceeding
    if not os.path.exists(image_file):
        print(f"Error: The image file '{image_file}' was not found in the current directory.")
    else:
        extract_black_dots(image_file, output_file)
