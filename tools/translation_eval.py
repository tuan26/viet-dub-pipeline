"""Benchmark a translation model/prompt on tests/data/translation_cases.json.

    python tools/translation_eval.py --base-url http://127.0.0.1:8089/v1 --model qwen \\
        --prompt strict --label qwen7b-strict --out results/
"""
import argparse, json, time
from pathlib import Path

from vietdub.engines.translate import PROMPTS, ChatConfig, translate
from vietdub.engines.translation_checks import check_line, summarize
from vietdub.models import Segment, VietdubError

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", required=True); ap.add_argument("--model", required=True)
ap.add_argument("--prompt", default="basic", choices=list(PROMPTS)); ap.add_argument("--temperature", type=float, default=0.3)
ap.add_argument("--label", required=True); ap.add_argument("--out", type=Path, default=Path("."))
ap.add_argument("--cases", type=Path, default=Path(__file__).parent.parent / "tests/data/translation_cases.json")
args = ap.parse_args()

chat = ChatConfig(args.base_url, args.model, None, args.temperature).chat
scenes = json.loads(args.cases.read_text(encoding="utf-8"))["scenes"]
results, started, failed_scenes = [], time.time(), 0
for scene in scenes:
    segs = [Segment(i, i, i + 1, line["text"]) for i, line in enumerate(scene["lines"], 1)]
    try:
        translate(segs, chat, scene["lang"], system=PROMPTS[args.prompt])
    except VietdubError as exc:
        failed_scenes += 1
        print("scene failed:", scene["id"], exc)
    for line, seg in zip(scene["lines"], segs):
        results.append({"scene": scene["id"], "cat": line["cat"], "source": line["text"],
                        "translation": seg.translation, "problems": check_line(line, seg.translation)})
summary = summarize(results) | {"label": args.label, "prompt": args.prompt, "temperature": args.temperature,
                                "seconds": round(time.time() - started, 1), "failed_scenes": failed_scenes}
args.out.mkdir(parents=True, exist_ok=True)
(args.out / f"{args.label}.json").write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
