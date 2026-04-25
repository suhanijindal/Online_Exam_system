import os
from flask import Flask, render_template, request
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()

    # Total counts
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM results")
    total_results = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM results WHERE status='Pass'")
    total_pass = cursor.fetchone()[0]

    cursor.execute("SELECT ROUND(AVG(marks),1) FROM results")
    avg_marks = cursor.fetchone()[0] or 0

    pass_rate = round((total_pass / total_results * 100), 1) if total_results else 0

    # Recent results
    cursor.execute("""
        SELECT s.student_id, s.name, sub.subject_name, r.marks, r.status, r.exam_date
        FROM results r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_id = sub.subject_id
        ORDER BY r.exam_date DESC LIMIT 10
    """)
    recent = cursor.fetchall()

    # Course distribution
    cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course ORDER BY course")
    course_dist = cursor.fetchall()

    # Subject pass rates
    cursor.execute("""
        SELECT sub.subject_name,
               COUNT(*) as total,
               SUM(CASE WHEN r.status='Pass' THEN 1 ELSE 0 END) as passed
        FROM results r
        JOIN subjects sub ON r.subject_id = sub.subject_id
        GROUP BY sub.subject_name ORDER BY sub.subject_name
    """)
    subject_rates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
        page='dashboard',
        total_students=total_students,
        total_results=total_results,
        total_questions=total_questions,
        pass_rate=pass_rate,
        avg_marks=avg_marks,
        recent=recent,
        course_dist=course_dist,
        subject_rates=subject_rates
    )

@app.route('/students')
def students():
    conn = get_db()
    cursor = conn.cursor()

    course = request.args.get('course', 'All')
    page_num = int(request.args.get('page', 1))
    per_page = 20

    where = ""
    params = []
    if course != 'All':
        where = "WHERE course = %s"
        params.append(course)

    cursor.execute(f"SELECT COUNT(*) FROM students {where}", params)
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_num = min(page_num, total_pages)
    offset = (page_num - 1) * per_page

    cursor.execute(f"SELECT * FROM students {where} ORDER BY student_id LIMIT %s OFFSET %s", params + [per_page, offset])
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
        page='students',
        students=data,
        current_page=page_num,
        total_pages=total_pages,
        total=total,
        course_filter=course
    )

@app.route('/results')
def results():
    conn = get_db()
    cursor = conn.cursor()

    subject = request.args.get('subject', 'All')
    status = request.args.get('status', 'All')
    page_num = int(request.args.get('page', 1))
    per_page = 20

    where_clauses = []
    params = []
    if subject != 'All':
        where_clauses.append("r.subject_id = %s")
        params.append(int(subject))
    if status != 'All':
        where_clauses.append("r.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    cursor.execute(f"""
        SELECT COUNT(*) FROM results r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_id = sub.subject_id
        {where}
    """, params)
    total = cursor.fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_num = min(page_num, total_pages)
    offset = (page_num - 1) * per_page

    cursor.execute(f"""
        SELECT s.student_id, s.name, s.roll_no, sub.subject_name, r.marks,
               r.correct_answers, r.wrong_answers, r.exam_date, r.status
        FROM results r
        JOIN students s ON r.student_id = s.student_id
        JOIN subjects sub ON r.subject_id = sub.subject_id
        {where}
        ORDER BY r.exam_date DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    data = cursor.fetchall()

    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
        page='results',
        results=data,
        subjects=subjects,
        current_page=page_num,
        total_pages=total_pages,
        total=total,
        subject_filter=subject,
        status_filter=status
    )

@app.route('/questions')
def questions():
    conn = get_db()
    cursor = conn.cursor()

    subject = request.args.get('subject', 'All')

    if subject != 'All':
        cursor.execute("""
            SELECT q.question_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
                   q.correct_answer, sub.subject_name
            FROM questions q JOIN subjects sub ON q.subject_id = sub.subject_id
            WHERE q.subject_id = %s ORDER BY RAND() LIMIT 10
        """, (int(subject),))
    else:
        cursor.execute("""
            SELECT q.question_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
                   q.correct_answer, sub.subject_name
            FROM questions q JOIN subjects sub ON q.subject_id = sub.subject_id
            ORDER BY RAND() LIMIT 10
        """)
    data = cursor.fetchall()

    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
        page='questions',
        questions=data,
        subjects=subjects,
        subject_filter=subject
    )

@app.route('/subjects')
def subjects():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sub.subject_id, sub.subject_name, sub.course,
               COUNT(DISTINCT q.question_id) as qcount,
               COUNT(DISTINCT r.result_id) as rcount,
               ROUND(AVG(r.marks),1) as avg_marks,
               ROUND(SUM(CASE WHEN r.status='Pass' THEN 1 ELSE 0 END)/COUNT(r.result_id)*100,1) as pass_rate
        FROM subjects sub
        LEFT JOIN questions q ON q.subject_id = sub.subject_id
        LEFT JOIN results r ON r.subject_id = sub.subject_id
        GROUP BY sub.subject_id, sub.subject_name, sub.course
        ORDER BY sub.subject_id
    """)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', page='subjects', subjects_list=data)

@app.route('/student/<int:sid>')
def student_detail(sid):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE student_id = %s", (sid,))
    student = cursor.fetchone()

    cursor.execute("""
        SELECT sub.subject_name, r.marks, r.total_marks, r.attempted,
               r.correct_answers, r.wrong_answers, r.exam_date, r.status
        FROM results r
        JOIN subjects sub ON r.subject_id = sub.subject_id
        WHERE r.student_id = %s ORDER BY r.exam_date DESC
    """, (sid,))
    exams = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html', page='student_detail', student=student, exams=exams)

@app.route('/search', methods=['GET', 'POST'])
def search():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '')
    else:
        name = request.args.get('q', '')

    student_results = []
    result_data = []

    if name:
        cursor.execute("""
            SELECT student_id, name, roll_no, gender, course, email
            FROM students WHERE name LIKE %s OR roll_no LIKE %s OR email LIKE %s
            LIMIT 20
        """, (f'%{name}%', f'%{name}%', f'%{name}%'))
        student_results = cursor.fetchall()

        cursor.execute("""
            SELECT s.student_id, s.name, sub.subject_name, r.marks, r.status, r.exam_date
            FROM results r
            JOIN students s ON r.student_id = s.student_id
            JOIN subjects sub ON r.subject_id = sub.subject_id
            WHERE s.name LIKE %s OR s.roll_no LIKE %s
            LIMIT 20
        """, (f'%{name}%', f'%{name}%'))
        result_data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
        page='search',
        query=name,
        student_results=student_results,
        result_data=result_data
    )

if __name__ == '__main__':
    app.run(debug=True)
