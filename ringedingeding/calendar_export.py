"""One calendar selection, three representations: web, iCalendar and Excel.

The important contract is that callers build :func:`calendar_entries` once and
pass that exact tuple to a renderer.  A project checkbox therefore changes the
display and the downloaded file in the same way; export has no hidden second
filter.  The module is deliberately standard-library-only so dry-run remains a
complete offline path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape as xml_escape
from io import BytesIO
from typing import Iterable, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from .projects import Project, ProjectMode, ProjectStore, Slot

__all__ = ["CalendarEntry", "calendar_entries", "render_ics", "render_xlsx"]


@dataclass(frozen=True)
class CalendarEntry:
    project_id: str
    project_title: str
    slot_id: str
    label: str
    day_date: str
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    all_day: bool = False
    decided: bool = False


def calendar_entries(
    projects: ProjectStore,
    selected_project_ids: Iterable[str] | None = None,
) -> tuple[CalendarEntry, ...]:
    """Return exactly the dated rows selected for display and export.

    ``None`` means every scheduling project.  An explicitly empty iterable
    means none, which matters for an unchecked checkbox form.
    """

    selected = None if selected_project_ids is None else set(selected_project_ids)
    result: list[CalendarEntry] = []
    for project in projects.projects():
        if project.mode != ProjectMode.SCHEDULE:
            continue
        if selected is not None and project.id not in selected:
            continue
        decision = projects.decision(project.id)
        for slot in projects.slots(project.id):
            if not slot.day_date:
                continue
            result.append(_entry(project, slot, decision.slot_id if decision else None))
    return tuple(sorted(result, key=_sort_key))


def _entry(project: Project, slot: Slot, decided_slot_id: str | None) -> CalendarEntry:
    return CalendarEntry(
        project_id=project.id,
        project_title=project.occasion,
        slot_id=slot.id,
        label=slot.label,
        day_date=slot.day_date or "",
        end_date=slot.end_date,
        start_time=slot.start_time,
        end_time=slot.end_time,
        all_day=slot.all_day,
        decided=slot.id == decided_slot_id,
    )


def _sort_key(entry: CalendarEntry) -> tuple[str, str, str, str]:
    return (entry.day_date, entry.start_time or "", entry.project_title.casefold(), entry.slot_id)


def render_ics(entries: Sequence[CalendarEntry]) -> bytes:
    """Render RFC 5545-compatible calendar data with stable, local UIDs."""

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ringedingeding//Filtered calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    stamp = "20000101T000000Z"  # deterministic output; not a claim about export time
    for entry in entries:
        lines.extend(["BEGIN:VEVENT", f"UID:{_ical(entry.project_id)}-{_ical(entry.slot_id)}@ringedingeding.local", f"DTSTAMP:{stamp}"])
        if entry.all_day or not entry.start_time:
            start = _date(entry.day_date)
            end_value = _date(entry.end_date or entry.day_date) + timedelta(days=1)
            lines.extend([f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end_value:%Y%m%d}"])
        else:
            start = _local_datetime(entry.day_date, entry.start_time)
            end = _local_datetime(entry.end_date or entry.day_date, entry.end_time or entry.start_time)
            lines.extend([f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}"])
        status = "CONFIRMED" if entry.decided else "TENTATIVE"
        lines.extend(
            [
                f"SUMMARY:{_ical(entry.project_title)}",
                f"DESCRIPTION:{_ical(entry.label)}",
                f"STATUS:{status}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in _fold_ical(line)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _local_datetime(day: str, clock: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{clock}")


def _ical(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_ical(line: str) -> list[str]:
    """Fold a content line at 75 UTF-8 octets as required by RFC 5545."""

    parts: list[str] = []
    remaining = line
    prefix = ""
    while len((prefix + remaining).encode("utf-8")) > 75:
        room = 75 - len(prefix.encode("utf-8"))
        used = 0
        cut = 0
        for index, character in enumerate(remaining):
            width = len(character.encode("utf-8"))
            if used + width > room:
                break
            used += width
            cut = index + 1
        if cut == 0:  # defensive; a UTF-8 code point is at most four bytes
            cut = 1
        parts.append(prefix + remaining[:cut])
        remaining = remaining[cut:]
        prefix = " "
    parts.append(prefix + remaining)
    return parts


def render_xlsx(entries: Sequence[CalendarEntry]) -> bytes:
    """Create a small real XLSX workbook without an office-library dependency."""

    headings = ("Project", "Date", "Start", "End", "Candidate", "Decision", "Project ID", "Slot ID")
    rows: list[tuple[str, ...]] = [headings]
    for entry in entries:
        rows.append(
            (
                entry.project_title,
                entry.day_date,
                entry.start_time or "",
                entry.end_time or "",
                entry.label,
                "decided" if entry.decided else "candidate",
                entry.project_id,
                entry.slot_id,
            )
        )
    workbook = BytesIO()
    with ZipFile(workbook, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/styles.xml", _STYLES)
        archive.writestr("xl/worksheets/sheet1.xml", _sheet(rows))
    return workbook.getvalue()


def _sheet(rows: Sequence[Sequence[str]]) -> str:
    xml_rows: list[str] = []
    for row_number, row in enumerate(rows, 1):
        cells: list[str] = []
        for column_number, value in enumerate(row, 1):
            reference = f"{_column(column_number)}{row_number}"
            style = ' s="1"' if row_number == 1 else ""
            cells.append(
                f'<c r="{reference}" t="inlineStr"{style}><is><t>{xml_escape(str(value))}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cols><col min="1" max="1" width="28" customWidth="1"/><col min="2" max="8" width="18" customWidth="1"/></cols>'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )


def _column(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


_CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
_ROOT_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
_WORKBOOK = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Calendar" sheetId="1" r:id="rId1"/></sheets></workbook>'''
_WORKBOOK_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
_STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font/><font><b/><color rgb="FFFFFFFF"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF6334F5"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>
<cellXfs count="2"><xf/><xf fontId="1" fillId="1" applyFont="1" applyFill="1"/></cellXfs>
</styleSheet>'''
