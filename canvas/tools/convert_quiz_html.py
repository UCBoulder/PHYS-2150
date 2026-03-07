"""Convert pulled Canvas quiz HTML files into YAML quiz definitions.

Reads the *_questions.html files from course_content/ and writes
structured YAML to canvas/config/quizzes/.

Usage:
    python canvas/tools/convert_quiz_html.py
"""

import re
from pathlib import Path

import yaml


QUIZ_DIR = Path(__file__).resolve().parents[2] / "course_content" / "PHYS 2150 - SP26" / "quizzes"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "config" / "quizzes"


def parse_question_html(html: str) -> list[dict]:
    """Parse a _questions.html file into a list of question dicts."""
    # Strip HTML boilerplate
    body_match = re.search(r"<body>(.*)</body>", html, re.DOTALL)
    if not body_match:
        return []
    body = body_match.group(1)

    # Remove DesignPLUS CSS/JS link tags
    body = re.sub(r'<link rel="stylesheet"[^>]*>', "", body)
    body = re.sub(r'<script[^>]*>[^<]*</script>', "", body)

    # Split on question headers
    parts = re.split(r"<h3>Q\d+:\s*Question</h3>", body)

    questions = []
    for part in parts[1:]:  # Skip everything before Q1
        part = part.strip()
        if not part:
            continue

        # Check for answer options (<ul> with <li> items)
        ul_match = re.search(r"<ul>(.*?)</ul>", part, re.DOTALL)
        answers = []
        if ul_match:
            answers = re.findall(r"<li>(.*?)</li>", ul_match.group(1))
            # Remove the <ul> from the question text
            question_text = part[:ul_match.start()].strip()
        else:
            question_text = part.strip()

        # Clean up question text HTML
        question_text = _clean_html(question_text)

        if not question_text:
            continue

        q = {"text": question_text}
        if answers:
            q["type"] = "multiple_choice"
            q["answers"] = [a.strip() for a in answers]
        else:
            # Tentatively mark as essay; we'll fix headers in a second pass
            q["type"] = "essay"

        questions.append(q)

    # Second pass: mark essay questions that are immediately followed by
    # multiple_choice questions as text_only (they're Likert intro/headers).
    for i, q in enumerate(questions):
        if q["type"] == "essay" and i + 1 < len(questions):
            if questions[i + 1]["type"] == "multiple_choice":
                q["type"] = "text_only"

    return questions


def parse_quiz_metadata(html: str) -> dict:
    """Parse a quiz metadata HTML file for the description body."""
    body_match = re.search(r"<body>(.*)</body>", html, re.DOTALL)
    if not body_match:
        return {}

    body = body_match.group(1)

    # Extract the content after the <hr> (quiz description body)
    hr_match = re.search(r"<hr>(.*)", body, re.DOTALL)
    if not hr_match:
        return {}

    desc = hr_match.group(1).strip()
    # Remove DesignPLUS wrapper but keep inner content
    desc = re.sub(r'<link rel="stylesheet"[^>]*>', "", desc)
    desc = re.sub(r'<script[^>]*>[^<]*</script>', "", desc)
    # Remove DesignPLUS banner wrapper, keep the description text
    desc = re.sub(r'<div id="kl_wrapper_3"[^>]*>.*?</div>\s*', "", desc, flags=re.DOTALL)

    desc = _clean_html(desc)
    return {"description": desc} if desc else {}


def _clean_html(text: str) -> str:
    """Clean HTML to plain text, preserving meaningful content."""
    # Remove wrapping tags but keep content
    text = re.sub(r"</?(?:span|div|p|em|br)\s*/?>", " ", text)
    text = re.sub(r"<br\s*/?>", " ", text)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Clean HTML entities
    text = text.replace("&nbsp;", " ").replace("&mdash;", "—")
    text = text.replace("&ndash;", "–").replace("&rsquo;", "'")
    text = text.replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def convert_all():
    """Convert all quiz HTML files to YAML."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    question_files = sorted(QUIZ_DIR.glob("*_questions.html"))
    print(f"Found {len(question_files)} quiz question files")

    for qfile in question_files:
        quiz_name = qfile.stem.replace("_questions", "")
        # Corresponding metadata file
        meta_file = qfile.parent / f"{quiz_name}.html"

        questions = parse_question_html(qfile.read_text(encoding="utf-8"))

        metadata = {}
        if meta_file.exists():
            metadata = parse_quiz_metadata(meta_file.read_text(encoding="utf-8"))

        # Build YAML structure
        data = {}
        if metadata.get("description"):
            data["description"] = metadata["description"]
        data["questions"] = questions

        # Output filename: sanitize
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", quiz_name).strip("_")
        safe_name = re.sub(r"_+", "_", safe_name)
        out_path = OUTPUT_DIR / f"{safe_name}.yaml"

        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)

        print(f"  {quiz_name} -> {out_path.name} ({len(questions)} questions)")


if __name__ == "__main__":
    convert_all()
