import json
from pathlib import Path

from dotenv import load_dotenv

from services.rag import embed_question, search_opensearch


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

load_dotenv(BACKEND_DIR / ".env")


GOOD_CASES_PATH = BASE_DIR / "cases.json"

BAD_QUESTIONS = [
    "What is the capital of France?",
    "How do I install Docker on Ubuntu?",
    "Who won the football World Cup?",
    "What is the weather today?",
    "How do I cook chicken curry?",

    # harder / medical-looking negatives
    "Does Ozempic cure cancer?",
    "Can Humira treat type 2 diabetes?",
    "Does Ozempic cure Alzheimer's disease?",
    "Can Ozempic permanently cure diabetes?",
    "Is Humira a treatment for high blood pressure?",
    "Can Humira cure cancer?",
]


def print_scores(label: str, question: str):
    embedding = embed_question(question)
    results = search_opensearch(embedding)

    print(f"\n[{label}] {question}")

    for index, result in enumerate(results, start=1):
        print(
            f"  {index}. score={result['score']:.4f} "
            f"source={result['source']}"
        )


def main():
    with GOOD_CASES_PATH.open(encoding="utf-8") as file:
        good_cases = json.load(file)["cases"]

    print("\n========== GOOD QUESTIONS ==========")

    for case in good_cases:
        print_scores("GOOD", case["question"])

    print("\n========== BAD QUESTIONS ==========")

    for question in BAD_QUESTIONS:
        print_scores("BAD", question)


if __name__ == "__main__":
    main()