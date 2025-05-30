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
COUNTRY_COUNT = 12

# 실제 게임 그리드의 너비와 높이 (REAL_LENGTH_FACTOR에 따라 조정)
REAL_WIDTH = round(SCREEN_WIDTH / REAL_LENGTH_FACTOR)
REAL_HEIGHT = round(SCREEN_HEIGHT / REAL_LENGTH_FACTOR)

# 군대 관련 파라미터
ARMY_BASE_STRENGTH = 2000 # 기본 군대 병력
GAME_TICKS_PER_LOGICAL_SECOND = 30 # 1초에 해당하는 게임 틱 수 (기존 60에서 변경)
ARMY_MAX_STRENGTH = 1000000 # 최대 군대 병력
GDP_STRENGTH_MULTIPLIER = 0.001 # GDP 1당 추가 병력 (GDP 100만 = +1000 병력)
GDP_BATTLE_STRENGTH_FACTOR = 0.000005 # GDP가 전투력에 미치는 영향 계수 (예: GDP 100만당 전투력 5배)
ARMY_MAINTENANCE_PER_STRENGTH_PER_TICK = 1 / (60 / GAME_TICKS_PER_LOGICAL_SECOND)
GDP_LOW_THRESHOLD = 100000
FIXED_GDP_BOOST_PER_TICK = 500 / (60 / GAME_TICKS_PER_LOGICAL_SECOND)
MILITARY_BUDGET_RATIO = 0.3
POPULATION_COST_PER_STRENGTH = 0.5
GDP_COST_PER_STRENGTH = 2
MAX_ARMIES_PER_TURN_BUDGET = 50

# 방어 관련 파라미터
DEFENSE_BORDER_RANGE = 1 # 국경에서 몇 프로빈스까지를 방어 지역으로 볼지 (2에서 1로 감소)
DEFENSE_ALLOCATION_RATIO = 0.4 # 전체 군대 중 방어에 할당할 비율 (기존 20%에서 40%로 증가)

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

    def add_gdp(self, amount):
        """
        국가의 총 GDP에 지정된 양을 고정적으로 추가합니다.
        수도 프로빈스에 우선적으로 추가하고, 없으면 첫 번째 소유 프로빈스에 추가합니다.
        """
        if not self.owned_provinces:
            return # 소유한 프로빈스가 없으면 추가할 수 없음

        target_province = None
        if self.capital_province and self.capital_province in self.owned_provinces:
            target_province = self.capital_province
        else:
            target_province = self.owned_provinces[0]
        
        target_province.gdp += amount
        # print(f"{self.color} 국가: 프로빈스 {target_province.id}에 고정 GDP {amount} 추가. 현재 GDP: {target_province.gdp}")


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

    def get_total_army_strength(self):
        """국가가 소유한 모든 군대의 총 병력 수를 반환합니다."""
        return sum(army.strength for army in self.armies if army.strength > 0)

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
        # GDP가 많은 프로빈스부터 차감 (기존 20%에서 40%로 증가)
        sorted_provinces = sorted(self.owned_provinces, key=lambda p: p.gdp, reverse=True)
        for p in sorted_provinces:
            if remaining_to_deduct <= 0:
                break
            deduct_from_province = min(p.gdp, remaining_to_deduct)
            p.gdp -= deduct_from_province
            remaining_to_deduct -= deduct_from_province
        return remaining_to_deduct == 0 # True if successfully deducted all
    
    def consolidate_armies_in_province(self, province):
        """
        특정 프로빈스에 있는 같은 국가의 군대들을 통합합니다.
        """
        armies_in_province = [army for army in self.armies 
                             if army.current_province == province and army.strength > 0]
        
        if len(armies_in_province) <= 1:
            return  # 통합할 군대가 1개 이하면 실행하지 않음
        
        # 가장 강한 군대를 기준으로 나머지 군대들을 통합
        armies_in_province.sort(key=lambda a: a.strength, reverse=True)
        main_army = armies_in_province[0]
        armies_to_merge = armies_in_province[1:]
        
        total_merged_strength = sum(army.strength for army in armies_to_merge)
        
        # 메인 군대에 병력 추가
        main_army.strength += total_merged_strength
        
        # 병합된 군대들을 제거
        for army in armies_to_merge:
            if army in self.armies:
                self.armies.remove(army)
        
        print(f"군대 통합: {self.color} 국가의 프로빈스 {province.id}에서 {len(armies_to_merge)}개 군대 통합 (총 병력: {main_army.strength:,})")
    
    def create_army(self, province, strength=None):
        """
        특정 프로빈스에 군대를 창설합니다.
        GDP에 따라 병력 규모가 결정됩니다.
        """
        # 고립된 프로빈스에서는 군대 생성 불가 (섬 제외)
        if not province.is_island and not self.is_province_connected_to_capital(province):
            return None
        
        # GDP에 따른 군대 규모 계산
        if strength is None:
            total_gdp = self.get_total_gdp()
            strength = min(ARMY_BASE_STRENGTH + int(total_gdp * GDP_STRENGTH_MULTIPLIER), ARMY_MAX_STRENGTH)
        
        # 해안 프로빈스에서는 군대 생성량 감소
        actual_strength = strength
        if province.is_coastal:
            actual_strength = int(strength * 0.7)
            print(f"해안 프로빈스에서 군대 생성량 30% 감소: {strength} -> {actual_strength}")

        required_population = actual_strength * POPULATION_COST_PER_STRENGTH
        required_gdp = actual_strength * GDP_COST_PER_STRENGTH

        # 1. 자원이 충분한지 먼저 확인합니다.
        if self.get_total_population() < required_population or self.get_total_gdp() < required_gdp:
            return None

        # 2. 자원 차감을 시도합니다.
        if self.deduct_population(required_population) and self.deduct_gdp(required_gdp):
            new_army = Army(self, province, actual_strength)
            self.armies.append(new_army)
            print(f"국가 {self.color}: 프로빈스 {province.id}에 {actual_strength:,}명 군대 창설! (GDP 기반)")
            return new_army
        else:
            return None

    def get_border_provinces(self):
        """
        적과 국경을 접하고 있는 프로빈스들을 반환합니다.
        """
        border_provinces = set()
        
        for province in self.owned_provinces:
            for border_province in province.border_provinces:
                if border_province.owner != self and border_province.owner is not None:
                    border_provinces.add(province)
                    break
        
        return list(border_provinces)

    def get_defense_zone_provinces(self):
        """
        방어가 필요한 지역의 프로빈스들을 반환합니다.
        국경에서 DEFENSE_BORDER_RANGE 범위 내의 프로빈스들입니다.
        """
        border_provinces = self.get_border_provinces()
        defense_zone = set(border_provinces)
        
        # 국경에서 지정된 범위만큼 확장
        for distance in range(1, DEFENSE_BORDER_RANGE + 1):
            current_layer = set()
            for province in defense_zone:
                for border_province in province.border_provinces:
                    if border_province.owner == self:
                        current_layer.add(border_province)
            defense_zone.update(current_layer)
        
        return list(defense_zone)

    def assign_defense_missions(self):
        """
        방어 임무를 효율적으로 배정합니다.
        최전선을 적극적으로 사수하도록 개선된 방어 시스템.
        """
        border_provinces = self.get_border_provinces()
        
        if not border_provinces:
            return
        
        # 방어에 더 많은 군대 할당 (전체 군대의 40%)
        available_armies = [army for army in self.armies 
                          if army.mission_type != "defense" and army.strength > 0]
        
        if not available_armies:
            return
        
        # 더 많은 군대를 방어에 할당
        max_defense_armies = max(1, int(len(available_armies) * DEFENSE_ALLOCATION_RATIO))
        
        # 가장 강한 군대들을 방어에 우선 할당
        available_armies.sort(key=lambda a: a.strength, reverse=True)
        defense_armies = available_armies[:max_defense_armies]
        
        # 가장 위험한 국경 프로빈스들 우선 순위 결정
        critical_borders = []
        for border_province in border_provinces:
            # 위험도 계산: 인접 적군 수 + 수도와의 거리 고려
            adjacent_enemy_count = sum(1 for bp in border_province.border_provinces 
                                     if bp.owner and bp.owner != self)
            
            # 수도 프로빈스는 최우선 방어
            is_capital_area = (border_province == self.capital_province or 
                             (self.capital_province and border_province in self.capital_province.border_provinces))
            
            danger_score = adjacent_enemy_count * 10
            if is_capital_area:
                danger_score += 50
            
            critical_borders.append({
                'province': border_province,
                'danger_score': danger_score
            })
        
        # 위험도 순으로 정렬
        critical_borders.sort(key=lambda x: x['danger_score'], reverse=True)
        
        # 최전선 직접 방어: 방어군을 국경 프로빈스에 직접 배치
        for i, border_info in enumerate(critical_borders):
            if i >= len(defense_armies):
                break
                
            border_province = border_info['province']
            army = defense_armies[i]
            
            # 최전선 직접 방어 임무 할당
            army.mission_type = "defense"
            army.target_province = border_province  # 국경 프로빈스에 직접 배치
            army.defense_province_target = border_province
            army.path = []
            
            print(f"최전선 방어군 {self.color} 배정: 프로빈스 {border_province.id} 직접 사수 (위험도: {border_info['danger_score']})")
        
        # 남은 방어군은 예비군으로 수도 근처에 배치
        remaining_defense_armies = defense_armies[len(critical_borders):]
        if remaining_defense_armies and self.capital_province:
            capital_area_provinces = [self.capital_province]
            capital_area_provinces.extend([p for p in self.capital_province.border_provinces 
                                         if p.owner == self])
            
            for army in remaining_defense_armies:
                reserve_position = random.choice(capital_area_provinces)
                army.mission_type = "defense"
                army.target_province = reserve_position
                army.defense_province_target = self.capital_province  # 수도 방어가 목적
                army.path = []
                
                print(f"예비 방어군 {self.color} 배정: 수도 근처 프로빈스 {reserve_position.id} 대기")

class Battle:
    """
    전투를 나타내는 클래스. 여러 틱에 걸쳐 진행됩니다.
    """
    def __init__(self, province, attacking_armies, defending_armies, province_defense_strength):
        """
        Battle 클래스의 생성자.
        
        Args:
            province (Province): 전투가 벌어지는 프로빈스
            attacking_armies (list): 공격하는 군대들의 리스트
            defending_armies (list): 방어하는 군대들의 리스트
            province_defense_strength (float): 프로빈스 자체의 방어력
        """
        self.province = province
        self.attacking_armies = list(attacking_armies)  # 복사본 생성
        self.defending_armies = list(defending_armies)  # 복사본 생성
        self.province_defense_strength = province_defense_strength
        self.original_province_owner = province.owner
        
        # 전투 진행 상태
        self.is_active = True
        self.battle_duration = 0
        self.max_battle_duration = GAME_TICKS_PER_LOGICAL_SECOND * 2  # 최대 2초간 지속 (기존 5초에서 단축)
        self.damage_per_tick = 2  # 틱당 피해율 (기존 0.02에서 증가)
        
        # 랜덤 전투 요소 추가
        self.random_factor = random.uniform(0.8, 1.2)  # 0.8~1.2배 랜덤 전투력 보정
        self.critical_battle_chance = 0.1  # 10% 확률로 빠른 결정전
        
        # 초기 병력 기록
        self.initial_attack_strength = sum(army.strength for army in self.attacking_armies)
        self.initial_defense_strength = sum(army.strength for army in self.defending_armies) + self.province_defense_strength
        
        # 고립 패널티 계산
        self.attack_penalty = self._calculate_attack_penalty()
        self.defense_penalty = self._calculate_defense_penalty()
        
        print(f"전투 시작! 프로빈스 {self.province.id}: 공격군 {len(self.attacking_armies)}개 ({self.initial_attack_strength}병력) vs 방어군 {len(self.defending_armies)}개 ({self.initial_defense_strength:.1f}병력) [랜덤보정: {self.random_factor:.2f}]")
        
    def _calculate_attack_penalty(self):
        """공격군의 고립 패널티를 계산합니다."""
        for army in self.attacking_armies:
            if army.owner:
                for owned_province in army.owner.owned_provinces:
                    if self.province in owned_province.border_provinces:
                        if not owned_province.is_island and not army.owner.is_province_connected_to_capital(owned_province):
                            print(f"공격군 {army.owner.color}: 고립된 프로빈스에서 공격하여 공격력 99% 감소!")
                            return 0.01
        return 1.0
    
    def _calculate_defense_penalty(self):
        """방어군의 고립 패널티를 계산합니다."""
        if not self.province.is_island and self.original_province_owner and \
           not self.original_province_owner.is_province_connected_to_capital(self.province):
            print(f"방어군 {self.original_province_owner.color}: 고립된 프로빈스로 방어력 99% 감소!")
            return 0.01
        return 1.0
    
    def get_current_attack_strength(self):
        """현재 공격군의 총 병력을 반환합니다. GDP 보너스 포함."""
        total_attack_strength = 0
        for army in self.attacking_armies:
            if army.strength > 0 and army.owner:
                gdp_bonus = 1 + (army.owner.get_total_gdp() * GDP_BATTLE_STRENGTH_FACTOR)
                total_attack_strength += army.strength * gdp_bonus
        
        base_strength = total_attack_strength * self.attack_penalty
        return base_strength * self.random_factor
    
    def get_current_defense_strength(self):
        """현재 방어군의 총 병력을 반환합니다. GDP 보너스 포함."""
        total_defense_strength = 0
        # 방어 군대 병력에 GDP 보너스 적용
        for army in self.defending_armies:
            if army.strength > 0 and army.owner:
                gdp_bonus = 1 + (army.owner.get_total_gdp() * GDP_BATTLE_STRENGTH_FACTOR)
                total_defense_strength += army.strength * gdp_bonus
        
        # 프로빈스 자체 방어력에도 GDP 보너스 적용 (프로빈스 소유 국가 기준)
        if self.province.owner:
            province_gdp_bonus = 1 + (self.province.owner.get_total_gdp() * GDP_BATTLE_STRENGTH_FACTOR)
            total_defense_strength += self.province_defense_strength * province_gdp_bonus
        else: # 프로빈스 소유자가 없는 경우 (예: 중립 지역)
            total_defense_strength += self.province_defense_strength

        base_strength = total_defense_strength * self.defense_penalty
        return base_strength * self.random_factor
    
    def update(self):
        """전투를 한 틱 진행시킵니다."""
        if not self.is_active:
            return False
        
        self.battle_duration += 1
        
        # 랜덤 빠른 결정전 체크 (초기 몇 틱 동안만)
        if self.battle_duration <= 3 and random.random() < self.critical_battle_chance:
            print(f"빠른 결정전! 프로빈스 {self.province.id}에서 전투가 급속히 전개됩니다!")
            self.damage_per_tick *= 10  # 피해량 3배 증가
        
        # 유효하지 않은 군대 제거
        self.attacking_armies = [army for army in self.attacking_armies if army.strength > 0 and army in army.owner.armies]
        self.defending_armies = [army for army in self.defending_armies if army.strength > 0 and army in army.owner.armies]
        
        # 전투 종료 조건 확인
        current_attack_strength = self.get_current_attack_strength()
        current_defense_strength = self.get_current_defense_strength()
        
        if len(self.attacking_armies) == 0 or current_attack_strength <= 0:
            self._end_battle_defender_victory()
            return False
        
        if len(self.defending_armies) == 0 and self.province_defense_strength <= 0:
            self._end_battle_attacker_victory()
            return False
        
        # 최대 지속 시간 초과 시 방어군 승리
        if self.battle_duration >= self.max_battle_duration:
            print(f"전투 시간 초과! 프로빈스 {self.province.id}에서 방어군 승리")
            self._end_battle_defender_victory()
            return False
        
        # 매 틱마다 피해 적용 (랜덤 요소 추가)
        random_damage_multiplier = random.uniform(0.7, 1.3)  # 틱마다 70%~130% 랜덤 피해
        self._apply_battle_damage(current_attack_strength, current_defense_strength, random_damage_multiplier)
        
        return True
    
    def _apply_battle_damage(self, attack_strength, defense_strength, damage_multiplier=1.0):
        """전투 피해를 적용합니다."""
        # 전력 차이에 따른 피해 계산
        total_strength = attack_strength + defense_strength
        if total_strength <= 0:
            return
        
        strength_ratio = attack_strength / total_strength
        
        # 우세한 쪽이 적은 피해, 열세한 쪽이 큰 피해
        if strength_ratio > 0.5:  # 공격군 우세
            attacker_damage_rate = self.damage_per_tick * 0.2 * damage_multiplier  # 더 적은 피해
            defender_damage_rate = self.damage_per_tick * 1.5 * damage_multiplier  # 더 큰 피해
        else:  # 방어군 우세
            attacker_damage_rate = self.damage_per_tick * 1.5 * damage_multiplier  # 더 큰 피해
            defender_damage_rate = self.damage_per_tick * 0.2 * damage_multiplier  # 더 적은 피해
        
        # 공격군에게 피해 적용
        self._damage_army_group(self.attacking_armies, attacker_damage_rate)
        
        # 방어군에게 피해 적용
        self._damage_army_group(self.defending_armies, defender_damage_rate)
        
        # 프로빈스 방어력 감소 (방어군이 우세하지 않을 때만)
        if strength_ratio >= 0.4:
            province_damage = self.province_defense_strength * defender_damage_rate
            self.province_defense_strength = max(0, self.province_defense_strength - province_damage)
    
    def _damage_army_group(self, armies, damage_rate):
        """군대 그룹에 피해를 적용합니다."""
        for army in armies:
            if army.strength > 0:
                damage = max(1, int(army.strength * damage_rate))
                army.strength = max(0, army.strength - damage)
                
                # 군대가 소멸했을 때 처리
                if army.strength <= 0 and army in army.owner.armies:
                    army.owner.armies.remove(army)
                    print(f"군대 {army.owner.color} 전투에서 소멸!")
    
    def _end_battle_attacker_victory(self):
        """공격군 승리로 전투를 종료합니다."""
        self.is_active = False
        print(f"전투 종료! 프로빈스 {self.province.id} - 공격군 승리!")
        
        # 모든 참여 군대의 전투 상태 해제
        for army in self.attacking_armies + self.defending_armies:
            army.in_battle = False
        
        # 승리한 공격군의 소유자 결정 (병력이 가장 많은 공격군의 소유자)
        if self.attacking_armies:
            winner = max(self.attacking_armies, key=lambda a: a.strength).owner
            
            # 프로빈스 정복
            conquered_population = self.province.population
            conquered_gdp = self.province.gdp
            
            if self.original_province_owner:
                self.original_province_owner.remove_province(self.province)
            
            # 정복한 프로빈스의 98% 인구, 70% GDP 유지
            preserved_population = int(conquered_population * 0.98)
            preserved_gdp = int(conquered_gdp * 0.7)
            winner.add_province(self.province, 
                              initial_population=preserved_population, 
                              initial_gdp=preserved_gdp)
            
            # 모든 공격군의 목표 초기화
            for army in self.attacking_armies:
                if army.mission_type != "defense":
                    army.target_province = None
                    army.path = []
                    army.mission_type = "idle"
    
    def _end_battle_defender_victory(self):
        """방어군 승리로 전투를 종료합니다."""
        self.is_active = False
        print(f"전투 종료! 프로빈스 {self.province.id} - 방어군 승리!")
        
        # 모든 참여 군대의 전투 상태 해제
        for army in self.attacking_armies + self.defending_armies:
            army.in_battle = False
        
        # 패배한 공격군들을 후퇴시킴
        for army in self.attacking_armies:
            if army.strength > 0:
                army.retreat_to_friendly_territory()

# 전투 관리자 클래스
class BattleManager:
    """
    게임 내 모든 전투를 관리하는 클래스
    """
    def __init__(self):
        self.active_battles = []  # 현재 진행 중인 전투들
    
    def start_battle(self, province, attacking_armies, defending_armies, province_defense_strength):
        """
        새로운 전투를 시작합니다.
        """
        # 이미 해당 프로빈스에서 전투가 진행 중인지 확인
        for battle in self.active_battles:
            if battle.province == province:
                # 기존 전투에 군대 추가 (중복 방지)
                for army in attacking_armies:
                    if army not in battle.attacking_armies:
                        battle.attacking_armies.append(army)
                        army.in_battle = True
                        print(f"프로빈스 {province.id}의 기존 전투에 공격군 합류!")
                return battle
        
        # 새로운 전투 생성
        new_battle = Battle(province, attacking_armies, defending_armies, province_defense_strength)
        
        # 모든 참여 군대를 전투 상태로 설정
        for army in attacking_armies + defending_armies:
            army.in_battle = True
            
        self.active_battles.append(new_battle)
        return new_battle
    
    def update_all_battles(self):
        """모든 활성 전투를 업데이트합니다."""
        completed_battles = []
        
        for battle in self.active_battles:
            if not battle.update():
                completed_battles.append(battle)
        
        # 완료된 전투 제거
        for completed_battle in completed_battles:
            self.active_battles.remove(completed_battle)
    
    def get_battle_at_province(self, province):
        """특정 프로빈스에서 진행 중인 전투를 반환합니다."""
        for battle in self.active_battles:
            if battle.province == province:
                return battle
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
        self.mission_type = "idle" # 군대의 현재 임무 (idle, attack, defense, garrison)
        self.defense_province_target = None # 방어 임무 시 방어할 특정 프로빈스
        
        # 애니메이션 관련 속성
        self.current_x, self.current_y = current_province.get_center_coordinates()
        self.target_x, self.target_y = self.current_x, self.current_y
        self.move_progress = 0.0  # 0.0(시작) ~ 1.0(완료)
        self.is_moving = False
        self.move_speed = 0.2  # 이동 속도 (프레임당 진행도)

        self.in_battle = False  # 전투 참여 상태 추가

    def set_target(self, target_province):
        """
        군대의 목표 프로빈스를 설정하고 경로를 계산합니다.
        (간단한 경로 계산, 추후 A* 등으로 개선 가능)
        """
        self.target_province = target_province
        self.in_battle = False # Reset battle status when a new target is set
        # 현재는 목표 프로빈스에 바로 도달하는 것으로 가정
        # 실제로는 BFS/A* 등으로 경로를 계산해야 함
        self.path = [target_province]

        # 애니메이션 시작
        if target_province and not self.is_moving:
            self.start_move_animation()

    def find_adjacent_reachable_empty_lands(self, country):
        """실제로 이동 가능한 인접 빈 땅만 찾기"""
        reachable_empty_lands = []
        
        for owned_province in country.owned_provinces:
            # 수도와 연결된 프로빈스에서만 출발 가능
            if not owned_province.is_island and not country.is_province_connected_to_capital(owned_province):
                continue
                
            for border_province in owned_province.border_provinces:
                if border_province.owner is None:
                    # 실제로 이동 가능한지 확인 (바다로 둘러싸인 섬이 아닌지)
                    if self.can_reach_province(owned_province, border_province):
                        reachable_empty_lands.append({
                            'target': border_province,
                            'from': owned_province,
                            'distance': 1  # 바로 인접이므로 거리 1
                        })
        
        return reachable_empty_lands

    def can_reach_province(self, start_province, target_province):
        """두 프로빈스 간 실제 이동 가능성 확인"""
        # 간단한 인접성 확인
        return target_province in start_province.border_provinces

    def assign_armies_to_nearest_empty_lands(self, country, idle_armies):
        """군대를 가장 가까운 실제 이동 가능한 빈 땅에 할당"""
        reachable_empty_lands = self.find_adjacent_reachable_empty_lands(country)
        
        if not reachable_empty_lands:
            return idle_armies  # 할당할 빈 땅이 없으면 모든 군대 반환
        
        assigned_armies = []
        remaining_armies = list(idle_armies)
        
        for army in idle_armies:
            if not reachable_empty_lands:
                break
                
            # 현재 군대 위치에서 가장 가까운 빈 땅 찾기
            best_target = None
            min_path_length = float('inf')
            
            for empty_land_info in reachable_empty_lands:
                # 실제 경로 길이 계산 (BFS 사용)
                path_length = self.calculate_actual_path_length(
                    army.current_province, 
                    empty_land_info['from']
                )
                
                if path_length < min_path_length:
                    min_path_length = path_length
                    best_target = empty_land_info
            
            if best_target:
                army.set_target(best_target['target'])
                assigned_armies.append(army)
                remaining_armies.remove(army)
                reachable_empty_lands.remove(best_target)  # 중복 할당 방지
                
                print(f"군대 {army.owner.color} -> 인접 빈 땅 {best_target['target'].id} (경로 길이: {min_path_length})")
        
        return remaining_armies

    def calculate_actual_path_length(self, start_province, end_province):
        """BFS를 사용한 실제 경로 길이 계산"""
        if start_province == end_province:
            return 0
            
        visited = set()
        queue = [(start_province, 0)]
        visited.add(start_province)
        
        while queue:
            current_province, distance = queue.pop(0)
            
            for border_province in current_province.border_provinces:
                if border_province == end_province:
                    return distance + 1
                    
                if (border_province not in visited and 
                    border_province.owner == start_province.owner):  # 자국 영토만 통과
                    visited.add(border_province)
                    queue.append((border_province, distance + 1))
        
        return float('inf')  # 도달 불가능

    def set_defense_mission(self, defense_target_province, staging_province):
        """방어 임무를 설정합니다."""
        self.mission_type = "defense"
        self.defense_province_target = defense_target_province # 실제 방어해야 할 적 프로빈스 또는 아군 중요 프로빈스
        self.set_target(staging_province) # 방어군이 주둔할 프로빈스
        # print(f"    방어군 {id(self)} ({self.strength}) 임무 설정: 주둔지 {staging_province.id}, 방어 대상 {defense_target_province.id if defense_target_province else '없음'}")

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
                # target_province는 engage_province 후에 None으로 설정 (engage_province에서 처리)
                
                print(f"군대 {self.owner.color} 프로빈스 {self.current_province.id}에 도착!")
                
                # 이동 완료 후 현재 프로빈스에서 군대 통폐합 시도
                if self.owner and self.current_province:
                    self.owner.consolidate_armies_in_province(self.current_province)
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
        # 1. 최우선: 현재 프로빈스가 비어있으면 점령 시도
        if self.current_province.owner is None:
            print(f"군대 {self.owner.color} (임무: {self.mission_type}, 이전 전투상태: {self.in_battle}) 프로빈스 {self.current_province.id} 점령 시도!")
            self.owner.add_province(self.current_province)
            # 점령 후 상태 초기화
            if self.mission_type != "defense": # 방어 임무 중 빈 땅 점령은 일반 점령으로 처리
                self.target_province = None
                self.path = []
                self.mission_type = "idle"
            self.in_battle = False # 빈 땅을 점령했으므로, 이전 전투 상태는 해제
            if hasattr(self, '_combat_initiated'):
                delattr(self, '_combat_initiated')  # 전투 개시 플래그 제거
            return

        # 2. 이미 전투 중인 경우 (그리고 프로빈스가 비어있지 않은 경우)
        #    전투는 BattleManager가 처리하므로, 여기서는 추가 행동이 거의 없음.
        if self.in_battle:
            # 방어 임무 중인 군대가 의도치 않은 적 프로빈스에 있고, 그곳이 방어 목표가 아닐 때 후퇴
            if self.mission_type == "defense" and \
               self.current_province.owner != self.owner and \
               (self.defense_province_target is None or self.current_province != self.defense_province_target):
                print(f"전투 중인 방어군 {self.owner.color}이 의도치 않은 적 프로빈스 {self.current_province.id}에 위치. 후퇴 시도.")
                self.retreat_to_friendly_territory()
            return # 그 외 전투 중 상황은 BattleManager에 위임 또는 현 상태 유지

        # 3. 전투 중이 아니고, 프로빈스가 비어있지도 않은 경우
        
        # 방어 임무 중이고, 현재 위치가 지정된 주둔지이며, 실제 방어 대상 프로빈스가 아군 소유로 안전한 경우 대기
        if self.mission_type == "defense" and \
           self.current_province == self.target_province and \
           self.defense_province_target and \
           self.defense_province_target.owner == self.owner:
            # print(f"방어군 {self.owner.color} 프로빈스 {self.current_province.id}에서 방어 대기 중.")
            return

        # 아군 프로빈스에 도착한 경우 (점령/전투 대상 아님)
        if self.current_province.owner == self.owner:
            if self.mission_type != "defense": # 방어 임무가 아니면 유휴 상태로 전환
                self.target_province = None
                self.path = []
                self.mission_type = "idle"
            if hasattr(self, '_combat_initiated'):
                delattr(self, '_combat_initiated')  # 전투 개시 플래그 제거
            return

        # 적군 프로빈스에 도착한 경우 (전투 개시)
        if self.current_province.owner != self.owner:
            enemy_country = self.current_province.owner
            defending_armies_in_province = [
                army for army in enemy_country.armies 
                if army.current_province == self.current_province and army.strength > 0
            ]
            province_defense_strength = self.current_province.population / 2000 

            # 방어 임무 관련 처리
            if self.mission_type == "defense":
                if self.defense_province_target and self.current_province == self.defense_province_target:
                    print(f"방어군 {self.owner.color} (ID: {id(self)})이 방어 대상 프로빈스 {self.current_province.id}에서 교전 시작!")
                    # 전투 시작 로직으로 진행
                else: # 방어 임무인데, 방어 대상이 아닌 엉뚱한 적 프로빈스에 도착
                    print(f"방어군 {self.owner.color} (ID: {id(self)}) 프로빈스 {self.current_province.id}에서 불필요한 교전 회피. 후퇴 시도.")
                    self.retreat_to_friendly_territory()
                    return
            
            # 전투 시작 (BattleManager가 self.in_battle = True 설정)
            # self는 공격군 리스트의 유일한 멤버로 전달
            battle_manager.start_battle(self.current_province, [self], defending_armies_in_province, province_defense_strength)
            # self.in_battle = True; # 이 줄은 start_battle 내부 또는 Battle 클래스에서 처리해야 함 (이미 그렇게 되어 있을 가능성 높음)

# --- 게임 초기화 ---

# 게임 초기화 부분에 전투 관리자 추가
battle_manager = BattleManager()

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
def create_province(start_x, start_y, min_tiles=50, max_tiles=200):  # max_tiles 감소
    global province_id_counter
    
    current_province_tiles = []
    q = [(start_x, start_y)]
    q_idx = 0
    
    # 디버깅 출력 추가
    if province_id_counter % 10 == 0:
        print(f"프로빈스 생성 중... ID: {province_id_counter}, 시작점: ({start_x}, {start_y})")
    
    # 시작점이 육지가 아니거나 이미 방문한 타일이면 프로빈스 생성 불가
    if (start_x, start_y) not in land_coords:
        return False
    
    if (start_x, start_y) in visited_tiles_for_province_creation:
        if tile_grid[start_x][start_y].province is not None:
            return False
        else:
            visited_tiles_for_province_creation.remove((start_x, start_y))

    iteration_count = 0  # 무한 루프 방지
    max_iterations = 10000  # 최대 반복 횟수
    
    while q_idx < len(q) and len(current_province_tiles) < max_tiles and iteration_count < max_iterations:
        iteration_count += 1
        cx, cy = q[q_idx]
        q_idx += 1
        
        if (cx, cy) in visited_tiles_for_province_creation:
            continue
            
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
                    if (nx, ny) in land_coords and \
                       (nx, ny) not in visited_tiles_for_province_creation:
                        q.append((nx, ny))
    
    if iteration_count >= max_iterations:
        print(f"경고: 프로빈스 생성에서 최대 반복 횟수 도달 (시작점: {start_x}, {start_y})")
    
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
    # 모든 타일이 land_coords에 있어야 육지 프로빈스로 간주하고, 섬이 아니어야 함
    valid_start_provinces = [p for p in provinces if all((t.x, t.y) in land_coords for t in p.tiles) and not p.is_island]
    
    if valid_start_provinces:
        for i in range(COUNTRY_COUNT):
            # 아직 소유되지 않은, 섬이 아닌 육지 프로빈스 중에서 선택
            available_provinces = [p for p in valid_start_provinces if p.owner is None] # valid_start_provinces에서 이미 섬이 걸러짐
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
        
        # 매 GAME_TICKS_PER_LOGICAL_SECOND 틱마다 경제 및 군사 로직 처리
        if country.time_elapsed % GAME_TICKS_PER_LOGICAL_SECOND == 0:
            # 1. 인구 및 GDP 성장 (퍼센트 + 고정값)
            for p in country.owned_provinces:
                p.population += int(p.population * 0.01)  # 프로빈스 인구 1% 성장 (주기가 짧아졌으므로 성장률 조정 필요시 고려)
                p.gdp += int(p.gdp * 0.05)              # 프로빈스 GDP 5% 성장 (주기가 짧아졌으므로 성장률 조정 필요시 고려)
            country.add_gdp(FIXED_GDP_BOOST_PER_TICK) # 고정 GDP 추가 (틱당)

            # 2. 군대 유지비 계산 및 차감
            total_army_strength = country.get_total_army_strength()
            maintenance_cost = total_army_strength * ARMY_MAINTENANCE_PER_STRENGTH_PER_TICK # 틱당 유지비
            
            if maintenance_cost > 0:
                # print(f"{country.color} 국가: 군대 유지비 {maintenance_cost:.2f} GDP 소모 시도 (총 병력: {total_army_strength}, 현재 GDP: {country.get_total_gdp()})")
                if not country.deduct_gdp(maintenance_cost):
                    # print(f"{country.color} 국가: 군대 유지비 {maintenance_cost:.1f} GDP 소모 실패. GDP 부족.")
                    # GDP가 부족하여 유지비를 모두 지불하지 못한 경우, GDP는 0이 될 수 있음 (deduct_gdp 내부 처리)
                    pass # 이미 deduct_gdp에서 가능한 만큼 차감됨
                # else:
                    # print(f"{country.color} 국가: 군대 유지비 {maintenance_cost:.1f} GDP 소모 완료. 남은 GDP: {country.get_total_gdp()}")


            # 3. GDP 확인 및 군대 자동 해체
            current_gdp = country.get_total_gdp()
            # print(f"{country.color} 국가: 유지비 처리 후 GDP: {current_gdp}, 임계값: {GDP_LOW_THRESHOLD}")

            while current_gdp < GDP_LOW_THRESHOLD and country.armies:
                country.armies.sort(key=lambda army: army.strength) # 병력이 적은 순으로 정렬
                if not country.armies: # 정렬 후 다시 한번 확인
                    break
                
                disbanded_army = country.armies.pop(0) # 가장 약한 군대 제거
                print(f"{country.color} 국가: GDP 부족 ({current_gdp} < {GDP_LOW_THRESHOLD})으로 가장 약한 군대 (병력: {disbanded_army.strength})를 해체합니다.")
                
                # 군대 해체 후에는 국가의 총 GDP가 변하지 않으므로, current_gdp를 다시 가져올 필요는 없음.
                # 루프는 country.armies가 비거나 current_gdp가 임계값 이상이 될 때까지 계속됨.
                # 하지만, 만약 군대 해체가 GDP에 영향을 준다면 여기서 추가 로직 구현 가능.
                # 현재 로직에서는 영향 없으므로, 다음 반복에서 같은 current_gdp로 다시 검사.
                # 만약 모든 군대를 해체해도 GDP가 임계값 미만이면 루프 종료.
            # 군대 창설 로직: 책정된 군사 예산 내에서 최대한 생성 (매 60프레임마다)
            if len(country.armies) < 5:  # 최소 군대 수 유지
                total_gdp = country.get_total_gdp()
                military_budget_gdp = total_gdp * MILITARY_BUDGET_RATIO
                
                for attempt in range(min(MAX_ARMIES_PER_TURN_BUDGET, 3)):  # 시도 횟수 제한
                    if len(country.armies) >= 20:  # 최대 군대 수 제한
                        break
                    
                    # GDP 기반 군대 규모 계산
                    base_strength = ARMY_BASE_STRENGTH + int(total_gdp * GDP_STRENGTH_MULTIPLIER)
                    army_strength = min(base_strength, ARMY_MAX_STRENGTH)
                    army_cost = army_strength * GDP_COST_PER_STRENGTH
                    
                    if military_budget_gdp >= army_cost:
                        suitable_provinces = [p for p in country.owned_provinces 
                                            if (p.is_island or country.is_province_connected_to_capital(p))]
                        
                        if suitable_provinces:
                            chosen_province = random.choice(suitable_provinces)
                            new_army = country.create_army(chosen_province, army_strength)
                            if new_army:
                                military_budget_gdp -= army_cost
                            else:
                                break
                        else:
                            break
                    else:
                        break
            # print(f"{country.color} 국가: 군사 예산 {military_budget_gdp:.0f} GDP 책정 (총 GDP: {country.get_total_gdp()})")

            population_cost_one_army = POPULATION_COST_PER_STRENGTH * ARMY_BASE_STRENGTH
            gdp_cost_one_army = GDP_COST_PER_STRENGTH * ARMY_BASE_STRENGTH
            
            armies_created_this_turn = 0
            # max_armies_per_turn 상수는 MAX_ARMIES_PER_TURN_BUDGET 으로 변경됨

            while military_budget_gdp >= gdp_cost_one_army and \
                  country.owned_provinces and \
                  armies_created_this_turn < MAX_ARMIES_PER_TURN_BUDGET:

                # 실제 국가 자원이 군대 생성 비용을 감당할 수 있는지 확인
                if country.get_total_population() < population_cost_one_army or \
                   country.get_total_gdp() < gdp_cost_one_army:
                    # print(f"{country.color} 국가: 실제 자원 부족으로 군대 생성 중단 (인구: {country.get_total_population()}, GDP: {country.get_total_gdp()})")
                    break

                # 군대 생성 가능한 프로빈스 선택 (수도 연결 또는 섬)
                eligible_provinces = [
                    p for p in country.owned_provinces
                    if (p.is_island or country.is_province_connected_to_capital(p))
                ]
                
                if not eligible_provinces:
                    # print(f"{country.color} 국가: 군대 생성 가능한 프로빈스 없음. 생성 중단.")
                    break

                spawn_province = random.choice(eligible_provinces)
                
                created_army = country.create_army(spawn_province, ARMY_BASE_STRENGTH)

                if created_army:
                    # print(f"{country.color} 국가: 예산으로 군대 생성 성공! (프로빈스: {spawn_province.id}, 병력: {created_army.strength}). 남은 예산 {military_budget_gdp - gdp_cost_one_army:.0f} GDP")
                    military_budget_gdp -= gdp_cost_one_army # 예산에서 비용 차감
                    armies_created_this_turn += 1
                else:
                    # print(f"{country.color} 국가: create_army 실패 (프로빈스: {spawn_province.id}). 군대 생성 중단.")
                    break # create_army 실패 시 루프 중단
            
            # if armies_created_this_turn > 0:
                # print(f"{country.color} 국가: 이번 턴에 총 {armies_created_this_turn}개 군대 생성 시도 완료.")
            # print(f"{country.color} 국가: 군대 생성 후 최종 남은 예산 {military_budget_gdp:.0f} GDP")

        # 고립된 지역의 군대 약화 처리
        # (매 프레임마다 체크할 필요는 없으므로, 1초 주기 로직으로 옮기거나 빈도를 조절할 수 있습니다)
        # 현재는 매 프레임마다 실행되도록 유지합니다. 필요시 country.time_elapsed % N == 0 조건 추가 가능.
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

        # 올바르지 않은 프로빈스에 있는 군대 삭제
        invalid_armies = []
        for army in country.armies:
            # 1. current_province가 None인 경우
            if army.current_province is None:
                invalid_armies.append(army)
                print(f"유효하지 않은 군대 발견 (프로빈스 None): {army.owner.color} 국가의 군대 삭제")
                continue
            
            # 2. current_province가 provinces 리스트에 없는 경우 (삭제된 프로빈스)
            if army.current_province not in provinces:
                invalid_armies.append(army)
                print(f"유효하지 않은 군대 발견 (삭제된 프로빈스): {army.owner.color} 국가의 군대 삭제")
                continue
            
            # 3. 적 프로빈스에 주둔한 군대가 있으면 전투 시작 (한 번만)
            province_owner = army.current_province.owner
            if (province_owner is not None and 
                province_owner != army.owner and 
                not army.is_moving and 
                not army.in_battle and
                not hasattr(army, '_combat_initiated')):  # 전투 개시 플래그 확인
                # 적군 프로빈스에 있는 군대는 자동으로 전투에 참여
                print(f"적 프로빈스 {army.current_province.id}에 주둔한 {army.owner.color} 군대가 전투 참여")
                army._combat_initiated = True  # 전투 개시 플래그 설정
                army.engage_province()

        # 유효하지 않은 군대들 제거 (적 프로빈스 주둔 제외)
        for invalid_army in invalid_armies:
            if invalid_army in country.armies:
                country.armies.remove(invalid_army)

        # --- 국가 AI: 작전 계획 및 군대 할당 (공격/방어 그룹 재도입) ---
        MIN_ARMIES_FOR_OPERATION = 3 
        MIN_STRENGTH_FOR_SINGLE_ARMY_OPERATION = ARMY_BASE_STRENGTH * 2.5 # 단일/소수 군대 작전 위한 최소 총 병력
        OPERATION_PLAN_INTERVAL = GAME_TICKS_PER_LOGICAL_SECOND / 2  # 더 자주 작전 계획 (기존 /3에서 /2로)

        if country.time_elapsed % OPERATION_PLAN_INTERVAL == 0:
            # 더 적극적인 방어 임무 할당 (더 자주 실행)
            country.assign_defense_missions()
            
            # 유휴 군대 선정 시 방어/주둔 임무 중인 군대는 제외하되, 전투 중인 군대는 포함하지 않음
            # 빈 땅을 점령 중인 군대도 유휴 군대로 간주하여 추가 임무 할당 가능
            idle_armies = [
                army for army in country.armies 
                if army.strength > 0 and army.mission_type not in ["defense", "garrison"] and not army.in_battle and
                (not army.target_province or 
                 (army.target_province and army.target_province.owner is None))  # 목표가 없거나 목표가 빈 땅인 경우
            ]

            # --- 빈 땅 점령 (항상 실행, 작전 조건과 무관) ---
            available_empty_lands_near_owned = {}
            for owned_p in country.owned_provinces:
                if not owned_p.is_island and not country.is_province_connected_to_capital(owned_p):
                    continue
                for border_p in owned_p.border_provinces:
                    if (border_p.owner is None and border_p.id not in available_empty_lands_near_owned):
                        available_empty_lands_near_owned[border_p.id] = {
                            'province': border_p,
                            'from_province': owned_p
                        }

            assigned_empty_provinces_this_turn = set()
            remaining_idle_armies = list(idle_armies)

            # 빈 땅이 있고 유휴 군대가 있으면 항상 점령 시도
            if available_empty_lands_near_owned and idle_armies:
                sorted_idle_armies_for_empty_land = sorted(idle_armies, key=lambda a: a.strength, reverse=True)
                
                # 빈 땅 점령에 더 많은 군대 할당 (기존: min, 변경: 가능한 모든 군대)
                # 빈 땅 수와 군대 수 중 더 많은 쪽에 맞춰서 할당
                num_armies_for_empty_land = min(
                    len(sorted_idle_armies_for_empty_land), 
                    max(len(available_empty_lands_near_owned), len(sorted_idle_armies_for_empty_land) * 2 // 3)
                )
                
                armies_to_assign_empty_land = sorted_idle_armies_for_empty_land[:num_armies_for_empty_land]
                remaining_idle_armies = sorted_idle_armies_for_empty_land[num_armies_for_empty_land:]

                for army_e in armies_to_assign_empty_land:
                    if not army_e.current_province:
                        continue
                        
                    best_empty_target = None
                   
                    min_actual_distance = float('inf')
                    
                    for p_id, land_info in available_empty_lands_near_owned.items():
                        if land_info['province'] not in assigned_empty_provinces_this_turn:
                            distance_to_launch_point = army_e.calculate_actual_path_length(
                                army_e.current_province, land_info['from_province']
                            )
                            total_distance = distance_to_launch_point + 1
                            
                            if total_distance < min_actual_distance:
                                min_actual_distance = total_distance
                                best_empty_target = land_info['province']
                    
                    if best_empty_target:
                        army_e.set_target(best_empty_target)
                        assigned_empty_provinces_this_turn.add(best_empty_target)
                        print(f"군대 {army_e.owner.color} -> 빈 땅 {best_empty_target.id}")

            # --- 주 작전 계획 (남은 군대로만) ---
            # 주 작전 계획 조건을 더 엄격하게 변경
            should_plan_operation = False
            if len(remaining_idle_armies) >= MIN_ARMIES_FOR_OPERATION * 2:  # 기존보다 2배 많은 군대가 있을 때만
                should_plan_operation = True
            elif 1 <= len(remaining_idle_armies) < MIN_ARMIES_FOR_OPERATION * 2:
                remaining_strength = sum(army.strength for army in remaining_idle_armies)
                if remaining_strength >= MIN_STRENGTH_FOR_SINGLE_ARMY_OPERATION * 1.5:  # 더 강한 군대만
                    should_plan_operation = True

            if should_plan_operation and remaining_idle_armies:
                # 기존 주 작전 로직은 remaining_idle_armies 사용
                idle_armies = remaining_idle_armies
                potential_enemy_targets = []
                actual_attack_targets = []

                if idle_armies: # 빈 땅 점령 후에도 유휴 군대가 남았다면
                    print(f"  빈 땅 점령 후 남은 유휴 군대 {len(idle_armies)}명으로 주 작전 계속.")
                    # 1. 공격 목표 선정 (여러 개 가능) - 여기서부터는 이전 로직과 유사하게 진행
                    # potential_enemy_targets = [] # 이미 위에서 초기화됨
                # for문은 if idle_armies 블록 바깥에 있어야 모든 경우에 potential_enemy_targets를 채울 수 있음.
                # 하지만, idle_armies가 없으면 어차피 공격 그룹도 없으므로, 현재 위치도 논리적으로는 큰 문제 없음.
                # 더 명확하게 하려면, 공격 목표를 찾는 로직은 idle_armies 유무와 관계없이 수행하고,
                # 실제 군대 할당만 idle_armies 유무에 따라 결정하는 것이 좋음.
                # 여기서는 일단 NameError만 해결하는 방향으로 최소 수정.
                # if idle_armies: # 이 조건은 이미 위에 있음.
                for p in provinces: # 이 for문은 공격 목표를 찾는 로직
                    if p.owner and p.owner != country: # 적 프로빈스인 경우
                        can_attack_directly = False # 직접 국경을 맞대고 공격 가능한지
                        can_attack_island = False   # 해안에서 섬을 공격 가능한지

                        for owned_p in country.owned_provinces:
                            # 1. 직접 국경을 맞댄 경우 (기존 로직)
                            if p in owned_p.border_provinces and \
                               (not owned_p.is_island and country.is_province_connected_to_capital(owned_p) or owned_p.is_island):
                                can_attack_directly = True
                                break # 직접 공격 가능하면 더 볼 필요 없음
                            
                            # 2. 섬 공격 가능성 확인 (새로 추가된 로직)
                            # 조건: 아군 프로빈스가 해안이고, 수도와 연결되어 있으며 (또는 자신이 섬이거나)
                            #       적 프로빈스는 섬이어야 함.
                            if owned_p.is_coastal and \
                               (owned_p.is_island or country.is_province_connected_to_capital(owned_p)) and \
                               p.is_island:
                                # 해안 프로빈스와 섬 사이의 거리 계산 (간단히 중심점 간 거리)
                                owned_p_center_x, owned_p_center_y = owned_p.get_center_coordinates()
                                island_p_center_x, island_p_center_y = p.get_center_coordinates()
                                
                                distance_to_island = math.sqrt(
                                    (owned_p_center_x - island_p_center_x)**2 + 
                                    (owned_p_center_y - island_p_center_y)**2
                                )
                                
                                # 예: 특정 거리 이내의 섬만 공격 대상으로 간주 (예: 50 유닛)
                                MAX_ISLAND_ATTACK_RANGE = 50 
                                if distance_to_island <= MAX_ISLAND_ATTACK_RANGE:
                                    can_attack_island = True
                                    # print(f"    섬 공격 가능: {owned_p.id} (해안) -> {p.id} (섬), 거리: {distance_to_island:.2f}")
                                    break # 공격 가능한 섬을 찾았으면 더 볼 필요 없음
                        
                        if can_attack_directly or can_attack_island:
                            if p not in potential_enemy_targets: # 중복 추가 방지
                                potential_enemy_targets.append(p)
                
                actual_attack_targets = []
                if potential_enemy_targets:
                    # 가장 가까운 적들을 우선 목표로 삼음 (최대 2-3개)
                    if idle_armies and idle_armies[0].current_province: # 첫 유휴 군대 위치 기준 (idle_armies 비어있는지 확인)
                        start_coord = idle_armies[0].current_province.get_center_coordinates()
                        potential_enemy_targets.sort(key=lambda p_target: math.sqrt(
                            (p_target.get_center_coordinates()[0] - start_coord[0])**2 +
                            (p_target.get_center_coordinates()[1] - start_coord[1])**2
                        ))
                    # else: # idle_armies가 비어있으면 정렬 없이 potential_enemy_targets 그대로 사용하거나, 다른 기준으로 정렬 가능
                        # print(f"    적 목표 정렬 스킵 (유휴 군대 없음 또는 현재 프로빈스 정보 없음)")
                    actual_attack_targets = list(potential_enemy_targets) # 모든 잠재적 적 목표를 실제 목표로 설정
                    if actual_attack_targets: # 실제 목표가 선정된 경우에만 로그 출력
                        print(f"  선정된 적 공격 목표: {[t.id for t in actual_attack_targets]} (섬 포함 가능)")

                    # 적 공격 목표가 없다면 빈 땅 점령 목표 선정
                    if not actual_attack_targets: # 여기서 actual_attack_targets는 위에서 적 목표를 못 찾았을 경우 비어있을 수 있음
                        # empty_provinces_targets = [] # 이 변수는 사용되지 않으므로 제거 가능
                        empty_provinces_all_candidates = [p for p in provinces if p.owner is None] # 모든 빈 땅 후보

                        # 이 계획 주기에서 이미 첫 번째 단계에서 목표로 지정된 빈 땅 제외
                        empty_provinces_available_for_main_op = [
                            p for p in empty_provinces_all_candidates
                            if p not in assigned_empty_provinces_this_turn
                        ]

                        if empty_provinces_available_for_main_op:
                            if idle_armies and idle_armies[0].current_province: # 여기서 idle_armies는 remaining_idle_armies 입니다.
                                start_coord = idle_armies[0].current_province.get_center_coordinates()
                                empty_provinces_available_for_main_op.sort(key=lambda p_target: math.sqrt(
                                    (p_target.get_center_coordinates()[0] - start_coord[0])**2 +
                                    (p_target.get_center_coordinates()[1] - start_coord[1])**2
                                ))
                            # else:
                                # print(f"    빈 땅 목표 정렬 스킵 (유휴 군대 없음 또는 현재 프로빈스 정보 없음)")
                            
                            # 실제 공격 목표로 설정 (최대 3개)
                            actual_attack_targets = empty_provinces_available_for_main_op[:min(len(empty_provinces_available_for_main_op), 3)]
                            if actual_attack_targets: # 실제 목표가 선정된 경우에만 로그 출력
                                print(f"  선정된 빈 땅 점령 목표 (주 작전): {[t.id for t in actual_attack_targets]}")
                
                if actual_attack_targets: # 공격/점령할 목표가 하나라도 있다면
                    # 2. 군대 그룹 분배 - 빈 땅이 우선이면 공격에 더 집중
                    idle_armies.sort(key=lambda army: army.strength, reverse=True) 
                    
                    # 빈 땅 목표가 많으면 방어군을 줄이고 공격군을 늘림
                    empty_land_targets = [t for t in actual_attack_targets if t.owner is None]
                    enemy_targets = [t for t in actual_attack_targets if t.owner is not None]
                    
                    attack_group = []
                    defense_group = []

                    if len(idle_armies) == 1:
                        attack_group = list(idle_armies)
                        defense_group = []
                        print(f"  단일 강력 군대 작전: 공격군 {len(attack_group)}명")
                    elif len(empty_land_targets) > len(enemy_targets):
                        # 빈 땅이 더 많으면 70% 공격, 30% 방어 (기존 80%/20%에서 조정)
                        num_attack_armies = max(1, math.ceil(len(idle_armies) * 0.7))
                        attack_group = idle_armies[:num_attack_armies]
                        defense_group = idle_armies[num_attack_armies:]
                        print(f"  빈 땅 우선 작전: 공격군 {len(attack_group)}명, 방어군 {len(defense_group)}명")
                    else:
                        # 적군이 더 많으면 50% 공격, 50% 방어 (기존 60%/40%에서 조정)
                        num_attack_armies = math.ceil(len(idle_armies) * 0.5)
                        attack_group = idle_armies[:num_attack_armies]
                        defense_group = idle_armies[num_attack_armies:]
                        print(f"  적군 우선 작전: 공격군 {len(attack_group)}명, 방어군 {len(defense_group)}명")


                    # 3. 공격 그룹 목표 할당
                    if attack_group and actual_attack_targets:
                        for i, army_atk in enumerate(attack_group):
                            target_for_atk_army = actual_attack_targets[i % len(actual_attack_targets)]
                            army_atk.mission_type = "attack" # 공격 임무 설정
                            army_atk.defense_province_target = None # 공격 임무 시 방어 목표는 없음
                            army_atk.set_target(target_for_atk_army)
                            # print(f"    공격군 {id(army_atk)} ({army_atk.strength}) -> 목표 {target_for_atk_army.id} ({'적' if target_for_atk_army.owner and target_for_atk_army.owner != country else '빈땅'})")
                    
                    # 4. 방어 그룹 목표 할당
                    if defense_group and actual_attack_targets:
                        # 방어 그룹은 주로 첫 번째 공격 목표(primary_defense_reference_target)를 기준으로 방어 위치를 선정
                        primary_defense_reference_target = actual_attack_targets[0]

                        # 방어 위치 선정: 공격 목표의 인접 프로빈스가 아닌, 해당 인접 프로빈스들의 '뒤쪽' 아군 프로빈스를 찾음
                        # 즉, 적과 직접 맞닿는 최전선보다는 한 칸 뒤의 안전한 지원 위치를 찾음.
                        potential_staging_areas = set()
                        # 1. primary_defense_reference_target(적 목표)에 인접한 아군 프로빈스 찾기 (최전선)
                        frontline_friendly_provinces = [
                            fp for fp in country.owned_provinces 
                            if primary_defense_reference_target in fp.border_provinces and \
                               (fp.is_island or country.is_province_connected_to_capital(fp))
                        ]

                        # 2. 최전선 아군 프로빈스들의 뒤에 있는(인접한 다른 아군 프로빈스) 곳을 주둔지로 고려
                        for front_p in frontline_friendly_provinces:
                            for rear_p in front_p.border_provinces:
                                if rear_p.owner == country and rear_p != front_p and \
                                   (rear_p.is_island or country.is_province_connected_to_capital(rear_p)):
                                    potential_staging_areas.add(rear_p)
                        
                        # 만약 적절한 후방 주둔지가 없다면, 최전선 아군 프로빈스를 주둔지로 사용
                        if not potential_staging_areas and frontline_friendly_provinces:
                            potential_staging_areas.update(frontline_friendly_provinces)
                        
                        friendly_staging_provinces = list(potential_staging_areas)

                        if friendly_staging_provinces:
                            # print(f"  방어 그룹 배치 시작. 기준 적 목표: {primary_defense_reference_target.id}, 주둔 가능 아군 프로빈스: {[p.id for p in friendly_staging_provinces]}")
                            
                            temp_defense_assignments = {p.id: [] for p in friendly_staging_provinces}
                            armies_for_defense_staging = list(defense_group)

                            # 각 주둔지에 최소 1개씩 또는 가능한 만큼 분산 배치
                            idx_staging = 0
                            while armies_for_defense_staging and idx_staging < len(friendly_staging_provinces):
                                army_to_stage = armies_for_defense_staging.pop(0)
                                temp_defense_assignments[friendly_staging_provinces[idx_staging].id].append(army_to_stage)
                                idx_staging = (idx_staging + 1) % len(friendly_staging_provinces) # 순환하며 배분
                            
                            # 남은 군대가 있다면, 가장 병력이 적게 할당된 주둔지부터 추가 배치 (균등 분배 시도)
                            if armies_for_defense_staging:
                                friendly_staging_provinces.sort(key=lambda p_sort: sum(a.strength for a in temp_defense_assignments[p_sort.id]))
                                for i, army_rem_def in enumerate(armies_for_defense_staging):
                                    target_staging_province = friendly_staging_provinces[i % len(friendly_staging_provinces)]
                                    temp_defense_assignments[target_staging_province.id].append(army_rem_def)
                                # print(f"    남은 방어군 {len(armies_for_defense_staging)}명 추가 분산 배치 완료.")

                            # 최종 할당: 각 군대에 방어 임무 부여
                            for p_id, armies_list in temp_defense_assignments.items():
                                staging_province_obj = next((p_obj for p_obj in friendly_staging_provinces if p_obj.id == p_id), None)
                                if staging_province_obj and armies_list:
                                    for army_final_def in armies_list:
                                        # 방어 대상은 primary_defense_reference_target (적 프로빈스) 또는
                                        # staging_province_obj에 가장 가까운 primary_defense_reference_target에 인접한 아군 프로빈스
                                        # 여기서는 primary_defense_reference_target을 주시하도록 설정
                                        army_final_def.set_defense_mission(primary_defense_reference_target, staging_province_obj)
                        else:
                            # print(f"  방어 그룹: 주둔할 적절한 아군 프로빈스 없음. 가장 가까운 아군 프로빈스로 후퇴/대기.")
                            for army_def_fallback in defense_group:
                                army_def_fallback.mission_type = "garrison" # 주둔 임무로 변경
                                army_def_fallback.defense_province_target = None
                                if country.owned_provinces:
                                    # 현재 위치 또는 가장 가까운 안전한 아군 프로빈스로 이동
                                    if army_def_fallback.current_province.owner == country and \
                                       (army_def_fallback.current_province.is_island or country.is_province_connected_to_capital(army_def_fallback.current_province)):
                                        army_def_fallback.set_target(army_def_fallback.current_province) # 현재 위치 고수
                                    else:
                                        # 가장 가까운 안전한 아군 프로빈스 찾기
                                        safest_fallback = None
                                        min_dist = float('inf')
                                        current_army_coord = army_def_fallback.current_province.get_center_coordinates()
                                        for p_owned in country.owned_provinces:
                                            if p_owned.is_island or country.is_province_connected_to_capital(p_owned):
                                                dist = math.sqrt(
                                                    (p_owned.get_center_coordinates()[0] - current_army_coord[0])**2 +
                                                    (p_owned.get_center_coordinates()[1] - current_army_coord[1])**2)
                                                if dist < min_dist:
                                                    min_dist = dist
                                                    safest_fallback = p_owned
                                        if safest_fallback:
                                            army_def_fallback.set_target(safest_fallback)
                                            # print(f"    방어군 {id(army_def_fallback)} -> 안전 후방 {safest_fallback.id}로 주둔 이동")
                                        else: # 이동할 곳이 없으면 현재 위치에서 대기 (이론상 여기까지 오면 안됨)
                                            army_def_fallback.set_target(army_def_fallback.current_province)

                else: # should_plan_operation이 False인 경우 또는 작전 목표가 없을 때
                    # print(f"{country.color} 국가: 대규모 작전 조건 미달 또는 목표 없음. 유휴 군대(공격/방어 임무 아닌) 개별 행동.")
                    # 여기서 idle_armies는 이미 방어/주둔 임무 군대가 필터링된 상태
                    for army_ind in idle_armies: 
                        if not army_ind.current_province: continue
                        army_ind.mission_type = "attack" # 기본적으로 공격 시도
                        army_ind.defense_province_target = None
                        # 간단히 가장 가까운 빈 땅 또는 적 땅
                        available_targets_overall = []
                        current_army_coord = army_ind.current_province.get_center_coordinates()
                        for p_candidate in provinces:
                            if p_candidate != army_ind.current_province and (p_candidate.owner is None or (p_candidate.owner and p_candidate.owner != country)):
                                dist = math.sqrt((p_candidate.get_center_coordinates()[0] - current_army_coord[0])**2 + (p_candidate.get_center_coordinates()[1] - current_army_coord[1])**2)
                                available_targets_overall.append({'province': p_candidate, 'distance': dist, 'is_island': p_candidate.is_island})
                        if available_targets_overall:
                            available_targets_overall.sort(key=lambda x: (x['is_island'], x['distance']))
                            army_ind.set_target(available_targets_overall[0]['province'])
                            print(f"  개별 군대 {id(army_ind)} -> 가장 가까운 미점령지 {available_targets_overall[0]['province'].id}")    
            # --- 후방 방어군 재배치 로직 추가 ---
            # "모든 방어군 중, 적과 접경하지 않은 프로빈스에 있는 군대의 70%를 가장 가까운 빈 땅으로 보내줘."
            non_frontier_defense_armies = []
            for army_to_check in country.armies:
                if army_to_check.strength > 0 and army_to_check.mission_type in ["defense", "garrison"] and army_to_check.current_province:
                    is_frontier = False
                    for border_p in army_to_check.current_province.border_provinces:
                        if border_p.owner is not None and border_p.owner != country:
                            is_frontier = True
                            break
                    if not is_frontier:
                        non_frontier_defense_armies.append(army_to_check)
            
            if non_frontier_defense_armies:
                num_to_reassign = math.ceil(len(non_frontier_defense_armies) * 0.7)
                armies_to_reassign = random.sample(non_frontier_defense_armies, num_to_reassign)
                
                print(f"{country.color} 국가: 후방 방어군 {len(armies_to_reassign)}명 재배치 시도 (총 {len(non_frontier_defense_armies)}명 중 70%).")

                available_empty_provinces_for_reassign = [p for p in provinces if p.owner is None]

                if available_empty_provinces_for_reassign:
                    # 빈 땅이 있을 경우: 가장 가까운 빈 땅으로 재배치
                    for army_reassign in armies_to_reassign:
                        if not army_reassign.current_province: continue

                        closest_empty_target = None
                        min_dist_empty = float('inf')
                        army_coord = army_reassign.current_province.get_center_coordinates()

                        # 사용 가능한 빈 땅 중에서만 탐색
                        current_available_empty_lands = [p for p in provinces if p.owner is None]
                        if not current_available_empty_lands: # 루프 중 빈 땅이 다 떨어지면 중단
                            print(f"{country.color} 국가: 재배치 중 빈 땅 소진.")
                            break

                        for empty_p in current_available_empty_lands:
                            dist = math.sqrt((empty_p.get_center_coordinates()[0] - army_coord[0])**2 + 
                                             (empty_p.get_center_coordinates()[1] - army_coord[1])**2)
                            if dist < min_dist_empty:
                                min_dist_empty = dist
                                closest_empty_target = empty_p
                        
                        if closest_empty_target:
                            army_reassign.mission_type = "attack" 
                            army_reassign.defense_province_target = None
                            army_reassign.set_target(closest_empty_target)
                            print(f"  재배치 (빈 땅): 군대 {id(army_reassign)} ({army_reassign.strength}) {army_reassign.current_province.id} -> 빈 땅 {closest_empty_target.id}")
                            # 목표로 지정된 빈 땅은 다음 탐색에서 제외 (선택적, 여기서는 간단히 매번 새로 탐색)
                else:
                    # 빈 땅이 없을 경우: 자국 내 군대가 가장 적은 프로빈스로 이동하여 통폐합
                    print(f"{country.color} 국가: 재배치할 빈 땅 없음. 아군 프로빈스로 통폐합 시도.")
                    if country.owned_provinces:
                        for army_reassign in armies_to_reassign:
                            if not army_reassign.current_province: continue

                            # 각 소유 프로빈스별 주둔 병력 계산
                            province_strengths = {}
                            for p_owned in country.owned_provinces:
                                strength_in_p = sum(a.strength for a in country.armies if a.current_province == p_owned)
                                province_strengths[p_owned] = strength_in_p
                            
                            # 병력이 가장 적은 프로빈스 찾기
                            if not province_strengths: # 소유 프로빈스가 있지만, 군대가 없는 경우 등 (이론상 드묾)
                                target_consolidation_province = random.choice(country.owned_provinces)
                            else:
                                target_consolidation_province = min(province_strengths, key=province_strengths.get)

                            if target_consolidation_province:
                                # 현재 위치와 다른 경우에만 이동
                                if army_reassign.current_province != target_consolidation_province:
                                    army_reassign.mission_type = "garrison" # 주둔 임무로 변경
                                    army_reassign.defense_province_target = None
                                    army_reassign.set_target(target_consolidation_province)
                                    print(f"  재배치 (통폐합): 군대 {id(army_reassign)} ({army_reassign.strength}) {army_reassign.current_province.id} -> 프로빈스 {target_consolidation_province.id} (주둔 병력: {province_strengths.get(target_consolidation_province, 0)})")
                                else:
                                    print(f"  재배치 (통폐합): 군대 {id(army_reassign)} 이미 목표 프로빈스 {target_consolidation_province.id}에 위치.")
                            else:
                                print(f"  재배치 (통폐합): {country.color} 국가가 소유한 프로빈스 없음. 군대 {id(army_reassign)} 대기.")
                    else:
                        print(f"{country.color} 국가: 소유한 프로빈스가 없어 통폐합 불가.")

            # --- 전투 시스템 업데이트 ---
            battle_manager.update_all_battles()

        # 각 군대의 행동 업데이트 (기존 이동 및 전투 로직은 유지)
        for army in list(country.armies): # 리스트가 변경될 수 있으므로 복사본 사용
            if army.strength <= 0:
                if army in country.armies: # 이미 제거되었을 수 있으므로 확인
                    country.armies.remove(army)
                continue
            
            # 군대 이동
            army.move()
            
            # 목표 프로빈스에 도착했고 이동 중이 아닐 때만 행동 수행
            if not army.is_moving and army.target_province and army.current_province.id == army.target_province.id:
                army.engage_province() # engage_province 내부에서 target_province를 None으로 설정할 수 있음

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
