import re
import random

def parse_template(text: str, variables: dict = None) -> str:
    if variables is None:
        variables = {}

    # Подстановка переменных {name}
    def replace_var(match):
        key = match.group(1)
        return str(variables.get(key, f"{{{key}}}"))

    text = re.sub(r"{(\w+)}", replace_var, text)

    # Рандомизация вариантов {привет|хей|здравствуй}
    def replace_random(match):
        options = match.group(1).split("|")
        return random.choice(options)

    text = re.sub(r"{([^{}|]+(?:\|[^{}|]+)+)}", replace_random, text)

    return text
