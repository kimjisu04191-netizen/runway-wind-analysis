from datetime import date
from unittest.mock import Mock, MagicMock

import pytest
import requests
from streamlit.testing.v1 import AppTest

from conftest import ROOT


def response(payload, status=200):
    r = Mock(status_code=status)
    r.json.return_value = payload
    return r


def test_https_midnight_and_api_error(core):
    session = Mock()
    session.get.return_value = response({'response': {'header': {'resultCode': '30', 'resultMsg': 'sensitive'}, 'body': {}}})
    with pytest.raises(RuntimeError, match='API 오류') as error:
        core._fetch_one(session, 'fake-key', '108', '20250101', '20250131')
    assert 'sensitive' not in str(error.value) and 'fake-key' not in str(error.value)
    args, kwargs = session.get.call_args
    assert args[0].startswith('https://') and kwargs['params']['startHh'] == '00'
    assert kwargs['allow_redirects'] is False


def test_request_error_does_not_expose_key(core):
    session = Mock()
    session.get.side_effect = requests.ConnectionError('https://example.com?serviceKey=fake-key')
    with pytest.raises(RuntimeError) as error:
        core._fetch_one(session, 'fake-key', '108', '20250101', '20250131')
    assert 'fake-key' not in str(error.value)
    assert error.value.__suppress_context__


def test_truncated_api_response_is_not_success(core):
    session = Mock()
    session.get.return_value = response({'response': {'header': {'resultCode': '00'}, 'body': {
        'totalCount': 744, 'items': {'item': [{'tm': '2025-01-01', 'wd': 0, 'ws': 1}]}}}})
    with pytest.raises(RuntimeError, match='응답 건수'):
        core._fetch_one(session, 'fake-key', '108', '20250101', '20250131')


def test_station_denied_and_kakao_errors_do_not_leak_key(core, monkeypatch):
    monkeypatch.setattr(core.requests, 'get', Mock(side_effect=requests.ConnectionError('authKey=fake-key')))
    with pytest.raises(RuntimeError) as error:
        core._load_station_db('fake-key')
    assert 'fake-key' not in str(error.value)
    assert 'fake-key' not in core._geocode_address_kakao('주소', 'fake-key')[3]


def test_partial_failure_is_not_success(core, monkeypatch):
    monkeypatch.setattr(core, 'st', MagicMock())
    def fetch(key, stn, start, end):
        if start == '20250201':
            raise requests.ConnectionError('fake-key')
        return [{'tm': '2025-01-01 00:00', 'wd': '0', 'ws': '1'}]
    monkeypatch.setattr(core, '_fetch_month', fetch)
    with pytest.raises(RuntimeError, match='구간 수집 실패'):
        core.get_weather_data_v28('fake-key', '108', date(2025, 1, 1), date(2025, 2, 28))


def test_api_reject_future_and_reversed_dates(core):
    assert core.get_weather_data_v28('', '108', date(2025, 2, 1), date(2025, 1, 1))[0] is None
    assert core.get_weather_data_v28('', '108', date.today(), date.today())[0] is None


def test_startup_and_server_secrets_not_sent_to_widgets(monkeypatch):
    monkeypatch.setenv('ASOS_API_KEY', 'server-only-test-value')
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label == 'API 키 설정').click().run()
    assert not app.exception
    assert next(w for w in app.text_input if w.key == 'api_key').value == ''
    assert all(w.value != 'server-only-test-value' for w in app.text_input)


def test_analysis_ui_with_mock_data(monkeypatch):
    monkeypatch.setenv('ASOS_API_KEY', 'server-only-test-value')
    def get(self, url, **kwargs):
        params = kwargs['params']
        start = params['startDt']
        # 실제 외부 서비스 호출 없이 월별 정상/정온 자료로 화면·다운로드까지 검사한다.
        return response({'response': {'header': {'resultCode': '00'}, 'body': {'items': {'item': [
            {'tm': f'{start[:4]}-{start[4:6]}-{start[6:]} 00:00', 'wd': '0', 'ws': '0'}]}}}})
    monkeypatch.setattr(requests.Session, 'get', get)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60).run()
    next(b for b in app.button if b.label == '분석 시작').click().run()
    assert not app.exception and not app.error
    assert len(app.get('download_button')) == 3
    assert any('미확보' in w.value for w in app.warning)
