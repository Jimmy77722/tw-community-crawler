# -*- coding: utf-8 -*-
"""tests/conftest.py：共用 fixture 與全域限速狀態清理。"""
import pytest

from twcc import http_client


@pytest.fixture(autouse=True)
def _reset_rate_state():
    """限速狀態是模組級全域：每個測試前清空，避免互相干扰。"""
    http_client._last_call.clear()
    yield
    http_client._last_call.clear()
