from datetime import date
import io

import numpy as np
import pandas as pd
import pytest

from wind_data import prepare_observations, parse_aws_csv, coverage_summary


def upload(text):
    result = io.BytesIO(text.encode('utf-8-sig'))
    result.name = 'weather.csv'
    return result


def frame(wd, ws):
    return pd.DataFrame({'tm': pd.date_range('2025-01-01', periods=len(ws), freq='h'), 'wd': wd, 'ws': ws})


def test_invalid_ranges_finite_and_flags():
    data = frame([0, 360, -9, 361, np.inf, 90, 90, 90, 90], [0, 1, 1, 1, 1, -9, np.inf, 1, 1])
    data['wsQcflg'] = ['', '0', '', '', '', '', '', '1', '9']
    valid, invalid = prepare_observations(data)
    assert len(valid) == 2 and len(invalid) == 7
    assert invalid['제외사유'].str.len().gt(0).all()
    assert valid.loc[1, 'ws_kt'] == pytest.approx(1.94384)


def test_duplicate_conflict_and_hourly_validation():
    data = pd.DataFrame({'tm': ['2025-01-01 00:00'] * 2 + ['2025-01-01 01:00'] * 2 + ['bad', '2025-01-01 02:30'],
                         'wd': [0, 0, 90, 100, 90, 90], 'ws': [2] * 6})
    valid, invalid = prepare_observations(data)
    assert len(valid) == 1 and len(invalid) == 5
    assert invalid['제외사유'].eq('동일 시각 관측값 충돌').sum() == 2


def test_filter_period_coverage_and_station_mixing():
    data = frame([0] * 48, [1] * 48)
    valid, _ = prepare_observations(data, date(2025, 1, 2), date(2025, 1, 2))
    assert len(valid) == 24
    assert coverage_summary(valid, date(2025, 1, 1), date(2025, 1, 2))['percent'] == 50
    data['stnId'] = ['90', '91'] * 24
    with pytest.raises(ValueError, match='지점번호'):
        prepare_observations(data)


def test_csv_repeatable_read_period_and_dedup():
    text = '지점,일시,풍향(deg),풍속(m/s)\n90,2025-01-01 00:00,0,1\n90,2025-01-02 00:00,90,2\n'
    files = [upload(text), upload(text)]
    for _ in range(2):
        valid, invalid, count, period = parse_aws_csv(files, date(2025, 1, 2), date(2025, 1, 2))
        assert count == 1 and len(invalid) == 1
        assert period == (date(2025, 1, 2), date(2025, 1, 2))
        assert valid.loc[0, 'ws'] == 2


@pytest.mark.parametrize('text', [
    '일시,풍향(16방위),풍속(m/s)\n2025-01-01,16,2',
    '일시,풍향(deg),풍속(kt)\n2025-01-01,90,2',
    '풍향(deg),풍속(m/s)\n90,2',
    '지점,일시,풍향(deg),풍속(m/s)\n90,2025-01-01,90,2\n91,2025-01-01 01:00,90,2',
    '일시,풍향(deg),풍속(m/s)\nbad,90,2',
])
def test_csv_rejects_ambiguous_or_invalid_data(text):
    assert parse_aws_csv([upload(text)])[0] is None


def test_csv_limits_and_missing_station_in_multiple_files():
    text = '일시,풍향(deg),풍속(m/s)\n2025-01-01,90,2'
    assert parse_aws_csv([upload(text)] * 21)[0] is None
    assert parse_aws_csv([upload(text), upload(text)])[0] is None
    assert parse_aws_csv([io.BytesIO(b'x' * (10 * 1024 * 1024 + 1))])[0] is None


def test_csv_rejects_duplicate_headers_and_canonical_collision():
    assert parse_aws_csv([upload('일시,풍향(deg),풍속(m/s),풍속(m/s)\n2025-01-01,90,2,3')])[0] is None
    assert parse_aws_csv([upload('일시,tm,풍향(deg),풍속(m/s)\n2025-01-01,2025-01-02,90,2')])[0] is None


def test_mixed_dates_and_raw_invalid_values_preserved():
    data = pd.DataFrame({'tm': ['2025-01-01', '2025-01-01 01:00', 'bad'], 'wd': [90, 90, '=1+1'], 'ws': [2, 2, 2]})
    valid, invalid = prepare_observations(data)
    assert len(valid) == 2
    assert invalid.loc[0, '원본_풍향'] == '=1+1'
