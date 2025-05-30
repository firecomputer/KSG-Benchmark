import google.generativeai as genai
import os
import re
import logging

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
    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter)
    # logger.addHandler(console_handler)

class GeminiAgent:
    def __init__(self, model_name="gemini-2.5-flash-preview-05-20"): # 모델명 변경 가능
        """
        Gemini 에이전트를 초기화합니다.
        :param model_name: 사용할 Gemini 모델 이름
        """
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)
        self.chat = None # 채팅 세션은 필요에 따라 시작
        self.logger = logging.getLogger('GeminiAgentLogger') # 클래스 인스턴스별 로거 사용
        self.logger.info(f"GeminiAgent 초기화 완료 (모델: {self.model_name})")


    def _start_chat_session(self):
        """채팅 세션을 시작합니다."""
        if not self.chat:
            self.chat = self.model.start_chat(history=[])

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
        self._start_chat_session()
        game_state_text = self._get_game_state_prompt_text(current_game_state)
        full_prompt = f"{game_state_text}\n{base_prompt}"
        
        self.logger.info(f"Gemini API 요청 시작. 전체 프롬프트:\n{full_prompt}")
        
        try:
            response = self.chat.send_message(full_prompt)
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
    # __main__ 실행 시 로깅 기본 설정 (콘솔 출력 및 파일 로깅)
    # GeminiAgent 클래스 내의 로거와는 별개로, 이 스크립트 자체 실행 시의 로그를 위함.
    # 만약 game.py에서 이 파일을 import하여 사용한다면, game.py의 로깅 설정을 따르게 됨.
    # 여기서는 이 파일 단독 실행 테스트를 위한 로깅 설정.
    
    # 루트 로거 설정 (모든 로거에 영향)
    # logging.basicConfig(level=logging.INFO,
    #                     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    #                     handlers=[
    #                         logging.FileHandler("gemini_agent_test.log", encoding='utf-8'), # 테스트용 로그 파일
    #                         logging.StreamHandler()
    #                     ])
    # logger = logging.getLogger(__name__) # 현재 모듈용 로거

    # API 키 설정
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.critical("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다! 테스트를 진행할 수 없습니다.")
        # print("GOOGLE_API_KEY 환경 변수를 설정해주세요. 또는 코드 내에서 genai.configure(api_key=...)를 호출해주세요.")
        exit()
    else:
        try:
            genai.configure(api_key=api_key)
            logger.info("GOOGLE_API_KEY가 성공적으로 설정되었습니다.")
        except Exception as e:
            logger.critical(f"GOOGLE_API_KEY 설정 중 오류 발생: {e}", exc_info=True)
            exit()
            
    agent = GeminiAgent() # 에이전트 초기화 시 INFO 로그 기록됨

    # 예시 게임 상태 (game.py 구조를 일부 반영)
    # 실제 게임에서는 GameState 객체에서 이 정보를 추출해야 합니다.
    # game_state_example 구조는 gemini_agent.py의 _get_game_state_prompt_text 와 game.py의 get_game_state_for_ai를 참고하여 일치시킵니다.
    game_state_example = {
        "current_turn": 10,
        "my_nation_name": "고양이 왕국", 
        "all_nations_details": [ # 첫 번째 요소가 '나의 국가' 정보여야 함
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
        "my_nation_bordering_nations_detail": [ # 나의 접경 국가 상세 정보
            {
                "name": "쥐 제국", "population": 200000, "gdp": 1800000,
                "relation_to_me": "적대" # 이 정보는 all_nations_details에서 가져오거나, 별도 계산
            },
            {
                "name": "너구리 연합", "population": 90000, "gdp": 1500000,
                "relation_to_me": "중립"
            }
        ],
        "global_events": ["대규모 기근 발생", "기술 혁신 전파"]
    }
    
    my_nation_info_for_prompt = next(n for n in game_state_example["all_nations_details"] if n["name"] == game_state_example["my_nation_name"])
    
    logger.info("--- 선전 포고 결정 테스트 ---")
    potential_war_targets = [
        n["name"] for n in game_state_example["all_nations_details"]
        if n["name"] != game_state_example["my_nation_name"] and \
           n["name"] not in my_nation_info_for_prompt.get("enemies", []) and \
           n["name"] not in my_nation_info_for_prompt.get("allies", [])
    ]
    if not potential_war_targets: potential_war_targets = ["너구리 연합"]

    decision_war, reason_war = agent.declare_war(potential_war_targets, game_state_example)
    logger.info(f"선전 포고 결정: {decision_war}, 이유: {reason_war}\n")

    logger.info("--- 동맹 결정 테스트 ---")
    potential_alliance_targets = [
        n["name"] for n in game_state_example["all_nations_details"]
        if n["name"] != game_state_example["my_nation_name"] and \
           n["name"] not in my_nation_info_for_prompt.get("allies", []) and \
           n["name"] not in my_nation_info_for_prompt.get("enemies", [])
    ]
    if not potential_alliance_targets: potential_alliance_targets = ["너구리 연합"]

    decision_alliance, reason_alliance = agent.form_alliance(potential_alliance_targets, game_state_example)
    logger.info(f"동맹 결정: {decision_alliance}, 이유: {reason_alliance}\n")

    logger.info("--- 휴전 결정 테스트 ---")
    truce_targets = list(my_nation_info_for_prompt.get("enemies", []))
    if not truce_targets: truce_targets = ["쥐 제국"] 

    decision_truce, reason_truce = agent.offer_truce(truce_targets, game_state_example)
    logger.info(f"휴전 결정: {decision_truce}, 이유: {reason_truce}\n")

    logger.info("--- 예산 편성 테스트 ---")
    current_budget_example = my_nation_info_for_prompt["gdp"] * 0.1
    budget_plan, reason_budget = agent.allocate_budget(current_budget_example, game_state_example)
    logger.info(f"예산 계획: {budget_plan}, 이유: {reason_budget}\n")

    logger.info("--- 공격-방어 비율 설정 테스트 ---")
    attack_consider_targets = list(my_nation_info_for_prompt.get("enemies", []))
    neutral_nations_for_attack = [
        n["name"] for n in game_state_example["all_nations_details"]
        if n["name"] != game_state_example["my_nation_name"] and \
           n["name"] not in my_nation_info_for_prompt.get("allies", []) and \
           n["name"] not in my_nation_info_for_prompt.get("enemies", [])
    ]
    attack_consider_targets.extend(neutral_nations_for_attack)
    if not attack_consider_targets : attack_consider_targets = ["쥐 제국", "너구리 연합"]

    attack_target_decision, attack_ratio, reason_ratio = agent.set_attack_defense_ratio(attack_consider_targets, game_state_example)
    logger.info(f"공격 대상: {attack_target_decision}, 공격 비율: {attack_ratio}, 이유: {reason_ratio}\n")

    logger.info("냐옹! Gemini 에이전트 테스트 완료! 로그는 gemini.log 또는 gemini_agent_test.log 에서 확인하세요!")
