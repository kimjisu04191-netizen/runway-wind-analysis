from datetime import date
import io
import zipfile

import numpy as np
import pandas as pd
import pytest


def winds(wd, ws):
    return pd.DataFrame({'wd': wd, 'ws_kt': ws,
                         'tm': pd.date_range('2025-01-01', periods=len(ws), freq='h')})


def test_all_calm_and_empty(core):
    result = core.analyze_runway(winds([0, 90], [0, 3]))
    for limit in (10, 13, 20):
        r = result['results'][limit]
        assert np.all(r['usability'] == 100) and r['pair_usab'] == 100
        assert r['mean_xwind'] == r['max_xwind'] == 0
    with pytest.raises(ValueError):
        core.analyze_runway(winds([], []))


@pytest.mark.parametrize('wd,ws', [([np.nan], [10]), ([90], [-1]), ([361], [10]), ([90], [np.inf])])
def test_reject_invalid_analysis(core, wd, ws):
    with pytest.raises(ValueError):
        core.analyze_runway(winds(wd, ws))


def test_coverage_against_direct_formula(core):
    rng = np.random.default_rng(943)
    wd, ws = rng.uniform(0, 360, 5000), rng.uniform(0, 45, 5000)
    ws[:10] = [0, 3, 3.1, 10, 10.1, 13, 13.1, 20, 20.1, 30]
    result = core.analyze_runway(winds(wd, ws))
    for limit in (10, 13, 20):
        r = result['results'][limit]
        xw = np.abs(ws[:, None] * np.sin(np.radians(wd[:, None] - result['angles'])))
        covered = (ws[:, None] <= 3) | (xw <= limit)
        np.testing.assert_allclose(r['usability'], covered.mean(axis=0) * 100)
        a, b = [x // 10 for x in r['pair_angles']]
        assert r['pair_usab'] == pytest.approx((covered[:, a] | covered[:, b]).mean() * 100)
    assert result['freq_table'].iloc[:, :-1].to_numpy().sum() == pytest.approx(100, abs=.5)
    assert len(result['angles']) == 18


def test_continuous_frequency_boundaries(core):
    ws = np.array([0, 3, 3.5, 10, 10.5, 13, 13.5, 20, 20.5])
    table = core._build_freq_table(np.zeros(len(ws)), ws, len(ws))
    np.testing.assert_allclose(table.iloc[0, :5], np.array([2, 2, 2, 2, 1]) / 9 * 100, atol=.005)


def test_excel_never_writes_uploaded_formula(core):
    data = pd.DataFrame({'=header': ['=1+1', ' +SUM(1,2)', '@SUM(1)', 'https://example.com'],
                         'wd': [0] * 4, 'ws': [1] * 4})
    output = core._build_quality_excel(data, data)
    with zipfile.ZipFile(io.BytesIO(output)) as z:
        for name in z.namelist():
            if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                xml = z.read(name)
                assert b'<f>' not in xml and b'<hyperlink ' not in xml


def test_report_uses_actual_failed_result_and_quality(core):
    from docx import Document
    data = winds([0, 90, 180, 270] * 10, [50] * 40)
    result = core.analyze_runway(data)
    document = Document(io.BytesIO(core.build_review_docx(result, data, '검증 지점', date(2025, 1, 1), date(2025, 1, 31), 20, 40, 40, 0)))
    text = '\n'.join(p.text for p in document.paragraphs)
    assert '95% 기준 미달' in text
    assert '미확보 시간은 704시간' in text
    assert '자기방위각' not in text and '자기편각을 적용하지 않았다' in text
    assert '방향에 관계없이 ICAO 기준' not in text
    assert '선정 규칙' in text


def test_windrose_dominant_direction_uses_rose_threshold(core):
    # 2 kt는 이용률 분석에서는 정온이지만 바람장미에서는 비정온이다.
    data = winds([90, 90, 0], [2, 2, 0])
    stats = core._narr_stats(core.analyze_runway(data), data, '검증', date(2025, 1, 1), date(2025, 1, 31), 20, 3, 3, 0)
    assert stats['top_dirs'][0][0] == 'E'
    assert stats['top_dirs'][0][2] == pytest.approx(200 / 3)
