"""Build 20 ordered topic groups per book from the local Cambridge PDFs."""

from collections import Counter
from pathlib import Path
import json
import math
import re

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
BOOK_DIR = ROOT.parent
WORDS = json.loads((ROOT / "data" / "words.json").read_text(encoding="utf-8"))


def clean(text):
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def groups(reader, book):
    outline = [(str(item.get("/Title", "")).strip(), reader.get_destination_page_number(item))
               for item in reader.outline if not isinstance(item, list)]
    if book < 4:
        units = [(title, page) for title, page in outline if re.match(r"^\d+\s", title)]
        sections = []
        for i in range(20):
            first = i * len(units) // 20
            last = (i + 1) * len(units) // 20
            title = units[first][0].split(" ", 1)[1]
            if last - first > 1:
                title += " / " + units[last - 1][0].split(" ", 1)[1]
            end = units[last][1] if last < len(units) else units[-1][1] + 2
            sections.append((title, units[first][1], end))
        return sections
    sections = [(title.replace("\r", " ").strip(), page) for title, page in outline[6:20]]
    weighted = []
    for i, (title, page) in enumerate(sections):
        end = sections[i + 1][1] if i + 1 < len(sections) else outline[20][1]
        weighted.append((title, page, end))
    while len(weighted) < 20:
        i = max(range(len(weighted)), key=lambda j: weighted[j][2] - weighted[j][1])
        title, start, end = weighted[i]
        mid = (start + end) // 2
        weighted[i:i + 1] = [(title, start, mid), (title, mid, end)]
    return weighted


def main():
    result = {}
    for book in range(1, 5):
        reader = PdfReader(next(BOOK_DIR.glob(f"{book}_*.pdf")))
        sections = groups(reader, book)
        texts = []
        for _, first, last in sections:
            texts.append(" ".join(clean(reader.pages[p].extract_text() or "") for p in range(first, last)))
        entries = [w for w in WORDS if w["book"] == book]
        assignments = []
        for word in entries:
            term = clean(word["en"])
            expression = re.compile(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, term.split())) + r"(?![a-z0-9])") if term else None
            counts = [len(expression.findall(text)) if expression else 0 for text in texts]
            assignments.append(max(range(20), key=lambda i: counts[i]) if any(counts) else None)
        # Terms absent from extracted PDF text go into the least populated topic.
        population = Counter(i for i in assignments if i is not None)
        for index, topic in enumerate(assignments):
            if topic is None:
                chosen = min(range(20), key=lambda i: population[i])
                assignments[index] = chosen
                population[chosen] += 1
        result[str(book)] = {"titles": [x[0] for x in sections], "topics": assignments}
        print(book, len(entries), "topic range", min(population.values()), max(population.values()))
    (ROOT / "data" / "topics.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
