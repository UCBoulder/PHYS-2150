"""
Canvas Course Setup Automation for PHYS 2150

Reads config/course_config.yaml and creates/updates all Canvas course structure:
assignment groups, assignments, quizzes, styled wiki pages, and per-section
due date overrides.

Uses a pages-only architecture (no modules): a styled homepage links to
per-week pages, each of which is a self-contained hub with checklist
and direct assignment links.

Usage:
    python canvas_setup_course.py --dry-run --all
    python canvas_setup_course.py --groups --assignments
    python canvas_setup_course.py --pages
    python canvas_setup_course.py --navigation

Requires:
    pip install -r requirements.txt
    Set CANVAS_TOKEN env var (and optionally CANVAS_DOMAIN).
"""

import argparse
import csv
import functools
import logging
import os
import re
import sys
import time
from getpass import getpass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests as http_requests
import yaml
from canvasapi import Canvas
from canvasapi.exceptions import (
    CanvasException,
    InvalidAccessToken,
    Unauthorized,
)

DAY_NAMES_TO_NUM = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2,
    "Thursday": 3, "Friday": 4,
}


def _load_csv_data(config: dict, config_dir: Path):
    """Load TA and section data from CSV files into config dict."""
    sections_path = config_dir / "sections.csv"
    tas_path = config_dir / "tas.csv"

    if sections_path.exists():
        sections = []
        with open(sections_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sections.append({
                    "name": row["name"],
                    "day": DAY_NAMES_TO_NUM[row["day"]],
                    "hour": int(row["hour"]),
                })
        config["sections"] = sections
        log.info(f"  Loaded {len(sections)} sections from {sections_path.name}")
    elif "sections" not in config:
        log.warning("  No sections found in CSV or YAML")

    if tas_path.exists():
        tas = []
        with open(tas_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sections = [
                    row[col].strip()
                    for col in ("section1", "section2", "section3")
                    if col in row and row[col].strip()
                ]
                tas.append({
                    "name": f"{row['first_name']} {row['last_name']}",
                    "email": row["email"],
                    "sections": sections,
                })
        config["tas"] = tas
        log.info(f"  Loaded {len(tas)} TAs from {tas_path.name}")
    elif "tas" not in config:
        log.warning("  No TAs found in CSV or YAML")


from html_templates import (
    generate_assignment_description,
    generate_contact_page,
    generate_feedback_page,
    generate_help_sessions_page,
    generate_homepage,
    generate_other_resources_page,
    generate_report_issue_page,
    generate_schedule_page,
    generate_sections_page,
    generate_syllabus_page,
    generate_syllabus_redirect,
    generate_week_page,
    generate_weeks_12_16_page,
)

log = logging.getLogger("canvas_setup")


# ===================================================================
# Rate limit handling
# ===================================================================

def with_retry(max_retries: int = 5, base_delay: float = 2.0):
    """Decorator for Canvas API calls with exponential backoff on rate limits."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except CanvasException as e:
                    err_str = str(e).lower()
                    if "rate limit" in err_str or "403" in err_str:
                        delay = base_delay * (2 ** attempt)
                        log.warning(
                            f"Rate limited, waiting {delay:.0f}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                    else:
                        raise
            raise CanvasException(
                f"Max retries ({max_retries}) exceeded for rate limiting"
            )
        return wrapper
    return decorator


# ===================================================================
# CourseSetup class
# ===================================================================

class CourseSetup:
    """Encapsulates all Canvas course setup operations.

    All operations are idempotent: they check for existing objects by name
    before creating new ones, and update existing objects if found.
    """

    def __init__(self, config: dict, course, dry_run: bool = False,
                 token: str = ""):
        self.config = config
        self.course = course
        self.dry_run = dry_run
        self.token = token
        self.course_url = (
            f"https://{config['canvas']['domain']}/courses/{course.id}"
        )
        self.api_base = f"https://{config['canvas']['domain']}/api/v1"
        self.tz = ZoneInfo(config["term"]["timezone"])

        self._pages_cache = None
        self._assignments_cache = None
        self._groups_cache = None
        self._sections_cache = None

    # ---- Cache loaders ----

    def _load_pages(self) -> dict:
        if self._pages_cache is None:
            self._pages_cache = {}
            try:
                for page in self.course.get_pages():
                    title = getattr(page, "title", "")
                    self._pages_cache[title] = page
            except CanvasException:
                log.warning("Could not load existing pages")
            log.debug(f"Loaded {len(self._pages_cache)} existing pages")
        return self._pages_cache

    def _load_assignments(self) -> dict:
        if self._assignments_cache is None:
            self._assignments_cache = {}
            try:
                for a in self.course.get_assignments():
                    name = getattr(a, "name", "").strip()
                    self._assignments_cache[name] = a
            except CanvasException:
                log.warning("Could not load existing assignments")
            log.debug(
                f"Loaded {len(self._assignments_cache)} existing assignments"
            )
        return self._assignments_cache

    def _load_groups(self) -> dict:
        if self._groups_cache is None:
            self._groups_cache = {}
            try:
                for g in self.course.get_assignment_groups():
                    name = getattr(g, "name", "")
                    self._groups_cache[name] = g
            except CanvasException:
                log.warning("Could not load existing assignment groups")
            log.debug(f"Loaded {len(self._groups_cache)} existing groups")
        return self._groups_cache

    def _load_sections(self) -> dict:
        if self._sections_cache is None:
            self._sections_cache = {}
            try:
                for s in self.course.get_sections():
                    name = getattr(s, "name", "")
                    self._sections_cache[name] = s
            except CanvasException:
                log.warning("Could not load sections")
            log.info(f"  Loaded {len(self._sections_cache)} section cache entries")
        return self._sections_cache

    # ---- 0. Sections ----

    def setup_sections(self):
        """Create course sections from config if they don't already exist."""
        log.info("Setting up course sections...")
        existing = self._load_sections()

        created = 0
        skipped = 0
        for section_cfg in self.config.get("sections", []):
            name = section_cfg["name"]

            if name in existing:
                log.debug(f"  Section already exists: {name}")
                skipped += 1
                continue

            if self.dry_run:
                log.info(f"  [DRY RUN] Would create section: {name}")
                created += 1
                continue

            section = self.course.create_course_section(
                course_section={"name": name}
            )
            existing[name] = section
            log.info(f"  Created section: {name} (id={section.id})")
            created += 1

        if created > 0:
            self._sections_cache = None

        log.info(f"  Sections created: {created}, already existed: {skipped}")

    # ---- 1. Assignment Groups ----

    def setup_assignment_groups(self):
        """Create assignment groups (organizational, not weighted)."""
        log.info("Setting up assignment groups...")
        existing = self._load_groups()

        for group_def in self.config["assignment_groups"]:
            name = group_def["name"]

            if name in existing:
                group = existing[name]
                # Clear any leftover weight from previous runs
                if not self.dry_run and getattr(group, "group_weight", 0):
                    group.edit(group_weight=0)
                    log.info(f"  Group '{name}' — cleared weight")
                else:
                    log.info(f"  Group '{name}' already exists")
            else:
                if not self.dry_run:
                    new_group = self.course.create_assignment_group(
                        name=name
                    )
                    existing[name] = new_group
                log.info(f"  Created group '{name}'")

        # Disable weighted grading — course uses total points
        if not self.dry_run:
            self.course.update(
                course={"apply_assignment_group_weights": False}
            )
        log.info("  Disabled weighted assignment groups (using total points)")

    # ---- 2. Assignments ----

    def setup_assignments(self) -> dict:
        """Create all assignments and return {name: id} mapping."""
        log.info("Setting up assignments...")
        existing = self._load_assignments()
        groups = self._load_groups()
        assignment_ids = {}
        dry_count = 0

        for spec in self.config.get("special_assignments", []):
            sub_types = spec.get("submission_types", ["none"])
            # Skip quiz types — handled by setup_quizzes()
            if "online_quiz" in sub_types:
                if spec.get("questions") or spec.get("quiz_settings"):
                    log.info(
                        f"  Skipping quiz '{spec['name']}' "
                        f"(handled by --quizzes)"
                    )
                else:
                    log.info(
                        f"  Skipping quiz '{spec['name']}' "
                        f"(create manually in Canvas)"
                    )
                continue

            # Wrap description in DesignPLUS banner unless disabled
            raw_desc = spec.get("description", "")
            if raw_desc and not spec.get("no_banner"):
                description = generate_assignment_description(
                    spec["name"], raw_desc,
                    banner_title=spec.get("banner_title"),
                )
            else:
                description = raw_desc

            aid = self._create_or_update_assignment(
                spec["name"], existing, groups,
                group_name=spec["group"],
                points=spec["points"],
                submission_types=sub_types,
                description=description,
                allowed_extensions=spec.get("allowed_extensions"),
                due_at=spec.get("due_date"),
            )
            if aid:
                assignment_ids[spec["name"]] = aid
            else:
                dry_count += 1

        if self.dry_run:
            log.info(f"  [DRY RUN] Would create/update {dry_count} assignments")
        else:
            log.info(f"  Total assignments: {len(assignment_ids)}")
        return assignment_ids

    @with_retry()
    def _create_or_update_assignment(
        self, name, existing, groups, group_name, points,
        submission_types, description="", allowed_extensions=None,
        due_at=None,
    ) -> int | None:
        """Find-or-create a single assignment. Returns Canvas assignment ID."""
        group = groups.get(group_name)
        group_id = getattr(group, "id", None) if group else None

        assignment_data = {
            "name": name,
            "points_possible": points,
            "submission_types": submission_types,
            "published": False,
            "description": description,
        }
        if group_id:
            assignment_data["assignment_group_id"] = group_id
        if allowed_extensions:
            assignment_data["allowed_extensions"] = allowed_extensions
        if due_at:
            assignment_data["due_at"] = due_at

        if name in existing:
            assignment = existing[name]
            if not self.dry_run:
                assignment.edit(assignment=assignment_data)
                log.info(f"  Updated: {name}")
            else:
                log.info(f"  [DRY RUN] Would update: {name}")
            return assignment.id

        if self.dry_run:
            log.info(f"  [DRY RUN] Would create: {name}")
            return None

        new_assignment = self.course.create_assignment(
            assignment=assignment_data
        )
        existing[name] = new_assignment
        log.info(f"  Created: {name} (id={new_assignment.id})")
        return new_assignment.id

    # ---- Quizzes ----

    def _load_quiz_questions_file(self, name: str) -> list:
        """Load quiz questions from config/quizzes/ YAML file.

        Looks for a file matching the assignment name (sanitized).
        Returns a list of question dicts in the format expected by
        _build_question_payload, or an empty list if no file found.
        """
        quizzes_dir = Path(__file__).resolve().parent / "config" / "quizzes"
        # Sanitize name to match filename convention
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")
        safe = re.sub(r"_+", "_", safe)
        path = quizzes_dir / f"{safe}.yaml"

        if not path.exists():
            return []

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw_questions = data.get("questions", [])

        # Type mapping from YAML shorthand to Canvas API question types
        type_map = {
            "multiple_choice": "multiple_choice_question",
            "essay": "essay_question",
            "text_only": "text_only_question",
        }

        questions = []
        for q in raw_questions:
            q_type = type_map.get(q["type"], q["type"])
            q_def = {
                "type": q_type,
                "text": q["text"],
                "points": 0 if q_type == "text_only_question" else 1,
            }

            # For graded surveys, all MC answers get weight 100
            # (any response earns full credit)
            if q_type == "multiple_choice_question" and q.get("answers"):
                q_def["answers"] = [
                    {"text": a, "weight": 100} for a in q["answers"]
                ]

            questions.append(q_def)

        log.debug(f"  Loaded {len(questions)} questions from {path.name}")
        return questions

    def setup_quizzes(self):
        """Create or update quizzes defined in special_assignments."""
        log.info("Setting up quizzes...")
        groups = self._load_groups()

        quiz_specs = [
            spec for spec in self.config.get("special_assignments", [])
            if "online_quiz" in spec.get("submission_types", [])
            and (spec.get("questions") or spec.get("quiz_settings"))
        ]

        if not quiz_specs:
            log.info("  No quiz definitions found in config")
            return

        existing_quizzes = {}
        if not self.dry_run:
            try:
                for q in self.course.get_quizzes():
                    title = getattr(q, "title", "")
                    existing_quizzes[title] = q
            except CanvasException:
                log.warning("  Could not load existing quizzes")
        log.debug(f"  Loaded {len(existing_quizzes)} existing quizzes")

        for spec in quiz_specs:
            name = spec["name"]
            # Load questions: inline config takes priority, then YAML file
            questions = spec.get("questions", [])
            if not questions:
                questions = self._load_quiz_questions_file(name)
            settings = spec.get("quiz_settings", {})

            group = groups.get(spec["group"])
            group_id = getattr(group, "id", None) if group else None

            # Wrap description in DesignPLUS banner unless disabled
            raw_desc = spec.get("description", "")
            if raw_desc and not spec.get("no_banner"):
                quiz_desc = generate_assignment_description(
                    name, raw_desc,
                    banner_title=spec.get("banner_title"),
                )
            else:
                quiz_desc = raw_desc

            quiz_data = {
                "title": name,
                "description": quiz_desc,
                "quiz_type": settings.get("quiz_type", "graded_survey"),
                "points_possible": spec["points"],
                "published": False,
                "shuffle_answers": settings.get("shuffle_answers", False),
                "allowed_attempts": settings.get("allowed_attempts", 1),
                "show_correct_answers": settings.get(
                    "show_correct_answers", False
                ),
                "one_question_at_a_time": settings.get(
                    "one_question_at_a_time", False
                ),
            }
            if settings.get("time_limit") is not None:
                quiz_data["time_limit"] = settings["time_limit"]
            if spec.get("due_date"):
                quiz_data["due_at"] = spec["due_date"]
            if group_id:
                quiz_data["assignment_group_id"] = group_id

            if name in existing_quizzes:
                quiz = existing_quizzes[name]
                if self.dry_run:
                    log.info(f"  [DRY RUN] Would update quiz: {name}")
                else:
                    self._update_quiz(quiz, quiz_data)
                    log.info(f"  Updated quiz: {name}")
                    if questions:
                        self._replace_quiz_questions(quiz, questions)
            else:
                if self.dry_run:
                    log.info(
                        f"  [DRY RUN] Would create quiz: {name} "
                        f"({len(questions)} questions)"
                    )
                else:
                    quiz = self._create_quiz(quiz_data)
                    log.info(f"  Created quiz: {name} (id={quiz.id})")
                    if questions:
                        self._create_quiz_questions(quiz, questions)

        log.info(f"  Processed {len(quiz_specs)} quiz(es)")

    @with_retry()
    def _create_quiz(self, quiz_data: dict):
        return self.course.create_quiz(quiz=quiz_data)

    @with_retry()
    def _update_quiz(self, quiz, quiz_data: dict):
        quiz.edit(quiz=quiz_data)

    def _replace_quiz_questions(self, quiz, questions: list):
        try:
            for existing_q in quiz.get_questions():
                self._delete_quiz_question(existing_q)
        except CanvasException:
            log.warning("  Could not delete existing questions")
        self._create_quiz_questions(quiz, questions)

    @with_retry()
    def _delete_quiz_question(self, question):
        question.delete()

    def _create_quiz_questions(self, quiz, questions: list):
        for i, q_def in enumerate(questions, 1):
            payload = self._build_question_payload(q_def, i)
            self._create_quiz_question(quiz, payload)
            log.info(
                f"    Created Q{i}: [{q_def['type']}] "
                f"{q_def['text'][:60]}..."
            )

    @with_retry()
    def _create_quiz_question(self, quiz, payload: dict):
        quiz.create_question(question=payload)

    def _build_question_payload(self, q_def: dict, position: int) -> dict:
        payload = {
            "question_name": f"Question {position}",
            "question_text": q_def["text"],
            "question_type": q_def["type"],
            "points_possible": q_def.get("points", 1),
            "position": position,
        }

        q_type = q_def["type"]

        if q_type == "numerical_question":
            answers = []
            for ans in q_def.get("answers", []):
                answers.append({
                    "numerical_answer_type": "exact_answer",
                    "exact": ans["exact"],
                    "margin": ans.get("margin", 0),
                    "weight": ans.get("weight", 100),
                })
            payload["answers"] = answers

        elif q_type == "true_false_question":
            correct = q_def.get("correct", True)
            correct_comment = q_def.get("correct_comment", "")
            incorrect_comment = q_def.get("incorrect_comment", "")
            payload["answers"] = [
                {
                    "answer_text": "True",
                    "answer_weight": 100 if correct else 0,
                    "answer_comment": (
                        correct_comment if correct else incorrect_comment
                    ),
                },
                {
                    "answer_text": "False",
                    "answer_weight": 0 if correct else 100,
                    "answer_comment": (
                        incorrect_comment if correct else correct_comment
                    ),
                },
            ]

        elif q_type == "multiple_choice_question":
            answers = []
            for ans in q_def.get("answers", []):
                answers.append({
                    "answer_text": ans["text"],
                    "answer_weight": ans.get("weight", 0),
                    "answer_comment": ans.get("comment", ""),
                })
            payload["answers"] = answers

        return payload

    # ---- Photo uploads ----

    def upload_photos(self) -> dict:
        """Upload all photos/images from canvas/config/photos/ to Canvas course files."""
        log.info("Uploading photos...")
        photos_dir = Path(__file__).resolve().parent / "config" / "photos"
        if not photos_dir.is_dir():
            log.warning(f"  Photos directory not found: {photos_dir}")
            return {}

        photo_files = [
            p for p in sorted(photos_dir.iterdir())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg")
            and p.name != "placeholder.png"
        ]
        if not photo_files:
            log.warning("  No photo files found in photos/")
            return {}

        photo_urls = {}
        for photo_path in photo_files:
            filename = photo_path.name
            if self.dry_run:
                log.info(f"  [DRY RUN] Would upload: {filename}")
                continue

            try:
                url = self._upload_file(photo_path, folder="course_photos")
                if url:
                    photo_urls[filename] = url
                    log.info(f"  Uploaded: {filename}")
            except Exception as e:
                log.warning(f"  Failed to upload {filename}: {e}")

        return photo_urls

    @with_retry()
    def _upload_file(self, file_path: Path, folder: str = "") -> str:
        """Upload a file to Canvas course files via the file upload API."""
        url = f"{self.api_base}/courses/{self.course.id}/files"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "name": file_path.name,
            "content_type": "application/octet-stream",
            "parent_folder_path": folder,
            "on_duplicate": "overwrite",
        }
        resp = http_requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        upload_info = resp.json()

        upload_url = upload_info["upload_url"]
        upload_params = upload_info.get("upload_params", {})
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            resp2 = http_requests.post(
                upload_url, data=upload_params, files=files, timeout=60
            )

        if resp2.status_code in (200, 201):
            result = resp2.json()
            return result.get("url", "")
        elif resp2.status_code in (301, 302, 303):
            confirm_url = resp2.headers.get("Location", "")
            if confirm_url:
                resp3 = http_requests.get(
                    confirm_url, headers=headers, timeout=30
                )
                resp3.raise_for_status()
                return resp3.json().get("url", "")

        log.warning(f"  Unexpected upload response: {resp2.status_code}")
        return ""

    def discover_photos(self) -> dict:
        """Look up previously uploaded photos in Canvas course files."""
        log.info("Discovering existing staff photos in Canvas...")
        photo_urls = {}
        if self.dry_run:
            log.info("  [DRY RUN] Skipping photo discovery")
            return photo_urls

        try:
            folders = list(self.course.get_folders())
            target = None
            for folder in folders:
                if getattr(folder, "full_name", "").endswith("course_photos"):
                    target = folder
                    break
            if not target:
                log.info("  No course_photos folder found in course files")
                return photo_urls

            for f in target.get_files():
                name = getattr(f, "display_name", "") or getattr(f, "filename", "")
                url = getattr(f, "url", "")
                if name and url:
                    photo_urls[name] = url
            log.info(f"  Found {len(photo_urls)} existing photos")
        except CanvasException as e:
            log.warning(f"  Could not discover photos: {e}")

        return photo_urls

    # ---- 3. Pages ----

    def setup_pages(self, assignment_ids: dict = None, photo_urls: dict = None):
        """Create or update all wiki pages.

        Two-phase approach: leaf pages first (no cross-links), then
        pages that link to other pages (using recorded slugs).
        """
        log.info("Setting up pages...")
        existing = self._load_pages()
        ids = assignment_ids or {}

        if not photo_urls:
            photo_urls = self.discover_photos()

        if not ids:
            for name, a in self._load_assignments().items():
                ids[name] = a.id
            if ids:
                log.info(
                    f"  Using {len(ids)} assignment IDs from existing course"
                )

        course_url = self.course_url
        page_slugs = {}

        def _record_slug(title: str):
            if title in existing:
                slug = getattr(existing[title], "url", "")
                if slug:
                    page_slugs[title] = slug

        # ---- Phase 1: leaf pages ----
        leaf_pages = [
            ("Contact Info", generate_contact_page, True),
            ("Lab Sections", generate_sections_page, False),
            ("Help Sessions", generate_help_sessions_page, False),
            ("Lab Issue Reporting Form", generate_report_issue_page, False),
            ("Feedback", generate_feedback_page, False),
        ]
        for title, gen_func, has_photos in leaf_pages:
            if has_photos and photo_urls:
                body = gen_func(self.config, course_url, ids,
                                photo_urls=photo_urls)
            else:
                body = gen_func(self.config, course_url, ids)
            self._create_or_update_page(title, body, existing)
            _record_slug(title)

        # ---- Phase 2: cross-linking pages ----
        ids["_page_slugs"] = page_slugs
        log.info(f"  Recorded {len(page_slugs)} page slugs for cross-linking")

        # Week pages
        combined_created = set()
        for entry in self.config["schedule"]:
            w = entry["week"]
            combined = entry.get("combined_page")

            if combined:
                # Create combined page once, skip individual pages
                if combined not in combined_created:
                    combined_created.add(combined)
                    body = generate_weeks_12_16_page(
                        self.config, course_url, ids
                    )
                    self._create_or_update_page(
                        combined, body, existing, published=True
                    )
                    _record_slug(combined)

                    # Set availability based on first week in the group
                    slug = page_slugs.get(combined) or getattr(
                        existing.get(combined), "url", ""
                    )
                    if slug:
                        release_dt = self._compute_release_date(w)
                        self._set_page_availability(slug, release_dt)
                continue

            title = f"Week {w}"
            body = generate_week_page(entry, self.config, course_url, ids)
            self._create_or_update_page(
                title, body, existing, published=True
            )
            _record_slug(title)

            # Set availability date (skip Week 1)
            if w > 1:
                slug = page_slugs.get(title) or getattr(
                    existing.get(title), "url", ""
                )
                if slug:
                    release_dt = self._compute_release_date(w)
                    self._set_page_availability(slug, release_dt)

        # Syllabus page (needs photos + cross-links for schedule)
        syllabus_body = generate_syllabus_page(
            self.config, course_url, ids, photo_urls=photo_urls
        )
        self._create_or_update_page("Syllabus", syllabus_body, existing)
        _record_slug("Syllabus")

        for title, gen_func in [
            ("Course Schedule", generate_schedule_page),
            ("Other Resources", generate_other_resources_page),
        ]:
            body = gen_func(self.config, course_url, ids)
            self._create_or_update_page(title, body, existing)
            _record_slug(title)

        # Homepage (front page, needs photo_urls for banner)
        home_body = generate_homepage(
            self.config, course_url, ids, photo_urls=photo_urls
        )
        self._create_or_update_page("Home", home_body, existing, True)
        _record_slug("Home")

        # Set built-in syllabus redirect
        self._set_syllabus_redirect(ids)

    @with_retry()
    def _set_syllabus_redirect(self, ids: dict = None):
        redirect_html = generate_syllabus_redirect(self.course_url, ids)
        if not self.dry_run:
            self.course.update(course={"syllabus_body": redirect_html})
        log.info("  Set built-in syllabus to redirect banner")

    def _compute_release_date(self, week_num: int) -> datetime:
        release = self.config.get("page_release", {})
        days_before = release.get("days_before", 0)
        hour = release.get("hour", 0)

        term_start = datetime.strptime(
            self.config["term"]["start"], "%Y-%m-%d"
        )
        week_monday = term_start + timedelta(weeks=week_num - 1)
        release_dt = week_monday - timedelta(days=days_before)
        release_dt = release_dt.replace(hour=hour, minute=0, second=0)
        return release_dt.replace(tzinfo=self.tz)

    @with_retry()
    def _set_page_availability(self, page_slug: str, unlock_at: datetime):
        unlock_iso = unlock_at.isoformat()

        if self.dry_run:
            log.info(
                f"  [DRY RUN] Would set availability: "
                f"{page_slug} -> unlock_at {unlock_iso}"
            )
            return

        url = (
            f"{self.api_base}/courses/{self.course.id}"
            f"/pages/{page_slug}/date_details"
        )
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"unlock_at": unlock_iso}

        try:
            resp = http_requests.put(url, json=payload, headers=headers,
                                     timeout=30)
            resp.raise_for_status()
            log.info(f"  Set availability: {page_slug} -> {unlock_iso}")
        except http_requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            if status in (404, 400):
                log.warning(
                    f"  Page date_details endpoint not available "
                    f"(HTTP {status}) for {page_slug} — skipping."
                )
            else:
                raise CanvasException(
                    f"Failed to set availability for {page_slug}: {e}"
                ) from e

    @with_retry()
    def _create_or_update_page(
        self, title: str, body: str, existing: dict,
        front_page: bool = False, published: bool = True,
    ):
        if title in existing:
            page = existing[title]
            if not self.dry_run:
                page.edit(wiki_page={"body": body, "published": published})
                status = "published" if published else "unpublished"
                log.info(f"  Updated page: {title} ({status})")
            else:
                log.info(f"  [DRY RUN] Would update page: {title}")
        else:
            if self.dry_run:
                status = "published" if published else "unpublished"
                log.info(
                    f"  [DRY RUN] Would create page: {title} ({status})"
                )
                return
            page = self.course.create_page(wiki_page={
                "title": title,
                "body": body,
                "published": published,
            })
            existing[title] = page
            actual_slug = getattr(page, "url", "")
            status = "published" if published else "unpublished"
            log.info(f"  Created page: {title} ({status}, slug: {actual_slug})")

        if front_page and not self.dry_run:
            try:
                page_slug = getattr(page, "url", "")
                front = self.course.get_page(page_slug)
                front.edit(wiki_page={"front_page": True})
                log.info(f"  Set '{title}' as front page")
            except CanvasException as e:
                log.warning(f"  Could not set front page: {e}")

    # ---- 4. Navigation Tabs ----

    def setup_navigation(self):
        """Configure course navigation tab visibility and order."""
        log.info("Setting up navigation tabs...")
        nav_config = self.config.get("navigation", [])
        if not nav_config:
            log.info("  No navigation config found, skipping")
            return

        tabs_by_label = {}
        for tab in self.course.get_tabs():
            label = getattr(tab, "label", "")
            tabs_by_label[label] = tab

        visible_labels = set(nav_config)
        visible_labels.add("Home")

        position = 2
        for label in nav_config:
            tab = tabs_by_label.get(label)
            if not tab:
                log.warning(f"  Tab not found: '{label}'")
                continue
            if not self.dry_run:
                self._update_tab(tab, hidden=False, position=position)
            log.info(f"  Show ({position}): {label}")
            position += 1

        for label, tab in tabs_by_label.items():
            if label in visible_labels:
                continue
            is_hidden = getattr(tab, "hidden", None)
            if is_hidden:
                continue
            tab_id = getattr(tab, "id", "")
            if tab_id == "settings" or label == "Settings":
                continue
            if not self.dry_run:
                try:
                    self._update_tab(tab, hidden=True)
                except CanvasException as e:
                    if "not manageable" in str(e).lower():
                        continue
                    raise
            log.info(f"  Hide: {label}")

    @with_retry()
    def _update_tab(self, tab, **kwargs):
        tab.update(**kwargs)


# ===================================================================
# CLI and main
# ===================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up PHYS 2150 Canvas course from config file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python canvas_setup_course.py --dry-run --all\n"
            "  python canvas_setup_course.py --groups --assignments\n"
            "  python canvas_setup_course.py --pages\n"
            "  python canvas_setup_course.py --navigation -v\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config" / "course_config.yaml"),
        help="Path to YAML config file (default: config/course_config.yaml)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview actions without making any changes",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose/debug logging",
    )

    ops = parser.add_argument_group("operations (at least one required)")
    ops.add_argument("--all", action="store_true", help="Run all operations")
    ops.add_argument(
        "--sections", action="store_true",
        help="Create course sections from config",
    )
    ops.add_argument(
        "--groups", action="store_true",
        help="Create/update assignment groups",
    )
    ops.add_argument(
        "--assignments", action="store_true",
        help="Create/update assignments",
    )
    ops.add_argument(
        "--pages", action="store_true",
        help="Create/update styled wiki pages",
    )
    ops.add_argument(
        "--navigation", action="store_true",
        help="Configure navigation tab visibility and order",
    )
    ops.add_argument(
        "--quizzes", action="store_true",
        help="Create/update quizzes from config",
    )
    ops.add_argument(
        "--photos", action="store_true",
        help="Upload staff photos from config/photos/ to Canvas",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    config_path = Path(args.config)
    if not config_path.exists():
        log.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    _load_csv_data(config, config_path.parent)

    run_all = args.all
    if not (run_all or args.sections or args.groups or args.assignments
            or args.quizzes or args.pages
            or args.navigation or args.photos):
        log.error(
            "No operations specified. Use --all or specific flags "
            "(--groups, --assignments, --pages, --navigation)."
        )
        sys.exit(1)

    domain = os.environ.get(
        "CANVAS_DOMAIN", config["canvas"]["domain"]
    )
    token = os.environ.get("CANVAS_TOKEN")
    if not token:
        token = getpass("Enter your Canvas API token: ")

    canvas = Canvas(f"https://{domain}", token)
    course_id = config["canvas"]["course_id"]

    try:
        course = canvas.get_course(course_id)
        log.info(f"Connected to: {getattr(course, 'name', course_id)}")
    except (InvalidAccessToken, Unauthorized) as e:
        log.error(f"Authentication failed: {e}")
        sys.exit(1)
    except CanvasException as e:
        log.error(f"Could not access course {course_id}: {e}")
        sys.exit(1)

    setup = CourseSetup(config, course, dry_run=args.dry_run, token=token)

    if args.dry_run:
        log.info("=" * 50)
        log.info("DRY RUN MODE — no changes will be made")
        log.info("=" * 50)

    assignment_ids = {}
    photo_urls = {}

    operations = [
        (run_all or args.sections, "Sections",
         lambda: setup.setup_sections()),
        (run_all or args.groups, "Assignment Groups",
         lambda: setup.setup_assignment_groups()),
        (run_all or args.assignments, "Assignments",
         None),
        (run_all or args.quizzes, "Quizzes",
         lambda: setup.setup_quizzes()),
        (run_all or args.photos, "Photos",
         None),
        (run_all or args.pages, "Pages",
         None),
        (run_all or args.navigation, "Navigation",
         lambda: setup.setup_navigation()),
    ]

    for should_run, label, func in operations:
        if not should_run:
            continue

        log.info("")
        log.info(f"{'=' * 50}")
        log.info(f"  {label}")
        log.info(f"{'=' * 50}")

        try:
            if label == "Assignments":
                assignment_ids = setup.setup_assignments()
            elif label == "Photos":
                photo_urls = setup.upload_photos()
            elif label == "Pages":
                setup.setup_pages(assignment_ids, photo_urls)
            else:
                func()
        except CanvasException as e:
            log.error(f"Error during {label}: {e}")
            if not args.dry_run:
                log.error("Stopping. Fix the issue and re-run.")
                sys.exit(1)

    log.info("")
    log.info("Done!")


if __name__ == "__main__":
    main()
