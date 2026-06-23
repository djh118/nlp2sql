from pathlib import Path

prompt_path = Path(__file__).parents[2] / "prompts"


def load_prompt(name: str) -> str:
    file_path = prompt_path / f"{name}.prompt"
    return file_path.read_text(encoding="utf-8")


if __name__ == '__main__':
    print(load_prompt("extend_keywords_for_column_recall"))
    prompt = load_prompt("extend_keywords_for_column_recall")
    print(prompt)
