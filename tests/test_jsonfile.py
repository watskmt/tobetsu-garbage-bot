from pathlib import Path

from jsonfile import load_json, save_json


def test_roundtrip(tmp_path):
    p = tmp_path / "x.json"
    save_json(p, {"a": [1, 2], "b": "日本語"})
    assert load_json(p, None) == {"a": [1, 2], "b": "日本語"}
    # 一時ファイルが残らない
    assert [f.name for f in tmp_path.iterdir()] == ["x.json"]


def test_missing_and_corrupt_return_default(tmp_path):
    assert load_json(tmp_path / "none.json", {"d": 1}) == {"d": 1}
    p = tmp_path / "bad.json"
    Path(p).write_text("{not json", encoding="utf-8")
    assert load_json(p, []) == []


def test_overwrite_replaces_atomically(tmp_path):
    p = tmp_path / "x.json"
    save_json(p, {"v": 1})
    save_json(p, {"v": 2})
    assert load_json(p, None) == {"v": 2}


def test_save_through_symlink_writes_target(tmp_path):
    """本番の /app/x.json → /data/x.json 構成: リンクを壊さず実体に書く"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    target = data_dir / "x.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "x.json"
    link.symlink_to(target)

    save_json(link, {"v": 1})

    assert link.is_symlink()                       # リンクのまま
    assert load_json(target, None) == {"v": 1}     # 実体に書かれている
    assert [f.name for f in data_dir.iterdir()] == ["x.json"]


def test_save_through_dangling_symlink_creates_target(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    link = tmp_path / "x.json"
    link.symlink_to(data_dir / "x.json")           # 実体はまだ無い
    save_json(link, {"v": 2})
    assert link.is_symlink()
    assert load_json(data_dir / "x.json", None) == {"v": 2}
