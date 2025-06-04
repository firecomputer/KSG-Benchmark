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
import logging
import os # for logging path
import asyncio # 비동기 처리를 위해 추가

# Gemini Agent Import
try:
    from gemini_agent import GeminiAgent
except ImportError:
    print("오류: gemini_agent.py를 찾을 수 없거나, 해당 모듈에 GeminiAgent 클래스가 없습니다.")
    GeminiAgent = None # Define as None if import fails

# --- 로깅 설정 ---
# 게임 전체 로거
game_logger = logging.getLogger('GameLogger')
game_logger.setLevel(logging.INFO)

# GeminiAgent 로거 (gemini_agent.py에서 설정된 로거를 가져오거나, 여기서 핸들러 추가)
# gemini_agent.py에서 이미 파일 핸들러를 설정하고 있으므로, 여기서는 콘솔 핸들러만 추가하거나
# game.py에서 파일 핸들러를 중앙 관리할 수 있습니다.
# 여기서는 game.py가 gemini.log 파일 핸들러를 관리하도록 하고,
# GeminiAgent 클래스 내에서는 getLogger만 사용하도록 하는 것이 좋습니다.
# 하지만 gemini_agent.py가 독립적으로 실행될 수도 있으므로, 중복 방지 로직이 중요합니다.

log_file_path_game = os.path.join(os.path.dirname(__file__), 'gemini.log') # game.py와 같은 디렉토리
# 파일 핸들러 (기존 핸들러가 없거나, 다른 파일이면 추가)
# game_logger와 gemini_agent_logger가 같은 파일을 사용하도록 설정
if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file_path_game for h in game_logger.handlers):
    file_handler_game = logging.FileHandler(log_file_path_game, encoding='utf-8', mode='a') # append mode
    formatter_game = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler_game.setFormatter(formatter_game)
    game_logger.addHandler(file_handler_game)

# GeminiAgent 로거에도 같은 파일 핸들러를 사용하도록 설정 (gemini_agent.py에서 설정 안했을 경우 대비)
if GeminiAgent: # GeminiAgent가 성공적으로 import 되었을 때만
    gemini_logger_instance = logging.getLogger('GeminiAgentLogger') # gemini_agent.py에서 사용하는 로거 이름
    gemini_logger_instance.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file_path_game for h in gemini_logger_instance.handlers):
        # game_logger에 추가된 핸들러를 공유하거나 새로 만들 수 있음
        # 여기서는 game_logger와 같은 핸들러를 사용하도록 함 (이미 위에서 생성)
        if 'file_handler_game' in locals() and file_handler_game not in gemini_logger_instance.handlers:
             gemini_logger_instance.addHandler(file_handler_game)
    # 콘솔 핸들러 (디버깅용)
    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter_game)
    # if not gemini_logger_instance.handlers: # 콘솔 핸들러는 중복 추가될 수 있으므로 주의
    #     gemini_logger_instance.addHandler(console_handler)
    # if not game_logger.handlers:
    #     game_logger.addHandler(console_handler)


game_logger.info("게임 시작 및 로거 설정 완료.")

# --- 게임 상수 설정 ---

# 화면 해상도 (원본 이미지 크기의 0.33배)
SCREEN_WIDTH = 551
SCREEN_HEIGHT = 964

# 실제 게임 내 길이 비율 (타일 크기 조절에 사용)
REAL_LENGTH_FACTOR = 1

# 게임에 참여할 국가의 수
COUNTRY_COUNT = 5

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
    with open('black_dot_coordinates.json', 'r') as f:
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
    def __init__(self, country_id, name, start_province, color, start_population, start_gdp):
        """
        Country 클래스의 생성자.

        Args:
            country_id (int): 국가의 고유 ID.
            name (str): 국가의 이름.
            start_province (Province): 국가가 시작할 프로빈스 객체.
            color (tuple): 국가의 고유 색상 RGB 튜플.
            start_population (int): 국가의 초기 인구.
            start_gdp (int): 국가의 초기 GDP.
        """
        self.id = country_id
        self.name = name # 국가 이름 추가
        self.color = color
        self.time_elapsed = 0  # 게임 시간/프레임 카운터
        self.owned_provinces = []  # 국가가 소유한 프로빈스 목록
        self.armies = [] # 국가가 소유한 군대 목록
        self.capital_province = start_province  # 국가의 수도 프로빈스
        
        self.allies = set() # 동맹 국가 Set (Country 객체 저장)
        self.enemies = set() # 적대 국가 Set (Country 객체 저장)

        # --- 반란 시스템 속성 ---
        self.rebellion_risk = 0.05  # 기본 반란 위험도 (5%)
        self.last_rebellion_turn = -1000 # 마지막 반란 발생 턴 (초기값은 아주 오래 전으로)
        self.economic_stability = 1.0 # 경제 안정도 (0.0 ~ 1.0+), 높을수록 안정
        # 반란 진압 후 안정화 기간 (턴 수)
        self.rebellion_cooldown_period = 100 # 예: 100턴 (논리적 초 기준으로는 더 길게 설정 가능)
        # --- 반란 시스템 속성 끝 ---
        
        # AI 에이전트 초기화
        if GeminiAgent:
            self.ai_agent = GeminiAgent() # 각 국가별 AI 에이전트
            game_logger.info(f"국가 '{self.name}' AI 에이전트 초기화 완료.")
        else:
            self.ai_agent = None
            game_logger.warning(f"국가 '{self.name}' AI 에이전트 초기화 실패 (GeminiAgent 모듈 로드 실패).")

        # 예산 관련 변수 (AI가 결정)
        self.budget_allocation = {"국방": 0.4, "경제": 0.3, "연구": 0.3} # 기본값
        self.military_budget_ratio_ai = MILITARY_BUDGET_RATIO # AI 결정용 국방 예산 비율 (기본값 사용)
        self.attack_ratio_ai = 0.5 # AI 결정용 공격 비율 (기본값: 50% 공격, 50% 방어)
        self.attack_target_ai = None # AI 결정용 공격 대상 국가

        # When adding the first province, assign its initial population and GDP
        self.add_province(start_province, initial_population=start_population, initial_gdp=start_gdp)
        game_logger.info(f"국가 '{self.name}' 생성 완료. 수도: {start_province.id if start_province else '없음'}, 인구: {start_population}, GDP: {start_gdp}")

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
            # print(f"해안 프로빈스에서 군대 생성량 30% 감소: {strength} -> {actual_strength}") # 로그로 대체

        required_population = actual_strength * POPULATION_COST_PER_STRENGTH
        required_gdp = actual_strength * GDP_COST_PER_STRENGTH

        # 1. 자원이 충분한지 먼저 확인합니다.
        if self.get_total_population() < required_population or self.get_total_gdp() < required_gdp:
            game_logger.debug(f"국가 '{self.name}': 프로빈스 {province.id}에 군대 창설 실패 - 자원 부족 (요구 인구: {required_population}, 요구 GDP: {required_gdp})")
            return None

        # 2. 자원 차감을 시도합니다.
        if self.deduct_population(required_population) and self.deduct_gdp(required_gdp):
            new_army = Army(self, province, actual_strength)
            self.armies.append(new_army)
            game_logger.info(f"국가 '{self.name}': 프로빈스 {province.id}에 {actual_strength:,}명 군대 창설! (GDP 기반)")
            return new_army
        else:
            game_logger.warning(f"국가 '{self.name}': 프로빈스 {province.id}에 군대 창설 실패 - 자원 차감 실패")
            return None

    def add_ally(self, other_country):
        if other_country and other_country != self and other_country not in self.allies:
            self.allies.add(other_country)
            other_country.allies.add(self) # 상호 동맹
            # 적대 관계였다면 해소
            if other_country in self.enemies:
                self.enemies.remove(other_country)
                other_country.enemies.remove(self)
            game_logger.info(f"외교: '{self.name}' 국가와 '{other_country.name}' 국가가 동맹을 맺었습니다.")
            return True
        return False

    def remove_ally(self, other_country):
        if other_country and other_country in self.allies:
            self.allies.remove(other_country)
            other_country.allies.remove(self) # 상호 동맹 해제
            game_logger.info(f"외교: '{self.name}' 국가와 '{other_country.name}' 국가의 동맹이 해제되었습니다.")
            return True
        return False

    def add_enemy(self, other_country):
        if other_country and other_country != self and other_country not in self.enemies:
            self.enemies.add(other_country)
            other_country.enemies.add(self) # 상호 적대
            # 동맹 관계였다면 해소
            if other_country in self.allies:
                self.allies.remove(other_country)
                other_country.allies.remove(self)
            game_logger.info(f"외교: '{self.name}' 국가가 '{other_country.name}' 국가에 선전포고했습니다!")
            return True
        return False

    def remove_enemy(self, other_country): # 휴전 등으로 적대 관계 해소
        if other_country and other_country in self.enemies:
            self.enemies.remove(other_country)
            other_country.enemies.remove(self) # 상호 적대 해제
            game_logger.info(f"외교: '{self.name}' 국가와 '{other_country.name}' 국가가 휴전했습니다.")
            return True
        return False

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
game_logger.info(f"프로빈스 생성 완료. 총 프로빈스 수: {len(provinces)}")

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
# 각 국가는 다른 국가들과 일정한 거리를 유지하며 스폰되도록 수정
country_id_counter = 0
if provinces:
    # 육지 프로빈스만 필터링 (land_coords에 속한 타일로만 구성된 프로빈스, 섬 제외)
    valid_start_provinces = [p for p in provinces if all((t.x, t.y) in land_coords for t in p.tiles) and not p.is_island]
    
    if valid_start_provinces:
        # 사용 가능한 프로빈스 복사본 생성 (소유되지 않은 프로빈스만)
        available_provinces_for_spawn = [p for p in valid_start_provinces if p.owner is None]
        
        country_colors = []
        for i in range(COUNTRY_COUNT):
            if not available_provinces_for_spawn:
                game_logger.warning("경고: 모든 유효한 시작 프로빈스가 소진되었습니다. 추가 국가를 초기화할 수 없습니다.")
                break

            start_province = None
            if not countries: # 첫 번째 국가인 경우
                if available_provinces_for_spawn: # 선택할 프로빈스가 있는지 확인
                    start_province = random.choice(available_provinces_for_spawn)
                else: # 선택할 프로빈스가 없으면 루프 종료
                    game_logger.warning("경고: 첫 번째 국가를 위한 시작 프로빈스가 없습니다.")
                    break 
            else:
                # 기존 국가들과 가장 멀리 떨어진 프로빈스 선택
                best_province_candidate = None
                max_overall_min_distance = -1

                for candidate_province in available_provinces_for_spawn:
                    candidate_center = candidate_province.get_center_coordinates()
                    current_province_min_distance_to_capitals = float('inf')
                    
                    # 이 후보 프로빈스와 기존 모든 국가 수도 간의 최소 거리 계산
                    for existing_country in countries:
                        if existing_country.capital_province: # 수도가 있어야 거리 계산 가능
                            existing_capital_center = existing_country.capital_province.get_center_coordinates()
                            distance = math.sqrt(
                                (candidate_center[0] - existing_capital_center[0])**2 +
                                (candidate_center[1] - existing_capital_center[1])**2
                            )
                            current_province_min_distance_to_capitals = min(current_province_min_distance_to_capitals, distance)
                    
                    # 이 후보 프로빈스의 '기존 수도들과의 최소 거리'가
                    # 지금까지 고려된 다른 후보 프로빈스들의 '기존 수도들과의 최소 거리'보다 크면 업데이트
                    if current_province_min_distance_to_capitals > max_overall_min_distance:
                        max_overall_min_distance = current_province_min_distance_to_capitals
                        best_province_candidate = candidate_province
                
                start_province = best_province_candidate

            if start_province:
                if start_province in available_provinces_for_spawn: # 아직 사용 가능한지 재확인 (동시성 문제 방지용이지만 여기선 단일 스레드)
                    available_provinces_for_spawn.remove(start_province) # 선택된 프로빈스 제거
                
                # 무작위 색상 생성
                for j in range(0,20000): # 20000d은 임의의 숫자. 추후 변경 가능
                    color_not_accepted = False
                    start_r, start_g, start_b = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
                    for country_color in country_colors:
                        rDiff = country_color[0]
                        gDiff = country_color[1]
                        bDiff = country_color[2]
                        if(rDiff+gDiff+bDiff < 100):
                            color_not_accepted = True
                    if(color_not_accepted == False):
                        break
                start_color = (start_r, start_g, start_b)
                country_colors.append(start_color)
                
                country_id_counter += 1
                country_name = f"냥냥 왕국 {country_id_counter}"

                countries.append(Country(country_id_counter, country_name, start_province, start_color, initial_population, initial_gdp))
                game_logger.info(f"국가 '{country_name}' 생성: 프로빈스 {start_province.id}, 최소 거리 유지값: {max_overall_min_distance if i > 0 else 'N/A'}")
            else:
                # 적절한 프로빈스를 찾지 못한 경우 (예: 모든 남은 프로빈스가 너무 가깝거나, 후보가 없는 경우)
                # fallback: 남은 프로빈스 중 무작위로 선택 (만약 있다면)
                if available_provinces_for_spawn:
                    game_logger.warning(f"경고: {i+1}번째 국가를 위한 최적의 시작 프로빈스를 찾지 못했습니다. 남은 후보 중 무작위 선택.")
                    start_province = random.choice(available_provinces_for_spawn)
                    available_provinces_for_spawn.remove(start_province)
                    
                    start_r, start_g, start_b = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
                    start_color = (start_r, start_g, start_b)
                    country_id_counter += 1
                    country_name = f"냥냥 왕국 {country_id_counter}"
                    countries.append(Country(country_id_counter, country_name, start_province, start_color, initial_population, initial_gdp))
                    game_logger.info(f"  ㄴ fallback: '{country_name}'을(를) 남은 프로빈스 {start_province.id}에 생성.")
                else:
                    game_logger.warning("경고: 더 이상 국가를 생성할 프로빈스가 없습니다. 국가 생성을 중단합니다.")
                    break 
    else:
        game_logger.warning("경고: 생성된 유효한 시작 프로빈스가 없습니다. 국가를 초기화할 수 없습니다.")
else:
    game_logger.warning("경고: 생성된 프로빈스가 없습니다. 국가를 초기화할 수 없습니다.")

game_logger.info(f"국가 생성 완료. 총 국가 수: {len(countries)}")


# --- AI용 게임 상태 정보 수집 함수 ---
def get_game_state_for_ai(current_country, all_countries, game_turn):
    """AI 에이전트에게 전달할 게임 상태 정보를 구성합니다."""
    all_nations_details = []
    for c in all_countries:
        relation_to_current = "자신"
        if c != current_country:
            if c in current_country.allies:
                relation_to_current = "동맹"
            elif c in current_country.enemies:
                relation_to_current = "적대"
            else:
                relation_to_current = "중립"
        
        nation_detail = {
            "name": c.name,
            "population": c.get_total_population(),
            "gdp": c.get_total_gdp(),
            "province_count": len(c.owned_provinces),
            "army_count": len(c.armies),
            "capital_province_id": c.capital_province.id if c.capital_province else None,
            "allies": [ally.name for ally in c.allies],
            "enemies": [enemy.name for enemy in c.enemies],
            "relation_to_me": relation_to_current # 현재 AI 국가 기준 관계
        }
        all_nations_details.append(nation_detail)

    my_bordering_nations_detail = []
    for p in current_country.owned_provinces:
        for bp in p.border_provinces:
            if bp.owner and bp.owner != current_country:
                # all_nations_details에서 해당 국가 정보 찾기
                border_nation_info = next((n for n in all_nations_details if n["name"] == bp.owner.name), None)
                if border_nation_info and border_nation_info not in my_bordering_nations_detail: # 중복 방지
                    my_bordering_nations_detail.append(border_nation_info)
    
    game_state = {
        "current_turn": game_turn,
        "my_nation_name": current_country.name,
        "all_nations_details": all_nations_details,
        "my_nation_bordering_nations_detail": my_bordering_nations_detail,
        "global_events": [] # 현재는 사용 안함
    }
    return game_state

# --- 게임 루프 ---
running = True
game_current_turn = 0 # 전체 게임 턴 카운터
while running:
    # 이벤트 처리
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False  # 창 닫기 버튼 클릭 시 게임 종료

        # 각 국가에 대한 게임 로직 업데이트
    game_current_turn += 1 # 매 프레임마다 턴 증가 (또는 GAME_TICKS_PER_LOGICAL_SECOND 마다)
    if game_current_turn % (GAME_TICKS_PER_LOGICAL_SECOND * 5) == 0: # 예: 5초마다 AI 결정
        game_logger.info(f"--- 게임 턴 {game_current_turn // GAME_TICKS_PER_LOGICAL_SECOND} 시작 ---")

    for country in countries:
        # 시간 경과에 따른 국가 스탯 업데이트
        country.time_elapsed += 1
        
        # 매 GAME_TICKS_PER_LOGICAL_SECOND 틱마다 경제 및 군사 로직 처리
        if country.time_elapsed % GAME_TICKS_PER_LOGICAL_SECOND == 0:
            current_logical_second = country.time_elapsed // GAME_TICKS_PER_LOGICAL_SECOND
            game_logger.debug(f"국가 '{country.name}' 틱 {country.time_elapsed} (논리적 초: {current_logical_second}) 경제/군사/반란 업데이트 시작")

            # 1. 인구 및 GDP 성장 (퍼센트 + 고정값)
            economy_investment_ratio = country.budget_allocation.get("경제", 0.3)
            gdp_growth_rate = 0.05 * (1 + economy_investment_ratio * 0.5) 
            
            for p in country.owned_provinces:
                p.population += int(p.population * 0.01)
                p.gdp += int(p.gdp * gdp_growth_rate)
            country.add_gdp(FIXED_GDP_BOOST_PER_TICK * (1 + economy_investment_ratio))
            game_logger.debug(f"국가 '{country.name}': 인구/GDP 성장 완료. 경제 투자율: {economy_investment_ratio*100:.1f}%, GDP 성장률: {gdp_growth_rate*100:.1f}%")

            # --- 반란 시스템 업데이트 ---
            # 경제 안정도 업데이트 (경제 투자 비율에 따라)
            # 경제 투자 비율이 0.3 (30%)일 때 안정도 1.0 기준
            country.economic_stability = (economy_investment_ratio / 0.3) * 1.0 
            country.economic_stability = max(0.1, min(country.economic_stability, 1.5)) # 최소 0.1, 최대 1.5

            # 반란 위험도 계산
            base_risk = 0.01 # 기본 최소 위험
            economic_factor = (1.0 / (country.economic_stability + 0.01)) # 경제 안정도가 낮을수록 위험 증가 (0.01은 분모 0 방지)
            
            # 경제 예산이 매우 낮으면 (예: 10% 미만) 위험도 급증
            if economy_investment_ratio < 0.1:
                economic_factor *= 5
            elif economy_investment_ratio < 0.2:
                economic_factor *= 2
            
            country.rebellion_risk = base_risk * economic_factor
            
            # 마지막 반란 이후 쿨다운 적용
            if game_current_turn - country.last_rebellion_turn < country.rebellion_cooldown_period:
                # 쿨다운 기간에는 위험도를 크게 낮춤
                # 남은 쿨다운 기간에 비례하여 점진적으로 회복하도록 수정 가능
                time_since_rebellion = game_current_turn - country.last_rebellion_turn
                cooldown_factor = time_since_rebellion / country.rebellion_cooldown_period # 0에서 1로 증가
                # 초기에는 매우 낮고, 쿨다운 종료 시점에 가까워질수록 원래 위험도에 근접
                country.rebellion_risk *= (0.1 + 0.9 * cooldown_factor) 
                country.rebellion_risk = max(0.001, country.rebellion_risk) # 최소 위험도 보장
            
            country.rebellion_risk = min(country.rebellion_risk, 0.5) # 최대 위험도 50%로 제한
            game_logger.debug(f"국가 '{country.name}': 경제 안정도 {country.economic_stability:.2f}, 반란 위험도 {country.rebellion_risk:.4f}")

            # 반란 발생 처리
            if random.random() < country.rebellion_risk and len(country.owned_provinces) > 1: # 최소 1개 프로빈스는 남겨둠
                # 반란 발생!
                rebel_province_count = random.randint(1, max(1, len(country.owned_provinces) // 3)) # 최대 1/3 프로빈스 반란
                rebel_provinces = random.sample(country.owned_provinces, min(rebel_province_count, len(country.owned_provinces) -1))
                
                game_logger.warning(f"*** 반란 발생! 국가 '{country.name}'에서 {len(rebel_provinces)}개 프로빈스 반란! ***")
                for p_rebel in rebel_provinces:
                    if p_rebel == country.capital_province: # 수도가 반란하면 수도 이전
                        country.remove_province(p_rebel) # 먼저 국가에서 제거
                        # 수도 이전 로직은 remove_province 내에서 처리됨
                        game_logger.warning(f"  ㄴ 수도 {p_rebel.id} 포함 반란! 수도 이전됨.")
                    else:
                        country.remove_province(p_rebel)
                    
                    # 반란 프로빈스는 중립화 (또는 새로운 반란군 세력으로 만들 수 있음)
                    p_rebel.owner = None 
                    p_rebel.change_color(black) # 중립 색상
                    # 반란 프로빈스의 군대 처리 (해당 프로빈스 주둔군은 소멸 또는 반란군으로 전환)
                    armies_in_rebel_province = [army for army in country.armies if army.current_province == p_rebel]
                    for army_rebel in armies_in_rebel_province:
                        if army_rebel in country.armies:
                            country.armies.remove(army_rebel)
                        game_logger.info(f"  ㄴ 반란 프로빈스 {p_rebel.id}의 군대 소멸.")
                    
                    game_logger.info(f"  ㄴ 프로빈스 {p_rebel.id}가 중립화되었습니다.")

                country.last_rebellion_turn = game_current_turn # 마지막 반란 턴 업데이트
                # 반란 직후에는 국가 전체의 반란 위험도를 일시적으로 더 낮출 수 있음 (이미 쿨다운으로 처리 중)
                # country.rebellion_risk *= 0.1 
            # --- 반란 시스템 업데이트 끝 ---

            # 2. 군대 유지비 계산 및 차감
            total_army_strength = country.get_total_army_strength()
            maintenance_cost = total_army_strength * ARMY_MAINTENANCE_PER_STRENGTH_PER_TICK
            
            if maintenance_cost > 0:
                if not country.deduct_gdp(maintenance_cost):
                    game_logger.warning(f"국가 '{country.name}': 군대 유지비 {maintenance_cost:.1f} GDP 소모 실패. GDP 부족.")
                else:
                    game_logger.debug(f"국가 '{country.name}': 군대 유지비 {maintenance_cost:.1f} GDP 소모 완료. 남은 GDP: {country.get_total_gdp()}")

            # 3. GDP 확인 및 군대 자동 해체
            current_gdp = country.get_total_gdp()
            while current_gdp < GDP_LOW_THRESHOLD and country.armies:
                country.armies.sort(key=lambda army: army.strength)
                if not country.armies: break
                disbanded_army = country.armies.pop(0)
                game_logger.info(f"국가 '{country.name}': GDP 부족 ({current_gdp} < {GDP_LOW_THRESHOLD})으로 군대 (병력: {disbanded_army.strength}) 해체.")
            
            # 4. 군대 창설 로직 (AI가 결정한 국방 예산 비율 사용)
            total_gdp = country.get_total_gdp()
            # military_budget_gdp = total_gdp * country.military_budget_ratio_ai # AI 결정 사용
            # AI가 결정한 국방 예산 비율을 사용
            actual_military_budget_ratio = country.budget_allocation.get("국방", country.military_budget_ratio_ai)
            military_budget_gdp = total_gdp * actual_military_budget_ratio

            game_logger.debug(f"국가 '{country.name}': 군대 창설 시도. 국방 예산 비율: {actual_military_budget_ratio*100:.1f}%, 가용 예산 GDP: {military_budget_gdp:.0f}")

            population_cost_one_army = POPULATION_COST_PER_STRENGTH * ARMY_BASE_STRENGTH
            gdp_cost_one_army = GDP_COST_PER_STRENGTH * ARMY_BASE_STRENGTH
            armies_created_this_turn = 0

            while military_budget_gdp >= gdp_cost_one_army and \
                  country.owned_provinces and \
                  armies_created_this_turn < MAX_ARMIES_PER_TURN_BUDGET and \
                  len(country.armies) < 20: # 최대 군대 수 제한

                if country.get_total_population() < population_cost_one_army or \
                   country.get_total_gdp() < gdp_cost_one_army:
                    game_logger.debug(f"국가 '{country.name}': 실제 자원 부족으로 군대 생성 중단.")
                    break

                eligible_provinces = [p for p in country.owned_provinces if (p.is_island or country.is_province_connected_to_capital(p))]
                if not eligible_provinces:
                    game_logger.debug(f"국가 '{country.name}': 군대 생성 가능한 프로빈스 없음.")
                    break

                spawn_province = random.choice(eligible_provinces)
                created_army = country.create_army(spawn_province, ARMY_BASE_STRENGTH)

                if created_army:
                    military_budget_gdp -= gdp_cost_one_army
                    armies_created_this_turn += 1
                    game_logger.info(f"국가 '{country.name}': 예산으로 군대 생성 (프로빈스: {spawn_province.id}, 병력: {created_army.strength}). 남은 예산 {military_budget_gdp:.0f} GDP")
                else:
                    game_logger.warning(f"국가 '{country.name}': create_army 실패 (프로빈스: {spawn_province.id}).")
                    break
            
            if armies_created_this_turn > 0:
                game_logger.info(f"국가 '{country.name}': 이번 턴에 총 {armies_created_this_turn}개 군대 생성 완료.")

        # --- AI 의사 결정 (예: 5초마다) ---
        # 비동기 종합 결정 로직으로 변경
        ai_decision_interval = GAME_TICKS_PER_LOGICAL_SECOND * 10 # AI 결정 주기 (예: 10초)
        # 모든 국가에 대해 한 번에 AI 결정을 요청하고 처리하기 위한 플래그 또는 조건
        # 여기서는 game_current_turn을 사용하여 특정 턴마다 모든 AI의 결정을 한 번에 처리
        if game_current_turn > 0 and game_current_turn % ai_decision_interval == 0:
            game_logger.info(f"===== 전체 AI 국가 의사결정 시작 (게임 턴: {game_current_turn}) =====")
            
            async def get_all_ai_decisions():
                tasks = []
                for c_ai in countries:
                    if c_ai.ai_agent:
                        current_game_state_for_ai = get_game_state_for_ai(c_ai, countries, game_current_turn)
                        # 종합 결정에 필요한 옵션들 준비
                        war_opts = [other_c.name for other_c in countries if other_c != c_ai and other_c not in c_ai.allies and other_c not in c_ai.enemies]
                        alliance_opts = [other_c.name for other_c in countries if other_c != c_ai and other_c not in c_ai.allies and other_c not in c_ai.enemies]
                        truce_opts = [enemy.name for enemy in c_ai.enemies]
                        budget_ref = c_ai.get_total_gdp() * 0.2 # 예산 편성 기준점 (예: GDP의 20%)

                        tasks.append(c_ai.ai_agent.get_comprehensive_decision_async(
                            current_game_state_for_ai,
                            budget_ref,
                            war_opts,
                            alliance_opts,
                            truce_opts
                        ))
                    else:
                        # AI 에이전트가 없는 경우, 기본 결정 반환 (또는 None 처리)
                        default_decision = {
                            "budget": {"defense_ratio": 0.4, "economy_ratio": 0.3, "research_ratio": 0.3, "reason": "기본 예산"},
                            "attack_strategy": {"target_nation": "없음", "attack_ratio": 0.5, "reason": "기본 전략"},
                            "declare_war": {"target_nation": "아니오", "reason": "기본"},
                            "form_alliance": {"target_nation": "아니오", "reason": "기본"},
                            "offer_truce": {"target_nation": "아니오", "reason": "기본"}
                        }
                        # asyncio.Future를 만들어 즉시 결과를 설정하거나, 단순 리스트에 추가 후 처리
                        future = asyncio.Future()
                        future.set_result(default_decision)
                        tasks.append(future)
                
                return await asyncio.gather(*tasks)

            all_decisions = asyncio.run(get_all_ai_decisions())

            for i, country_obj in enumerate(countries):
                if country_obj.ai_agent and i < len(all_decisions):
                    decisions = all_decisions[i]
                    game_logger.info(f"--- 국가 '{country_obj.name}' AI 종합 결정 적용 시작 ---")
                    game_logger.info(f"AI 종합 결정 내용 ({country_obj.name}): {decisions}")

                    # 1. 예산 편성 적용
                    budget_decision = decisions.get("budget", {})
                    country_obj.budget_allocation = {
                        "국방": budget_decision.get("defense_ratio", 0.4),
                        "경제": budget_decision.get("economy_ratio", 0.3),
                        "연구": budget_decision.get("research_ratio", 0.3)
                    }
                    game_logger.info(f"AI 결정 ({country_obj.name}): 예산 편성 = {country_obj.budget_allocation}, 이유 = {budget_decision.get('reason', 'N/A')}")

                    # 2. 공격-방어 전략 적용
                    attack_strategy = decisions.get("attack_strategy", {})
                    country_obj.attack_ratio_ai = attack_strategy.get("attack_ratio", 0.5)
                    attack_target_name = attack_strategy.get("target_nation")
                    if attack_target_name and attack_target_name.lower() != "없음":
                        country_obj.attack_target_ai = next((c for c in countries if c.name == attack_target_name), None)
                    else:
                        country_obj.attack_target_ai = None
                    game_logger.info(f"AI 결정 ({country_obj.name}): 공격 대상 = {country_obj.attack_target_ai.name if country_obj.attack_target_ai else '없음'}, 공격 비율 = {country_obj.attack_ratio_ai:.2f}, 이유 = {attack_strategy.get('reason', 'N/A')}")

                    # 3. 선전포고 적용
                    declare_war_decision = decisions.get("declare_war", {})
                    war_target_name = declare_war_decision.get("target_nation")
                    if war_target_name and war_target_name.lower() != "아니오" and war_target_name.lower() != "없음":
                        target_c_obj = next((c for c in countries if c.name == war_target_name), None)
                        if target_c_obj and target_c_obj != country_obj and target_c_obj not in country_obj.enemies: # 이미 적이 아닌 경우에만
                            country_obj.add_enemy(target_c_obj)
                            game_logger.info(f"AI 결정 ({country_obj.name}): '{war_target_name}'에 선전포고. 이유: {declare_war_decision.get('reason', 'N/A')}")
                    elif war_target_name and (war_target_name.lower() == "아니오" or war_target_name.lower() == "없음"):
                         game_logger.info(f"AI 결정 ({country_obj.name}): 선전포고하지 않음. 이유: {declare_war_decision.get('reason', 'N/A')}")


                    # 4. 동맹 결정 적용
                    form_alliance_decision = decisions.get("form_alliance", {})
                    alliance_target_name = form_alliance_decision.get("target_nation")
                    if alliance_target_name and alliance_target_name.lower() != "아니오" and alliance_target_name.lower() != "없음":
                        target_c_obj = next((c for c in countries if c.name == alliance_target_name), None)
                        if target_c_obj and target_c_obj != country_obj and target_c_obj not in country_obj.allies and target_c_obj not in country_obj.enemies: # 동맹/적이 아닌 경우
                            country_obj.add_ally(target_c_obj)
                            game_logger.info(f"AI 결정 ({country_obj.name}): '{alliance_target_name}'와 동맹 시도. 이유: {form_alliance_decision.get('reason', 'N/A')}")
                    elif alliance_target_name and (alliance_target_name.lower() == "아니오" or alliance_target_name.lower() == "없음"):
                        game_logger.info(f"AI 결정 ({country_obj.name}): 동맹 맺지 않음. 이유: {form_alliance_decision.get('reason', 'N/A')}")
                    
                    # 5. 휴전 결정 적용
                    offer_truce_decision = decisions.get("offer_truce", {})
                    truce_target_name = offer_truce_decision.get("target_nation")
                    if truce_target_name and truce_target_name.lower() != "아니오" and truce_target_name.lower() != "없음":
                        target_c_obj = next((c for c in countries if c.name == truce_target_name), None)
                        if target_c_obj and target_c_obj in country_obj.enemies: # 현재 적대 관계일 때만
                            country_obj.remove_enemy(target_c_obj) # 휴전
                            game_logger.info(f"AI 결정 ({country_obj.name}): '{truce_target_name}'와 휴전 시도. 이유: {offer_truce_decision.get('reason', 'N/A')}")
                    elif truce_target_name and (truce_target_name.lower() == "아니오" or truce_target_name.lower() == "없음"):
                         game_logger.info(f"AI 결정 ({country_obj.name}): 휴전하지 않음. 이유: {offer_truce_decision.get('reason', 'N/A')}")
                    game_logger.info(f"--- 국가 '{country_obj.name}' AI 종합 결정 적용 완료 ---")
            game_logger.info(f"===== 전체 AI 국가 의사결정 완료 (게임 턴: {game_current_turn}) =====")


        # 고립된 지역의 군대 약화 처리 (기존 로직 유지)
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

        # --- 국가 AI: 작전 계획 및 군대 할당 (AI 결정 반영) ---
        # MIN_ARMIES_FOR_OPERATION = 3 
        # MIN_STRENGTH_FOR_SINGLE_ARMY_OPERATION = ARMY_BASE_STRENGTH * 2.5
        # OPERATION_PLAN_INTERVAL = GAME_TICKS_PER_LOGICAL_SECOND / 2 # 기존 AI 로직 주기
        # AI 결정 주기는 위에서 별도로 처리 (ai_decision_interval)
        # 여기서는 AI가 결정한 attack_ratio_ai 와 attack_target_ai를 사용하도록 수정

        # 매 프레임 또는 짧은 주기마다 군대 운용 업데이트 (기존 로직 기반, AI 결정 활용)
        # 예: 매초마다 군대 운용 업데이트
        if country.time_elapsed % GAME_TICKS_PER_LOGICAL_SECOND == 0:
            game_logger.debug(f"국가 '{country.name}' 군대 운용 업데이트 시작. 공격 목표 AI: {country.attack_target_ai.name if country.attack_target_ai else '없음'}, 공격 비율 AI: {country.attack_ratio_ai:.2f}")
            
            # 1. 방어 임무 할당 (기존 assign_defense_missions 사용하되, AI의 공격 비율 고려)
            # 전체 군대의 (1 - attack_ratio_ai) 만큼을 방어에 우선 할당하도록 수정 필요
            # assign_defense_missions 내부의 DEFENSE_ALLOCATION_RATIO를 동적으로 변경하거나,
            # 여기서 방어군을 먼저 선별하고 나머지를 공격군으로 활용
            
            # 임시: 기존 방어 로직은 유지하되, 유휴 군대 선정 시 AI 결정 반영
            country.assign_defense_missions() # 기존 방어 로직 호출

            # 2. 유휴 군대 선정 (방어/주둔 임무 제외, AI의 공격 목표 고려)
            idle_armies_for_offense = [
                army for army in country.armies
                if army.strength > 0 and army.mission_type not in ["defense", "garrison"] and not army.in_battle and
                (not army.target_province or (army.target_province and army.target_province.owner is None))
            ]
            game_logger.debug(f"국가 '{country.name}': 공격 작전용 유휴 군대 {len(idle_armies_for_offense)}명")

            # 3. 공격 목표 설정 (AI 결정 우선, 없으면 빈 땅 또는 가까운 적)
            primary_attack_target_province = None
            can_attack_ai_target = False
            if country.attack_target_ai: # AI가 지정한 국가가 있다면
                # 해당 국가가 현재 'enemies' 목록에 있는지 확인 (전쟁 중인지)
                if country.attack_target_ai in country.enemies:
                    can_attack_ai_target = True
                    if country.attack_target_ai.owned_provinces:
                        # 수도를 우선 공격 대상으로 고려
                        if country.attack_target_ai.capital_province and country.attack_target_ai.capital_province in country.attack_target_ai.owned_provinces:
                            primary_attack_target_province = country.attack_target_ai.capital_province
                        else:
                            # 수도가 없거나 점령 불가능하면, 다른 프로빈스 중 랜덤 선택 (또는 다른 가치 기반 선택)
                            primary_attack_target_province = random.choice(country.attack_target_ai.owned_provinces)
                        game_logger.info(f"국가 '{country.name}': AI 지정 공격 대상 국가 '{country.attack_target_ai.name}' (적대 관계 확인됨)의 프로빈스 '{primary_attack_target_province.id if primary_attack_target_province else '없음'}' 공격 시도.")
                    else:
                        game_logger.info(f"국가 '{country.name}': AI 지정 공격 대상 국가 '{country.attack_target_ai.name}'는 프로빈스가 없어 공격 불가.")
                        primary_attack_target_province = None # 공격할 프로빈스가 없음
                else:
                    game_logger.info(f"국가 '{country.name}': AI 지정 공격 대상 국가 '{country.attack_target_ai.name}'와 전쟁 중이 아님. 공격 보류.")
                    # 이 경우, AI에게 선전포고를 다시 요청하거나, 다른 행동을 하도록 유도할 수 있음
                    # 현재는 단순히 공격하지 않는 것으로 처리
            
            # 빈 땅 점령 로직 (AI 공격 목표가 없거나, 공격할 수 없는 상황일 때 또는 남는 군대로)
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
            remaining_idle_armies = list(idle_armies_for_offense) # 수정된 부분: idle_armies -> idle_armies_for_offense

            # 빈 땅이 있고 유휴 군대가 있으면 항상 점령 시도
            # 여기서 idle_armies_for_offense를 사용해야 합니다.
            if available_empty_lands_near_owned and idle_armies_for_offense: 
                sorted_idle_armies_for_empty_land = sorted(idle_armies_for_offense, key=lambda a: a.strength, reverse=True)
                
                # 빈 땅 점령에 더 많은 군대 할당 (기존: min, 변경: 가능한 모든 군대)
                # 빈 땅 수와 군대 수 중 더 많은 쪽에 맞춰서 할당
                num_armies_for_empty_land = min(
                    len(sorted_idle_armies_for_empty_land), 
                    max(len(available_empty_lands_near_owned), len(sorted_idle_armies_for_empty_land) * 2 // 3)
                )
                
                armies_to_assign_empty_land = sorted_idle_armies_for_empty_land[:num_armies_for_empty_land]
                # remaining_idle_armies는 여기서 업데이트됩니다.
                remaining_idle_armies = sorted_idle_armies_for_empty_land[num_armies_for_empty_land:]

                for army_e in armies_to_assign_empty_land:
                    if not army_e.current_province:
                        continue
                        
                    best_empty_target = None
                    min_actual_distance = float('inf')
                    
                    # 빈 땅 점령 시에도 AI가 지정한 공격 대상 국가가 있다면, 그쪽으로 향하는 경로 상의 빈 땅을 우선 고려할 수 있음
                    # 여기서는 간단히 가장 가까운 빈 땅으로 설정
                    for p_id, land_info in available_empty_lands_near_owned.items():
                        if land_info['province'] not in assigned_empty_provinces_this_turn: # 아직 이번 턴에 할당 안된 빈 땅
                            # 현재 군대 위치에서 빈 땅까지의 실제 경로 길이 계산
                            # 빈 땅은 'from_province'를 거쳐서 가야 하므로, army -> from_province -> target_empty_land
                            distance_to_launch_point = army_e.calculate_actual_path_length(
                                army_e.current_province, land_info['from_province']
                            )
                            if distance_to_launch_point == float('inf'): # 도달 불가
                                continue
                                
                            total_distance_to_empty = distance_to_launch_point + 1 # from_province에서 빈 땅까지는 1
                            
                            if total_distance_to_empty < min_actual_distance:
                                min_actual_distance = total_distance_to_empty
                                best_empty_target = land_info['province']
                    
                    if best_empty_target:
                        army_e.set_target(best_empty_target)
                        army_e.mission_type = "attack" # 빈 땅 점령도 공격 임무로 간주
                        assigned_empty_provinces_this_turn.add(best_empty_target)
                        game_logger.info(f"국가 '{country.name}' 군대 (ID: {id(army_e)}) -> 빈 땅 {best_empty_target.id} 점령 이동 (거리: {min_actual_distance})")
            
            # AI가 지정한 공격 대상이 있고, 공격이 가능한 상황이라면 해당 목표 공격
            if primary_attack_target_province and can_attack_ai_target and remaining_idle_armies:
                game_logger.info(f"국가 '{country.name}': AI 지정 목표 '{primary_attack_target_province.id}' (소유: {primary_attack_target_province.owner.name}) 공격 작전 시작. 가용 군대: {len(remaining_idle_armies)}")
                # AI가 결정한 공격 비율에 따라 군대 할당
                num_attackers_for_ai_target = math.ceil(len(remaining_idle_armies) * country.attack_ratio_ai)
                attackers_ai = remaining_idle_armies[:num_attackers_for_ai_target]
                # 나머지 군대는 다른 임무 (예: 빈 땅 점령 또는 추가 방어)에 사용될 수 있도록 남겨둠
                remaining_idle_armies = remaining_idle_armies[num_attackers_for_ai_target:] 
                
                for attacker in attackers_ai:
                    attacker.set_target(primary_attack_target_province)
                    attacker.mission_type = "attack"
                    game_logger.info(f"  ㄴ 군대 (ID: {id(attacker)}) -> AI 목표 프로빈스 {primary_attack_target_province.id} 공격 이동.")
            
            # AI 지정 공격 목표가 없거나, 공격할 수 없는 상황이거나, AI 공격 후 남은 유휴 군대가 있다면
            # 이 군대로 다른 작전 (주로 빈 땅 점령 또는 현재 적대 관계인 다른 적 공격) 수행
            if remaining_idle_armies:
                game_logger.debug(f"국가 '{country.name}': AI 지정 공격 외 추가 작전 수행. 남은 유휴 군대 {len(remaining_idle_armies)}명.")
                for army_ind in remaining_idle_armies:
                    if not army_ind.current_province: continue
                    
                    candidate_targets = []
                    current_army_coord = army_ind.current_province.get_center_coordinates()

                    for p_candidate in provinces:
                        if p_candidate.owner == country: # 아군 프로빈스 제외
                            continue

                        # 목표 우선순위:
                        # 1. 현재 적대 관계(enemies)인 국가의 수도
                        # 2. 현재 적대 관계(enemies)인 국가의 일반 프로빈스
                        # 3. 빈 땅
                        # 중립 국가는 명시적인 선전포고 없이는 공격하지 않음 (AI가 선전포고 후 attack_target_ai로 지정해야 함)
                        
                        priority = 10 # 기본값 (공격 대상 아님)
                        target_owner = p_candidate.owner

                        if target_owner is None: # 빈 땅
                            priority = 3
                        elif target_owner in country.enemies: # 적대 국가
                            if target_owner.capital_province == p_candidate:
                                priority = 1 # 적 수도
                            else:
                                priority = 2 # 적 일반 프로빈스
                        # else: 중립 국가는 여기서는 공격 대상으로 고려 안 함
                        
                        if priority <= 3: # 공격 가능한 대상 (적 또는 빈 땅)
                            dist = math.sqrt(
                                (p_candidate.get_center_coordinates()[0] - current_army_coord[0])**2 +
                                (p_candidate.get_center_coordinates()[1] - current_army_coord[1])**2
                            )
                            candidate_targets.append({'province': p_candidate, 'distance': dist, 'priority': priority})
                    
                    if candidate_targets:
                        candidate_targets.sort(key=lambda x: (x['priority'], x['distance'])) # 우선순위, 그 다음 거리
                        chosen_target_province = candidate_targets[0]['province']
                        army_ind.set_target(chosen_target_province)
                        army_ind.mission_type = "attack"
                        target_status = "빈 땅"
                        if chosen_target_province.owner:
                            target_status = f"적국({chosen_target_province.owner.name}) 프로빈스"
                            if chosen_target_province.owner.capital_province == chosen_target_province:
                                target_status = f"적국({chosen_target_province.owner.name}) 수도"
                        game_logger.info(f"  ㄴ 군대 (ID: {id(army_ind)}) -> 일반 목표 {chosen_target_province.id} ({target_status}) 공격 이동.")
                    else:
                        game_logger.debug(f"  ㄴ 군대 (ID: {id(army_ind)}): 공격할 적절한 일반 목표 없음. 대기.")


            # --- 후방 방어군 재배치 로직 (기존 로직 유지 또는 AI 결정과 통합) ---
            # 현재는 기존 로직 유지
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
        # 외교 관계 표시 추가
        allies_str = ", ".join([ally.name for ally in country.allies]) if country.allies else "없음"
        enemies_str = ", ".join([enemy.name for enemy in country.enemies]) if country.enemies else "없음"
        
        country_info = f"{country.name} ({country.color}): 인구 {country.get_total_population():,} | GDP {country.get_total_gdp():,}"
        country_info2 = f"  프로빈스 {len(country.owned_provinces)} | 군대 {len(country.armies)} | 동맹: {allies_str} | 적대: {enemies_str}"
        
        text_surface = font.render(country_info, True, black)
        screen.blit(text_surface, (10, text_y_offset))
        text_y_offset += 20
        text_surface2 = font.render(country_info2, True, black)
        screen.blit(text_surface2, (10, text_y_offset))
        text_y_offset += 25 # 국가별 간격

    # 화면 업데이트 (그려진 내용을 화면에 표시)
    pygame.display.update()

# Pygame 종료 및 시스템 종료
game_logger.info("게임 종료.")
pygame.quit()
sys.exit()
