from unittest.mock import MagicMock, patch


def test_clear_all_caches_calls_st_cache_data_clear():
    mock_st = MagicMock()
    with patch.dict("sys.modules", {"streamlit": mock_st}):
        import importlib
        import app.role_loader as rl
        importlib.reload(rl)
        rl.clear_all_caches()
    mock_st.cache_data.clear.assert_called_once()
