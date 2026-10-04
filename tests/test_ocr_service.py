import builtins

import pytest

from backend import ocr_service


def test_get_ocr_engine_reports_missing_runtime_module(monkeypatch):
    original_import = builtins.__import__

    def import_without_rapidocr(name, *args, **kwargs):
        if name == "rapidocr_onnxruntime":
            raise ModuleNotFoundError(
                "No module named 'rapidocr_onnxruntime'",
                name="rapidocr_onnxruntime",
            )
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_rapidocr)
    ocr_service.get_ocr_engine.cache_clear()
    try:
        with pytest.raises(
            RuntimeError,
            match="RapidOCR dependency 'rapidocr_onnxruntime' is unavailable",
        ):
            ocr_service.get_ocr_engine()
    finally:
        ocr_service.get_ocr_engine.cache_clear()
