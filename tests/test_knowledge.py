"""Тесты сборки базы знаний и системного промпта."""

from bot.knowledge import build_system_prompt, load_knowledge


def test_load_knowledge_reads_md_and_txt_in_sorted_order(tmp_path):
    (tmp_path / "b.txt").write_text("second", encoding="utf-8")
    (tmp_path / "a.md").write_text("first", encoding="utf-8")
    (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

    assert load_knowledge(str(tmp_path)) == "first\n\n---\n\nsecond"


def test_load_knowledge_missing_dir_returns_empty(tmp_path):
    assert load_knowledge(str(tmp_path / "does-not-exist")) == ""


def test_load_knowledge_empty_dir_returns_empty(tmp_path):
    assert load_knowledge(str(tmp_path)) == ""


def test_build_system_prompt_replaces_placeholder_and_appends_knowledge(tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("Форма: {{MANAGER_FORM_URL}}", encoding="utf-8")

    result = build_system_prompt(str(prompt_file), "ФАКТЫ", "https://example.com")

    assert "https://example.com" in result
    assert "{{MANAGER_FORM_URL}}" not in result
    assert "ФАКТЫ" in result


def test_build_system_prompt_without_knowledge_keeps_prompt(tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("OK", encoding="utf-8")

    assert build_system_prompt(str(prompt_file), "", "https://example.com") == "OK"
