"""
HTML template generators for PHYS 2150 Canvas course pages.

Uses CIDI Labs DesignPLUS CSS classes (newer dp- pattern from the CU Boulder
sandbox template) that are loaded campus-wide on CU's Canvas instance.

All generated HTML is designed to be set as the `body` content of Canvas wiki
pages via the API. No external dependencies — pure Python string formatting.

Adapted from PHYS 1140 canvas system for PHYS 2150's research-experience
course structure.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

import mistune

# CU Boulder brand colors
CU_GOLD = "#cfb87c"
CU_BLACK = "#000000"


def _page_slug(ids: dict, title: str) -> str:
    """Look up the actual Canvas slug for a page title."""
    slugs = ids.get("_page_slugs", {}) if ids else {}
    actual = slugs.get(title, "")
    if actual:
        return actual
    fallback = title.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")

# DesignPLUS assets (loaded campus-wide by CU's Canvas instance)
DP_CSS_URL = (
    "https://instructure-uploads.s3.amazonaws.com/"
    "account_107720000000000001/attachments/74035876/dp_app.css"
)
DP_JS_URL = (
    "https://instructure-uploads.s3.amazonaws.com/"
    "account_107720000000000001/attachments/74035875/dp_app.js"
)


# ===================================================================
# Internal helpers
# ===================================================================

def _dp_wrapper(content: str) -> str:
    """Wrap content in DesignPLUS outer wrapper with CSS/JS links."""
    return (
        f'<link rel="stylesheet" href="{DP_CSS_URL}">'
        f'<div id="dp-wrapper" class="dp-wrapper dp-flat-sections variation-2">'
        f'{content}'
        f'</div>'
        f'<script src="{DP_JS_URL}"></script>'
    )


def _dp_header(badge_text: str, title_text: str) -> str:
    """Generate a gold-accented DesignPLUS section header."""
    return (
        f'<header class="dp-header dp-flat-sections variation-2">'
        f'<h2 class="dp-heading" style="border-top-color: {CU_GOLD};">'
        f'<span class="dp-header-pre" style="background-color: {CU_GOLD}; color: black;">'
        f'<span class="dp-header-pre-1">{badge_text}</span>'
        f'</span> '
        f'<span class="dp-header-title">{title_text}</span>'
        f'</h2>'
        f'</header>'
    )


def _dp_icon_section(icon_class: str, heading: str, content: str) -> str:
    """Generate a content block with a Font Awesome icon heading."""
    return (
        f'<div class="dp-content-block">'
        f'<h3 class="dp-has-icon">'
        f'<i class="{icon_class}" '
        f'style="background-color: black; color: white;" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> {heading}'
        f'</h3>'
        f'{content}'
        f'</div>'
    )


def _dp_content_block(content: str, block_class: str = "") -> str:
    """Generate a DesignPLUS content block."""
    cls = f"dp-content-block {block_class}".strip()
    return f'<div class="{cls}">{content}</div>'


def _dp_nav_button(url: str, icon_class: str, label: str) -> str:
    """Generate a single nav grid button."""
    return (
        f'<li class="col-xs-6 col-sm-6 col-md-6 col-lg-4">'
        f'<a class="dp-has-icon dp-course-link cph-bg-dp-secondary dp-hover-shadow-b6 btn-block" '
        f'style="background-color: {CU_BLACK}; color: #ffffff;" '
        f'href="{url}">'
        f'<i class="{icon_class} dp-i-shape-circle cp-bg-dp-white" '
        f'aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i>&nbsp;{label}'
        f'</a></li>'
    )


def _dp_nav_grid(buttons: list) -> str:
    """Generate the full nav grid from a list of (url, icon_class, label) tuples."""
    items = "\n".join(
        _dp_nav_button(url, icon, label) for url, icon, label in buttons
    )
    return (
        f'<nav class="container-fluid dp-link-grid dp-rounded-headings dp-rh-1">'
        f'<ul class="row">'
        f'{items}'
        f'</ul>'
        f'</nav>'
    )


def _gold_button(url: str, label: str, icon: str = "",
                 col_class: str = "col-xs-12") -> str:
    """Generate a gold link-grid item."""
    if icon:
        icon_html = (
            f'<i class="{icon} dp-i-shape-circle" '
            f'style="background-color: black; color: {CU_GOLD};" '
            f'aria-hidden="true">'
            f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
            f'</i>&nbsp;'
        )
        a_class = ("dp-has-icon dp-course-link btn btn-dp-secondary "
                   "cph-bg-dp-primary dp-hover-shadow-b6 btn-block")
    else:
        icon_html = ""
        a_class = ("dp-course-link btn btn-dp-secondary "
                   "cph-bg-dp-primary dp-hover-shadow-b6 btn-block")
    return (
        f'<li class="{col_class}">'
        f'<a class="{a_class}" '
        f'style="background-color: {CU_GOLD}; color: black; text-align: center;" '
        f'href="{url}">'
        f'{icon_html}{label}'
        f'</a></li>'
    )


def _gold_button_grid(buttons_html: str) -> str:
    """Wrap one or more ``_gold_button`` items in a DesignPLUS link grid."""
    return (
        f'<nav class="container-fluid dp-link-grid dp-rounded-headings dp-rh-1">'
        f'<ul class="row">{buttons_html}</ul>'
        f'</nav>'
    )


def _accessible_table(headers: list, rows: list, caption: str = "") -> str:
    """Generate an accessible HTML table with Canvas built-in styling."""
    caption_html = (
        f'<caption style="position: absolute; width: 1px; height: 1px; '
        f'padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); '
        f'border: 0;">{caption}</caption>'
        if caption else ""
    )

    header_cells = "\n".join(
        f'<th scope="col">{h}</th>' for h in headers
    )

    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i == 0:
                cells.append(f'<th scope="row">{cell}</th>')
            else:
                cells.append(f'<td>{cell}</td>')
        body_rows.append(f'<tr>{"".join(cells)}</tr>')

    return (
        f'<div style="overflow-x: auto;">'
        f'<table class="table-bordered ic-Table ic-Table--hover-row '
        f'ic-Table--striped" style="border-collapse: collapse; width: 100%;">'
        f'{caption_html}'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table>'
        f'</div>'
    )


def _assignment_link(course_url: str, assignment_id: int, text: str) -> str:
    """Generate a Canvas-internal assignment link."""
    return (
        f'<a title="{text}" href="{course_url}/assignments/{assignment_id}" '
        f'data-course-type="assignments">{text}</a>'
    )


def _resolve_links(text: str, course_url: str, ids: dict) -> str:
    """Replace ``{{assignment:Name}}`` and ``{{page:Title}}`` placeholders."""
    def _repl_assignment(m: re.Match) -> str:
        name = m.group(1)
        if name in ids:
            return (f"<strong>"
                    f"{_assignment_link(course_url, ids[name], name)}"
                    f"</strong>")
        return f"<strong>{name}</strong>"

    def _repl_page(m: re.Match) -> str:
        title = m.group(1)
        display = m.group(2) or f"<strong>{title}</strong>"
        slug = _page_slug(ids, title)
        return f'<a href="{course_url}/pages/{slug}">{display}</a>'

    text = re.sub(r"\{\{assignment:([^}]+)\}\}", _repl_assignment, text)
    text = re.sub(r"\{\{page:([^}|]+?)(?:\|([^}]+))?\}\}", _repl_page, text)
    return text


def _html_note(text: str) -> str:
    """Convert Unicode punctuation in YAML note text to HTML entities."""
    return text.replace("\u2014", "&mdash;").replace("\u2013", "&ndash;")


def _coordinator_contact(config: dict = None) -> str:
    """Return coordinator email as an HTML mailto link string."""
    if not config:
        return ""
    for inst in config.get("instructors", []):
        if "coordinator" in inst.get("title", "").lower():
            email = inst["email"]
            return (
                f' (<a href="mailto:{email}">{email}</a>)'
            )
    return ""


def generate_assignment_description(name: str, body_html: str,
                                    banner_title: str = None) -> str:
    """Wrap assignment body HTML in a DesignPLUS kl_banner description.

    Uses the legacy kl_ class pattern (still supported by DesignPLUS CSS)
    to produce the black banner with gold "PHYS 2150" badge seen on SP26
    assignment pages.

    Args:
        name: Assignment name (used as banner title if banner_title not set).
        body_html: Inner HTML paragraphs for the description body.
        banner_title: Override for the banner title text (defaults to name).
    """
    title = banner_title or name
    return (
        '<div id="kl_wrapper_3" class="kl_flat_sections kl_wrapper">'
        '<div id="kl_banner">'
        '<h2>'
        '<span id="kl_banner_left">'
        '<span class="kl_mod_text">PHYS </span>'
        '<span class="kl_mod_num">2150</span>'
        '</span>'
        f'<span id="kl_banner_right">{title}</span>'
        '</h2>'
        '</div>'
        f'{body_html}'
        '</div>'
    )


def _staff_card(person: dict, photo_urls: dict = None, photo_size: int = 100) -> str:
    """Generate a staff card with circular photo and contact details."""
    photo_urls = photo_urls or {}
    photo_file = person.get("photo", "placeholder.png")
    photo_src = photo_urls.get(photo_file, "")

    photo_html = ""
    if photo_src:
        photo_html = (
            f'<img src="{photo_src}" alt="Photo of {person["name"]}" '
            f'style="width: {photo_size}px; height: {photo_size}px; '
            f'border-radius: 50%; object-fit: cover; flex-shrink: 0;">'
        )

    phone = person.get("phone", "")
    phone_line = (
        f'<br><i class="fas fa-phone" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> {phone}'
    ) if phone else ""

    office_hours = person.get("office_hours", "")
    oh_line = (
        f'<br><i class="fas fa-clock" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> Office Hours: {office_hours}'
    ) if office_hours else ""

    zoom_link = person.get("zoom_link", "")
    zoom_line = (
        f'<br>Office Hour Zoom Link: '
        f'<a href="{zoom_link}" target="_blank">{zoom_link}</a>'
    ) if zoom_link else ""

    email = person.get("email", "")
    email_line = (
        f'<br><i class="fas fa-envelope" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> <a href="mailto:{email}">{email}</a>'
    ) if email else ""

    office = person.get("office", "")
    office_line = (
        f'<br><i class="fas fa-map-marker-alt" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> {office}'
    ) if office else ""

    affiliations = person.get("affiliations", [])
    affil_lines = "".join(
        f'<br><i class="fas fa-building" aria-hidden="true">'
        f'<span class="dp-icon-content" style="display: none;">&nbsp;</span>'
        f'</i> {a}'
        for a in affiliations
    )

    text_html = (
        f'<p><strong>{person["name"]}</strong> &mdash; {person["title"]}'
        f'{affil_lines}'
        f'{email_line}'
        f'{office_line}'
        f'{phone_line}'
        f'{oh_line}'
        f'{zoom_line}</p>'
    )

    if photo_html:
        return (
            f'<div class="dp-content-block" '
            f'style="display: flex; align-items: center; gap: 16px; '
            f'margin-bottom: 16px;">'
            f'{photo_html}'
            f'<div>{text_html}</div>'
            f'</div>'
        )
    return (
        f'<div class="dp-content-block" style="margin-bottom: 16px;">'
        f'{text_html}'
        f'</div>'
    )


def _week_dates(term_start_str: str, week_num: int) -> tuple:
    """Compute the Monday and Friday dates for a given week number."""
    term_start = datetime.strptime(term_start_str, "%Y-%m-%d")
    monday = term_start + timedelta(weeks=week_num - 1)
    friday = monday + timedelta(days=4)
    return (monday.strftime("%b %d"), friday.strftime("%b %d"))


# ===================================================================
# Markdown content loading
# ===================================================================

_CONTENT_DIR = Path(__file__).resolve().parent / "config" / "content"
_md = mistune.create_markdown(escape=False)


def _load_content(filename: str) -> str:
    """Read a markdown file from the content/ directory."""
    return (_CONTENT_DIR / filename).read_text(encoding="utf-8")


def _split_sections(text: str) -> list:
    """Split markdown text on ``## `` headings."""
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    sections = []
    for i, part in enumerate(parts):
        if i == 0:
            stripped = part.strip()
            if stripped:
                sections.append((None, stripped))
            continue
        lines = part.split("\n", 1)
        heading = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sections.append((heading, body))
    return sections


def _render_content_page(filename: str, icon_map: dict,
                         replacements: dict = None,
                         header_badge: str = "PHYS 2150",
                         header_title: str = "",
                         intro_text: str = "") -> str:
    """Load a markdown file and render as a DesignPLUS page."""
    text = _load_content(filename)
    if replacements:
        for key, val in replacements.items():
            text = text.replace("{{" + key + "}}", val)

    sections = _split_sections(text)
    header = _dp_header(header_badge, header_title)

    body = ""
    if intro_text:
        body += _dp_content_block(intro_text)

    for heading, md_body in sections:
        if heading is None:
            body += _dp_content_block(_md(md_body))
            continue
        html_body = _md(md_body) if md_body else ""
        icon = icon_map.get(heading, "fas fa-info-circle")
        body += _dp_icon_section(icon, heading, html_body)

    return _dp_wrapper(header + body)


# ===================================================================
# Page generators
# ===================================================================

def generate_homepage(config: dict, course_url: str,
                      assignment_ids: dict = None,
                      photo_urls: dict = None) -> str:
    """Generate the course homepage HTML."""
    term_name = config["term"]["name"]
    photo_urls = photo_urls or {}

    header = _dp_header("PHYS 2150", f"Experimental Physics 2 &mdash; {term_name}")

    # Banner image — use uploaded photo or fallback
    banner_src = photo_urls.get(
        "homepage_banner.jpeg",
        "https://files.ciditools.com/cuboulder/cu_leeds.jpg"
    )
    banner = (
        '<div class="dp-banner-image" style="margin-bottom: 16px;">'
        '<img style="width: 100%; height: auto; max-width: 100%;" '
        f'src="{banner_src}" '
        f'alt="Solar panels" '
        'width="1100" height="330">'
        '</div>'
    )

    ids = assignment_ids

    # Navigation grid
    syllabus_slug = _page_slug(ids, "Syllabus")
    contact_slug = _page_slug(ids, "Contact Info")
    sections_slug = _page_slug(ids, "Lab Sections")
    resources_slug = _page_slug(ids, "Other Resources")
    report_slug = _page_slug(ids, "Lab Issue Reporting Form")
    help_slug = _page_slug(ids, "Help Sessions")
    nav = _dp_nav_grid([
        (f"{course_url}/pages/{syllabus_slug}", "fas fa-info-circle", "Syllabus"),
        (f"{course_url}/pages/{contact_slug}", "far fa-address-card", "Contact Info"),
        (f"{course_url}/pages/{sections_slug}", "fas fa-atom", "Lab Sections"),
        (f"{course_url}/pages/{help_slug}", "fas fa-question", "Help Sessions"),
        (f"{course_url}/pages/{resources_slug}", "fas fa-folder-open", "Other Resources"),
        (f"{course_url}/pages/{report_slug}", "fas fa-comments", "Report a Lab Issue"),
    ])

    # Welcome section
    welcome = _dp_content_block(
        '<h3>Welcome to PHYS 2150</h3>'
        '<p>Physics 2150 is an in-person research experience where you will '
        'learn about experimental physics by engaging in actual experimental '
        'physics research!</p>'
        '<p>This semester, we&rsquo;ll be working with perovskite solar cells '
        'fabricated at NLR (formerly NREL). We will study the impact of '
        'environmental stressors on the external quantum efficiency of the '
        'solar cells to produce research results that will add to the '
        'scientific community&rsquo;s knowledge of perovskite solar cells.</p>'
        '<p>Each week, we will post a new page describing your tasks and '
        'assignments. Open each one and follow the checklists to stay on track.</p>',
        "kl_custom_block_0"
    )

    # Weekly Schedule section
    week_btns = ""
    combined_seen = set()
    for entry in config["schedule"]:
        w = entry["week"]
        combined = entry.get("combined_page")
        if combined:
            if combined in combined_seen:
                continue
            combined_seen.add(combined)
            slug = _page_slug(ids, combined)
            week_btns += _gold_button(
                f"{course_url}/pages/{slug}", combined,
                col_class="col-xs-6 col-sm-4 col-md-3",
            )
        else:
            slug = _page_slug(ids, f"Week {w}")
            week_btns += _gold_button(
                f"{course_url}/pages/{slug}", f"Week {w}",
                col_class="col-xs-6 col-sm-4 col-md-3",
            )

    schedule_section = _dp_icon_section(
        "fas fa-calendar-alt",
        "Course Schedule",
        _gold_button_grid(week_btns),
    )

    return _dp_wrapper(header + banner + nav + welcome + schedule_section)


def generate_week_page(week_entry: dict, config: dict, course_url: str,
                       assignment_ids: dict = None) -> str:
    """Generate a per-week overview page.

    PHYS 2150 weeks are all custom (no structured lab pages). Each week
    has a checklist, optional lecture info, and assignment links.
    """
    week_num = week_entry["week"]
    ids = assignment_ids or {}

    # Lecture lookup
    lecture_lookup = {
        lec["week"]: lec for lec in config.get("lectures", [])
    }
    lecture = lecture_lookup.get(week_num)

    title = _html_note(week_entry.get("title", f"Week {week_num}"))
    header = _dp_header(f"Week {week_num}", title)

    sections = ""

    # Checklist
    checklist_items = week_entry.get("checklist", [])
    if checklist_items:
        items_html = "".join(
            f"<li>{_resolve_links(_html_note(item), course_url, ids)}</li>"
            for item in checklist_items
        )
        sections += _dp_icon_section(
            "fa fa-check", "Checklist", f"<ol>{items_html}</ol>"
        )

    # Lecture section
    if lecture:
        n = lecture["number"]
        topic = lecture.get("topic", "")
        topic_str = f": {topic}" if topic else ""
        sections += _dp_icon_section(
            "fas fa-play-circle",
            "Lectures",
            f'<h4>Lecture {n}{topic_str}</h4>'
            f'<p><em>Lecture Slides &mdash; Week {week_num}'
            f'</em></p>'
            f'<p><strong>Lecture slides will be posted '
            f'following the lecture.</strong></p>'
        )

    # Lab Guide section
    lab_guide = week_entry.get("lab_guide", "")
    if lab_guide:
        sections += _dp_icon_section(
            "fas fa-atom",
            "Lab Guide and Other Lab Documents",
            f'<ul><li>Download and read through the Lab Guide for this week '
            f'before your lab session.</li></ul>'
        )

    # Note section (for non-lab weeks like Spring Break)
    note = week_entry.get("note", "")
    if note and week_num != 1:
        sections += _dp_icon_section(
            "fas fa-flask",
            "Lab",
            f"<p>{_html_note(note)}</p>"
        )

    # Assignments section
    assign_names = week_entry.get("assignments", [])
    if assign_names:
        assignment_items = '<ol>'
        for name in assign_names:
            aid = ids.get(name)
            if aid:
                link = _assignment_link(course_url, aid, name)
                assignment_items += f'<li>{link}</li>'
            else:
                assignment_items += f'<li><strong>{name}</strong></li>'
        assignment_items += '</ol>'

        sections += _dp_icon_section(
            "fas fa-pencil-alt",
            "Assignments",
            assignment_items
            + '<p><strong>All due dates are listed on the individual assignments '
            'and can also be found on the '
            '<a href="https://canvas.colorado.edu/calendar" target="_blank">'
            'Canvas calendar</a>.</strong></p>'
        )

    # Reminders
    reminders = week_entry.get("reminders", [])
    if reminders:
        items_html = "".join(
            f"<li>{_html_note(r)}</li>" for r in reminders
        )
        sections += _dp_icon_section(
            "fas fa-exclamation-circle",
            "Reminders",
            f"<ul>{items_html}</ul>"
        )

    # Week 1: append onboarding content from markdown
    if week_num == 1:
        welcome_icon_map = {
            "Course Overview": "fas fa-clipboard-list",
            "Questions?": "fas fa-question-circle",
        }
        coordinator_contact = _coordinator_contact(config)
        welcome_text = _load_content("week1_welcome.md")
        welcome_text = welcome_text.replace(
            "{{coordinator_contact}}", coordinator_contact
        )
        for heading, md_body in _split_sections(welcome_text):
            if heading is None:
                sections += _dp_content_block(_md(md_body))
                continue
            html_body = _md(md_body) if md_body else ""
            icon = welcome_icon_map.get(heading, "fas fa-info-circle")
            sections += _dp_icon_section(icon, heading, html_body)

    # PI note for Week 1
    if week_num == 1:
        pi = config.get("pi", {})
        if pi:
            sections += _dp_icon_section(
                "fa fa-book",
                f"A Note from our PI, {pi['name']}",
                f'<p><em>Hi everybody, welcome to my research group! '
                f'I&rsquo;m excited to have your help this semester working '
                f'on this project and I look forward to talking to you all '
                f'in a couple of weeks.</em></p>'
            )

    return _dp_wrapper(header + sections)


def generate_weeks_12_16_page(config: dict, course_url: str = "",
                               assignment_ids: dict = None) -> str:
    """Generate combined Weeks 12-16 page matching SP26 structure."""
    ids = assignment_ids or {}
    header = _dp_header("PHYS 2150", "Weeks 12 - 16")

    w1216 = config.get("weeks_12_16", {})

    # Intro
    intro = _dp_content_block(
        '<p style="text-align: center;"><strong>For the remainder of the '
        'semester, you will work on your team research project.</strong></p>'
        '<p style="text-align: center;"><strong>Project management, the '
        'process of planning, organizing, and overseeing a project from '
        'start to finish, is an important aspect of research.</strong></p>'
        '<p style="text-align: center;"><strong>For Weeks 12 to 16 '
        '(except for Week 15 for Spring Break), you will manage your '
        'project including communicating the results of your '
        'analysis.</strong></p>'
    )

    # Checklist
    checklist_items = w1216.get("checklist", [])
    items_html = "".join(f"<li>{item}</li>" for item in checklist_items)
    checklist = _dp_icon_section(
        "fa fa-check", "Checklist", f"<ol>{items_html}</ol>"
    )

    # Lab Guide section
    lab_guide = _dp_icon_section(
        "fas fa-atom",
        "Lab Guide and Other Lab Documents",
        '<ul>'
        '<li>Download and read through the Lab Guide for Weeks 12-16.</li>'
        '<li>Download the Team Project Colab notebook and aggregate data file.</li>'
        '<li>Download Team Project Summary slide guide and template.</li>'
        '<li>Download Team Project Memo guide.</li>'
        '<li>Download Report to Future Researchers guide.</li>'
        '</ul>'
    )

    # Remaining Assignments section
    assign_html = (
        '<p style="text-align: center;"><strong>Note. Individual assignments '
        'will become available during the weeks indicated below.<br>'
        'All assignment due dates can be found on the Canvas calendar.<br>'
        'Please check the calendar regularly to stay up to date on deadlines '
        'and availability.</strong></p>'
    )

    # Team assignments
    assign_html += '<h3><strong>Team Assignments</strong></h3><ul>'
    for ta in w1216.get("team_assignments", []):
        name = ta["name"]
        aid = ids.get(name)
        if aid:
            link = _assignment_link(course_url, aid, name)
        else:
            link = f'<strong>{name}</strong>'
        assign_html += f'<li>{link} &mdash; {ta["description"]}</li>'
    assign_html += '</ul>'

    # Individual - Reflections
    assign_html += '<h3><strong>Individual Assignments</strong></h3>'
    assign_html += '<h4><strong>Reflections</strong></h4><ul>'
    for r in w1216.get("individual_assignments", {}).get("reflections", []):
        week = r.get("week")
        note = r.get("note", "")
        if week:
            name = f"Reflection Questions: Week {week}"
            aid = ids.get(name)
            if aid:
                link = _assignment_link(course_url, aid, f"Week {week}")
            else:
                link = f'<strong>Week {week}</strong>'
            assign_html += f'<li>{link} &mdash; {note}</li>'
        else:
            assign_html += f'<li>Week 15 &mdash; {note}</li>'
    assign_html += '</ul>'

    # Individual - Assessments
    assign_html += '<h4><strong>Assessments</strong></h4><ul>'
    for a in w1216.get("individual_assignments", {}).get("assessments", []):
        name = a["name"]
        aid = ids.get(name)
        if aid:
            link = _assignment_link(course_url, aid, name)
        else:
            link = f'<strong>{name}</strong>'
        assign_html += f'<li>{link} &mdash; {a["note"]}</li>'
    assign_html += '</ul>'

    # Individual - Other
    for o in w1216.get("individual_assignments", {}).get("other", []):
        name = o["name"]
        aid = ids.get(name)
        if aid:
            link = _assignment_link(course_url, aid, name)
        else:
            link = f'<strong>{name}</strong>'
        assign_html += f'<h4><strong>{name}</strong></h4>'
        assign_html += f'<p>{link} &mdash; {o["note"]}</p>'

    assignments = _dp_icon_section(
        "fas fa-pencil-alt", "Remaining Assignments", assign_html
    )

    return _dp_wrapper(header + intro + checklist + lab_guide + assignments)


def generate_contact_page(config: dict, course_url: str = "",
                          assignment_ids: dict = None,
                          photo_urls: dict = None) -> str:
    """Generate the contact information page."""
    header = _dp_header("PHYS 2150", "Contact Information")

    # Instructor section
    instructor_cards = "".join(
        _staff_card(inst, photo_urls, photo_size=100)
        for inst in config.get("instructors", [])
    )
    instructors = _dp_icon_section(
        "fa fa-address-book",
        "Instructor",
        instructor_cards
    )

    # Technical staff section
    tech_staff = config.get("technical_staff", [])
    tech_section = ""
    if tech_staff:
        tech_cards = "".join(
            _staff_card(person, photo_urls, photo_size=100)
            for person in tech_staff
        )
        tech_section = _dp_icon_section(
            "fas fa-user-ninja",
            "Technical Staff",
            tech_cards
        )

    # TA section
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Build help session lookup from config
    help_by_ta = {}
    for hs in config.get("help_sessions", []):
        ta_name = hs.get("ta", "")
        help_by_ta[ta_name] = f'{hs["day"]}s {hs["time"]}'

    ta_rows = []
    for ta in config.get("tas", []):
        help_time = help_by_ta.get(ta["name"], "")
        ta_rows.append([
            ta["name"],
            f'<a href="mailto:{ta["email"]}">{ta["email"]}</a>',
            help_time,
        ])

    ta_section = ""
    if ta_rows:
        ta_section = _dp_icon_section(
            "fa fa-address-book",
            "Teaching Assistants",
            '<p>Contact information for the course TAs. Help sessions are held '
            'in the PHYS 2150 lab space &mdash; Duane G2B83. You can attend '
            'the help session of any TA, not just your own.</p>'
            + _accessible_table(
                ["Name", "Email", "Help Session"],
                ta_rows,
                caption="Teaching Assistants"
            )
        )

    return _dp_wrapper(header + instructors + tech_section + ta_section)


def generate_sections_page(config: dict, course_url: str = "",
                           assignment_ids: dict = None) -> str:
    """Generate lab sections meeting times page."""
    header = _dp_header("PHYS 2150", "Lab Sections")

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = {
        10: "10:05&ndash;11:55 AM",
        12: "12:10&ndash;2:00 PM",
        14: "2:15&ndash;4:05 PM",
    }

    # Build section_number -> TA lookup
    ta_by_section = {}
    for ta in config.get("tas", []):
        for sec_num in ta.get("sections", []):
            ta_by_section[sec_num] = ta

    rows = []
    for sec in config.get("sections", []):
        day = day_names[sec["day"]]
        time_str = time_slots.get(sec["hour"], f'{sec["hour"]}:00')
        name = sec["name"]
        section_num = ""
        if "-" in name:
            section_num = name.rsplit("-", 1)[-1]
            name = f"Section {section_num}"

        ta = ta_by_section.get(section_num)
        ta_name = ta["name"] if ta else "TBD"

        rows.append([name, day, time_str, ta_name])

    table = _accessible_table(
        ["Section", "Day", "Time", "TA"],
        rows,
        caption="Lab Section Meeting Times"
    )

    intro = _dp_content_block(
        '<p>All lab sections meet in <strong>Duane G2B83</strong>. '
        'You must attend the lab section for which you are enrolled.</p>'
    )

    return _dp_wrapper(header + intro + table)


def generate_schedule_page(config: dict, course_url: str = "",
                           assignment_ids: dict = None) -> str:
    """Generate the course schedule as a styled HTML table."""
    header = _dp_header("PHYS 2150", "Course Schedule")

    term_start = config["term"]["start"]
    ids = assignment_ids or {}

    # Build lecture lookup
    lecture_lookup = {
        lec["week"]: lec for lec in config.get("lectures", [])
    }

    rows = []
    for entry in config["schedule"]:
        week_num = entry["week"]
        mon, fri = _week_dates(term_start, week_num)
        dates = f"{mon} &ndash; {fri}"

        # Phase column
        phase = entry.get("phase", "")

        # Lecture column
        lec = lecture_lookup.get(week_num)
        if lec:
            topic = lec.get("topic", "")
            lecture_col = f"Lec {lec['number']}: {topic}" if topic else f"Lecture {lec['number']}"
        else:
            lecture_col = "&mdash;"

        # Title/activity column
        title = _html_note(entry.get("title", ""))
        if not title:
            note = _html_note(entry.get("note", ""))
            title = note if note else "&mdash;"

        # Assignments column
        assign_names = entry.get("assignments", [])
        if assign_names:
            parts = []
            for name in assign_names:
                aid = ids.get(name)
                if aid:
                    parts.append(_assignment_link(course_url, aid, name))
                else:
                    parts.append(name)
            assignments_col = ", ".join(parts)
        else:
            assignments_col = "&mdash;"

        rows.append([
            f'<span style="display: block; text-align: center;">{week_num}</span>',
            dates,
            lecture_col,
            f"<strong>{title}</strong>" if phase else title,
            assignments_col,
        ])

    intro = _dp_content_block(
        '<p style="text-align: center;">'
        '<em>Schedule is subject to change. Check your week page each week '
        'for the most current information.</em></p>'
    )

    table = _accessible_table(
        ["Week", "Dates", "Lecture", "Activity", "Assignments Due"],
        rows,
        caption="PHYS 2150 Course Schedule"
    )

    return _dp_wrapper(header + intro + table)


def generate_other_resources_page(config: dict, course_url: str = "",
                                   assignment_ids: dict = None) -> str:
    """Generate Other Resources page from markdown content."""
    ids = assignment_ids
    text = _load_content("other_resources.md")
    coordinator_contact = _coordinator_contact(config)
    text = text.replace("{{coordinator_contact}}", coordinator_contact)
    sections = _split_sections(text)

    header = _dp_header("PHYS 2150", "Other Resources")

    # Render all sections with appropriate icons
    icon_map = {
        "Quick Links": "fas fa-link",
        "Troubleshooting & Guides": "fas fa-desktop",
        "Google Colab & Python": "fas fa-desktop",
        "Learning Python": "fas fa-desktop",
        "Introduction to Photovoltaics": "fas fa-sun",
        "SULI Program": "fas fa-sun",
        "Well-Being": "fas fa-hands-helping",
    }

    body = ""
    for heading, md_body in sections:
        if heading is None:
            body += _dp_content_block(_md(md_body))
            continue
        html_body = _md(md_body) if md_body else ""
        icon = icon_map.get(heading, "fas fa-info-circle")
        body += _dp_icon_section(icon, heading, html_body)

    return _dp_wrapper(header + body)


def generate_help_sessions_page(config: dict, course_url: str = "",
                                 assignment_ids: dict = None) -> str:
    """Generate Help Sessions page."""
    header = _dp_header("PHYS 2150", "Help Sessions")

    intro = '<p>Help sessions are held in the PHYS 2150 lab room (G2B83). ' \
            'You can attend any of the sessions.</p>'

    sessions = config.get("help_sessions", [])
    if sessions:
        # Group by day
        by_day = {}
        for s in sessions:
            by_day.setdefault(s["day"], []).append(s["time"])
        schedule_lines = []
        for day, times in by_day.items():
            schedule_lines.append(f'<p>{day} {", ".join(times)}</p>')
        intro += "".join(schedule_lines)

    content = _dp_content_block(intro)

    return _dp_wrapper(header + content)


def generate_report_issue_page(config: dict = None, course_url: str = "",
                                assignment_ids: dict = None) -> str:
    """Generate Report Lab Issue page with embedded Microsoft Forms link."""
    header = _dp_header("PHYS 2150", "Report a Lab Issue")

    report_url = ""
    if config:
        report_url = config.get("report_issue_url", "")

    if report_url and "PLACEHOLDER" not in report_url:
        content = _dp_content_block(
            '<p>Please submit the form below to report an issue with lab '
            'equipment or facilities to the technical staff. You may need to '
            'log in with your CU IdentiKey to access the form.</p>'
            f'<p>If the form does not load, '
            f'<a href="{report_url}" target="_blank">open it directly</a>.</p>'
            f'<iframe style="border: none; max-width: 100%; max-height: 100vh;" '
            f'src="{report_url}?embed=true" width="100%" height="600px" '
            f'title="Report a Lab Issue form" '
            f'allowfullscreen="allowfullscreen" loading="lazy"></iframe>'
        )
    else:
        content = _dp_content_block(
            '<p>The lab issue reporting form will be available here. '
            'In the meantime, please email the course coordinator directly.</p>'
        )

    return _dp_wrapper(header + content)


def generate_syllabus_page(config: dict, course_url: str = "",
                           assignment_ids: dict = None,
                           photo_urls: dict = None) -> str:
    """Generate the course syllabus from markdown content.

    Dynamic sections (instructor cards, grade table, schedule) are generated
    from config and injected via ``{{placeholder}}`` tokens.
    """
    term_name = config["term"]["name"]

    # Instructor cards
    instructor_cards = "".join(
        _staff_card(inst, photo_urls, photo_size=80)
        for inst in config.get("instructors", [])
    )

    # PI card
    pi = config.get("pi", {})
    pi_card = ""
    if pi and pi.get("name"):
        pi_info = {
            "name": pi["name"],
            "title": pi.get("title", "Principal Investigator"),
            "email": pi.get("email", ""),
            "office": pi.get("office", ""),
            "affiliations": pi.get("affiliations", []),
            "photo": pi.get("photo", "placeholder.png"),
        }
        pi_card = _staff_card(pi_info, photo_urls, photo_size=80)

    # Technical staff cards
    tech_staff = config.get("technical_staff", [])
    tech_cards = "".join(
        _staff_card(person, photo_urls, photo_size=80)
        for person in tech_staff
    ) if tech_staff else "<p>See the Contact Info page for current staff.</p>"

    # Grade table — compute point totals per group from assignments
    group_points = {}
    for a in config.get("special_assignments", []):
        g = a.get("group", "")
        group_points[g] = group_points.get(g, 0) + a.get("points", 0)
    grade_rows = [
        [g["name"], f'{group_points.get(g["name"], 0):.0f} pts']
        for g in config.get("assignment_groups", [])
    ]
    total = sum(group_points.values())
    grade_rows.append(["<strong>Total</strong>", f"<strong>{total:.0f} pts</strong>"])
    grade_table = _accessible_table(
        ["Category", "Points"], grade_rows, caption="Grade Breakdown"
    )

    # Schedule table
    term_start = config["term"]["start"]
    lecture_lookup = {
        lec["week"]: lec for lec in config.get("lectures", [])
    }
    sched_rows = []
    for entry in config["schedule"]:
        w = entry["week"]
        title = entry.get("title", "")
        note = entry.get("note", "")
        lab_col = title if title else (note if note else "&mdash;")

        lec = lecture_lookup.get(w)
        lec_col = lec["topic"] if lec else "&mdash;"

        sched_rows.append([str(w), lab_col, lec_col])

    schedule_table = _accessible_table(
        ["Week", "Lab (Tuesdays, Thursdays)", "Lecture"],
        sched_rows,
        caption="Course Schedule"
    )

    coordinator_contact = _coordinator_contact(config)

    return _render_content_page(
        "syllabus.md",
        icon_map={
            "Course Goals": "fas fa-bullseye",
            "Instructors": "fas fa-user",
            "Principal Investigator": "fas fa-microscope",
            "Technical Staff": "fas fa-user-ninja",
            "Equipment": "fas fa-tools",
            "Lectures": "fas fa-chalkboard-teacher",
            "Research Meetings": "fas fa-users",
            "Labs": "fas fa-flask",
            "Assignments and Grading": "fas fa-chart-bar",
            "Course Schedule": "fas fa-calendar-alt",
            "Policy on the Use of Artificial Intelligence (AI)": "fas fa-robot",
            "University Policies": "fas fa-university",
        },
        replacements={
            "instructor_cards": instructor_cards,
            "pi_card": pi_card,
            "tech_staff_cards": tech_cards,
            "grade_table": grade_table,
            "schedule_table": schedule_table,
            "coordinator_contact": coordinator_contact,
        },
        header_title=f"Course Syllabus &mdash; {term_name}",
    )


def generate_syllabus_redirect(course_url: str,
                                assignment_ids: dict = None) -> str:
    """Generate the HTML body for the built-in Canvas syllabus page.

    Displays a 'Not Used' warning banner that redirects instructors/admins
    to the wiki-based Syllabus page (which has revision history).
    This is set via course.update(course={"syllabus_body": ...}).
    """
    syllabus_slug = _page_slug(assignment_ids, "Syllabus")
    return (
        '<div style="border: 2px solid #6b1113; border-radius: 4px; '
        'overflow: hidden; max-width: 900px; margin: 24px auto;">'

        '<div style="background-color: #6b1113; color: #ffffff; '
        'padding: 8px 16px; font-weight: bold; text-align: center;">'
        '&#9888; Caution: Not Used</div>'

        '<div style="padding: 12px 16px;">'
        '<p>This course does not use the syllabus feature. Use the '
        f'<a href="{course_url}/pages/{syllabus_slug}">Syllabus Page</a> '
        'for the course syllabus.</p>'
        '</div>'

        '</div>'
    )


def generate_feedback_page(config: dict = None, course_url: str = "",
                            assignment_ids: dict = None) -> str:
    """Generate Feedback page."""
    header = _dp_header("PHYS 2150", "Feedback")

    content = _dp_content_block(
        '<p>We value your feedback about the course. Please share any '
        'suggestions, concerns, or comments with the course coordinator.</p>'
    )

    return _dp_wrapper(header + content)
