import json

def test_config_load():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    assert "min_delay" in config
    assert "message_text" in config
    assert isinstance(config["thread_count"], int)
