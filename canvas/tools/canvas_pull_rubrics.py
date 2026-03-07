"""
Canvas Rubric Puller for PHYS 1140

One-time script that fetches rubrics from Canvas lab notebook assignments
and prints them in the compact YAML format used by course_config.yaml.

The rubrics typically live on the production course, not the sandbox.
Use --course-id to specify the source course.

Usage:
    cd canvas
    python tools/canvas_pull_rubrics.py --course-id 12345

Requires:
    pip install canvasapi pyyaml
    Set CANVAS_TOKEN env var (and optionally CANVAS_DOMAIN).
"""

import argparse
import os
import re
import sys
from getpass import getpass
from pathlib import Path

import yaml
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException, InvalidAccessToken, Unauthorized


def load_config():
    """Load course_config.yaml and return (config, path)."""
    config_path = Path(__file__).resolve().parent.parent / "config" / "course_config.yaml"
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f), config_path


def connect_canvas(config, course_id_override=None):
    """Connect to Canvas and return (canvas, course) objects.

    Args:
        config: Parsed course_config.yaml.
        course_id_override: If set, use this course ID instead of config.
    """
    domain = os.environ.get("CANVAS_DOMAIN", config["canvas"]["domain"])
    token = os.environ.get("CANVAS_TOKEN")
    if not token:
        token = getpass("Enter your Canvas API token: ")

    canvas = Canvas(f"https://{domain}", token)
    course_id = course_id_override or config["canvas"]["course_id"]

    try:
        course = canvas.get_course(course_id)
        print(f"Connected to: {getattr(course, 'name', course_id)} (id={course_id})")
    except (InvalidAccessToken, Unauthorized) as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
    except CanvasException as e:
        print(f"Could not access course {course_id}: {e}")
        sys.exit(1)

    return canvas, course


def fetch_rubrics(course):
    """Fetch all rubrics for the course, keyed by rubric ID."""
    rubrics = {}
    try:
        for r in course.get_rubrics():
            rubrics[r.id] = r
    except CanvasException as e:
        print(f"Warning: Could not fetch rubrics: {e}")
    return rubrics


def fetch_assignments(course):
    """Fetch all assignments, keyed by name."""
    assignments = {}
    try:
        for a in course.get_assignments():
            name = getattr(a, "name", "").strip()
            assignments[name] = a
    except CanvasException as e:
        print(f"Warning: Could not fetch assignments: {e}")
    return assignments


def rubric_to_yaml(rubric_data):
    """Convert a Canvas rubric data list to the compact YAML format.

    Each criterion in rubric_data has:
      - description (str): criterion name
      - points (float): max points
      - ratings (list of dicts): each with description, long_description, points

    Returns a list of dicts in the compact format.
    """
    criteria = []
    for criterion in rubric_data:
        desc = criterion.get("description", "")
        points = int(criterion.get("points", 0))
        ratings = criterion.get("ratings", [])

        # Sort ratings by points descending (highest = full, lowest = none)
        ratings_sorted = sorted(ratings, key=lambda r: r.get("points", 0), reverse=True)

        entry = {"criterion": desc, "points": points}

        if points == 3 and len(ratings_sorted) >= 4:
            entry["full"] = ratings_sorted[0].get("long_description", "")
            entry["partial"] = ratings_sorted[1].get("long_description", "")
            entry["limited"] = ratings_sorted[2].get("long_description", "")
            entry["none"] = ratings_sorted[3].get("long_description", "")
        elif points == 2 and len(ratings_sorted) >= 3:
            entry["full"] = ratings_sorted[0].get("long_description", "")
            entry["partial"] = ratings_sorted[1].get("long_description", "")
            entry["none"] = ratings_sorted[2].get("long_description", "")
        elif len(ratings_sorted) >= 2:
            # Generic: map by position
            level_names = ["full", "partial", "limited", "none"]
            for i, rating in enumerate(ratings_sorted):
                if i < len(level_names):
                    entry[level_names[i]] = rating.get("long_description", "")
        elif len(ratings_sorted) == 1:
            entry["full"] = ratings_sorted[0].get("long_description", "")

        criteria.append(entry)

    return criteria


def find_notebook_assignment(lab_number, assignments):
    """Find the notebook assignment for a lab by number, using fuzzy matching.

    Tries exact config name first, then falls back to regex matching on
    'Lab N:' pattern (skipping attendance assignments).
    """
    pattern = re.compile(rf'^Lab\s*0?{lab_number}\b', re.IGNORECASE)
    skip = re.compile(r'attendance|prelab', re.IGNORECASE)
    for name, a in assignments.items():
        if pattern.search(name) and not skip.search(name):
            return name, a
    return None, None


def format_rubric_yaml(criteria):
    """Format a rubric criteria list as indented YAML for insertion into config.

    Returns a string like:
        rubric:
          - criterion: "Name"
            points: 3
            full: "..."
    """
    rubric_yaml = yaml.dump(
        criteria,
        default_flow_style=False,
        allow_unicode=True,
        width=120,
        sort_keys=False,
    )
    lines = rubric_yaml.strip().split("\n")
    indented = ["    rubric:"]
    for line in lines:
        indented.append(f"      {line}")
    return "\n".join(indented)


def write_rubrics_to_config(results, config_path):
    """Insert rubric YAML blocks into course_config.yaml.

    Uses text-level insertion after each lab's attendance_points line
    to preserve existing comments and formatting.
    """
    text = config_path.read_text(encoding="utf-8")

    for lab_number, criteria in sorted(results.items()):
        rubric_block = format_rubric_yaml(criteria)

        # Remove any existing rubric block for this lab
        # Match from "    rubric:\n" up to the next lab entry or section
        pattern = re.compile(
            rf'(    attendance_points: \d+)\n'
            rf'    rubric:\n'
            rf'((?:      .+\n)*)'
            rf'(\n  - number: {lab_number + 1}\b|\n# ---)',
        )
        text = pattern.sub(rf'\1\n\3', text)

        # Insert rubric block after attendance_points for this lab
        # Find the lab entry by its number and locate its attendance_points line
        lab_pattern = re.compile(
            rf'(  - number: {lab_number}\n'
            rf'(?:    .+\n)*?'
            rf'    attendance_points: \d+)\n',
        )
        match = lab_pattern.search(text)
        if match:
            insert_pos = match.end()
            text = text[:insert_pos] + rubric_block + "\n" + text[insert_pos:]
            print(f"  Inserted rubric for Lab {lab_number}")
        else:
            print(f"  WARNING: Could not find Lab {lab_number} entry in config")

    config_path.write_text(text, encoding="utf-8")
    print(f"\nWrote rubrics to {config_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pull rubrics from Canvas and output compact YAML.",
    )
    parser.add_argument(
        "--course-id", type=int, default=None,
        help="Canvas course ID to pull rubrics from (default: from config)",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Write rubric data directly into course_config.yaml",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print all assignment names from the source course",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config, config_path = load_config()
    canvas, course = connect_canvas(config, course_id_override=args.course_id)

    print("\nFetching rubrics...")
    rubrics = fetch_rubrics(course)
    print(f"  Found {len(rubrics)} rubric(s)")

    print("Fetching assignments...")
    assignments = fetch_assignments(course)
    print(f"  Found {len(assignments)} assignment(s)")

    if args.verbose:
        print("\n  All assignments in course:")
        for name in sorted(assignments.keys()):
            print(f"    - {name}")
        print()

    # Build lab number -> config lookup
    labs_by_number = {lab["number"]: lab for lab in config.get("labs", [])}

    # Match notebook assignments to rubrics
    results = {}
    for lab in config.get("labs", []):
        n = lab["number"]

        # Try exact config name, then fuzzy match by lab number
        notebook_name = f"Lab {n}: {lab['notebook_title']}"
        assignment = assignments.get(notebook_name)
        if not assignment:
            matched_name, assignment = find_notebook_assignment(n, assignments)
            if assignment:
                print(f"  Lab {n}: matched '{matched_name}'")
                notebook_name = matched_name

        if not assignment:
            print(f"  Lab {n}: notebook assignment not found")
            # Fall through to rubric title matching below

        # Try to find rubric data from multiple sources
        found = False

        # Source 1: rubric attribute directly on the assignment
        if assignment:
            rubric_data = getattr(assignment, "rubric", None)
            if rubric_data:
                results[n] = rubric_to_yaml(rubric_data)
                print(f"  Lab {n}: {len(rubric_data)} criteria (from assignment.rubric)")
                found = True

        # Source 2: rubric_settings -> rubric ID lookup
        if not found and assignment:
            rubric_settings = getattr(assignment, "rubric_settings", None)
            if rubric_settings and isinstance(rubric_settings, dict):
                rubric_id = rubric_settings.get("id")
                if rubric_id and rubric_id in rubrics:
                    r = rubrics[rubric_id]
                    r_data = getattr(r, "data", [])
                    if r_data:
                        results[n] = rubric_to_yaml(r_data)
                        print(f"  Lab {n}: {len(r_data)} criteria (from rubric {rubric_id})")
                        found = True

        # Source 3: match rubric by title (works even without assignment)
        if not found:
            lab_pattern = re.compile(rf'\bLab\s*0?{n}\b', re.IGNORECASE)
            for rid, r in rubrics.items():
                title = getattr(r, "title", "")
                if lab_pattern.search(title):
                    r_data = getattr(r, "data", [])
                    if r_data:
                        results[n] = rubric_to_yaml(r_data)
                        print(f"  Lab {n}: {len(r_data)} criteria (matched rubric title: {title})")
                        found = True
                        break

        if not found:
            print(f"  Lab {n}: no rubric found")

    if not results:
        print("\nNo rubrics found to export.")
        return

    if args.write:
        print(f"\nWriting rubrics to {config_path}...")
        write_rubrics_to_config(results, config_path)
    else:
        # Print YAML output to stdout
        print("\n" + "=" * 60)
        print("YAML rubric data — paste under each lab entry in course_config.yaml")
        print("(or re-run with --write to insert automatically)")
        print("=" * 60)

        for n in sorted(results.keys()):
            lab = labs_by_number[n]
            print(f"\n  # Lab {n}: {lab['title']}")
            print(format_rubric_yaml(results[n]))

    print(f"\nExported rubrics for {len(results)} lab(s).")


if __name__ == "__main__":
    main()
