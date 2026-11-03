from datetime import date
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest
import requests
from streamlit.testing.v1 import AppTest

import browser_keys
from weather_errors import WeatherAPIError, api_error, response_error_code
from conftest import ROOT
from test_network_ui import response


def test_results_survive_rerun_and_settings_change(monkeypatch):
    monkeypatch.setenv('ASOS_API_KEY', 'test-results-persistence')
    def get(self, url, **kwargs):
        month = kwargs['params']['startDt']
        return response({'response': {'header': {'resultCode': '00'}, 'body': {'items': {'item': [
            {'tm': f'{month[:4]}-{month[4:6]}-01 00:00', 'wd': '90', 'ws': '3'}]}}}})
    monkeypatch.setattr(requests.Session, 'get', get)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=60).run()
    next(b for b in app.button if b.label == '분석 시작').click().run()
    assert not app.exception and not app.error
    saved = app.session_state['analysis_result']
    assert saved['docx_bytes'] and saved['excel_bytes']
    app.run()
    assert len(app.get('download_button')) == 3
    next(r for r in app.radio if r.label == '기간 설정').set_value('최근 5년').run()
    assert not app.exception and not app.error
    assert app.session_state['analysis_result']['start'] == saved['start']
    assert app.session_state['analysis_result']['docx_bytes'] == saved['docx_bytes']
    assert app.session_state['analysis_result']['excel_bytes'] == saved['excel_bytes']
    assert len(app.get('download_button')) == 3
    next(b for b in app.button if b.label == 'API 키 설정').click().run()
    next(b for b in app.button if b.label == '닫기').click().run()
    assert len(app.get('download_button')) == 3
    next(b for b in app.button if b.label == 'API 키 설정').click().run()
    next(w for w in app.text_input if w.key == 'api_key').set_value('new-invalid-test-key')
    next(b for b in app.button if b.label == '닫기').click().run()
    monkeypatch.setattr(requests.Session, 'get', lambda *args, **kwargs: response({'response': {'header': {'resultCode': '30'}}}))
    next(b for b in app.button if b.label == '분석 시작').click().run()
    assert not app.exception and any('등록되지 않은 인증키' in item.value for item in app.error)
    assert app.session_state['analysis_result']['docx_bytes'] == saved['docx_bytes']
    assert len(app.get('download_button')) == 3


def test_user_key_survives_dialog_close_and_widget_cleanup(monkeypatch):
    monkeypatch.delenv('ASOS_API_KEY', raising=False)
    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
    next(b for b in app.button if b.label == 'API 키 설정').click().run()
    next(w for w in app.text_input if w.key == 'api_key').set_value('user-session-test-key')
    next(b for b in app.button if b.label == '닫기').click().run()
    app.run()
    assert app.session_state['user_api_keys']['api_key'] == 'user-session-test-key'
    next(b for b in app.button if b.label == 'API 키 설정').click().run()
    assert next(w for w in app.text_input if w.key == 'api_key').value == 'user-session-test-key'


def test_invalid_key_stops_after_first_request_and_gives_action(core, monkeypatch):
    ui = MagicMock()
    monkeypatch.setattr(core, 'st', ui)
    fetch = Mock(side_effect=api_error('30'))
    monkeypatch.setattr(core, '_fetch_month', fetch)
    with pytest.raises(WeatherAPIError, match='Decoding'):
        core.get_weather_data_v28('test-key', '108', date(2020, 1, 1), date(2025, 1, 31))
    assert fetch.call_count == 1
    assert '인증' in ui.progress.call_args.kwargs['text']
    assert ui.status.return_value.__enter__.return_value.update.call_args.kwargs['state'] == 'error'


def test_waiting_months_update_elapsed_progress(core, monkeypatch):
    ui = MagicMock()
    monkeypatch.setattr(core, 'st', ui)
    monkeypatch.setattr(core, '_fetch_month', lambda key, stn, start, end: [
        {'tm': f'{start[:4]}-{start[4:6]}-01', 'wd': '90', 'ws': '3'}])
    real_wait = core.wait
    calls = 0
    def wait(futures, **kwargs):
        nonlocal calls
        calls += 1
        return (set(), set(futures)) if calls == 1 else real_wait(futures, **kwargs)
    monkeypatch.setattr(core, 'wait', wait)
    valid, _, count = core.get_weather_data_v28('test-key', '108', date(2025, 1, 1), date(2025, 2, 28))
    assert count == len(valid) == 2
    texts = [call.kwargs['text'] for call in ui.progress.return_value.progress.call_args_list]
    assert any('기상청 응답 대기' in text and '경과' in text for text in texts)


def test_xml_error_and_http_quota_are_safe(core):
    session = Mock()
    r = response(None)
    r.json.side_effect = ValueError()
    r.text = '<returnReasonCode>30</returnReasonCode><returnAuthMsg>test-secret</returnAuthMsg>'
    session.get.return_value = r
    with pytest.raises(WeatherAPIError, match='등록되지 않은 인증키') as error:
        core._fetch_one(session, 'test-secret', '108', '20250101', '20250131')
    assert 'test-secret' not in str(error.value)
    session.get.return_value = response(None, 429)
    with pytest.raises(WeatherAPIError, match='호출 한도 초과'):
        core._fetch_one(session, 'test-secret', '108', '20250101', '20250131')
    assert response_error_code('<resultCode>30</resultCode>') == '30'
    assert 'sensitive' not in str(api_error('sensitive'))


def test_browser_storage_is_opt_in_and_never_contains_server_key(monkeypatch):
    state = {'user_api_keys': {'api_key': 'explicit-user-key'}}
    monkeypatch.setattr(browser_keys.st, 'session_state', state)
    monkeypatch.setenv('ASOS_API_KEY', 'server-only-key')
    browser_keys.queue_browser_command('save')
    assert state['browser_key_command']['keys']['api_key'] == 'explicit-user-key'
    assert 'server-only-key' not in str(state['browser_key_command'])
    state['browser_key_store'] = {'event': {'id': 'r1', 'action': 'restored', 'keys': {'api_key': 'saved-key', 'unknown': 'ignored'}}}
    browser_keys.apply_browser_event()
    assert state['user_api_keys']['api_key'] == 'explicit-user-key'
    assert 'unknown' not in state['user_api_keys']
    state['browser_key_store'] = {'event': {'id': 'd1', 'action': 'deleted'}}
    browser_keys.apply_browser_event()
    assert state['user_api_keys'] == {} and 'browser_key_command' not in state


def test_browser_restore_into_new_session_and_failure_notice(monkeypatch):
    state = {'browser_key_store': {'event': {'id': 'restore', 'action': 'restored', 'keys': {'api_key': 'saved-user-key'}}}}
    monkeypatch.setattr(browser_keys.st, 'session_state', state)
    browser_keys.apply_browser_event()
    assert state['user_api_keys']['api_key'] == 'saved-user-key'
    assert state['browser_key_restore_done']
    state['browser_key_store'] = {'event': {'id': 'failure', 'action': 'unavailable'}}
    browser_keys.apply_browser_event()
    assert '저장 권한' in state['browser_key_message']


def test_report_over20_uses_only_strict_over20_observations(core):
    for speeds, expected in (([5, 5, 5, 5], 0), ([5, 13, 20, 21], 25)):
        frame = pd.DataFrame({'wd': [90] * 4, 'ws_kt': speeds,
                              'tm': pd.date_range('2025-01-01', periods=4, freq='h')})
        stats = core._narr_stats(core.analyze_runway(frame), frame, '검증', date(2025, 1, 1), date(2025, 1, 31), 20, 4, 4, 0)
        assert stats['over20_pct'] == expected
