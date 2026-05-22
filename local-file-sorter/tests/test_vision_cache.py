"""Test VisionClient SHA256 caching – cache hit must skip model call."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _mock_chat_response(content: str) -> MagicMock:
    """Return a mock that mirrors the ollama ChatResponse attribute structure."""
    resp = MagicMock()
    resp.message.content = content
    return resp


def test_cache_hit_skips_model_call(tmp_path):
    """Second classify() for the same file must not call the Ollama API."""
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    cache_file = tmp_path / "vision_cache.json"

    with patch("ollama.Client") as MockClient:
        mock_inst = MagicMock()
        MockClient.return_value = mock_inst
        mock_inst.chat.return_value = _mock_chat_response("Landschaft")

        from src.llm.vision_client import VisionClient

        client1 = VisionClient(cache_path=cache_file)
        result1 = client1.classify(img)
        assert result1 == "Landschaft"
        assert mock_inst.chat.call_count == 1

        # Re-create client so it reloads cache from disk
        client2 = VisionClient(cache_path=cache_file)
        result2 = client2.classify(img)
        assert result2 == "Landschaft"
        assert mock_inst.chat.call_count == 1   # still 1 → cache hit


def test_cache_persisted_to_disk(tmp_path):
    """Cache JSON is written after each new classification."""
    img = tmp_path / "shot.png"
    img.write_bytes(b"\x89PNG" + b"\x00" * 50)
    cache_file = tmp_path / "vcache.json"

    with patch("ollama.Client") as MockClient:
        mock_inst = MagicMock()
        MockClient.return_value = mock_inst
        mock_inst.chat.return_value = _mock_chat_response("Natur")

        from src.llm.vision_client import VisionClient
        client = VisionClient(cache_path=cache_file)
        client.classify(img)

    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "Natur" in data.values()


def test_different_files_get_separate_cache_entries(tmp_path):
    """Two distinct image files produce two independent cache entries."""
    img1 = tmp_path / "a.jpg"
    img1.write_bytes(b"\xff\xd8\xff" + b"A" * 50)
    img2 = tmp_path / "b.jpg"
    img2.write_bytes(b"\xff\xd8\xff" + b"B" * 50)
    cache_file = tmp_path / "vc2.json"

    counter = {"n": 0}

    def fake_chat(**kwargs):
        counter["n"] += 1
        resp = MagicMock()
        resp.message.content = f"Kategorie{counter['n']}"
        return resp

    with patch("ollama.Client") as MockClient:
        mock_inst = MagicMock()
        MockClient.return_value = mock_inst
        mock_inst.chat.side_effect = fake_chat

        from src.llm.vision_client import VisionClient
        client = VisionClient(cache_path=cache_file)
        r1 = client.classify(img1)
        r2 = client.classify(img2)

    assert r1 != r2
    assert counter["n"] == 2


def test_classify_batch_returns_all_paths(tmp_path):
    """classify_batch covers every image path even if count > 1."""
    imgs = []
    for i in range(3):
        p = tmp_path / f"img{i}.jpg"
        p.write_bytes(b"\xff\xd8\xff" + bytes([i]) * 20)
        imgs.append(p)
    cache_file = tmp_path / "batch_cache.json"

    with patch("ollama.Client") as MockClient:
        mock_inst = MagicMock()
        MockClient.return_value = mock_inst
        mock_inst.chat.return_value = _mock_chat_response("Tier")

        from src.llm.vision_client import VisionClient
        client = VisionClient(cache_path=cache_file)
        result = client.classify_batch(imgs)

    assert set(result.keys()) == set(imgs)
    assert all(v == "Tier" for v in result.values())


def test_classify_batch_progress_cb(tmp_path):
    """progress_cb is called once per image with (done, total)."""
    imgs = [tmp_path / f"x{i}.jpg" for i in range(4)]
    for p in imgs:
        p.write_bytes(b"\xff\xd8\xff" + p.name.encode())
    cache_file = tmp_path / "pb_cache.json"
    calls = []

    with patch("ollama.Client") as MockClient:
        mock_inst = MagicMock()
        MockClient.return_value = mock_inst
        mock_inst.chat.return_value = _mock_chat_response("X")

        from src.llm.vision_client import VisionClient
        client = VisionClient(cache_path=cache_file)
        client.classify_batch(imgs, progress_cb=lambda d, t: calls.append((d, t)))

    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]
