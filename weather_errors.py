"""공식 오류코드만 사용자 안내로 바꾼다. 응답 원문·인증 URL은 전달하지 않는다."""
import re


class WeatherAPIError(RuntimeError):
    pass


_MESSAGES = {
    '10': '요청값 오류: 지점과 분석 기간을 확인하세요.',
    '11': '필수 요청값 오류: 지점과 분석 기간을 확인하세요.',
    '12': '서비스 경로 오류: ASOS 시간자료 서비스 상태를 확인하세요.',
    '20': '서비스 접근 거부: 공공데이터포털에서 ASOS 시간자료 활용신청이 승인되었는지 확인하세요.',
    '21': '인증키 일시 정지: 공공데이터포털에서 키 상태를 확인하세요.',
    '22': '호출 한도 초과: 공공데이터포털의 일일 호출 한도를 확인하고 한도 초기화 후 재시도하세요.',
    '23': '초당 호출 한도 초과: 짧은 시간에 요청이 집중되었습니다. 잠시 후 재시도하세요.',
    '29': '접속 IP 차단: 호출 서버의 IP와 공공데이터포털 접근 제한 상태를 확인하세요.',
    '30': '등록되지 않은 인증키: ASOS 서비스의 Decoding 키를 공백 없이 입력하세요.',
    '31': '인증키 사용기간 만료: 공공데이터포털에서 기간 연장 또는 키 재발급을 확인하세요.',
    '32': '등록되지 않은 접속 IP: 활용신청의 허용 IP 설정을 확인하세요.',
}


def api_error(code):
    code = str(code).strip()
    if code not in _MESSAGES:
        return WeatherAPIError('기상자료 API 오류: 기상청 서비스 상태를 확인한 뒤 잠시 후 재시도하세요.')
    return WeatherAPIError(f'기상자료 API 오류 {code} · {_MESSAGES[code]}')


def response_error_code(text):
    match = re.search(r'<(?:returnReasonCode|resultCode)>\s*(\d{2})\s*</', text[:8192])
    return match.group(1) if match else None
