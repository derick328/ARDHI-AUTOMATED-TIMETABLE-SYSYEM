"""
Timetable export module.
Supports Excel (.xlsx via XlsxWriter) and PDF (via ReportLab).
Export types: 'by_programme', 'by_venue', 'by_lecturer'
"""
import io
from collections import defaultdict

# ── Excel ──────────────────────────────────────────────────────────────────────

def export_excel(entries, export_type='by_programme', title='ARDHI University Timetable'):
    """
    Export timetable entries to an Excel file.

    Args:
        entries: list/queryset of TimetableEntry with select_related loaded
        export_type: 'by_programme' | 'by_venue' | 'by_lecturer'
        title: document title string

    Returns:
        BytesIO containing the .xlsx file
    """
    import xlsxwriter

    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})

    # Formats
    header_fmt = wb.add_format({
        'bold': True, 'bg_color': '#0066CC', 'font_color': 'white',
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 11
    })
    title_fmt = wb.add_format({
        'bold': True, 'font_size': 14, 'font_color': '#0066CC', 'align': 'center'
    })
    cell_fmt = wb.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
    alt_fmt = wb.add_format({
        'border': 1, 'align': 'left', 'valign': 'vcenter',
        'bg_color': '#F0F4FF', 'text_wrap': True
    })

    DAY_ORDER = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4}

    if export_type == 'by_programme':
        _excel_by_programme(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title)
    elif export_type == 'by_venue':
        _excel_by_venue(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title)
    elif export_type == 'by_lecturer':
        _excel_by_lecturer(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title)

    wb.close()
    output.seek(0)
    return output


def _write_sheet_header(ws, title, subtitle, title_fmt):
    ws.merge_range('A1:F1', 'ARDHI UNIVERSITY', title_fmt)
    ws.merge_range('A2:F2', title, title_fmt)
    ws.merge_range('A3:F3', subtitle, title_fmt)


def _excel_by_programme(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title):
    grouped = defaultdict(list)
    for e in entries:
        key = (e.programme.code, e.course.study_year, e.course.semester)
        grouped[key].append(e)

    for (prog_code, year, sem), group in sorted(grouped.items()):
        sheet_name = f"{prog_code} Y{year} S{sem}"[:31]
        ws = wb.add_worksheet(sheet_name)
        ws.set_column('A:A', 12)
        ws.set_column('B:B', 35)
        ws.set_column('C:C', 20)
        ws.set_column('D:D', 12)
        ws.set_column('E:F', 10)

        _write_sheet_header(ws, title, f"{prog_code} — Year {year} Semester {sem}", title_fmt)

        headers = ['Course Code', 'Course Title', 'Lecturer', 'Venue', 'Day', 'Time']
        for col, h in enumerate(headers):
            ws.write(4, col, h, header_fmt)

        group_sorted = sorted(group, key=lambda e: (
            DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
        ))
        for row_i, e in enumerate(group_sorted):
            fmt = alt_fmt if row_i % 2 else cell_fmt
            lecturer_name = e.lecturer.name if e.lecturer else 'TBA'
            ws.write(5 + row_i, 0, e.course.code, fmt)
            ws.write(5 + row_i, 1, e.course.title, fmt)
            ws.write(5 + row_i, 2, lecturer_name, fmt)
            ws.write(5 + row_i, 3, e.room.name, fmt)
            ws.write(5 + row_i, 4, e.timeslot.get_day_display(), fmt)
            ws.write(5 + row_i, 5,
                     f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}", fmt)


def _excel_by_venue(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title):
    grouped = defaultdict(list)
    for e in entries:
        grouped[e.room.name].append(e)

    for room_name, group in sorted(grouped.items()):
        sheet_name = room_name[:31]
        ws = wb.add_worksheet(sheet_name)
        ws.set_column('A:A', 12)
        ws.set_column('B:B', 30)
        ws.set_column('C:C', 20)
        ws.set_column('D:D', 15)
        ws.set_column('E:F', 10)

        _write_sheet_header(ws, title, f"Venue: {room_name}", title_fmt)
        headers = ['Course Code', 'Course Title', 'Lecturer', 'Programme', 'Day', 'Time']
        for col, h in enumerate(headers):
            ws.write(4, col, h, header_fmt)

        group_sorted = sorted(group, key=lambda e: (
            DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
        ))
        for row_i, e in enumerate(group_sorted):
            fmt = alt_fmt if row_i % 2 else cell_fmt
            lecturer_name = e.lecturer.name if e.lecturer else 'TBA'
            ws.write(5 + row_i, 0, e.course.code, fmt)
            ws.write(5 + row_i, 1, e.course.title, fmt)
            ws.write(5 + row_i, 2, lecturer_name, fmt)
            ws.write(5 + row_i, 3, e.programme.code, fmt)
            ws.write(5 + row_i, 4, e.timeslot.get_day_display(), fmt)
            ws.write(5 + row_i, 5,
                     f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}", fmt)


def _excel_by_lecturer(wb, entries, title_fmt, header_fmt, cell_fmt, alt_fmt, DAY_ORDER, title):
    grouped = defaultdict(list)
    for e in entries:
        key = e.lecturer.name if e.lecturer else 'Unassigned'
        grouped[key].append(e)

    for lecturer_name, group in sorted(grouped.items()):
        sheet_name = lecturer_name[:31]
        ws = wb.add_worksheet(sheet_name)
        ws.set_column('A:A', 12)
        ws.set_column('B:B', 30)
        ws.set_column('C:C', 15)
        ws.set_column('D:D', 15)
        ws.set_column('E:F', 10)

        _write_sheet_header(ws, title, f"Lecturer: {lecturer_name}", title_fmt)
        headers = ['Course Code', 'Course Title', 'Programme', 'Venue', 'Day', 'Time']
        for col, h in enumerate(headers):
            ws.write(4, col, h, header_fmt)

        group_sorted = sorted(group, key=lambda e: (
            DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
        ))
        total_hours = 0
        for row_i, e in enumerate(group_sorted):
            fmt = alt_fmt if row_i % 2 else cell_fmt
            ws.write(5 + row_i, 0, e.course.code, fmt)
            ws.write(5 + row_i, 1, e.course.title, fmt)
            ws.write(5 + row_i, 2, e.programme.code, fmt)
            ws.write(5 + row_i, 3, e.room.name, fmt)
            ws.write(5 + row_i, 4, e.timeslot.get_day_display(), fmt)
            ws.write(5 + row_i, 5,
                     f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}", fmt)
            total_hours += e.timeslot.duration_hours

        summary_row = 5 + len(group_sorted) + 1
        bold_fmt = wb.add_format({'bold': True, 'border': 1})
        ws.write(summary_row, 0, 'Total Teaching Hours:', bold_fmt)
        ws.write(summary_row, 1, f"{total_hours:.1f} hrs", bold_fmt)


# ── PDF ────────────────────────────────────────────────────────────────────────

def export_pdf(entries, export_type='by_programme', title='ARDHI University Timetable'):
    """
    Export timetable entries to a PDF file.

    Returns:
        BytesIO containing the PDF
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from collections import defaultdict

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'],
        fontSize=14, alignment=TA_CENTER, textColor=colors.HexColor('#0066CC'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, spaceAfter=12
    )

    DAY_ORDER = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4}
    ARDHI_BLUE = colors.HexColor('#0066CC')
    ALT_ROW = colors.HexColor('#F0F4FF')

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ARDHI_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ALT_ROW]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    story = []
    story.append(Paragraph('ARDHI UNIVERSITY', title_style))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.3 * cm))

    if export_type == 'by_programme':
        grouped = defaultdict(list)
        for e in entries:
            key = (e.programme.code, e.course.study_year, e.course.semester)
            grouped[key].append(e)

        for (prog_code, year, sem), group in sorted(grouped.items()):
            story.append(Paragraph(f"{prog_code} — Year {year}, Semester {sem}", subtitle_style))
            headers = [['#', 'Code', 'Course Title', 'Lecturer', 'Venue', 'Day', 'Time']]
            group_sorted = sorted(group, key=lambda e: (
                DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
            ))
            data = headers + [
                [
                    str(i + 1),
                    e.course.code,
                    e.course.title[:40],
                    e.lecturer.name if e.lecturer else 'TBA',
                    e.room.name,
                    e.timeslot.get_day_display(),
                    f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}",
                ]
                for i, e in enumerate(group_sorted)
            ]
            col_widths = [1 * cm, 2.5 * cm, 7 * cm, 5 * cm, 3 * cm, 2.5 * cm, 3 * cm]
            tbl = Table(data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(table_style)
            story.append(tbl)
            story.append(PageBreak())

    elif export_type == 'by_venue':
        grouped = defaultdict(list)
        for e in entries:
            grouped[e.room.name].append(e)

        for room_name, group in sorted(grouped.items()):
            story.append(Paragraph(f"Venue: {room_name}", subtitle_style))
            headers = [['#', 'Code', 'Course Title', 'Lecturer', 'Programme', 'Day', 'Time']]
            group_sorted = sorted(group, key=lambda e: (
                DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
            ))
            data = headers + [
                [
                    str(i + 1), e.course.code, e.course.title[:35],
                    e.lecturer.name if e.lecturer else 'TBA',
                    e.programme.code,
                    e.timeslot.get_day_display(),
                    f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}",
                ]
                for i, e in enumerate(group_sorted)
            ]
            col_widths = [1 * cm, 2.5 * cm, 7 * cm, 5 * cm, 3 * cm, 2.5 * cm, 3 * cm]
            tbl = Table(data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(table_style)
            story.append(tbl)
            story.append(PageBreak())

    elif export_type == 'by_lecturer':
        grouped = defaultdict(list)
        for e in entries:
            key = e.lecturer.name if e.lecturer else 'Unassigned'
            grouped[key].append(e)

        for lecturer_name, group in sorted(grouped.items()):
            story.append(Paragraph(f"Lecturer: {lecturer_name}", subtitle_style))
            headers = [['#', 'Code', 'Course Title', 'Programme', 'Venue', 'Day', 'Time']]
            group_sorted = sorted(group, key=lambda e: (
                DAY_ORDER.get(e.timeslot.day, 0), e.timeslot.start_time
            ))
            total_hours = sum(e.timeslot.duration_hours for e in group_sorted)
            data = headers + [
                [
                    str(i + 1), e.course.code, e.course.title[:35],
                    e.programme.code, e.room.name,
                    e.timeslot.get_day_display(),
                    f"{e.timeslot.start_time.strftime('%H:%M')}–{e.timeslot.end_time.strftime('%H:%M')}",
                ]
                for i, e in enumerate(group_sorted)
            ]
            data.append(['', '', f'Total Teaching Hours: {total_hours:.1f} hrs', '', '', '', ''])
            col_widths = [1 * cm, 2.5 * cm, 7 * cm, 4 * cm, 3 * cm, 2.5 * cm, 3 * cm]
            tbl = Table(data, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(table_style)
            story.append(tbl)
            story.append(PageBreak())

    if not story:
        story.append(Paragraph('No timetable entries found.', styles['Normal']))

    doc.build(story)
    output.seek(0)
    return output
