"""
Pygame 기반의 전략 시뮬레이션 게임 구현.
이 스크립트는 게임의 메인 루프, 타일 및 국가 관리, 그리고 정복 로직을 포함합니다.
"""

import pygame
import sys
import json
import random
from copy import copy
import math # 거리 계산을 위해 math 모듈 추가

# --- 게임 상수 설정 ---

# 화면 해상도 (원본 이미지 크기의 0.33배)
SCREEN_WIDTH = 551
SCREEN_HEIGHT = 964

# 실제 게임 내 길이 비율 (타일 크기 조절에 사용)
REAL_LENGTH_FACTOR = 1

# 게임에 참여할 국가의 수
COUNTRY_COUNT = 4

# 실제 게임 그리드의 너비와 높이 (REAL_LENGTH_FACTOR에 따라 조정)
REAL_WIDTH = round(SCREEN_WIDTH / REAL_LENGTH_FACTOR)
REAL_HEIGHT = round(SCREEN_HEIGHT / REAL_LENGTH_FACTOR)

# 군대 관련 파라미터
ARMY_INITIAL_STRENGTH = 2000 # 새로 생성되는 군대의 초기 병력

# 색상 정의 (RGB)
white = (255, 255, 255)  # 흰색
black = (0, 0, 0)      # 검은색

# Pygame 초기화
pygame.init()
pygame.display.set_caption("간단한 PyGame 전략 시뮬레이션")  # 게임 창 제목 설정
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))  # 화면 모드 설정

# 폰트 설정 (한글 지원을 위해 '맑은 고딕' 사용)
font = pygame.font.SysFont('Malgun Gothic', 20) # 맑은 고딕, 크기 20
title_font = pygame.font.SysFont('Malgun Gothic', 24) # 맑은 고딕, 크기 24

# 색상을 밝게 만드는 헬퍼 함수
def lighten_color(color, factor=0.5):
    r, g, b = color
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return (r, g, b)

# 별 모양 그리기 함수
def draw_star(surface, color, center, radius):
    """
    별 모양을 그리는 함수
    """
    import math
    points = []
    for i in range(10):  # 5개 꼭짓점 + 5개 안쪽 점
        angle = math.pi * i / 5
        if i % 2 == 0:
            # 바깥쪽 점
            x = center[0] + radius * math.cos(angle - math.pi/2)
            y = center[1] + radius * math.sin(angle - math.pi/2)
        else:
            # 안쪽 점
            x = center[0] + (radius * 0.5) * math.cos(angle - math.pi/2)
            y = center[1] + (radius * 0.5) * math.sin(angle - math.pi/2)
        points.append((int(x), int(y)))
    
    pygame.draw.polygon(surface, color, points)

# --- 데이터 로드 ---

# black_dot_coordinates.json 파일에서 검은 점(육지) 좌표 로드
try:
    with open('../KSG Benchmark/black_dot_coordinates.json', 'r') as f:
        black_dots_data = json.load(f)
except FileNotFoundError:
    print("오류: black_dot_coordinates.json 파일을 찾을 수 없습니다.")
    black_dots_data = []
except json.JSONDecodeError:
    print("오류: black_dot_coordinates.json 파일의 JSON 디코딩에 실패했습니다.")
    black_dots_data = []

# --- 클래스 정의 ---
# (향후 별도의 파일로 분리될 예정)

class Tile:
    """
    게임 맵의 개별 타일을 나타내는 클래스.
    각 타일은 화면에 그려지며, 자신이 속한 프로빈스에 대한 참조를 가집니다.
    """
    def __init__(self, screen, x, y):
        """
        Tile 클래스의 생성자.

        Args:
            screen (pygame.Surface): 타일이 그려질 Pygame 화면 객체.
            x (int): 타일의 X 좌표 (그리드 기준).
            y (int): 타일의 Y 좌표 (그리드 기준).
        """
        self.screen = screen
        self.x = x
        self.y = y
        self.province = None  # 이 타일이 속한 Province 객체, 초기값은 None

class Province:
    """
    여러 개의 타일을 묶는 더 큰 단위인 프로빈스를 나타내는 클래스.
    프로빈스는 소유 국가, 색상 등의 속성을 가집니다.
    """
    def __init__(self, screen, province_id, tiles, initial_population=0, initial_gdp=0):
        """
        Province 클래스의 생성자.

        Args:
            screen (pygame.Surface): 프로빈스 내 타일이 그려질 Pygame 화면 객체.
            province_id (int): 프로빈스의 고유 ID.
            tiles (list): 이 프로빈스에 속할 Tile 객체들의 리스트.
            initial_population (int): 프로빈스의 초기 인구.
            initial_gdp (int): 프로빈스의 초기 GDP.
        """
        self.screen = screen
        self.id = province_id
        self.tiles = []  # 이 프로빈스에 속한 타일 목록
        self.color = (0, 0, 0)  # 기본 색상은 검은색
        self.owner = None       # 프로빈스의 소유 국가 (Country 객체), 초기값은 None
        self.border_provinces = [] # 이 프로빈스와 인접한 프로빈스들의 목록
        self.is_island = False  # 이 프로빈스가 섬인지 여부
        self.is_coastal = False # 이 프로빈스가 해안 프로빈스인지 여부
        self.population = initial_population # New: Province-level population
        self.gdp = initial_gdp             # New: Province-level GDP

        for tile in tiles:
            self.add_tile(tile)

    def add_tile(self, tile):
        """
        프로빈스에 타일을 추가하고, 타일의 province 속성을 이 프로빈스로 설정합니다.

        Args:
            tile (Tile): 프로빈스에 추가할 타일 객체.
        """
        tile.province = self
        self.tiles.append(tile)

    def change_color(self, color):
        """
        프로빈스의 색상을 변경합니다.

        Args:
            color (tuple): 변경할 RGB 색상 튜플.
        """
        self.color = color

    def add_border_province(self, province):
        """
        이 프로빈스와 인접한 프로빈스를 border_provinces 목록에 추가합니다.

        Args:
            province (Province): 추가할 Province 객체.
        """
        if province not in self.border_provinces:
            self.border_provinces.append(province)

    def get_center_coordinates(self):
        """
        프로빈스의 중심 좌표를 계산하여 반환합니다.
        (모든 타일의 평균 X, Y 좌표)
        """
        if not self.tiles:
            return 0, 0
        
        sum_x = sum(tile.x for tile in self.tiles)
        sum_y = sum(tile.y for tile in self.tiles)
        return sum_x / len(self.tiles), sum_y / len(self.tiles)

class Country:
    """
    게임 내 국가를 나타내는 클래스.
    각 국가는 색상, 인구, GDP, 소유 프로빈스 등의 속성을 가집니다.
    """
    def __init__(self, start_province, color, start_population, start_gdp):
        """
        Country 클래스의 생성자.

        Args:
            start_province (Province): 국가가 시작할 프로빈스 객체.
            color (tuple): 국가의 고유 색상 RGB 튜플.
            start_population (int): 국가의 초기 인구.
            start_gdp (int): 국가의 초기 GDP.
        """
        self.color = color
        self.time_elapsed = 0  # 게임 시간/프레임 카운터
        self.owned_provinces = []  # 국가가 소유한 프로빈스 목록
        self.armies = [] # 국가가 소유한 군대 목록
        self.capital_province = start_province  # 국가의 수도 프로빈스
        # When adding the first province, assign its initial population and GDP
        self.add_province(start_province, initial_population=start_population, initial_gdp=start_gdp)

    def add_province(self, province, initial_population=None, initial_gdp=None):
        """
        국가에 새로운 프로빈스를 추가합니다.
        Args:
            province (Province): 국가에 추가할 프로빈스 객체.
            initial_population (int, optional): 프로빈스의 초기 인구. None이면 기존 인구 유지.
            initial_gdp (int, optional): 프로빈스의 초기 GDP. None이면 기존 GDP 유지.
        """
        province.owner = self
        province.change_color(self.color)
        self.owned_provinces.append(province)
        if initial_population is not None:
            province.population = initial_population
        if initial_gdp is not None:
            province.gdp = initial_gdp

    def remove_province(self, province):
        """
        국가에서 프로빈스를 제거합니다.
        Args:
            province (Province): 국가에서 제거할 프로빈스 객체.
        """
        # 수도가 함락되었는지 확인
        if province == self.capital_province:
            print(f"수도 프로빈스 {province.id}가 함락되었습니다! {self.color} 국가의 수도를 재배치합니다.")
            self.relocate_capital()
        
        province.owner = None
        province.change_color((0, 0, 0))  # 프로빈스 색상을 기본(검은색)으로 리셋
        if province in self.owned_provinces:
            self.owned_provinces.remove(province)
        province.population = 0 # Reset population/gdp when province is lost
        province.gdp = 0

    def relocate_capital(self):
        """
        수도를 다른 소유 프로빈스로 재배치합니다.
        """
        # 현재 수도를 제외한 소유 프로빈스 중에서 선택
        available_provinces = [p for p in self.owned_provinces if p != self.capital_province]
        
        if available_provinces:
            # 섬이 아니고 해안이 아닌 프로빈스를 우선 선택
            inland_provinces = [p for p in available_provinces if not p.is_island and not p.is_coastal]
            
            if inland_provinces:
                new_capital = random.choice(inland_provinces)
            else:
                # 내륙 프로빈스가 없으면 일반 프로빈스 중에서 선택
                new_capital = random.choice(available_provinces)
            
            old_capital_id = self.capital_province.id if self.capital_province else "없음"
            self.capital_province = new_capital
            print(f"{self.color} 국가의 수도가 프로빈스 {old_capital_id}에서 프로빈스 {new_capital.id}로 이전되었습니다.")
        else:
            # 소유한 프로빈스가 없으면 수도도 없음
            self.capital_province = None
            print(f"{self.color} 국가의 모든 영토가 상실되어 수도가 사라졌습니다.")

    def is_province_connected_to_capital(self, province):
        """
        특정 프로빈스가 수도와 연결되어 있는지 BFS로 확인합니다.
        """
        if not self.capital_province or province not in self.owned_provinces:
            return False
        
        if province == self.capital_province:
            return True
        
        # BFS를 사용하여 수도에서 해당 프로빈스까지의 연결성 확인
        visited = set()
        queue = [self.capital_province]
        visited.add(self.capital_province)
        
        while queue:
            current = queue.pop(0)
            
            # 인접한 소유 프로빈스들을 확인
            for border_province in current.border_provinces:
                if border_province.owner == self and border_province not in visited:
                    if border_province == province:
                        return True
                    visited.add(border_province)
                    queue.append(border_province)
        
        return False

    def get_isolated_provinces(self):
        """
        수도와 연결되지 않은 고립된 프로빈스들을 반환합니다.
        """
        if not self.capital_province:
            return self.owned_provinces.copy()  # 수도가 없으면 모든 프로빈스가 고립됨
        
        isolated = []
        for province in self.owned_provinces:
            if not province.is_island and not self.is_province_connected_to_capital(province):
                isolated.append(province)
        
        return isolated

    def get_total_population(self):
        """국가가 소유한 모든 프로빈스의 인구를 합산하여 반환합니다."""
        return sum(p.population for p in self.owned_provinces)

    def get_total_gdp(self):
        """국가가 소유한 모든 프로빈스의 GDP를 합산하여 반환합니다."""
        return sum(p.gdp for p in self.owned_provinces)

    def deduct_population(self, amount):
        """
        국가의 총 인구에서 지정된 양을 차감합니다.
        프로빈스별로 인구를 분배하여 차감합니다.
        """
        remaining_to_deduct = amount
        # 인구가 많은 프로빈스부터 차감 (간단한 분배 방식)
        sorted_provinces = sorted(self.owned_provinces, key=lambda p: p.population, reverse=True)
        for p in sorted_provinces:
            if remaining_to_deduct <= 0:
                break
            deduct_from_province = min(p.population, remaining_to_deduct)
            p.population -= deduct_from_province
            remaining_to_deduct -= deduct_from_province
        return remaining_to_deduct == 0 # True if successfully deducted all

    def deduct_gdp(self, amount):
        """
        국가의 총 GDP에서 지정된 양을 차감합니다.
        프로빈스별로 GDP를 분배하여 차감합니다.
        """
        remaining_to_deduct = amount
        # GDP가 많은 프로빈스부터 차감 (간단한 분배 방식)
        sorted_provinces = sorted(self.owned_provinces, key=lambda p: p.gdp, reverse=True)
        for p in sorted_provinces:
            if remaining_to_deduct <= 0:
                break
            deduct_from_province = min(p.gdp, remaining_to_deduct)
            p.gdp -= deduct_from_province
            remaining_to_deduct -= deduct_from_province
        return remaining_to_deduct == 0 # True if successfully deducted all
    
    def create_army(self, province, strength):
        """
        특정 프로빈스에 군대를 창설합니다.
        인구와 GDP를 소모합니다.
        """
        # 고립된 프로빈스에서는 군대 생성 불가 (섬 제외)
        if not province.is_island and not self.is_province_connected_to_capital(province):
            print(f"{self.color} 국가: 프로빈스 {province.id}는 수도와 고립되어 군대를 창설할 수 없습니다.")
            return None
        
        # 군대 창설 비용 (병력 1당 인구 및 GDP 소모) - 비용 대폭 감소
        POPULATION_COST_PER_STRENGTH = 0.5 # 병력 1당 인구 소모 (1에서 0.5로 감소)
        GDP_COST_PER_STRENGTH = 2 # 병력 1당 GDP 소모 (5에서 2로 감소)

        # 해안 프로빈스에서는 군대 생성량 감소
        actual_strength = strength
        if province.is_coastal:
            actual_strength = int(strength * 0.5)  # 해안에서는 50% 병력으로 생성
            print(f"{self.color} 국가: 해안 프로빈스 {province.id}에서 군대 생성량이 {actual_strength}로 감소했습니다.")

        required_population = actual_strength * POPULATION_COST_PER_STRENGTH
        required_gdp = actual_strength * GDP_COST_PER_STRENGTH

        if self.get_total_population() >= required_population and self.get_total_gdp() >= required_gdp:
            if self.deduct_population(required_population) and self.deduct_gdp(required_gdp):
                new_army = Army(self, province, actual_strength)
                self.armies.append(new_army)
                print(f"{self.color} 국가가 프로빈스 {province.id}에 {actual_strength} 병력의 군대를 창설했습니다.")
                return new_army
            else:
                print(f"{self.color} 국가: 군대 창설 비용을 차감하는 데 실패했습니다 (내부 오류).")
                return None
        else:
            print(f"{self.color} 국가: 군대 창설에 필요한 인구 또는 GDP가 부족합니다. (인구: {self.get_total_population()}, GDP: {self.get_total_gdp()})")
            return None

class Army:
    """
    국가의 군대를 나타내는 클래스.
    """
    def __init__(self, owner, current_province, strength):
        """
        Army 클래스의 생성자.

        Args:
            owner (Country): 이 군대의 소유 국가.
            current_province (Province): 군대가 현재 주둔하고 있는 프로빈스.
            strength (int): 군대의 병력 수.
        """
        self.owner = owner
        self.current_province = current_province
        self.strength = strength
        self.target_province = None # 군대의 목표 프로빈스
        self.path = [] # 목표 프로빈스까지의 경로 (타일 단위)
        
        # 애니메이션 관련 속성
        self.current_x, self.current_y = current_province.get_center_coordinates()
        self.target_x, self.target_y = self.current_x, self.current_y
        self.move_progress = 0.0  # 0.0(시작) ~ 1.0(완료)
        self.is_moving = False
        self.move_speed = 0.2  # 이동 속도 (프레임당 진행도)

    def set_target(self, target_province):
        """
        군대의 목표 프로빈스를 설정하고 경로를 계산합니다.
        (간단한 경로 계산, 추후 A* 등으로 개선 가능)
        """
        self.target_province = target_province
        # 현재는 목표 프로빈스에 바로 도달하는 것으로 가정
        # 실제로는 BFS/A* 등으로 경로를 계산해야 함
        self.path = [target_province]
        
        # 애니메이션 시작
        if target_province and not self.is_moving:
            self.start_move_animation()

    def start_move_animation(self):
        """
        이동 애니메이션을 시작합니다.
        """
        if self.target_province:
            self.target_x, self.target_y = self.target_province.get_center_coordinates()
            self.move_progress = 0.0
            self.is_moving = True

    def update_animation(self):
        """
        애니메이션을 업데이트합니다.
        """
        if self.is_moving and self.target_province:
            # 애니메이션 진행
            self.move_progress += self.move_speed
            
            if self.move_progress >= 1.0:
                # 애니메이션 완료
                self.move_progress = 1.0
                self.is_moving = False
                self.current_x = self.target_x
                self.current_y = self.target_y
                
                # 프로빈스 이동 완료
                self.current_province = self.target_province
                # target_province는 engage_province 후에 None으로 설정
                
                print(f"군대 {self.owner.color} 프로빈스 {self.current_province.id}에 도착!")
            else:
                # 중간 위치 계산 (선형 보간)
                start_x, start_y = self.current_x, self.current_y
                if self.move_progress == self.move_speed:  # 첫 프레임
                    start_x, start_y = self.current_province.get_center_coordinates()
                
                self.current_x = start_x + (self.target_x - start_x) * self.move_progress
                self.current_y = start_y + (self.target_y - start_y) * self.move_progress

    def move(self):
        """
        군대를 목표 프로빈스 방향으로 이동시킵니다.
        """
        # 애니메이션 업데이트
        self.update_animation()
        
        # 이동이 완료되면 다음 목표로 이동하거나 전투 진행
        if not self.is_moving and self.target_province is None and self.path:
            # 경로에 다음 목표가 있으면 계속 이동
            if self.path:
                next_target = self.path.pop(0)
                self.set_target(next_target)

    def retreat_to_friendly_territory(self):
        """
        패배한 군대를 가장 가까운 자국 영토로 후퇴시킵니다.
        """
        if not self.owner.owned_provinces:
            # 소유한 프로빈스가 없으면 후퇴할 곳이 없음
            print(f"군대 {self.owner.color}: 후퇴할 자국 영토가 없습니다!")
            return
        
        # 현재 위치에서 가장 가까운 자국 영토 찾기
        current_x, current_y = self.current_province.get_center_coordinates()
        closest_province = None
        min_distance = float('inf')
        
        for province in self.owner.owned_provinces:
            province_x, province_y = province.get_center_coordinates()
            distance = math.sqrt((current_x - province_x)**2 + (current_y - province_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_province = province
        
        if closest_province:
            print(f"군대 {self.owner.color} 프로빈스 {self.current_province.id}에서 프로빈스 {closest_province.id}로 후퇴!")
            self.current_province = closest_province
            self.target_province = None
            self.path = []

    def engage_province(self):
        """
        군대가 현재 프로빈스에서 행동을 수행합니다 (점령 또는 전투).
        """
        if self.current_province.owner == self.owner:
            # 이미 소유한 프로빈스에 도착했다면 목표 달성
            self.target_province = None
            self.path = []
            return

        if self.current_province.owner is None:
            # 빈 땅 점령
            print(f"군대 {self.owner.color} 프로빈스 {self.current_province.id} 점령!")
            self.owner.add_province(self.current_province)
            self.target_province = None
            self.path = []
        elif self.current_province.owner != self.owner:
            # 적 프로빈스 공격 (간단한 전투 로직)
            enemy_country = self.current_province.owner
            print(f"군대 {self.owner.color} 프로빈스 {self.current_province.id}에서 {enemy_country.color}와 전투!")
            
            # 방어 프로빈스의 "방어력"을 인구에 비례하여 설정 (방어력 더욱 감소)
            province_defense_strength = self.current_province.population / 2000 # 프로빈스 인구의 1/2000을 방어력으로 가정 (1/50에서 1/2000으로 변경)
            
            # 방어하는 프로빈스에 있는 적 군대들 찾기
            defending_armies = [army for army in enemy_country.armies if army.current_province == self.current_province]
            defending_army_strength = sum(army.strength for army in defending_armies)
            
            print(f"방어 상황: 프로빈스 방어력 {province_defense_strength:.1f}, 주둔 군대 {len(defending_armies)}개 (총 병력: {defending_army_strength})")
            
            # 수도 연결 여부에 따른 공격력/방어력 보정
            attack_strength = self.strength
            defense_strength = province_defense_strength + defending_army_strength
            
            # 공격하는 군대가 있는 프로빈스가 수도와 고립되었는지 확인 (섬 제외)
            attacking_from_province = None
            for province in self.owner.owned_provinces:
                if any(army for army in self.owner.armies if army == self and army.current_province == province):
                    attacking_from_province = province
                    break
            
            # 실제로는 현재 군대가 있는 프로빈스를 찾아야 함
            # 하지만 현재 구조상 군대가 어느 프로빈스에서 출발했는지 추적이 어려우므로
            # 대신 공격하는 군대의 소유자가 가진 프로빈스 중 현재 공격 대상과 인접한 프로빈스를 찾음
            attacking_from_isolated = False
            for owned_province in self.owner.owned_provinces:
                if self.current_province in owned_province.border_provinces:
                    if not owned_province.is_island and not self.owner.is_province_connected_to_capital(owned_province):
                        attacking_from_isolated = True
                        print(f"공격군 {self.owner.color}: 고립된 프로빈스에서 공격하여 공격력 99% 감소!")
                        break
            
            # 방어하는 프로빈스가 수도와 고립되었는지 확인 (섬 제외)
            defending_isolated = False
            if not self.current_province.is_island and not enemy_country.is_province_connected_to_capital(self.current_province):
                defending_isolated = True
                print(f"방어군 {enemy_country.color}: 고립된 프로빈스로 방어력 99% 감소!")
            
            # 고립 패널티 적용 (40% 불리 = 60%로 감소)
            if attacking_from_isolated:
                attack_strength = attack_strength * 0.01
            
            if defending_isolated:
                defense_strength = defense_strength * 0.01

            # 공격력과 방어력 차이에 비례한 피해 계산
            strength_difference = attack_strength - defense_strength
            total_strength = attack_strength + defense_strength
            
            if total_strength > 0:
                # 피해 계산 - 차이가 클수록 더 많은 피해
                base_damage_rate = abs(strength_difference) / total_strength
                
                if attack_strength > defense_strength:
                    # 공격자 우세 - 공격자 승리
                    attacker_damage_rate = base_damage_rate * 0.1  # 승자는 적은 피해
                    defender_damage_rate = base_damage_rate * 0.8  # 패자는 큰 피해
                    
                    attacker_damage = int(self.strength * attacker_damage_rate)
                    defender_damage = int(defending_army_strength * defender_damage_rate)
                    
                    # 최소/최대 피해 제한
                    attacker_damage = max(1, min(attacker_damage, int(self.strength * 0.3)))
                    
                    self.strength -= attacker_damage
                    
                    # 방어군에게 피해 적용
                    total_defender_damage = defender_damage
                    for defending_army in defending_armies:
                        if total_defender_damage <= 0:
                            break
                        army_damage = min(defending_army.strength, total_defender_damage)
                        defending_army.strength -= army_damage
                        total_defender_damage -= army_damage
                        print(f"방어군 {defending_army.owner.color} 피해: {army_damage} (남은 병력: {defending_army.strength})")
                    
                    # 병력이 0 이하가 된 방어군 제거
                    for defending_army in list(defending_armies):
                        if defending_army.strength <= 0:
                            enemy_country.armies.remove(defending_army)
                            print(f"방어군 {defending_army.owner.color} 소멸!")
                    
                    print(f"군대 {self.owner.color} 승리! 프로빈스 {self.current_province.id} 정복! (공격군 피해: {attacker_damage})")
                    
                    # 프로빈스 정복
                    enemy_country.remove_province(self.current_province)
                    self.owner.add_province(self.current_province)
                    self.target_province = None
                    self.path = []
                    
                else:
                    # 방어자 우세 또는 동점 - 공격자 패배
                    attacker_damage_rate = base_damage_rate * 0.8  # 패자는 큰 피해
                    defender_damage_rate = base_damage_rate * 0.1  # 승자는 적은 피해
                    
                    attacker_damage = int(self.strength * attacker_damage_rate)
                    defender_damage = int(defending_army_strength * defender_damage_rate)
                    
                    # 최소/최대 피해 제한
                    attacker_damage = max(int(self.strength * 0.2), min(attacker_damage, int(self.strength * 0.7)))
                    
                    self.strength -= attacker_damage
                    
                    # 방어군에게도 피해 적용 (승리했지만 약간의 피해)
                    total_defender_damage = defender_damage
                    for defending_army in defending_armies:
                        if total_defender_damage <= 0:
                            break
                        army_damage = min(defending_army.strength, total_defender_damage)
                        defending_army.strength -= army_damage
                        total_defender_damage -= army_damage
                        print(f"방어군 {defending_army.owner.color} 피해: {army_damage} (남은 병력: {defending_army.strength})")
                    
                    # 병력이 0 이하가 된 방어군 제거
                    for defending_army in list(defending_armies):
                        if defending_army.strength <= 0:
                            enemy_country.armies.remove(defending_army)
                            print(f"방어군 {defending_army.owner.color} 소멸!")
                    
                    print(f"군대 {self.owner.color} 패배! 프로빈스 {self.current_province.id} 정복 실패. (공격군 피해: {attacker_damage})")
                    
                    # 패배한 군대를 가장 가까운 자국 영토로 후퇴시킴
                    self.retreat_to_friendly_territory()
            else:
                # 예외 상황 - 기본 피해
                self.strength = int(self.strength * 0.8)
                print(f"군대 {self.owner.color} 전투에서 기본 피해를 입었습니다.")
                self.retreat_to_friendly_territory()


# --- 게임 초기화 ---

# Tile 인스턴스의 2D 그리드 생성
# 모든 타일을 초기에는 프로빈스 참조가 없는 상태로 초기화
tile_grid = [[Tile(screen, x, y) for y in range(REAL_HEIGHT)] for x in range(REAL_WIDTH)]

# black_dots_data를 기반으로 육지 타일 집합 생성 (is_black_dot이 True인 경우)
land_coords = set()
for dot in black_dots_data:
    scaled_x = int(round(dot["x"] / (3 * REAL_LENGTH_FACTOR)))
    scaled_y = int(round(dot["y"] / (3 * REAL_LENGTH_FACTOR)))
    if 0 <= scaled_x < REAL_WIDTH and 0 <= scaled_y < REAL_HEIGHT:
        land_coords.add((scaled_x, scaled_y))

# 프로빈스 생성 및 타일 할당
provinces = []
province_id_counter = 0
visited_tiles_for_province_creation = set() # 프로빈스 생성 시 방문한 타일 추적

# 프로빈스 생성 함수 (BFS 기반)
def create_province(start_x, start_y, min_tiles=50, max_tiles=500):
    global province_id_counter
    
    current_province_tiles = []
    q = [(start_x, start_y)]
    q_idx = 0 # 큐 인덱스 (pop(0) 대신 사용)
    
    # 시작점이 육지가 아니거나 이미 방문한 타일이면 프로빈스 생성 불가
    if (start_x, start_y) not in land_coords:
        return False
    
    # 이전에 실패한 프로빈스 생성 시 visited_tiles_for_province_creation에 남아있는 경우를 처리
    if (start_x, start_y) in visited_tiles_for_province_creation:
        # 해당 타일이 이미 다른 프로빈스에 할당된 경우 (성공적으로 생성된 프로빈스)
        if tile_grid[start_x][start_y].province is not None:
            return False
        # 할당되지 않았지만 visited에 남아있는 경우, 제거하고 다시 시도
        else:
            visited_tiles_for_province_creation.remove((start_x, start_y))

    while q_idx < len(q) and len(current_province_tiles) < max_tiles:
        cx, cy = q[q_idx]
        q_idx += 1
        
        if (cx, cy) in visited_tiles_for_province_creation:
            continue
            
        # 육지 타일만 프로빈스에 포함
        if (cx, cy) not in land_coords:
            continue

        current_province_tiles.append(tile_grid[cx][cy])
        visited_tiles_for_province_creation.add((cx, cy))

        # 인접 타일 탐색 (8방향)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = cx + dx, cy + dy
                
                if 0 <= nx < REAL_WIDTH and 0 <= ny < REAL_HEIGHT:
                    # 인접 타일이 육지이고, 아직 방문하지 않은 타일인 경우에만 큐에 추가
                    if (nx, ny) in land_coords and \
                       (nx, ny) not in visited_tiles_for_province_creation:
                        q.append((nx, ny))
    
    if len(current_province_tiles) >= min_tiles:
        province_id_counter += 1
        # 타일 수에 따라 초기 인구와 GDP를 동적으로 설정
        # 타일 수가 많을수록 더 큰 인구와 GDP를 가짐
        tile_count = len(current_province_tiles)
        base_population = 50000
        base_gdp = 80000
        
        # 타일 수에 비례하여 인구와 GDP 증가
        population_multiplier = 1 + (tile_count / 100) * 2  # 타일 100개당 2배 증가
        gdp_multiplier = 1 + (tile_count / 50) * 1.5        # 타일 50개당 1.5배 증가
        
        initial_population = int(base_population * population_multiplier)
        initial_gdp = int(base_gdp * gdp_multiplier)
        
        new_province = Province(screen, province_id_counter, current_province_tiles, 
                               initial_population=initial_population, initial_gdp=initial_gdp)
        provinces.append(new_province)
        print(f"프로빈스 {province_id_counter} 생성: 타일 {tile_count}개, 인구 {initial_population:,}, GDP {initial_gdp:,}")
        return True
    else:
        # 최소 타일 수를 만족하지 못하면 방문했던 타일을 다시 해제
        for tile in current_province_tiles:
            if (tile.x, tile.y) in visited_tiles_for_province_creation:
                visited_tiles_for_province_creation.remove((tile.x, tile.y))
        print(f"경고: 프로빈스 생성 실패 (시작점: {start_x},{start_y}). 최소 타일 수({min_tiles}) 미달. 현재 타일 수: {len(current_province_tiles)}")
        return False

# 모든 타일을 순회하며 프로빈스 생성 시도
for x in range(REAL_WIDTH):
    for y in range(REAL_HEIGHT):
        # 아직 방문하지 않았고, 육지 타일에서만 프로빈스 생성 시도
        if (x, y) not in visited_tiles_for_province_creation and (x, y) in land_coords:
            create_province(x, y, min_tiles=1) # min_tiles를 1로 변경하여 모든 육지 타일이 프로빈스에 포함되도록 함

# 프로빈스 간의 인접 관계 설정 (border_provinces) 및 섬/해안 여부 판단
for p1 in provinces:
    is_connected_to_mainland = False
    is_coastal_province = False # is_coastal 속성 초기화
    for tile1 in p1.tiles:
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = tile1.x + dx, tile1.y + dy
                if 0 <= nx < REAL_WIDTH and 0 <= ny < REAL_HEIGHT:
                    neighbor_tile = tile_grid[nx][ny]
                    if neighbor_tile.province and neighbor_tile.province != p1:
                        p1.add_border_province(neighbor_tile.province)
                        neighbor_tile.province.add_border_province(p1)
                        is_connected_to_mainland = True
                    # 바다 타일(land_coords에 없는 타일)에 인접해 있으면 해안 프로빈스
                    if (nx, ny) not in land_coords:
                        is_coastal_province = True
    # 인접한 프로빈스가 없으면 섬으로 간주 (완전히 고립된 섬)
    if not p1.border_provinces:
        p1.is_island = True
    p1.is_coastal = is_coastal_province # is_coastal 속성 업데이트

# Debugging prints
print(f"총 프로빈스 수: {len(provinces)}")
island_count = sum(1 for p in provinces if p.is_island)
print(f"섬 프로빈스 수: {island_count}")

# 모든 육지 타일이 프로빈스에 할당되었는지 확인
unassigned_land_tiles = [(x, y) for x, y in land_coords if tile_grid[x][y].province is None]
if unassigned_land_tiles:
    print(f"경고: 프로빈스에 할당되지 않은 육지 타일이 {len(unassigned_land_tiles)}개 있습니다. 예시: {unassigned_land_tiles[:5]}")
else:
    print("모든 육지 타일이 프로빈스에 성공적으로 할당되었습니다.")

# 초기 인구 및 GDP 설정
initial_population = 10000
initial_gdp = 1000000

countries = [] # 국가 객체들을 저장할 리스트

# COUNTRY_COUNT 만큼의 국가 인스턴스 생성 및 초기화
# 각 국가는 무작위 육지 프로빈스를 시작 프로빈스로 가짐
if provinces:
    # 육지 프로빈스만 필터링 (land_coords에 속한 타일로만 구성된 프로빈스)
    # 모든 타일이 land_coords에 있어야 육지 프로빈스로 간주
    valid_start_provinces = [p for p in provinces if all((t.x, t.y) in land_coords for t in p.tiles)]
    
    if valid_start_provinces:
        for i in range(COUNTRY_COUNT):
            # 아직 소유되지 않은 육지 프로빈스 중에서 선택
            available_provinces = [p for p in valid_start_provinces if p.owner is None]
            if available_provinces:
                start_province = random.choice(available_provinces)
                
                # 무작위 색상 생성
                start_r, start_g, start_b = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                start_color = (start_r, start_g, start_b)

                # 새로운 국가를 생성하여 리스트에 추가
                # initial_population과 initial_gdp는 이제 시작 프로빈스에 할당됩니다.
                countries.append(Country(start_province, start_color, initial_population, initial_gdp))
            else:
                print("경고: 모든 육지 프로빈스가 이미 소유되었습니다. 추가 국가를 초기화할 수 없습니다.")
                break # 더 이상 초기화할 프로빈스가 없으므로 루프 종료
    else:
        print("경고: 생성된 유효한 시작 프로빈스가 없습니다. 국가를 초기화할 수 없습니다.")
else:
    print("경고: 생성된 프로빈스가 없습니다. 국가를 초기화할 수 없습니다.")

# --- 게임 루프 ---
running = True
while running:
    # 이벤트 처리
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False  # 창 닫기 버튼 클릭 시 게임 종료

    # 각 국가에 대한 게임 로직 업데이트
    for country in countries:
        # 시간 경과에 따른 국가 스탯 업데이트
        country.time_elapsed += 1
        
        # 60프레임(1초)마다 인구와 GDP 증가 (프로빈스별로)
        if country.time_elapsed % 60 == 0:
            for p in country.owned_provinces:
                p.population += int(p.population * 0.01)  # 프로빈스 인구 1% 성장
                p.gdp += int(p.gdp * 0.05)              # 프로빈스 GDP 5% 성장

        # 인구가 충분하고, 소유한 프로빈스가 있다면 군대 창설 시도 (조건 완화)
        if country.get_total_population() >= 1500 and country.get_total_gdp() >= 8000 and country.owned_provinces:
            # 무작위로 소유한 프로빈스 중 하나를 선택하여 군대 창설
            spawn_province = random.choice(country.owned_provinces)
            country.create_army(spawn_province, ARMY_INITIAL_STRENGTH) # ARMY_INITIAL_STRENGTH 병력의 군대 창설

        # 고립된 지역의 군대 약화 처리
        isolated_provinces = country.get_isolated_provinces()
        for province in isolated_provinces:
            # 해당 프로빈스에 있는 군대들을 약화시킴
            armies_in_isolated_province = [army for army in country.armies if army.current_province == province]
            for army in armies_in_isolated_province:
                # 고립된 지역의 군대는 매 초마다 5% 병력 감소
                army.strength = int(army.strength * 0.95)
                if army.strength <= 100:  # 병력이 100 이하로 떨어지면 소멸
                    print(f"고립된 프로빈스 {province.id}의 군대 {army.owner.color}가 보급 부족으로 소멸했습니다.")
                    if army in country.armies:
                        country.armies.remove(army)

        # 각 군대의 행동 업데이트
        for army in list(country.armies): # 리스트가 변경될 수 있으므로 복사본 사용
            if army.strength <= 0:
                country.armies.remove(army)
                continue


            if not army.target_province:
                # 목표가 없는 군대는 새로운 목표를 찾음
                print(f"군대 {army.owner.color} (ID: {id(army)}) 목표 탐색 시작. 현재 프로빈스: {army.current_province.id}")
                
                # 인접한 빈 프로빈스와 적 프로빈스 모두 찾기
                unowned_border_provinces = [p for p in army.current_province.border_provinces if p.owner is None]
                enemy_border_provinces = [p for p in army.current_province.border_provinces if p.owner and p.owner != country]
                
                # 육지 프로빈스를 우선적으로 선택
                unowned_land_provinces = [p for p in unowned_border_provinces if not p.is_island]
                unowned_island_provinces = [p for p in unowned_border_provinces if p.is_island]
                enemy_land_provinces = [p for p in enemy_border_provinces if not p.is_island]
                enemy_island_provinces = [p for p in enemy_border_provinces if p.is_island]
                
                print(f"  인접 빈 육지 프로빈스: {[p.id for p in unowned_land_provinces]}")
                print(f"  인접 빈 섬 프로빈스: {[p.id for p in unowned_island_provinces]}")
                print(f"  인접 적 육지 프로빈스: {[p.id for p in enemy_land_provinces]}")
                print(f"  인접 적 섬 프로빈스: {[p.id for p in enemy_island_provinces]}")

                # 50% 확률로 빈 땅 vs 적 프로빈스 선택 (균형 유지)
                choose_empty = random.random() < 0.6  # 60% 확률로 빈 땅 우선
                
                if choose_empty and (unowned_land_provinces or unowned_island_provinces):
                    # 1. 빈 프로빈스 우선 (육지 > 섬)
                    if unowned_land_provinces:
                        army.set_target(random.choice(unowned_land_provinces))
                        print(f"  목표 설정: 인접 빈 육지 프로빈스 {army.target_province.id}")
                    elif unowned_island_provinces:
                        army.set_target(random.choice(unowned_island_provinces))
                        print(f"  목표 설정: 인접 빈 섬 프로빈스 {army.target_province.id}")
                elif enemy_land_provinces or enemy_island_provinces:
                    # 2. 적 프로빈스 공격 (육지 > 섬)
                    if enemy_land_provinces:
                        army.set_target(random.choice(enemy_land_provinces))
                        print(f"  목표 설정: 인접 적 육지 프로빈스 {army.target_province.id}")
                    elif enemy_island_provinces:
                        army.set_target(random.choice(enemy_island_provinces))
                        print(f"  목표 설정: 인접 적 섬 프로빈스 {army.target_province.id}")
                elif unowned_land_provinces or unowned_island_provinces:
                    # 3. 적이 없으면 빈 프로빈스라도 점령
                    if unowned_land_provinces:
                        army.set_target(random.choice(unowned_land_provinces))
                        print(f"  목표 설정: 인접 빈 육지 프로빈스 {army.target_province.id}")
                    elif unowned_island_provinces:
                        army.set_target(random.choice(unowned_island_provinces))
                        print(f"  목표 설정: 인접 빈 섬 프로빈스 {army.target_province.id}")
                else:
                    # 4. 가까운 빈 프로빈스나 적 프로빈스 찾기 (거리 기반)
                    army_current_province_center_x, army_current_province_center_y = army.current_province.get_center_coordinates()
                    available_targets = []
                    
                    for p_candidate in provinces:
                        if p_candidate != army.current_province and (p_candidate.owner is None or (p_candidate.owner and p_candidate.owner != country)):
                            target_center_x, target_center_y = p_candidate.get_center_coordinates()
                            distance = math.sqrt(math.pow(army_current_province_center_x - target_center_x, 2) + 
                                                  math.pow(army_current_province_center_y - target_center_y, 2))
                            # 육지면 거리에 0.5 가중치 적용 (우선순위 높임)
                            priority_distance = distance * 0.5 if not p_candidate.is_island else distance
                            available_targets.append((priority_distance, p_candidate))
                    
                    available_targets.sort(key=lambda x: x[0])
                    top_5_targets = [item[1] for item in available_targets[:5]]
                    
                    print(f"  가까운 목표 프로빈스 (육지 우선): {[p.id for p in top_5_targets]}")
                    
                    if top_5_targets:
                        target = random.choice(top_5_targets)
                        army.set_target(target)
                        print(f"  목표 설정: 가까운 프로빈스 {army.target_province.id}")
                    else:
                        # 5. 목표가 없으면 무작위로 소유한 다른 프로빈스로 이동 (재배치)
                        other_owned_provinces = [p for p in country.owned_provinces if p != army.current_province]
                        if other_owned_provinces:
                            army.set_target(random.choice(other_owned_provinces))
                            print(f"  목표 설정: 재배치 프로빈스 {army.target_province.id}")
                        else:
                            print(f"  이동할 다른 소유 프로빈스가 없습니다. 군대 {army.owner.color} (ID: {id(army)}) 유휴 상태.")

            # 군대 이동
            army.move()
            
            # 목표 프로빈스에 도착했고 이동 중이 아닐 때만 행동 수행
            if not army.is_moving and army.target_province and army.current_province.id == army.target_province.id:
                army.engage_province()

    # 화면 지우기 (매 프레임마다 새로 그림)
    screen.fill(white)

    # --- 타일 그리기 루프 ---
    # 모든 타일을 순회하며 자신이 속한 프로빈스의 소유자 색상으로 그림
    for x in range(REAL_WIDTH):
        for y in range(REAL_HEIGHT):
            tile = tile_grid[x][y]
            if tile.province and tile.province.owner:
                # 프로빈스 소유자가 있는 타일은 해당 프로빈스 소유 국가의 색상으로 그림
                pygame.draw.rect(screen, tile.province.owner.color, (tile.x * REAL_LENGTH_FACTOR, tile.y * REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR))
            elif (tile.x, tile.y) in land_coords: # 육지 타일이지만 아직 프로빈스에 할당되지 않은 경우
                pygame.draw.rect(screen, black, (tile.x * REAL_LENGTH_FACTOR, tile.y * REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR, REAL_LENGTH_FACTOR))

    # --- 수도 그리기 루프 ---
    for country in countries:
        if country.capital_province:
            center_x, center_y = country.capital_province.get_center_coordinates()
            # 수도를 별 모양으로 표시 (국가 색상의 밝은 버전)
            capital_color = lighten_color(country.color, factor=0.7)
            draw_star(screen, capital_color, 
                     (int(center_x * REAL_LENGTH_FACTOR), int(center_y * REAL_LENGTH_FACTOR)), 
                     8) # 반지름 8인 별로 표시

    # --- 군대 그리기 루프 ---
    for country in countries:
        for army in country.armies:
            if army.current_province:
                # 애니메이션된 위치 사용
                center_x, center_y = army.current_x, army.current_y
                # 군대 색상을 국가 색상보다 약간 밝게
                army_color = lighten_color(country.color, factor=0.3)
                pygame.draw.circle(screen, army_color, 
                                   (int(center_x * REAL_LENGTH_FACTOR), int(center_y * REAL_LENGTH_FACTOR)), 
                                   5) # 반지름 5인 원으로 표시

    # --- 국가 정보 표시 ---
    text_y_offset = 10
    for i, country in enumerate(countries):
        country_info = f"국가 {i+1} ({country.color}): 인구 {country.get_total_population():,} | GDP {country.get_total_gdp():,} | 프로빈스 {len(country.owned_provinces)} | 군대 {len(country.armies)}"
        text_surface = font.render(country_info, True, black) # 검은색 텍스트
        screen.blit(text_surface, (10, text_y_offset))
        text_y_offset += 20 # 다음 줄로 이동

    # 화면 업데이트 (그려진 내용을 화면에 표시)
    pygame.display.update()

# Pygame 종료 및 시스템 종료
pygame.quit()
sys.exit()
