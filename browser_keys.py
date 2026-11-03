"""사용자가 선택한 키만 브라우저에 저장한다. 서버 비밀키는 전달받지 않는다."""
import uuid

import streamlit as st

KEY_NAMES = ('api_key', 'kma_hub_key', 'kakao_key')

JS = r"""
export default function(component) {
  const { data, setStateValue } = component;
  const storageKey = 'runway-wind-analysis.user-api-keys.v1:' + window.location.pathname;
  const validKeys = (value) => {
    const result = {};
    for (const key of ['api_key', 'kma_hub_key', 'kakao_key']) {
      if (typeof value?.[key] === 'string' && value[key].length <= 4096) result[key] = value[key].trim();
    }
    return result;
  };
  const command = data.command;
  if (!command && !data.restore) return;
  try {
    if (command?.action === 'save') {
      localStorage.setItem(storageKey, JSON.stringify({version: 1, keys: validKeys(command.keys)}));
      setStateValue('event', {id: command.id, action: 'saved'});
    } else if (command?.action === 'delete') {
      localStorage.removeItem(storageKey);
      setStateValue('event', {id: command.id, action: 'deleted'});
    } else if (data.restore) {
      const raw = localStorage.getItem(storageKey);
      const saved = raw && raw.length <= 20000 ? JSON.parse(raw) : null;
      setStateValue('event', {id: 'restore', action: 'restored', keys: saved?.version === 1 ? validKeys(saved.keys) : {}});
    }
  } catch (error) {
    setStateValue('event', {id: command?.id || 'restore', action: 'unavailable'});
  }
}
"""

_store = st.components.v2.component('runway_browser_key_store', js=JS)


def apply_browser_event():
    event = st.session_state.get('browser_key_store', {}).get('event') or {}
    if not isinstance(event, dict) or event.get('id') == st.session_state.get('browser_key_event_id'):
        return
    st.session_state['browser_key_event_id'] = event.get('id')
    st.session_state['browser_key_restore_done'] = True
    st.session_state.pop('browser_key_command', None)
    action = event.get('action')
    if action == 'restored':
        restored = event.get('keys', {})
        current = dict(st.session_state.get('user_api_keys', {}))
        if isinstance(restored, dict):
            for key in KEY_NAMES:
                value = restored.get(key)
                if not current.get(key) and isinstance(value, str) and len(value) <= 4096:
                    current[key] = value.strip()
        st.session_state['user_api_keys'] = current
        if any(current.values()):
            st.session_state['browser_key_message'] = '이 브라우저에 저장된 API 키를 불러왔습니다.'
    elif action == 'deleted':
        st.session_state['user_api_keys'] = {}
        for key in KEY_NAMES:
            st.session_state.pop(key, None)
        st.session_state['browser_key_message'] = '브라우저에 저장된 키와 현재 세션 입력을 삭제했습니다.'
    elif action == 'saved':
        st.session_state['browser_key_message'] = '이 브라우저에 API 키를 저장했습니다. 같은 주소로 재접속하면 자동으로 불러옵니다.'
    elif action == 'unavailable':
        st.session_state['browser_key_message'] = '브라우저 저장을 사용할 수 없습니다. 브라우저의 사이트 저장 권한을 확인하세요. 현재 세션에서는 입력한 키를 사용할 수 있습니다.'


def queue_browser_command(action):
    command = {'action': action, 'id': uuid.uuid4().hex}
    if action == 'save':
        command['keys'] = {key: st.session_state.get('user_api_keys', {}).get(key, '') for key in KEY_NAMES}
    st.session_state['browser_key_command'] = command


def mount_browser_store():
    _store(key='browser_key_store', data={
        'restore': not st.session_state.get('browser_key_restore_done', False),
        'command': st.session_state.get('browser_key_command'),
    }, default={'event': None}, on_event_change=apply_browser_event)
    message = st.session_state.pop('browser_key_message', None)
    if message:
        st.info(message)
