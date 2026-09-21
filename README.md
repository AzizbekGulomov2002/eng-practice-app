# eng-practice-app

Django web app for reading (MCQ / closest meaning / open-ended), writing, and speaking.

Students **cannot register**. Superadmin creates users in `/admin/` with phone (username) and password.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Demo accounts

| Role | Phone / username | Password |
| --- | --- | --- |
| Superadmin | `admin` | `admin123` |
| Teacher | `998907654321` | `teacher123` |
| Student | `998901234567` | `student123` |

Admin panel: http://127.0.0.1:8000/admin/

## How teachers add materials

In admin, create Test → Test material → Reading / Writing / Speaking.

- **Reading**: paste passage and questions in the CKEditor rich text fields. Add **Reading Questions** with `question_number` and `true_answer` (use `;` for alternative keys). MCQ answers are letters such as `B`.
- **Writing / speaking**: students submit; teachers score on `/teacher/`.
