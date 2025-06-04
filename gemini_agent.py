from google import genai
from google.genai import types
import os
import re
import logging
import json # JSON 파싱을 위해 추가
import asyncio # 비동기 처리를 위해 추가

# --- 로깅 설정 ---
# gemini.log 파일에 로그를 기록하도록 설정합니다.
# 다른 모듈에서도 이 로거를 사용하거나, 각 모듈별로 로거를 설정할 수 있습니다.
# 여기서는 GeminiAgent 전용 로거를 만들겠습니다.
logger = logging.getLogger('GeminiAgentLogger')
logger.setLevel(logging.INFO) # INFO 레벨 이상의 로그를 기록

# 파일 핸들러 설정
# 이 핸들러는 game.py에서도 설정될 수 있으므로, 중복 추가되지 않도록 주의합니다.
# 여기서는 agent 내부의 로그만 담당하도록 하고, game.py에서 전체 파일 핸들러를 설정하는 것이 더 좋을 수 있습니다.
# 하지만 독립적인 테스트를 위해 여기서도 핸들러를 추가해봅니다.
if not logger.handlers: # 핸들러가 이미 설정되어 있지 않은 경우에만 추가
    log_file_path = os.path.join(os.path.dirname(__file__), 'gemini.log') # gemini_agent.py와 같은 디렉토리에 생성
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # 콘솔 핸들러도 추가 (디버깅 시 유용)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class GeminiAgent:
    def __init__(self, model_name="gemini-2.5-flash-preview-05-20"): # 모델명 변경 가능
        """
        Gemini 에이전트를 초기화합니다.
        :param model_name: 사용할 Gemini 모델 이름
        """
        self.model_name = model_name
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY")) # 기본 클라이언트 생성성
        # API 키 설정은 genai.configure()를 사용하거나, Client 생성 시 직접 전달할 수 있습니다.
        # genai.configure(api_key=os.getenv("GOOGLE_API_KEY")) # 보통 애플리케이션 시작 시 한 번 호출
        self.logger = logging.getLogger('GeminiAgentLogger') # 클래스 인스턴스별 로거 사용
        self.logger.info(f"GeminiAgent 초기화 완료 (모델: {self.model_name})")

    async def _send_message_async(self, full_prompt: str) -> str | None:
        """
        Gemini 모델에 프롬프트를 비동기적으로 보내고 응답을 받습니다.
        :param full_prompt: 전체 프롬프트 문자열
        :return: 모델의 응답 텍스트 또는 실패 시 None
        """
        self.logger.info(f"Gemini API 비동기 요청 시작. 프롬프트 길이: {len(full_prompt)}")
        try:
            # 여기서는 단순 문자열 프롬프트를 사용합니다.
            # config 인자도 추가하여 _send_message와 일관성 유지
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[full_prompt]
            )
            self.logger.info(f"Gemini API 비동기 응답 수신 (일부): {response.text[:200] if response.text else '응답 없음'}")
            return response.text
        except Exception as e:
            self.logger.error(f"Gemini API 비동기 호출 중 오류 발생: {e}", exc_info=True)
            return None

    def _get_game_state_prompt_text(self, game_state):
        """현재 게임 상태를 LLM 프롬프트에 포함할 텍스트로 변환합니다."""
        prompt_text = "현재 게임 상황:\n"
        
        my_nation_name = game_state.get("my_nation_name", "알 수 없는 국가")
        all_nations_details = game_state.get("all_nations_details", [])
        my_nation_info = next((n for n in all_nations_details if n.get("name") == my_nation_name), None)

        if my_nation_info:
            prompt_text += f"- 나의 국가: {my_nation_info.get('name', '알 수 없음')}\n"
            prompt_text += f"  - 인구: {my_nation_info.get('population', '알 수 없음'):,}\n"
            prompt_text += f"  - GDP: {my_nation_info.get('gdp', '알 수 없음'):,}\n"
            prompt_text += f"  - 프로빈스 수: {my_nation_info.get('province_count', '알 수 없음')}\n"
            prompt_text += f"  - 군대 수: {my_nation_info.get('army_count', '알 수 없음')}\n"
            prompt_text += f"  - 동맹: {', '.join(my_nation_info.get('allies', [])) if my_nation_info.get('allies') else '없음'}\n"
            prompt_text += f"  - 적대: {', '.join(my_nation_info.get('enemies', [])) if my_nation_info.get('enemies') else '없음'}\n"
        else:
            prompt_text += f"- 나의 국가: {my_nation_name} (상세 정보 없음)\n"

        prompt_text += "\n- 다른 국가 정보:\n"
        other_nations_info_for_prompt = [n for n in all_nations_details if n.get("name") != my_nation_name]
        if not other_nations_info_for_prompt:
            prompt_text += "  (다른 국가 정보 없음)\n"
        for nation in other_nations_info_for_prompt:
            prompt_text += f"  - 국가명: {nation.get('name', '알 수 없음')}\n"
            prompt_text += f"    - 인구: {nation.get('population', '알 수 없음'):,}\n"
            prompt_text += f"    - GDP: {nation.get('gdp', '알 수 없음'):,}\n"
            prompt_text += f"    - 우리 국가와의 관계: {nation.get('relation_to_me', '알 수 없음')}\n"
            prompt_text += f"    - 해당 국가의 동맹: {', '.join(nation.get('allies', [])) if nation.get('allies') else '없음'}\n"
            prompt_text += f"    - 해당 국가의 적대: {', '.join(nation.get('enemies', [])) if nation.get('enemies') else '없음'}\n"

        my_bordering_nations_detail = game_state.get("my_nation_bordering_nations_detail", [])
        if my_bordering_nations_detail:
            prompt_text += "\n- 나의 접경 국가 상세 정보:\n"
            for border_nation in my_bordering_nations_detail:
                prompt_text += f"  - 접경국: {border_nation.get('name', '알 수 없음')}\n"
                # 접경국 상세 정보는 이미 other_nations_info_for_prompt에 포함된 형태로 제공되므로, 중복 기술 피하거나 요약
                prompt_text += f"    - (상세 정보는 '다른 국가 정보' 섹션 참조, 우리와의 관계: {border_nation.get('relation_to_me', '알 수 없음')})\n"
        else:
            prompt_text += "\n- 나의 접경 국가: 없음\n"
        
        global_events = game_state.get("global_events", [])
        if global_events:
            prompt_text += f"\n- 현재 발생 중인 주요 사건: {', '.join(global_events)}\n"
        
        prompt_text += f"\n- 현재 턴: {game_state.get('current_turn', '알 수 없음')}\n"
            
        return prompt_text

    def _send_message(self, base_prompt, current_game_state):
        """
        Gemini 모델에 프롬프트를 보내고 응답을 받습니다.
        :param base_prompt: 기본적인 지시사항 프롬프트
        :param current_game_state: 현재 게임 상태 정보
        :return: 모델의 응답 텍스트
        """
        game_state_text = self._get_game_state_prompt_text(current_game_state)
        full_prompt = f"{game_state_text}\n{base_prompt}"
        
        self.logger.info(f"Gemini API 요청 시작. 전체 프롬프트:\n{full_prompt}")
        
        try:
            # generate_content 호출 시 config 대신 generation_config 사용 (Gemini API 표준)
            # self.generate_content_config가 정의되어 있지 않을 수 있으므로 getattr 사용
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            self.logger.info(f"Gemini API 응답 수신:\n{response.text}")
            return response.text
        except Exception as e:
            self.logger.error(f"Gemini API 호출 중 오류 발생: {e}", exc_info=True)
            return None

    def _parse_decision_reason(self, response_text, pattern_keyword, expect_nation_target=True):
        """
        모델 응답에서 결정 (국가명/예/아니오)과 이유를 파싱합니다.
        :param response_text: 모델의 응답 문자열
        :param pattern_keyword: 정규식에 사용할 키워드 (예: "선전 포고 결정")
        :param expect_nation_target: 결정 부분이 국가명일 수 있는지 여부
        :return: (결정: str 또는 bool, 이유: str) 튜플. 파싱 실패 시 (None, 원본 텍스트)
        """
        if not response_text:
            return None, "모델 응답 없음"

        # 국가명을 포함하거나 예/아니오를 포함하는 패턴
        # 예: "선전 포고 결정: [국가명/예/아니오], 이유: [상세 설명]"
        pattern = rf"{pattern_keyword}:\s*\[?([^,\]]+)\]?,\s*이유:\s*(.+)"
        match = re.search(pattern, response_text, re.IGNORECASE)
        
        if match:
            decision_str = match.group(1).strip()
            reason = match.group(2).strip()
            
            if expect_nation_target:
                if decision_str.lower() == "예":
                    return True, reason
                elif decision_str.lower() == "아니오":
                    return False, reason
                else: # 국가명으로 간주
                    self.logger.info(f"파싱 결과: 결정={decision_str}, 이유={reason}")
                    return decision_str, reason
            else: # 예/아니오만 예상 (set_attack_defense_ratio의 경우처럼)
                if decision_str.lower() == "예":
                    self.logger.info(f"파싱 결과: 결정=True, 이유={reason}")
                    return True, reason
                elif decision_str.lower() == "아니오":
                    self.logger.info(f"파싱 결과: 결정=False, 이유={reason}")
                    return False, reason
                # 이 경우, True/False가 아니면 파싱 실패로 간주하거나,
                # 다른 특정 값을 반환하도록 수정할 수 있습니다.
                # 여기서는 일단 문자열 그대로 반환 (추후 수정 가능)
                self.logger.warning(f"예상치 못한 결정 값(예/아니오 기대): {decision_str}. 응답: {response_text}")
                return decision_str, reason

        self.logger.warning(f"'{pattern_keyword}' 패턴 파싱 실패. 응답: {response_text}")
        return None, response_text # 파싱 실패 시 원본 반환

    def declare_war(self, target_nation_options, current_game_state):
        """
        특정 국가 또는 옵션 중 하나에 선전 포고를 결정합니다.
        :param target_nation_options: 선전 포고 대상 국가 옵션 리스트 또는 단일 국가명
        :param current_game_state: 현재 게임 상태 정보 (딕셔너리 형태)
        :return: 선전 포고 대상 국가명 또는 False, 및 이유 (문자열)
        """
        # target_nation_options가 리스트가 아니면 리스트로 만듭니다.
        if not isinstance(target_nation_options, list):
            target_nation_options = [target_nation_options]

        options_text = ", ".join(target_nation_options)
        prompt = f"""당신은 전략 시뮬레이션 게임의 AI 플레이어입니다.
다음 국가들 중 하나에 선전 포고를 하거나, 하지 않을 수 있습니다: {options_text}
어떤 국가에 선전 포고를 하는 것이 가장 유리할까요? 아니면 선전포고를 하지 않는 것이 나을까요? 그 이유는 무엇인가요?
정확히 다음 형식으로만 답변해주세요: "선전 포고 결정: [국가명 또는 아니오], 이유: [상세 설명]"
예시1: "선전 포고 결정: 쥐 제국, 이유: 해당 국가는 현재 군사력이 약하며, 점령 시 주요 자원을 확보할 수 있습니다."
예시2: "선전 포고 결정: 아니오, 이유: 현재 우리 국력으로는 어떤 국가와도 전쟁을 감당하기 어렵고, 국제적 비난을 받을 수 있습니다."
"""
        response_text = self._send_message(prompt, current_game_state)
        # expect_nation_target=True 이므로, 반환값은 국가명(str) 또는 False(bool)이 될 수 있음
        decision, reason = self._parse_decision_reason(response_text, "선전 포고 결정", expect_nation_target=True)

        if decision is not None:
            # 결정이 True (파서에서 "예"로 해석된 경우)이면, 프롬프트 형식이 잘못된 것임.
            # 이 함수는 국가명 또는 "아니오"를 기대함.
            if decision is True:
                 self.logger.error(f"선전 포고 결정 파싱 오류: '예'는 유효한 결정이 아님. 응답: {response_text}")
                 return False, f"'예'는 유효한 결정이 아님. {response_text}"
            return decision, reason
        
        # 파싱 실패 시 이미 _parse_decision_reason에서 로그를 남겼으므로 여기서는 추가 로그 없이 반환
        return False, response_text

    def form_alliance(self, target_nation_options, current_game_state):
        """
        특정 국가 또는 옵션 중 하나와 동맹을 결정합니다.
        :param target_nation_options: 동맹 제안 대상 국가 옵션 리스트 또는 단일 국가명
        :param current_game_state: 현재 게임 상태 정보
        :return: 동맹 제안 대상 국가명 또는 False, 및 이유 (문자열)
        """
        if not isinstance(target_nation_options, list):
            target_nation_options = [target_nation_options]

        options_text = ", ".join(target_nation_options)
        prompt = f"""당신은 전략 시뮬레이션 게임의 AI 플레이어입니다.
다음 국가들 중 하나와 동맹을 맺거나, 맺지 않을 수 있습니다: {options_text}
어떤 국가와 동맹을 맺는 것이 가장 유리할까요? 아니면 동맹을 맺지 않는 것이 나을까요? 그 이유는 무엇인가요?
정확히 다음 형식으로만 답변해주세요: "동맹 결정: [국가명 또는 아니오], 이유: [상세 설명]"
예시1: "동맹 결정: 강아지 공화국, 이유: 해당 국가와 군사적, 경제적으로 상호 보완적 관계를 형성할 수 있습니다."
예시2: "동맹 결정: 아니오, 이유: 현재 어떤 국가와도 동맹을 맺을 실익이 없습니다."
"""
        response_text = self._send_message(prompt, current_game_state)
        decision, reason = self._parse_decision_reason(response_text, "동맹 결정", expect_nation_target=True)

        if decision is not None:
            if decision is True: # "예"는 여기서 유효하지 않음
                 self.logger.error(f"동맹 결정 파싱 오류: '예'는 유효한 결정이 아님. 응답: {response_text}")
                 return False, f"'예'는 유효한 결정이 아님. {response_text}"
            return decision, reason
        # 파싱 실패 시 이미 _parse_decision_reason에서 로그를 남겼으므로 여기서는 추가 로그 없이 반환
        return False, response_text

    def offer_truce(self, target_nation_options, current_game_state):
        """
        특정 국가 또는 옵션 중 하나에 휴전을 제안할지 결정합니다.
        :param target_nation_options: 휴전 제안 대상 국가 옵션 리스트 또는 단일 국가명 (현재 전쟁 중인 국가)
        :param current_game_state: 현재 게임 상태 정보
        :return: 휴전 제안 대상 국가명 또는 False, 및 이유 (문자열)
        """
        if not isinstance(target_nation_options, list):
            target_nation_options = [target_nation_options]
        
        options_text = ", ".join(target_nation_options)
        prompt = f"""당신은 전략 시뮬레이션 게임의 AI 플레이어입니다.
현재 다음 국가들과 전쟁 중입니다: {options_text} (만약 목록이 비어있다면, 현재 전쟁 중인 국가가 없다는 의미입니다.)
어떤 국가에 휴전을 제안하는 것이 가장 유리할까요? 아니면 휴전을 제안하지 않는 것이 나을까요? 그 이유는 무엇인가요?
정확히 다음 형식으로만 답변해주세요: "휴전 결정: [국가명 또는 아니오], 이유: [상세 설명]"
예시1: "휴전 결정: 쥐 제국, 이유: 장기전으로 인해 국력 소모가 심하며, 재정비할 시간이 필요합니다."
예시2: "휴전 결정: 아니오, 이유: 현재 전황이 유리하며, 이 기회에 적을 완전히 제압해야 합니다."
"""
        response_text = self._send_message(prompt, current_game_state)
        decision, reason = self._parse_decision_reason(response_text, "휴전 결정", expect_nation_target=True)

        if decision is not None:
            if decision is True: # "예"는 여기서 유효하지 않음
                 self.logger.error(f"휴전 결정 파싱 오류: '예'는 유효한 결정이 아님. 응답: {response_text}")
                 return False, f"'예'는 유효한 결정이 아님. {response_text}"
            return decision, reason
        # 파싱 실패 시 이미 _parse_decision_reason에서 로그를 남겼으므로 여기서는 추가 로그 없이 반환
        return False, response_text

    async def get_comprehensive_decision_async(self, current_game_state: dict, budget_to_allocate: float, war_options: list, alliance_options: list, truce_options: list) -> dict:
        """
        한 번의 API 호출로 모든 주요 AI 결정을 비동기적으로 가져옵니다.
        JSON 형식으로 응답을 요청하고 파싱합니다.
        """
        game_state_text = self._get_game_state_prompt_text(current_game_state)
        
        # 사용 가능한 옵션들을 문자열로 변환
        war_options_str = ", ".join(war_options) if war_options else "없음"
        alliance_options_str = ", ".join(alliance_options) if alliance_options else "없음"
        truce_options_str = ", ".join(truce_options) if truce_options else "없음"

        # JSON 응답을 위한 프롬프트 구성
        # 모델이 JSON을 더 잘 생성하도록 예시를 명확히 하고, 필요한 모든 키를 나열합니다.
        prompt = f"""{game_state_text}
당신은 전략 시뮬레이션 게임의 AI 플레이어입니다. 현재 상황을 분석하여 다음 모든 결정 사항에 대해 최적의 판단을 내려주세요.
반드시 다음 JSON 형식에 맞춰 모든 키와 함께 응답해야 합니다. 각 결정에 대한 이유도 포함해주세요.
만약 특정 행동을 하지 않기로 결정했다면, 해당 target_nation 필드에 "없음" 또는 "아니오"를 사용하세요.

요청 형식:
{{
  "budget": {{
    "defense_ratio": "[0.0-1.0 사이 국방 예산 비율]",
    "economy_ratio": "[0.0-1.0 사이 경제 예산 비율]",
    "research_ratio": "[0.0-1.0 사이 연구 예산 비율]",
    "reason": "[예산 편성 이유]"
  }},
  "attack_strategy": {{
    "target_nation": "[공격 대상 국가명 또는 '없음']",
    "attack_ratio": "[0.0-1.0 사이 공격 병력 비율]",
    "reason": "[공격/방어 전략 이유]"
  }},
  "declare_war": {{
    "target_nation": "[선전포고 대상 국가명 또는 '아니오']",
    "reason": "[선전포고 결정 이유]"
  }},
  "form_alliance": {{
    "target_nation": "[동맹 제안 대상 국가명 또는 '아니오']",
    "reason": "[동맹 결정 이유]"
  }},
  "offer_truce": {{
    "target_nation": "[휴전 제안 대상 국가명 또는 '아니오']",
    "reason": "[휴전 결정 이유]"
  }}
}}

현재 상황을 고려할 때, 다음 사항들을 반드시 기억하세요:
- 너무 평화를 지향하려 하지 마십시오. 비슷하거나 약한 체급의 경쟁자가 있으면 최종 승리를 하기 위해 전쟁을 해야 합니다.
- 너무 공격적이지도 마십시오. 너무 강한 경쟁자와의 전쟁은 자원 낭비가 될 수 있습니다.
- 현재 상황에서는 세력 균형을 고려하여 전략적으로 행동해야 합니다.
- 동맹국이 있다면 그들과의 관계를 고려하여 공동 전선을 형성할 수 있는지 판단하세요.
- 경제력(GDP)과 군사력(army_count), 인구를 종합적으로 고려하여 상대의 강약을 판단하세요.
- 접경국가와의 관계는 특히 중요합니다. 국경을 맞대고 있는 국가와의 전쟁이나 동맹은 즉각적인 영향을 미칩니다.
- 현재 발생 중인 전역 사건들(global_events)이 당신의 결정에 어떤 영향을 미칠지 고려하세요.
- 예산 편성 시에는 현재 전쟁 상황, 경제 상태, 기술 격차를 모두 고려해야 합니다.
- 공격 전략에서는 상대방의 방어력과 지리적 위치를 고려하여 현실적인 성공 가능성을 판단하세요.
- 휴전은 현재 전황이 불리하거나 장기전으로 인한 소모전이 예상될 때 고려해야 합니다.
- 동맹 제안은 상호 이익이 되고, 장기적으로 안정적인 관계를 유지할 수 있는 국가를 우선시하세요.
- 모든 결정은 최종 승리라는 목표를 달성하기 위한 단계적 전략의 일부여야 합니다.


현재 고려할 수 있는 옵션:
- 선전포고 가능 대상: {war_options_str}
- 동맹 가능 대상: {alliance_options_str}
- 휴전 가능 대상 (현재 전쟁 중인 국가): {truce_options_str}
- 편성할 총 예산의 기준점 (실제 총 예산의 일부): {budget_to_allocate} (이 값을 기준으로 국방, 경제, 연구 비율을 정해주세요. 비율의 합은 1.0이어야 합니다.)

위 정보를 바탕으로 최적의 종합적인 결정을 JSON 형식으로 내려주세요.
"""
        response_text = await self._send_message_async(prompt)
        
        default_decisions = {
            "budget": {"defense_ratio": 0.4, "economy_ratio": 0.3, "research_ratio": 0.3, "reason": "기본 예산 편성"},
            "attack_strategy": {"target_nation": "없음", "attack_ratio": 0.5, "reason": "기본 전략"},
            "declare_war": {"target_nation": "아니오", "reason": "기본 결정"},
            "form_alliance": {"target_nation": "아니오", "reason": "기본 결정"},
            "offer_truce": {"target_nation": "아니오", "reason": "기본 결정"}
        }

        if not response_text:
            self.logger.error("종합 결정 API 응답 없음. 기본값 사용.")
            return default_decisions

        try:
            # 모델 응답에서 JSON 부분만 추출 시도 (마크다운 코드 블록 처리)
            json_match = re.search(r"```json\s*([\s\S]+?)\s*```", response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 코드 블록이 없다면 전체 텍스트를 JSON으로 가정
                json_str = response_text
            
            decisions = json.loads(json_str)
            self.logger.info(f"종합 결정 파싱 성공: {decisions}")
            
            # 필수 키 존재 여부 및 기본값 채우기 (더 견고하게)
            for key, default_value_map in default_decisions.items():
                if key not in decisions or not isinstance(decisions[key], dict):
                    decisions[key] = default_value_map
                    self.logger.warning(f"종합 결정에서 '{key}' 누락 또는 타입 오류. 기본값 사용.")
                else:
                    for sub_key, default_sub_value in default_value_map.items():
                        if sub_key not in decisions[key]:
                            decisions[key][sub_key] = default_sub_value
                            self.logger.warning(f"종합 결정 '{key}'에서 '{sub_key}' 누락. 기본값 '{default_sub_value}' 사용.")
            
            # 예산 비율 합계 검증
            budget = decisions.get("budget", {})
            b_def = budget.get("defense_ratio", 0)
            b_eco = budget.get("economy_ratio", 0)
            b_res = budget.get("research_ratio", 0)
            if not (isinstance(b_def, (int, float)) and isinstance(b_eco, (int, float)) and isinstance(b_res, (int, float)) and abs(b_def + b_eco + b_res - 1.0) < 0.01):
                self.logger.error(f"종합 결정: 예산 비율 합계 또는 타입 오류 ({b_def}, {b_eco}, {b_res}). 기본 예산으로 재설정.")
                decisions["budget"] = default_decisions["budget"]

            # 공격 비율 검증
            attack_strat = decisions.get("attack_strategy", {})
            atk_ratio = attack_strat.get("attack_ratio", 0.5)
            if not (isinstance(atk_ratio, (int, float)) and 0.0 <= atk_ratio <= 1.0):
                self.logger.error(f"종합 결정: 공격 비율 범위 또는 타입 오류 ({atk_ratio}). 기본값 0.5로 재설정.")
                decisions["attack_strategy"]["attack_ratio"] = 0.5


            return decisions
        except json.JSONDecodeError as e:
            self.logger.error(f"종합 결정 JSON 파싱 실패: {e}. 응답: {response_text}", exc_info=True)
            return default_decisions
        except Exception as e:
            self.logger.error(f"종합 결정 처리 중 알 수 없는 오류: {e}. 응답: {response_text}", exc_info=True)
            return default_decisions

    def allocate_budget(self, current_budget, current_game_state):
        """
        예산을 편성합니다. (예: 국방, 경제, 연구 등)
        :param current_budget: 현재 사용 가능한 총 예산
        :param current_game_state: 현재 게임 상태 정보
        :return: 예산 편성 계획 (딕셔너리 형태, 예: {"국방": 0.5, "경제": 0.3, "연구": 0.2}) 및 이유
        """
        base_prompt = f"""당신은 전략 시뮬레이션 게임의 AI 플레이어입니다.
현재 가용 예산: {current_budget}
이 예산을 국방, 경제, 연구 개발에 어떻게 분배하는 것이 최적일까요? 각 항목에 대한 비율(소수점 형태, 예: 0.5)과 그 이유를 설명해주세요.
정확히 다음 형식으로만 답변해주세요: "예산 편성: 국방=[0.0-1.0 사이 비율], 경제=[0.0-1.0 사이 비율], 연구=[0.0-1.0 사이 비율], 이유: [상세 설명]"
비율의 합은 1.0이 되어야 합니다.
예시: "예산 편성: 국방=0.5, 경제=0.3, 연구=0.2, 이유: 현재 전쟁 중이므로 국방에 우선 투자하고, 경제와 연구도 균형있게 발전시킵니다."
"""
        response_text = self._send_message(base_prompt, current_game_state)
        if not response_text:
            return {"국방": 0.4, "경제": 0.3, "연구": 0.3}, "모델 응답 없음" # 기본값

        match = re.search(
            r"예산 편성:\s*국방=([0-9.]+),\s*경제=([0-9.]+),\s*연구=([0-9.]+),\s*이유:\s*(.+)",
            response_text,
            re.IGNORECASE
        )
        if match:
            try:
                defense = float(match.group(1))
                economy = float(match.group(2))
                research = float(match.group(3))
                reason = match.group(4).strip()
                # 비율 합계 검증 (근사치 허용)
                if abs(defense + economy + research - 1.0) < 0.01:
                    self.logger.info(f"예산 편성 파싱 성공: 국방={defense}, 경제={economy}, 연구={research}, 이유={reason}")
                    return {"국방": defense, "경제": economy, "연구": research}, reason
                else:
                    self.logger.error(f"예산 비율 합계 오류: {defense + economy + research}. 응답: {response_text}")
                    return {"국방": 0.4, "경제": 0.3, "연구": 0.3}, f"비율 합계 오류. {response_text}"
            except ValueError:
                self.logger.error(f"예산 비율 숫자 변환 오류. 응답: {response_text}", exc_info=True)
                return {"국방": 0.4, "경제": 0.3, "연구": 0.3}, f"숫자 변환 오류. {response_text}"

        self.logger.warning(f"예산 편성 파싱 실패: {response_text}")
        return {"국방": 0.4, "경제": 0.3, "연구": 0.3}, response_text # 기본값

    def set_attack_defense_ratio(self, potential_target_nations, current_game_state):
        """
        공격 대상 국가 및 공격과 방어의 비율을 설정합니다.
        :param potential_target_nations: 공격을 고려할 수 있는 국가 리스트. 비어있을 수 있음.
        :param current_game_state: 현재 게임 상태 정보
        :return: (공격 대상 국가명 또는 None, 공격 비율(0.0~1.0), 이유)
        """
        targets_text = "없음"
        if potential_target_nations:
            targets_text = ", ".join(potential_target_nations)
        
        prompt = f"""당신은 전략 시뮬레이션 게임의 AI 플레이어입니다.
현재 공격을 고려할 수 있는 국가는 다음과 같습니다: {targets_text}. (없을 수도 있습니다)
만약 공격한다면 어떤 국가를 대상으로 하는 것이 좋을까요? (공격하지 않는다면 '없음'으로 표시)
그리고 현재 상황에서 공격과 방어 중 어느 쪽에 더 비중을 두어야 할까요? 공격에 투자할 비율(0.0에서 1.0 사이의 소수)과 그 이유를 설명해주세요.
(예: 공격 비율: 0.7은 공격에 70%, 방어에 30%를 투자한다는 의미입니다.)
정확히 다음 형식으로만 답변해주세요: "공격-방어 비율 설정: 공격 대상 국가=[국가명 또는 없음], 공격 비율=[0.0-1.0 사이 값], 이유: [상세 설명]"
예시1: "공격-방어 비율 설정: 공격 대상 국가=쥐 제국, 공격 비율=0.6, 이유: 적의 주요 도시를 공략하여 전쟁을 조기에 끝내기 위함입니다."
예시2: "공격-방어 비율 설정: 공격 대상 국가=없음, 공격 비율=0.3, 이유: 현재는 방어에 집중하며 국력을 키우는 것이 중요합니다."
공격 군대는 적 국가를 공격하는데만 사용되는 것이 아니라, 빈 땅을 공격하는 데에도 사용될 수 있습니다. 지금 국력이 너무 작다면, 공격 비율을 늘리는 것이 좋습니다.
"""
        response_text = self._send_message(prompt, current_game_state)
        if not response_text:
            return None, 0.5, "모델 응답 없음" # 기본값

        # "공격-방어 비율 설정: 공격 대상 국가=[국가명 또는 없음], 공격 비율=[0.0-1.0 사이 값], 이유: [상세 설명]"
        pattern = r"공격-방어 비율 설정:\s*공격 대상 국가=\s*\[?([^,\]]+)\]?,\s*공격 비율=\s*\[?([0-9.]+)\]?,\s*이유:\s*(.+)"
        match = re.search(pattern, response_text, re.IGNORECASE)
        
        if match:
            try:
                target_nation_str = match.group(1).strip()
                attack_ratio_str = match.group(2).strip()
                reason = match.group(3).strip()

                attack_target = None
                if target_nation_str.lower() != "없음":
                    attack_target = target_nation_str
                
                attack_ratio = float(attack_ratio_str)

                if 0.0 <= attack_ratio <= 1.0:
                    self.logger.info(f"공격-방어 비율 파싱 성공: 대상={attack_target}, 비율={attack_ratio}, 이유={reason}")
                    return attack_target, attack_ratio, reason
                else:
                    self.logger.error(f"공격 비율 범위 오류: {attack_ratio}. 응답: {response_text}")
                    return None, 0.5, f"비율 범위 오류. {response_text}" # 기본값
            except ValueError:
                self.logger.error(f"공격 비율 숫자 변환 오류. 응답: {response_text}", exc_info=True)
                return None, 0.5, f"숫자 변환 오류. {response_text}" # 기본값
            except Exception as e:
                self.logger.error(f"공격-방어 비율 파싱 중 일반 오류 발생: {e}. 응답: {response_text}", exc_info=True)
                return None, 0.5, f"파싱 중 일반 오류. {response_text}"

        self.logger.warning(f"공격-방어 비율 파싱 실패: {response_text}")
        return None, 0.5, response_text # 기본값

if __name__ == '__main__':
    # GeminiAgent 인스턴스 생성
    agent = GeminiAgent()
    # agent.generate_content_config = types.GenerationConfig(temperature=0.7, top_p=0.9, top_k=40) # 필요시 설정

    # get_comprehensive_decision_async 호출을 위한 예시 데이터
    game_state_example = {
        "current_turn": 10,
        "my_nation_name": "고양이 왕국",
        "all_nations_details": [
            {
                "name": "고양이 왕국", "population": 150000, "gdp": 2000000,
                "province_count": 5, "army_count": 3, "capital_province_id": 1,
                "allies": ["강아지 공화국"], "enemies": ["쥐 제국"]
            },
            {
                "name": "쥐 제국", "population": 200000, "gdp": 1800000,
                "province_count": 6, "army_count": 5, "capital_province_id": 10,
                "allies": [], "enemies": ["고양이 왕국", "강아지 공화국"], "relation_to_me": "적대"
            },
            {
                "name": "강아지 공화국", "population": 120000, "gdp": 2200000,
                "province_count": 4, "army_count": 2, "capital_province_id": 20,
                "allies": ["고양이 왕국"], "enemies": ["쥐 제국"], "relation_to_me": "동맹"
            },
            {
                "name": "너구리 연합", "population": 90000, "gdp": 1500000,
                "province_count": 3, "army_count": 1, "capital_province_id": 30,
                "allies": [], "enemies": [], "relation_to_me": "중립"
            }
        ],
        "my_nation_bordering_nations_detail": [
            {"name": "쥐 제국", "relation_to_me": "적대"},
            {"name": "너구리 연합", "relation_to_me": "중립"}
        ],
        "global_events": ["대규모 기근 발생", "기술 혁신 전파"]
    }
    budget_to_allocate_example = 200000.0  # 예시 예산 (GDP의 10% 정도)
    
    my_nation_info = next((n for n in game_state_example["all_nations_details"] if n["name"] == game_state_example["my_nation_name"]), {})

    war_options_example = [
        n["name"] for n in game_state_example["all_nations_details"]
        if n["name"] != game_state_example["my_nation_name"] and \
           n["name"] not in my_nation_info.get("allies", []) and \
           n["name"] not in my_nation_info.get("enemies", [])
    ]
    if not war_options_example: war_options_example = ["임의의 적국1"] # 예시: 대상 없을 경우

    alliance_options_example = [
        n["name"] for n in game_state_example["all_nations_details"]
        if n["name"] != game_state_example["my_nation_name"] and \
           n["name"] not in my_nation_info.get("allies", [])
    ]
    if not alliance_options_example: alliance_options_example = ["임의의 중립국1"]

    truce_options_example = list(my_nation_info.get("enemies", []))
    if not truce_options_example: truce_options_example = [] # 전쟁 중인 국가가 없을 수도 있음

    # 비동기 함수를 실행하기 위한 main 코루틴 정의
    async def main():
        logger.info("--- 종합 결정 테스트 (비동기) 시작 ---")
        decisions = await agent.get_comprehensive_decision_async(
            current_game_state=game_state_example,
            budget_to_allocate=budget_to_allocate_example,
            war_options=war_options_example,
            alliance_options=alliance_options_example,
            truce_options=truce_options_example
        )
        logger.info(f"종합 결정 (비동기) 결과:\n{json.dumps(decisions, indent=2, ensure_ascii=False)}")
        print("--- 종합 결정 (비동기) 결과 ---")
        print(json.dumps(decisions, indent=2, ensure_ascii=False))
        logger.info("--- 종합 결정 테스트 (비동기) 완료 ---")

    # asyncio.run()을 사용하여 main 코루틴 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("사용자에 의해 테스트 중단됨.")
    except Exception as e:
        logger.error(f"__main__ 실행 중 오류 발생: {e}", exc_info=True)

    logger.info("Gemini 에이전트 스크립트 실행 완료!")
