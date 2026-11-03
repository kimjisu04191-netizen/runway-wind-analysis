import ast
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def core():
    """실제 app.py의 함수·상수만 로드해 UI 실행 없이 계산/수집 경계를 검증한다."""
    tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
    names = {'ASOS_BY_REGION', 'STATION_LOOKUP', 'STATION_DB', 'API_URL',
             'MAX_WORKERS', 'REQUEST_TIMEOUT', 'MAX_RETRIES', 'NEAR_ASOS_PREFER_KM',
             'CROSSWIND_LIMITS_KT', 'CALM_THRESHOLD_KT', 'USABILITY_TARGET',
             'TIE_TOLERANCE', 'MIN_SEPARATION_DEG', 'KT_TO_MS', 'RWY_ANGLE_STEP_DEG',
             'REPORT_TEMPLATE_PATH', 'REPORT_TABLE_STYLE', '_KDIR', '_ASOS_ID_TO_INFO'}
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            nodes.append(node)
        elif isinstance(node, ast.FunctionDef):
            node.decorator_list = []
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            nodes.append(node)
    module = types.ModuleType('app_core')
    module.__file__ = str(ROOT / 'app.py')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'app.py'), 'exec'), module.__dict__)
    return module
