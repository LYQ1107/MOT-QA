"""Read the unchanged canonical TOC-Bench release."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_bench(path=ROOT / 'data/toc_bench/answer_final.json'):
    return json.loads(Path(path).read_text())['items']
