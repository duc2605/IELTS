"""Build one stage per book unit from the local Cambridge PDFs."""

from collections import Counter
from pathlib import Path
import json
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
        return [(title, page, units[i + 1][1] if i + 1 < len(units) else page + 2)
                for i, (title, page) in enumerate(units)]
    categories = [(title.replace("\r", " ").strip(), page) for title, page in outline[6:20]]
    last_page = outline[20][1]
    units = []
    for number, page in enumerate(range(categories[0][1], last_page, 2), 1):
        category = max((title for title, start in categories if start <= page),
                       key=lambda title: next(start for name, start in categories if name == title))
        units.append((f"{number} {category}", page, min(page + 2, last_page)))
    return units


def main():
    result = {}
    for book in range(1, 5):
        reader = PdfReader(next(BOOK_DIR.glob(f"{book}_*.pdf")))
        sections = groups(reader, book)
        entries = [w for w in WORDS if w["book"] == book]
        terms = {clean(word["en"]) for word in entries}
        lengths = {len(term.split()) for term in terms if term}
        occurrences = {term: Counter() for term in terms}
        for unit, (_, first, last) in enumerate(sections):
            tokens = " ".join(clean(reader.pages[p].extract_text() or "") for p in range(first, last)).split()
            for length in lengths:
                for pos in range(len(tokens) - length + 1):
                    term = " ".join(tokens[pos:pos + length])
                    if term in occurrences:
                        occurrences[term][unit] += 1
        assignments = [occurrences[clean(word["en"])].most_common(1)[0][0]
                       if occurrences[clean(word["en"])] else None for word in entries]
        # Terms absent from extracted PDF text go into the least populated topic.
        population = Counter(i for i in assignments if i is not None)
        for index, topic in enumerate(assignments):
            if topic is None:
                chosen = min(range(len(sections)), key=lambda i: population[i])
                assignments[index] = chosen
                population[chosen] += 1
        result[str(book)] = {"titles": [x[0] for x in sections], "topics": assignments}
        print(book, len(entries), "topic range", min(population.values()), max(population.values()))
    (ROOT / "data" / "topics.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
