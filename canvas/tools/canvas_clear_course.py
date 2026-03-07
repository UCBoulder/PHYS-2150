"""
Canvas Course Content Clearer

Removes all content from a Canvas course: assignments, pages, assignment groups,
modules, discussion topics, and files. Useful for resetting a sandbox course
before testing canvas_setup_course.py.

WARNING: This is destructive and irreversible. Use only on sandbox/test courses.

Requires:
    pip install canvasapi
    Set CANVAS_TOKEN env var (and optionally CANVAS_DOMAIN).

Usage:
    python canvas/tools/canvas_clear_course.py
    python canvas/tools/canvas_clear_course.py --course-id 86214
    python canvas/tools/canvas_clear_course.py --dry-run
"""

import argparse
import os
import sys
import time
from getpass import getpass

from canvasapi import Canvas
from canvasapi.exceptions import (
    CanvasException,
    InvalidAccessToken,
    Unauthorized,
)


def clear_assignments(course, dry_run: bool = False) -> int:
    """Delete all assignments."""
    print("\n  Assignments...")
    try:
        assignments = list(course.get_assignments())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not assignments:
        print("    None found")
        return 0

    count = 0
    for a in assignments:
        name = getattr(a, "name", "untitled")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {name}")
        else:
            try:
                a.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{name}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(assignments)} assignment(s)")
    return count


def clear_pages(course, dry_run: bool = False) -> int:
    """Delete all wiki pages (except the front page, which Canvas protects)."""
    print("  Pages...")
    try:
        pages = list(course.get_pages())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not pages:
        print("    None found")
        return 0

    count = 0
    for page in pages:
        title = getattr(page, "title", "untitled")
        is_front = getattr(page, "front_page", False)
        if is_front:
            # Canvas won't let us delete the front page, so blank it out
            if dry_run:
                print(f"    [DRY RUN] Would clear front page: {title}")
            else:
                try:
                    page.edit(wiki_page={"body": "<p>&nbsp;</p>"})
                    print(f"    Cleared front page content: {title}")
                except CanvasException as e:
                    print(f"    Error clearing front page '{title}': {e}")
            count += 1
            continue
        if dry_run:
            print(f"    [DRY RUN] Would delete: {title}")
        else:
            try:
                page.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{title}': {e}")

    print(f"    {'Would process' if dry_run else 'Processed'} {len(pages)} page(s)")
    return count


def clear_assignment_groups(course, dry_run: bool = False) -> int:
    """Delete all assignment groups (Canvas recreates a default 'Assignments' group)."""
    print("  Assignment Groups...")
    try:
        groups = list(course.get_assignment_groups())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not groups:
        print("    None found")
        return 0

    count = 0
    for group in groups:
        name = getattr(group, "name", "untitled")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {name}")
        else:
            try:
                group.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{name}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(groups)} group(s)")
    return count


def clear_modules(course, dry_run: bool = False) -> int:
    """Delete all modules."""
    print("  Modules...")
    try:
        modules = list(course.get_modules())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not modules:
        print("    None found")
        return 0

    count = 0
    for mod in modules:
        name = getattr(mod, "name", "untitled")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {name}")
        else:
            try:
                mod.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{name}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(modules)} module(s)")
    return count


def clear_discussions(course, dry_run: bool = False) -> int:
    """Delete all discussion topics (including announcements)."""
    print("  Discussion Topics...")
    try:
        topics = list(course.get_discussion_topics())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not topics:
        print("    None found")
        return 0

    count = 0
    for topic in topics:
        title = getattr(topic, "title", "untitled")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {title}")
        else:
            try:
                topic.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{title}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(topics)} topic(s)")
    return count


def clear_files(course, dry_run: bool = False) -> int:
    """Delete all course files."""
    print("  Files...")
    try:
        files = list(course.get_files())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not files:
        print("    None found")
        return 0

    count = 0
    for f in files:
        name = getattr(f, "display_name", None) or getattr(f, "filename", "unknown")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {name}")
        else:
            try:
                f.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{name}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(files)} file(s)")
    return count


def clear_quizzes(course, dry_run: bool = False) -> int:
    """Delete all quizzes."""
    print("  Quizzes...")
    try:
        quizzes = list(course.get_quizzes())
    except CanvasException:
        print("    Skipped (no access)")
        return 0

    if not quizzes:
        print("    None found")
        return 0

    count = 0
    for q in quizzes:
        title = getattr(q, "title", "untitled")
        if dry_run:
            print(f"    [DRY RUN] Would delete: {title}")
        else:
            try:
                q.delete()
                count += 1
            except CanvasException as e:
                print(f"    Error deleting '{title}': {e}")

    print(f"    {'Would delete' if dry_run else 'Deleted'} {len(quizzes)} quiz(zes)")
    return count


def display_courses(courses: list):
    print(f"\n{'#':<4} {'ID':<10} {'Code':<20} {'Name'}")
    print("-" * 70)
    for i, course in enumerate(courses, 1):
        code = getattr(course, "course_code", "N/A")[:18]
        name = getattr(course, "name", "N/A")[:35]
        print(f"{i:<4} {course.id:<10} {code:<20} {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear all content from a Canvas course.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "WARNING: This is destructive and irreversible!\n"
            "Use only on sandbox/test courses.\n\n"
            "Examples:\n"
            "  python canvas_clear_course.py --dry-run\n"
            "  python canvas_clear_course.py --course-id 86214\n"
            "  python canvas_clear_course.py --course-id 86214 --dry-run\n"
        ),
    )
    parser.add_argument(
        "--course-id", type=int, default=None,
        help="Canvas course ID to clear (skips interactive selection)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be deleted without making changes",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    domain = os.environ.get("CANVAS_DOMAIN", "canvas.colorado.edu")
    token = os.environ.get("CANVAS_TOKEN")

    if not token:
        token = getpass("Enter your Canvas API token: ")

    canvas = Canvas(f"https://{domain}", token)

    try:
        if args.course_id:
            course = canvas.get_course(args.course_id)
        else:
            print("\nFetching your courses...")
            courses = list(canvas.get_courses(enrollment_type="teacher"))

            if not courses:
                print("No courses found. Trying all enrollments...")
                courses = list(canvas.get_courses())

            if not courses:
                print("No courses found.")
                return

            display_courses(courses)

            while True:
                try:
                    choice = input("\nSelect course number (or 'q' to quit): ").strip()
                    if choice.lower() == "q":
                        return
                    idx = int(choice) - 1
                    if 0 <= idx < len(courses):
                        course = courses[idx]
                        break
                    print(f"Please enter a number between 1 and {len(courses)}")
                except ValueError:
                    print("Please enter a valid number")

        course_name = getattr(course, "name", str(course.id))
        course_id = str(course.id)
        print(f"\nSelected course: {course_name} (ID: {course_id})")

        if args.dry_run:
            print("\n" + "=" * 50)
            print("  DRY RUN — no changes will be made")
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("  WARNING: This will DELETE all content from:")
            print(f"    {course_name} (ID: {course_id})")
            print("  This action is IRREVERSIBLE!")
            print("=" * 50)

            confirm = input(
                f"\nType the course ID ({course_id}) or name to confirm: "
            ).strip()
            if confirm != course_id and confirm != course_name:
                print("Confirmation does not match. Aborting.")
                return

        start = time.time()

        print("\nClearing course content...")

        # Delete assignments first (before groups, since groups may contain them)
        clear_assignments(course, args.dry_run)
        clear_quizzes(course, args.dry_run)
        clear_modules(course, args.dry_run)
        clear_pages(course, args.dry_run)
        clear_discussions(course, args.dry_run)
        clear_files(course, args.dry_run)
        # Delete assignment groups last (after assignments are gone)
        clear_assignment_groups(course, args.dry_run)

        elapsed = time.time() - start
        action = "Dry run completed" if args.dry_run else "Course cleared"
        print(f"\n{action} in {elapsed:.1f}s.")

    except (InvalidAccessToken, Unauthorized):
        print("Error: Invalid or expired token.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except CanvasException as e:
        print(f"Canvas API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
