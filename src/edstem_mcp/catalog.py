import re
from dataclasses import dataclass, field


class EdError(ValueError):
    """Only fixed, safe messages belong in this exception."""

    def __init__(self, message: str, code="invalid_request", http_status=None):
        super().__init__(message)
        self.code, self.http_status = code, http_status


@dataclass(frozen=True)
class TextParam:
    required: bool = False
    max_length: int = 300


@dataclass(frozen=True)
class Operation:
    path: str
    summary: str
    query: dict = field(default_factory=dict)
    collection: str | None = None
    paginated: bool = False
    evidence: str = "edapi"
    notes: str = ""


PAGE = {"limit": (1, 100, 20), "offset": (0, 1000000, 0)}
ACTIVITY = {
    "limit": (1, 50, 20),
    "offset": (0, 1000000, 0),
    "courseID": (1, 2**63 - 1, None),
    "filter": ("all", "thread", "answer", "comment"),
}
OPERATIONS = {
    "user": Operation(
        "/user", "Your profile, enrolled courses, roles, realms, and settings.", evidence="official"
    ),
    "course": Operation(
        "/courses/{course_id}", "Course details, categories, and settings.", evidence="ed-mcp"
    ),
    "threads": Operation(
        "/courses/{course_id}/threads",
        "Browse posts, questions, announcements, authors, and reply counts.",
        PAGE | {"sort": ("new", "top", "trending")},
        "threads",
        True,
        notes="No server search filter: it was silently ignored in live checks.",
    ),
    "thread": Operation(
        "/threads/{thread_id}",
        "Full thread, answers, comments, and participants.",
        notes="Never sends view=1. Thread IDs differ from course-local numbers.",
    ),
    "course_thread": Operation(
        "/courses/{course_id}/threads/{number}",
        "Full thread using the course-local post number.",
        notes="Never sends view=1.",
    ),
    "user_activity": Operation(
        "/users/{user_id}/profile/activity",
        "Visible posts and replies by a user. Use your ID from user.",
        ACTIVITY,
        "items",
        True,
        notes="courseID is source-documented; scope is not assumed. "
        "Check returned course IDs before treating results as course-specific.",
    ),
    "resources": Operation(
        "/courses/{course_id}/resources",
        "Course resources and file links.",
        collection="resources",
        evidence="campus-copilot",
    ),
    "lessons": Operation(
        "/courses/{course_id}/lessons",
        "Lesson outlines, modules, dates, status.",
        collection="lessons",
        evidence="edstem-cli",
    ),
    "lesson": Operation(
        "/lessons/{lesson_id}",
        "Lesson details and slide list, without tracking.",
        evidence="edstem-cli",
        notes="Source-reviewed; no live lesson available.",
    ),
    "slide": Operation(
        "/lessons/slides/{slide_id}",
        "Slide text, metadata, and file links.",
        evidence="edstem-cli",
        notes="No view flag. Source-reviewed, not live-tested.",
    ),
    "slide_questions": Operation(
        "/lessons/slides/{slide_id}/questions",
        "Visible slide questions.",
        collection="questions",
        evidence="edstem-cli",
        notes="Does not answer or submit. Source-reviewed, not live-tested.",
    ),
    "slide_responses": Operation(
        "/lessons/slides/{slide_id}/questions/responses",
        "Existing visible responses to slide questions.",
        collection="responses",
        evidence="edstem-cli",
        notes="Does not submit. Source-reviewed, not live-tested.",
    ),
    "events": Operation(
        "/courses/{course_id}/events",
        "Attendance sessions.",
        collection="events",
        evidence="ed-mcp",
    ),
    "event": Operation(
        "/events/{event_id}",
        "Attendance session details; never checks in.",
        evidence="ed-mcp",
        notes="Source-reviewed; no live event available.",
    ),
    "check_ins": Operation(
        "/courses/{course_id}/check_ins",
        "Visible existing attendance records.",
        collection="check_ins",
        evidence="ed-mcp",
    ),
    "event_check_ins": Operation(
        "/events/{event_id}/check_ins",
        "Visible existing attendance records for an event.",
        collection="check_ins",
        evidence="ed-mcp",
    ),
    "course_stats": Operation(
        "/courses/{course_id}/stats",
        "Course statistics, if permitted.",
        evidence="ed-mcp",
        notes="403 in student live check.",
    ),
    "enrollment_stats": Operation(
        "/courses/{course_id}/analytics/enrollments",
        "Enrollment counts, if permitted.",
        evidence="ed-mcp",
        notes="403 in student live check.",
    ),
    "course_users": Operation(
        "/courses/{course_id}/analytics/users",
        "Roster, if permitted.",
        collection="users",
        notes="403 in student live check.",
    ),
    "attendance_stats": Operation(
        "/courses/{course_id}/analytics/sessions",
        "Attendance analytics, if permitted.",
        evidence="ed-mcp",
        notes="403 in student live check.",
    ),
}

OPERATIONS.update(
    {
        "native_search": Operation(
            "/courses/{course_id}/threads/search",
            "Search the whole course using Ed's native index.",
            PAGE
            | {
                "query": TextParam(required=True),
                "category": TextParam(),
                "subcategory": TextParam(),
                "subsubcategory": TextParam(),
            },
            "threads",
            True,
            "ed-web-client",
            "Returns Ed's total and paginated matches. Index freshness and reply coverage are "
            "controlled by Ed; use local search with include_replies for explicit reply scanning.",
        ),
        "user_stats": Operation(
            "/users/{user_id}/profile/stats",
            "Visible profile activity statistics.",
            {"courseID": (1, 2**63 - 1, None)},
            evidence="ed-web-client",
        ),
        "user_resources": Operation(
            "/users/resources",
            "Resources across your accessible courses.",
            {"realm_id": (1, 2**63 - 1, None)},
            "resources",
            evidence="ed-web-client",
        ),
        "user_lessons": Operation(
            "/users/lessons",
            "Lessons and modules across your accessible courses.",
            collection="lessons",
            evidence="ed-web-client",
        ),
        "snippets": Operation(
            "/courses/{course_id}/snippets",
            "Saved course code snippets; never runs code.",
            collection="snippets",
            evidence="ed-web-client",
        ),
        "labs": Operation(
            "/courses/{course_id}/labs",
            "Course lab or tutorial groups.",
            collection="labs",
            evidence="ed-web-client",
        ),
        "lab_categories": Operation(
            "/courses/{course_id}/lab_categories",
            "Course lab group categories.",
            collection="categories",
            evidence="ed-web-client",
        ),
    }
)


def operation(name: str) -> Operation:
    if name not in OPERATIONS:
        raise EdError("Unknown operation. Use edstem_find_operations.")
    return OPERATIONS[name]


def prepare(name: str, path: dict, query: dict) -> tuple[str, dict]:
    op = operation(name)
    expected = set(re.findall(r"{(\w+)}", op.path))
    if set(path) != expected:
        raise EdError(
            f"Path parameters must be exactly: {', '.join(sorted(expected)) or 'none'}. "
            "Use edstem_describe_operation for query parameters."
        )
    for value in path.values():
        if type(value) not in (str, int) or not re.fullmatch(r"[1-9][0-9]{0,18}", str(value)):
            raise EdError("Path IDs must be positive decimal integers, without URLs or slashes.")
    if set(query) - set(op.query):
        raise EdError(
            "Unsupported query parameter. Tracking flags and arbitrary filters are blocked."
        )
    clean = {}
    for key, spec in op.query.items():
        if isinstance(spec, TextParam):
            if key not in query and not spec.required:
                continue
            value = query.get(key)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > spec.max_length
                or any(ord(c) < 32 for c in value)
            ):
                raise EdError(
                    "Text query parameter is missing or invalid; inspect operation bounds."
                )
        elif isinstance(spec[0], int):
            value = query.get(key, spec[2])
            if value is None and key not in query:
                continue
            if type(value) is not int or not spec[0] <= value <= spec[1]:
                raise EdError("Integer query parameter is invalid; inspect operation bounds.")
        else:
            value = query.get(key, spec[0])
            if not isinstance(value, str) or value not in spec:
                raise EdError("Query value is not in the operation's allowed choices.")
        clean[key] = value
    return op.path.format(**path), clean


def describe(name: str) -> dict:
    op = operation(name)
    return {
        "operation": name,
        "method": "GET",
        "path": op.path,
        "summary": op.summary,
        "path_parameters": re.findall(r"{(\w+)}", op.path),
        "query": {
            k: (
                {"min": v[0], "max": v[1], "default": v[2]}
                if not isinstance(v, TextParam) and isinstance(v[0], int)
                else (
                    {"type": "text", "required": v.required, "max_length": v.max_length}
                    if isinstance(v, TextParam)
                    else {"choices": v, "default": v[0]}
                )
            )
            for k, v in op.query.items()
        },
        "pagination": "Use pagination.next_query until null."
        if op.paginated
        else "Single response; no client pagination.",
        "evidence": op.evidence,
        "notes": op.notes,
    }
