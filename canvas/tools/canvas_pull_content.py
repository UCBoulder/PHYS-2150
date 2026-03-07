"""
Canvas Course Content Downloader
Pulls all content from a Canvas course into a local directory.

Content types: pages, assignments, files, modules, discussions,
announcements, quizzes, and syllabus.

Requires:
    pip install canvasapi
    Set CANVAS_TOKEN env var (and optionally CANVAS_DOMAIN).
    python canvas/tools/canvas_pull_content.py
"""

import os
import re
import json
import time
import requests
from getpass import getpass
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException, InvalidAccessToken, Unauthorized


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Make a string safe for use as a file/directory name."""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip('. ')
    if len(name) > max_length:
        name = name[:max_length].rstrip('. ')
    return name or "untitled"


def save_html(path: Path, title: str, body: str):
    """Save HTML content wrapped in a minimal page."""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
  img {{ max-width: 100%; }}
  pre {{ background: #f4f4f4; padding: 12px; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{title}</h1>
{body or '<p><em>(no content)</em></p>'}
</body>
</html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def save_json(path: Path, data):
    """Save data as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def download_file(url: str, dest: Path) -> bool:
    """Download a file from a URL to a local path."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Error downloading {dest.name}: {e}")
        return False


def pull_pages(course, out_dir: Path):
    """Download all wiki pages."""
    print("\n  Pages...")
    pages_dir = out_dir / "pages"
    try:
        pages = list(course.get_pages())
    except CanvasException:
        print("    Skipped (no access)")
        return

    if not pages:
        print("    None found")
        return

    count = 0
    for page in pages:
        try:
            full_page = course.get_page(page.url)
        except CanvasException:
            continue
        title = getattr(full_page, 'title', page.url)
        body = getattr(full_page, 'body', '') or ''
        filename = sanitize_filename(title) + ".html"
        save_html(pages_dir / filename, title, body)
        count += 1

    print(f"    {count} page(s) saved")


def pull_assignments(course, out_dir: Path):
    """Download all assignments."""
    print("  Assignments...")
    assign_dir = out_dir / "assignments"
    try:
        assignments = list(course.get_assignments())
    except CanvasException:
        print("    Skipped (no access)")
        return

    if not assignments:
        print("    None found")
        return

    count = 0
    for a in assignments:
        name = getattr(a, 'name', 'untitled')
        body = getattr(a, 'description', '') or ''
        meta = f"""<div class="meta">
<p><strong>Due:</strong> {getattr(a, 'due_at', 'N/A')}</p>
<p><strong>Points:</strong> {getattr(a, 'points_possible', 'N/A')}</p>
<p><strong>Type:</strong> {getattr(a, 'submission_types', [])}</p>
</div><hr>"""
        filename = sanitize_filename(name) + ".html"
        save_html(assign_dir / filename, name, meta + body)
        count += 1

    summary = [{"id": a.id, "name": getattr(a, 'name', None),
                "due_at": getattr(a, 'due_at', None),
                "points": getattr(a, 'points_possible', None)} for a in assignments]
    save_json(assign_dir / "_assignments.json", summary)
    print(f"    {count} assignment(s) saved")


def pull_files(course, out_dir: Path):
    """Download all course files, preserving folder structure."""
    print("  Files...")
    files_dir = out_dir / "files"

    try:
        folders = list(course.get_folders())
    except CanvasException:
        print("    Skipped (no access)")
        return

    folder_map = {}
    for f in folders:
        full_name = getattr(f, 'full_name', '')
        path = re.sub(r'^course files/?', '', full_name)
        folder_map[f.id] = path

    try:
        files = list(course.get_files())
    except CanvasException:
        print("    Skipped (no access)")
        return

    if not files:
        print("    None found")
        return

    count = 0
    errors = 0
    for file_obj in files:
        file_url = getattr(file_obj, 'url', None)
        if not file_url:
            continue
        folder_id = getattr(file_obj, 'folder_id', None)
        folder_path = folder_map.get(folder_id, "")
        filename = getattr(file_obj, 'display_name', None) or getattr(file_obj, 'filename', 'unknown')
        dest = files_dir / folder_path / filename

        if download_file(file_url, dest):
            count += 1
        else:
            errors += 1

    msg = f"    {count} file(s) downloaded"
    if errors:
        msg += f", {errors} error(s)"
    print(msg)


def pull_modules(course, out_dir: Path):
    """Download module structure and item details."""
    print("  Modules...")
    modules_dir = out_dir / "modules"
    try:
        modules = list(course.get_modules())
    except CanvasException:
        print("    Skipped (no access)")
        return

    if not modules:
        print("    None found")
        return

    all_modules = []
    for mod in modules:
        mod_name = getattr(mod, 'name', 'Untitled Module')
        try:
            items = list(mod.get_module_items())
        except CanvasException:
            items = []

        mod_data = {
            "id": mod.id,
            "name": mod_name,
            "position": getattr(mod, 'position', None),
            "state": getattr(mod, 'state', None),
            "items": [{"id": getattr(it, 'id', None),
                        "title": getattr(it, 'title', None),
                        "type": getattr(it, 'type', None),
                        "url": getattr(it, 'html_url', None),
                        "position": getattr(it, 'position', None)}
                       for it in items]
        }
        all_modules.append(mod_data)

    save_json(modules_dir / "modules.json", all_modules)

    items_html = ""
    for mod in all_modules:
        items_html += f"<h2>{mod['name']}</h2>\n<ol>\n"
        for item in mod["items"]:
            link = f' <a href="{item["url"]}">[link]</a>' if item.get("url") else ""
            items_html += f"  <li><strong>[{item['type']}]</strong> {item['title']}{link}</li>\n"
        items_html += "</ol>\n"

    save_html(modules_dir / "modules.html", "Modules", items_html)
    print(f"    {len(all_modules)} module(s) saved")


def pull_discussions(course, out_dir: Path):
    """Download discussion topics. Returns announcements found."""
    print("  Discussions...")
    disc_dir = out_dir / "discussions"
    try:
        topics = list(course.get_discussion_topics())
    except CanvasException:
        print("    Skipped (no access)")
        return None

    discussions = [t for t in topics if not getattr(t, 'is_announcement', False)]
    announcements = [t for t in topics if getattr(t, 'is_announcement', False)]

    if not discussions:
        print("    None found")
    else:
        for t in discussions:
            title = getattr(t, 'title', 'untitled')
            body = getattr(t, 'message', '') or ''
            posted = getattr(t, 'posted_at', 'N/A')
            meta = f"<p><em>Posted: {posted}</em></p><hr>"
            filename = sanitize_filename(title) + ".html"
            save_html(disc_dir / filename, title, meta + body)
        print(f"    {len(discussions)} discussion(s) saved")

    return announcements


def pull_announcements(course, out_dir: Path, from_discussions=None):
    """Download announcements."""
    print("  Announcements...")
    ann_dir = out_dir / "announcements"

    announcements = from_discussions or []
    if not from_discussions:
        try:
            announcements = list(course.get_discussion_topics(only_announcements=True))
        except CanvasException:
            print("    Skipped (no access)")
            return

    if not announcements:
        print("    None found")
        return

    for a in announcements:
        title = getattr(a, 'title', 'untitled')
        body = getattr(a, 'message', '') or ''
        date = getattr(a, 'posted_at', '') or ''
        date_prefix = str(date)[:10] + " - " if date else ""
        filename = sanitize_filename(date_prefix + title) + ".html"
        meta = f"<p><em>Posted: {date or 'N/A'}</em></p><hr>"
        save_html(ann_dir / filename, title, meta + body)

    print(f"    {len(announcements)} announcement(s) saved")


def pull_quizzes(course, out_dir: Path):
    """Download quiz info (questions require separate permissions)."""
    print("  Quizzes...")
    quiz_dir = out_dir / "quizzes"
    try:
        quizzes = list(course.get_quizzes())
    except CanvasException:
        print("    Skipped (no access)")
        return

    if not quizzes:
        print("    None found")
        return

    for q in quizzes:
        title = getattr(q, 'title', 'untitled')
        desc = getattr(q, 'description', '') or ''
        meta = f"""<div class="meta">
<p><strong>Points:</strong> {getattr(q, 'points_possible', 'N/A')}</p>
<p><strong>Time Limit:</strong> {getattr(q, 'time_limit', 'None')} min</p>
<p><strong>Allowed Attempts:</strong> {getattr(q, 'allowed_attempts', 'N/A')}</p>
<p><strong>Due:</strong> {getattr(q, 'due_at', 'N/A')}</p>
<p><strong>Quiz Type:</strong> {getattr(q, 'quiz_type', 'N/A')}</p>
</div><hr>"""
        filename = sanitize_filename(title) + ".html"
        save_html(quiz_dir / filename, title, meta + desc)

        try:
            questions = list(q.get_questions())
            if questions:
                q_html = ""
                for i, qn in enumerate(questions, 1):
                    q_html += f"<h3>Q{i}: {getattr(qn, 'question_name', '')}</h3>\n"
                    q_html += (getattr(qn, 'question_text', '') or '') + "\n"
                    answers = getattr(qn, 'answers', [])
                    if answers:
                        q_html += "<ul>\n"
                        for ans in answers:
                            text = ans.get('text', '') or ans.get('html', '')
                            q_html += f"  <li>{text}</li>\n"
                        q_html += "</ul>\n"
                qname = sanitize_filename(title) + "_questions.html"
                save_html(quiz_dir / qname, f"{title} - Questions", q_html)
        except CanvasException:
            pass  # questions not accessible

    print(f"    {len(quizzes)} quiz(zes) saved")


def pull_syllabus(canvas, course_id: int, out_dir: Path):
    """Download the course syllabus."""
    print("  Syllabus...")
    try:
        course_with_syllabus = canvas.get_course(course_id, include=["syllabus_body"])
    except CanvasException:
        print("    Skipped (no access)")
        return

    body = getattr(course_with_syllabus, 'syllabus_body', '')
    if body:
        save_html(out_dir / "syllabus.html", "Syllabus", body)
        print("    Saved")
    else:
        print("    No syllabus content")


def display_courses(courses: list):
    print(f"\n{'#':<4} {'ID':<10} {'Code':<20} {'Name'}")
    print("-" * 70)
    for i, course in enumerate(courses, 1):
        code = getattr(course, 'course_code', 'N/A')[:18]
        name = getattr(course, 'name', 'N/A')[:35]
        print(f"{i:<4} {course.id:<10} {code:<20} {name}")


def select_item(items: list, prompt: str):
    while True:
        try:
            choice = input(prompt).strip()
            if choice.lower() == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(f"Please enter a number between 1 and {len(items)}")
        except ValueError:
            print("Please enter a valid number")


def main():
    domain = os.environ.get("CANVAS_DOMAIN", "canvas.colorado.edu")
    token = os.environ.get("CANVAS_TOKEN")

    if not token:
        token = getpass("Enter your Canvas API token: ")

    canvas = Canvas(f"https://{domain}", token)

    try:
        print("\nFetching your courses...")
        courses = list(canvas.get_courses(enrollment_type="teacher"))

        if not courses:
            print("No courses found. Trying all enrollments...")
            courses = list(canvas.get_courses())

        if not courses:
            print("No courses found.")
            return

        display_courses(courses)
        course = select_item(courses, "\nSelect course number (or 'q' to quit): ")
        if not course:
            return

        course_name = sanitize_filename(
            getattr(course, 'course_code', '') or getattr(course, 'name', str(course.id)))

        out_dir = Path("course_content") / course_name
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nDownloading content for: {course.name}")
        print(f"Output directory: {out_dir.resolve()}\n")

        start = time.time()

        term = getattr(course, 'term', None)
        if isinstance(term, dict):
            term_name = term.get('name')
        elif term:
            term_name = getattr(term, 'name', None)
        else:
            term_name = None

        save_json(out_dir / "course_info.json", {
            "id": course.id,
            "name": getattr(course, 'name', None),
            "code": getattr(course, 'course_code', None),
            "term": term_name,
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        pull_syllabus(canvas, course.id, out_dir)
        pull_pages(course, out_dir)
        pull_assignments(course, out_dir)
        pull_modules(course, out_dir)
        announcements = pull_discussions(course, out_dir)
        pull_announcements(course, out_dir, from_discussions=announcements)
        pull_quizzes(course, out_dir)
        pull_files(course, out_dir)

        elapsed = time.time() - start
        print(f"\nDone in {elapsed:.1f}s. Content saved to: {out_dir.resolve()}")

    except (InvalidAccessToken, Unauthorized):
        print("Error: Invalid or expired token.")
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except CanvasException as e:
        print(f"Canvas API Error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
