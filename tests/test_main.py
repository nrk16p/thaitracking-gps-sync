import os

import main
from unittest.mock import patch, Mock

import pytest


def test_to_bkk_parses_thai_slash_format():
    assert main._to_bkk('02/07/2026 13:01:25') == '2026-07-02 13:01:25'


def test_to_bkk_handles_iso_dash_format():
    assert main._to_bkk('2026-07-02 13:01:25') == '2026-07-02 13:01:25'


def test_to_bkk_returns_original_string_when_unparseable():
    assert main._to_bkk('not-a-date') == 'not-a-date'


def test_load_env_file_sets_env_vars(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('THAITRACKING_USERNAME=from-file\n# comment\nEMPTY_LINE_ABOVE=1\n')
    monkeypatch.delenv('THAITRACKING_USERNAME', raising=False)

    main.load_env_file(str(env_file))

    assert os.environ['THAITRACKING_USERNAME'] == 'from-file'


def test_load_env_file_does_not_overwrite_existing_env(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('THAITRACKING_USERNAME=from-file\n')
    monkeypatch.setenv('THAITRACKING_USERNAME', 'from-real-env')

    main.load_env_file(str(env_file))

    assert os.environ['THAITRACKING_USERNAME'] == 'from-real-env'


def test_load_env_file_missing_file_is_a_noop(tmp_path):
    missing = tmp_path / 'does-not-exist.env'
    main.load_env_file(str(missing))  # must not raise


def test_build_payload_maps_fields_and_running_status():
    records = [{
        'plate': '71-2035',
        'latitude': '13.618802',
        'longitude': '100.659985',
        'speed': 40,
        'gps_datetime': '02/07/2026 13:01:25',
        'status': 'วิ่งปกติ',
    }]
    result = main.build_payload(records)

    assert result == [{
        'gps_id': '71-2035',
        'plate_master': '71-2035',
        'plate_type': 'H',
        'gps_vendor': 'thaitracking',
        'current_latlng': '13.618802,100.659985',
        'gps_updated_at': '2026-07-02 13:01:25',
        'status': 'วิ่ง',
    }]


def test_build_payload_zero_speed_is_stopped():
    records = [{'plate': '71-2035', 'latitude': '1', 'longitude': '2',
                'speed': 0, 'gps_datetime': '02/07/2026 13:01:25'}]
    result = main.build_payload(records)
    assert result[0]['status'] == 'หยุด'


def test_build_payload_string_speed_zero_is_stopped():
    records = [{'plate': '71-2035', 'latitude': '1', 'longitude': '2',
                'speed': '0', 'gps_datetime': '02/07/2026 13:01:25'}]
    result = main.build_payload(records)
    assert result[0]['status'] == 'หยุด'


def test_build_payload_missing_latlng_becomes_empty_string():
    records = [{'plate': '71-2035', 'latitude': None, 'longitude': None,
                'speed': 0, 'gps_datetime': '02/07/2026 13:01:25'}]
    result = main.build_payload(records)
    assert result[0]['current_latlng'] == ''


def test_build_payload_gps_id_matches_plate():
    records = [{'plate': '73-1757', 'latitude': '1', 'longitude': '2',
                'speed': 10, 'gps_datetime': '02/07/2026 13:01:25'}]
    result = main.build_payload(records)
    assert result[0]['gps_id'] == '73-1757'
    assert result[0]['plate_master'] == '73-1757'


def _mock_response(json_body):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = json_body
    return resp


def test_fetch_gps_returns_list_when_response_is_a_list():
    body = [{'plate': '71-2035', 'latitude': '1', 'longitude': '2', 'speed': 0, 'gps_datetime': ''}]
    with patch('main.requests.get', return_value=_mock_response(body)) as mock_get:
        result = main.fetch_gps('user', 'pass')

    assert result == body
    assert mock_get.call_count == 1


def test_fetch_gps_unwraps_dict_with_data_key():
    body = {'data': [{'plate': '71-2035'}]}
    with patch('main.requests.get', return_value=_mock_response(body)):
        result = main.fetch_gps('user', 'pass')
    assert result == [{'plate': '71-2035'}]


def test_fetch_gps_returns_empty_list_for_unexpected_shape():
    with patch('main.requests.get', return_value=_mock_response('unexpected')):
        result = main.fetch_gps('user', 'pass')
    assert result == []


def test_post_to_backend_sends_payload_and_logs_summary(caplog):
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.status_code = 200
    resp.text = '[{"gps_updated_at": "2026-07-02 13:01:25"}]'
    resp.json.return_value = [{'gps_updated_at': '2026-07-02 13:01:25'}]

    payload = [{'gps_id': '71-2035', 'plate_master': '71-2035'}]

    with caplog.at_level('INFO'):
        with patch('main.requests.post', return_value=resp) as mock_post:
            main.post_to_backend(payload)

    mock_post.assert_called_once_with(
        main.BACKEND_URL,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30,
    )
    assert 'sent=1, updated=1' in caplog.text


def test_post_to_backend_propagates_http_errors():
    import requests as requests_module
    resp = Mock()
    resp.raise_for_status = Mock(side_effect=requests_module.HTTPError('500 error'))

    with patch('main.requests.post', return_value=resp):
        with pytest.raises(requests_module.HTTPError):
            main.post_to_backend([{'gps_id': 'A1'}])


def test_main_exits_when_credentials_missing(monkeypatch):
    monkeypatch.delenv('THAITRACKING_USERNAME', raising=False)
    monkeypatch.delenv('THAITRACKING_PASSWORD', raising=False)
    monkeypatch.chdir(os.path.dirname(os.path.abspath(main.__file__)) + '/tests')  # no .env here
    with pytest.raises(SystemExit):
        main.main()


def test_main_happy_path_fetches_and_posts(monkeypatch):
    monkeypatch.setenv('THAITRACKING_USERNAME', 'user')
    monkeypatch.setenv('THAITRACKING_PASSWORD', 'pass')

    fetch_resp = _mock_response([{
        'plate': '71-2035', 'latitude': '13.6', 'longitude': '100.6',
        'speed': 40, 'gps_datetime': '02/07/2026 13:01:25',
    }])
    backend_resp = Mock()
    backend_resp.raise_for_status = Mock()
    backend_resp.status_code = 200
    backend_resp.text = '[{"gps_updated_at": "2026-07-02 13:01:25"}]'
    backend_resp.json.return_value = [{'gps_updated_at': '2026-07-02 13:01:25'}]

    with patch('main.requests.get', return_value=fetch_resp) as mock_get:
        with patch('main.requests.post', return_value=backend_resp) as mock_post:
            main.main()

    assert mock_get.call_count == 1
    assert mock_post.call_count == 1


def test_main_aborts_post_when_no_records(monkeypatch):
    monkeypatch.setenv('THAITRACKING_USERNAME', 'user')
    monkeypatch.setenv('THAITRACKING_PASSWORD', 'pass')

    with patch('main.requests.get', return_value=_mock_response([])):
        with patch('main.requests.post') as mock_post:
            with pytest.raises(SystemExit):
                main.main()

    mock_post.assert_not_called()
