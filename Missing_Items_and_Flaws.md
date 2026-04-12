# Missing Items and Flaws — ARDHI Timetable System

---

## 1. Degree Programmes With No Courses Assigned

The following 8 degree programmes exist in the database but have **zero courses** linked to them.
Their curriculum sheets were either missing from the uploaded Excel file or the sheet names did not
match any known programme code or name.

All 8 belong to **SERBI** (School of Environment, Resources and Business Innovation).

| # | Code | Degree Programme | School |
|---|------|-----------------|--------|
| 1 | BAF | Bachelor of Accounts and Finance (BAF) | SERBI |
| 2 | CSN | Computer Systems and Networks (CSN) | SERBI |
| 3 | GIS &RS | Geographical Information Systems and Remote Sensing (GIS &RS) | SERBI |
| 4 | GM | Geomatics (GM) | SERBI |
| 5 | ISM | Information System Management (ISM) | SERBI |
| 6 | LMV | Land Management and Valuation (LMV) | SERBI |
| 7 | PFM | Property and Facilities Management (PFM) | SERBI |
| 8 | REFI | Real Estate Finance and Investment (REFI) | SERBI |

**Action required:** Upload a curriculum Excel file that includes one sheet per missing programme,
with sheet names matching the programme code or name listed above.

---

## 2. Programmes With Courses Assigned (Reference)

| Code | Degree Programme | School | Courses |
|------|-----------------|--------|---------|
| ARCH | Architecture (ARCH) | SACEM | 72 |
| ID | Interior Design (ID) | SACEM | 57 |
| LA | Landscape Architecture (LA) | SACEM | 54 |
| QSCE | Quantity Surveying and Construction Economics (QSCE) | SACEM | 60 |
| CE | Civil Engineering (CE) | SEES | 65 |
| EE | Environmental Engineering (EE) | SEES | 61 |
| ELST | Environmental Laboratory Science and Technology (ELST) | SEES | 60 |
| ESM | Environmental Science and Management (ESM) | SEES | 60 |
| MISE | Municipal and Industrial Services Engineering (MISE) | SEES | 66 |
| B.A CDS | Community Development Studies (B.A CDS) | SSPSS | 48 |
| B.A ECON | Bachelor of Arts in Economics (B.A ECON) | SSPSS | 49 |
| HIP | Housing and Infrastructure Planning (HIP) | SSPSS | 60 |
| RDP | Regional and Development Planning (RDP) | SSPSS | 61 |
| URP | Urban and Regional Planning (URP) | SSPSS | 62 |

---

## 3. Data Entry Error in BSc. LA Curriculum Sheet

The **Landscape Architecture (LA)** curriculum sheet contains two course codes that appear to be
data entry errors — the code and title are swapped with another course:

| Code in Sheet | Title in Sheet | Expected |
|---------------|---------------|----------|
| `DS102` (no space) | "Communications Skills" | Should be **DS 102 — Development Perspectives II** |
| `CS102` (no space) | "Development Perspective 2" | Should be **CS 102 — Communication Skills** |

**Action required:** Correct these two entries in the BSc. LA curriculum sheet and re-upload.

---

## 4. Curriculum Parser Bug — Shared Courses Overwritten (Fixed)

**Status: Fixed**

**Root cause:** The curriculum parser used `Course.objects.update_or_create(code=course_code, ...)`
with only the course code as the lookup key. When the same course code (e.g. `DS 102`) appeared
in multiple programme sheets, each subsequent sheet overwrote the previous one, leaving only the
**last sheet processed** with that course.

**Impact:** DS 102 (Development Perspectives II) is taken by 13 out of 14 programmes but only
QSCE retained it after upload. The other 12 programmes were silently stripped of this course.

**Fix applied:** Changed the lookup to `(code, programme)` as a composite key, and removed the
`unique=True` database constraint on `Course.code`, replacing it with
`unique_together = ('code', 'programme')`. A database migration was created and applied.

---

## 5. CE Curriculum Sheet — Non-Standard Column Layout (Fixed)

**Status: Fixed**

The **BSc. CE** curriculum sheet uses a non-standard column order:

| Column header in sheet | Actual content |
|------------------------|---------------|
| Programme | Row / serial number |
| S/N | Course code (e.g. CE 101) |
| Course Code | Course name (e.g. "Engineering Drawing") |
| Study Period | Study period (e.g. Year 1:Semester 1) |

The column labelled **"S/N"** actually contained course codes, and the column labelled
**"Course Code"** actually contained course names. The parser's fallback detection was not
triggering because it required `header_row_idx` to be set, which it was not when no
`course_name` column was detected.

**Fix applied:** The parser now defaults `header_row_idx = 0` and runs the column-swap fallback
unconditionally when `course_name` is missing, allowing it to auto-detect and correct the
swapped columns.

---

## 6. B.A. BAE Sheet — Programme Code Mismatch (Resolved)

**Status: Resolved manually**

The curriculum Excel contains a sheet named **"B.A. BAE"** but the database stores this programme
as **B.A ECON** (Bachelor of Arts in Economics). The parser could not match "BAE" to "B.A ECON"
automatically.

**Resolution:** The admin manually identified the mapping. The sheet was processed successfully
after the programme match was confirmed.

**Recommendation:** Rename the sheet in the Excel file from "B.A. BAE" to "B.A ECON" or "B.A.
ECON" to ensure automatic matching on future uploads.

---

*Document generated: 2026-04-12*
