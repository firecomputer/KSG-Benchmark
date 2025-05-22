from PIL import Image
import json
import numpy as np
import os

def extract_black_dots(image_path, output_json_path):
    """
    Extracts the top-left coordinates of all 10x10 black pixel clusters
    from an image and saves them to a JSON file.

    Args:
        image_path (str): The path to the input image file.
        output_json_path (str): The path to the output JSON file.
    """
    try:
        img = Image.open(image_path).convert("RGB")
        pixels = np.array(img)
        width, height = img.size
        black_dots = []

        # Iterate through the image, stopping 1 pixel before the edge
        # to allow checking for a 3x3 block.
        for y in range(0, height, 11):
            for x in range(0, width, 11):
                # Check if the current pixel and its neighbors form a 2x2 black square
                # A pixel is considered black if its RGB values are all 0.
                is_black = is_nearly_black(pixels, x, y)

                if is_black:
                    black_dots.append({"x": x, "y": y})

        # Save the coordinates to a JSON file
        with open(output_json_path, 'w') as f:
            json.dump(black_dots, f, indent=4)

        print(f"Found {len(black_dots)} 10x10 black dots.")
        print(f"Coordinates saved to {output_json_path}")

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def is_nearly_black(image_array, start_x, start_y, threshold=5):
    """
    주어진 이미지 배열에서 [start_x, start_y]부터 [start_x+9, start_y+9]까지의
    모든 픽셀을 더한 평균값이 (0,0,0)에 근접하는지 확인합니다.

    Args:
        image_array (numpy.ndarray): 이미지의 픽셀 값을 담고 있는 NumPy 배열.
                                     (높이, 너비) 또는 (높이, 너비, 채널) 형태.
                                     채널이 없는 경우 흑백 이미지로 간주합니다.
        start_x (int): 영역의 시작 X 좌표.
        start_y (int): 영역의 시작 Y 좌표.
        threshold (int, optional): 평균값이 (0,0,0)으로 간주될 최대 허용 오차.
                                   기본값은 5입니다.

    Returns:
        bool: 평균값이 (0,0,0)에 근접하면 True, 그렇지 않으면 False.
    """

    end_x = start_x + 11
    end_y = start_y + 11

    # 이미지 배열의 크기 확인
    height, width = image_array.shape[:2]

    # 유효한 영역인지 확인
    if not (0 <= start_x <= width - 12 and 0 <= start_y <= height - 12):
        print(f"오류: 지정된 시작 좌표 [{start_x}, {start_y}]는 유효한 10x10 영역을 포함하지 않습니다.")
        return False

    # 관심 영역(ROI) 추출
    # 이미지 배열이 (높이, 너비, 채널) 또는 (높이, 너비) 형태이므로 y, x 순서로 인덱싱합니다.
    roi = image_array[start_y : end_y + 1, start_x : end_x + 1]

    # ROI의 모든 픽셀 평균 계산
    # 채널이 있는 경우 (예: RGB), 각 채널의 평균을 계산하고, 채널이 없는 경우 (흑백), 단일 평균을 계산합니다.
    average_pixel_value = np.mean(roi, axis=(0, 1))

    # (0,0,0)에 근접하는지 확인
    # RGB 이미지의 경우 각 채널이 threshold 이하인지 확인
    if len(average_pixel_value.shape) > 0:  # 채널이 있는 경우
        return np.all(average_pixel_value < threshold)
    else:  # 흑백 이미지인 경우
        return average_pixel_value < threshold

if __name__ == "__main__":
    # Assuming the image is in the current working directory
    image_file = "../KSG Benchmark/Map_of_Korea-blank.png"
    output_file = "black_dot_coordinates.json"

    # Check if the image file exists before proceeding
    if not os.path.exists(image_file):
        print(f"Error: The image file '{image_file}' was not found in the current directory.")
    else:
        extract_black_dots(image_file, output_file)
