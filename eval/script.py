import asyncio
import json
from pathlib import Path

from app.api.dependencies import get_moderation_service

CATEGORIES = ["toxicity", "spam", "pii", "off_topic"]
THRESHOLD = 0.7


def load_jsonl(path):
    full_path = Path(__file__).parent / path
    with open(full_path) as f:
        return [json.loads(line) for line in f if line.strip()]


def expected_flags(labels: dict) -> dict:
    return {cat: labels.get(cat, 0) >= THRESHOLD for cat in CATEGORIES}


async def run_eval(dataset_path="dataset.jsonl"):
    service = get_moderation_service()
    model = service._llm_client._model
    examples = load_jsonl(dataset_path)

    correct = {cat: 0 for cat in CATEGORIES}
    incorrect = {cat: 0 for cat in CATEGORIES}
    false_positives = {cat: 0 for cat in CATEGORIES}
    false_negatives = {cat: 0 for cat in CATEGORIES}
    overall_correct = 0
    overall_incorrect = 0
    failures = []
    skipped = []

    for i, ex in enumerate(examples):
        text = ex["text"]
        labels = ex["labels"]
        expected = expected_flags(labels)
        expected_overall = labels.get("overall_flagged", False)

        print(f"[{i + 1}/{len(examples)}] {ex['id']}...", end=" ", flush=True)

        result = None
        for attempt in range(3):
            try:
                result = await service.moderate(text)
                break
            except Exception as e:
                if ("429" in str(e) or "503" in str(e)) and attempt < 2:
                    print("rate limited, retrying in 30s...", end=" ", flush=True)
                    await asyncio.sleep(30)
                else:
                    print(f"SKIPPED ({e})")
                    skipped.append({"id": ex["id"], "error": str(e)})
                    break

        if result is None:
            continue

        got = {s.category: s.flagged for s in result.scores}
        got_overall = result.overall_flagged

        category_mismatches = {}
        for cat in CATEGORIES:
            if got[cat] == expected[cat]:
                correct[cat] += 1
            else:
                incorrect[cat] += 1
                category_mismatches[cat] = {
                    "expected": expected[cat],
                    "got": got[cat],
                }
                if got[cat] and not expected[cat]:
                    false_positives[cat] += 1
                elif not got[cat] and expected[cat]:
                    false_negatives[cat] += 1

        overall_match = got_overall == expected_overall
        if overall_match:
            overall_correct += 1
        else:
            overall_incorrect += 1

        if category_mismatches or not overall_match:
            failures.append(
                {
                    "id": ex["id"],
                    "text": text,
                    "difficulty": ex.get("difficulty"),
                    "intended_category": ex.get("intended_category"),
                    "category_mismatches": category_mismatches,
                    "overall_expected": expected_overall,
                    "overall_got": got_overall,
                    "scores": {s.category: s.score for s in result.scores},
                    "label_scores": {cat: labels.get(cat) for cat in CATEGORIES},
                }
            )
            print("MISMATCH")
        else:
            print("OK")

        await asyncio.sleep(5)

    print_summary(
        correct,
        incorrect,
        false_positives,
        false_negatives,
        overall_correct,
        overall_incorrect,
        len(examples),
        len(skipped),
    )
    safe_model = model.replace("/", "_").replace(":", "_")
    if failures:
        save_failures(failures, out_path=f"eval_failures_{safe_model}.json")
    else:
        print("\nNo failures — eval passed cleanly.\n")


def print_summary(correct, incorrect, fp, fn, overall_correct, overall_incorrect, total, skipped):
    print("\n" + "=" * 70)
    print(f"  EVAL SUMMARY  —  {total} examples ({skipped} skipped)")
    print("=" * 70)
    print(f"{'Category':<18} {'Correct':>8} {'Wrong':>8} {'FP':>6} {'FN':>6} {'Acc':>8}")
    print("-" * 70)
    for cat in CATEGORIES:
        total_cat = correct[cat] + incorrect[cat]
        acc = correct[cat] / total_cat * 100 if total_cat else 0
        print(
            f"{cat:<18} {correct[cat]:>8} {incorrect[cat]:>8}"
            f" {fp[cat]:>6} {fn[cat]:>6} {acc:>7.1f}%"
        )
    print("-" * 70)
    total_overall = overall_correct + overall_incorrect
    acc_overall = overall_correct / total_overall * 100 if total_overall else 0
    print(
        f"{'overall_flagged':<18} {overall_correct:>8} {overall_incorrect:>8}"
        f" {'':>6} {'':>6} {acc_overall:>7.1f}%"
    )
    print("=" * 70)


def save_failures(failures, out_path="eval_failures.json"):
    full_path = Path(__file__).parent / out_path
    with open(full_path, "w") as f:
        json.dump(failures, f, indent=2)
    print(f"\n{len(failures)} failures saved to {out_path}\n")


if __name__ == "__main__":
    asyncio.run(run_eval("dataset.jsonl"))
