# ARDHI University Timetable System — Setup Guide

## 1. PostgreSQL Setup

Open pgAdmin or psql and run:

```sql
CREATE DATABASE ardhi_timetable;
CREATE USER ardhi_user WITH PASSWORD 'ardhi_password123';
GRANT ALL PRIVILEGES ON DATABASE ardhi_timetable TO ardhi_user;
```

Then update `.env` if you used different credentials.

## 2. Activate Virtual Environment

```bash
# From ARDHI-AUTOMATED-TIMETABLE-SYSYEM\
.venv\Scripts\activate
```

## 3. Apply Migrations

```bash
cd TimetableManagementSystem
python manage.py migrate
```

## 4. Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

## 5. Seed Default Timeslots

```bash
python manage.py seed_timeslots
```

This creates 18 timeslots:
- Mon–Thu: 08:00–10:00, 10:00–12:00, 13:00–15:00, 15:00–17:00
- Fri: 08:00–10:00, 10:00–12:00 (Friday afternoon restricted)

## 6. Run Development Server

```bash
python manage.py runserver
```

Access at: http://127.0.0.1:8000

## 7. Upload Data (Login as Admin)

1. Go to http://127.0.0.1:8000/admin-dashboard/
2. Upload in order:
   - **Rooms** (.xlsx) — Room_Name, Capacity, Is_Lab
   - **Lecturers** (.xlsx) — Name, Email, Is_Full_Time
   - **Student Populations** (.xlsx multi-sheet by school) — Programme_Code, Study_Year(integer), Male_Count, Female_Count
   - **Curriculum** (.xlsx multi-sheet by programme) — Course_Code, Course_Title, Semester, Study_Year, Is_Exam, Is_Lab
   - **Course Assignments** (.xlsx) — Course_Code, Lecturer_Name

## 8. Generate Timetable

From the Admin Dashboard → Generate section:
- Select programme(s), semester, year(s)
- Click **Generate Teaching** → HGCSA runs all 5 phases
- System returns: entries count + conflict status (should be 0 conflicts)

## 9. User Roles

| Role | URL | Notes |
|------|-----|-------|
| Admin (superuser) | /admin-dashboard/ | Full access |
| Coordinator (TTC/HOD) | /coordinator/ | Generate + FullCalendar drag-drop |
| Lecturer | /lecturer/ | View own schedule |
| Student | /student/ | Public, no login |
| Exam Officer (EXAM) | /examination-officer/ | Exam timetable only |
| Stakeholder | /stakeholder/ | Read-only |

## 10. API Token Auth

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'
```

Returns `{"token": "..."}` — use as `Authorization: Token <key>` header.
