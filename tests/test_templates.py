import sys
import os

# Добавим корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.templates import parse_template

def test_variable_substitution():
    text = "Привет, {name}!"
    result = parse_template(text, {"name": "Алексей"})
    assert result == "Привет, Алексей!"

def test_random_choice():
    text = "{Привет|Здравствуй|Хей}"
    results = set(parse_template(text) for _ in range(10))
    assert len(results) > 1  # Должна быть вариативность
