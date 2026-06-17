from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from datetime import date

app = Flask(__name__)
app.secret_key = 'secretkey'

# =============================
# DATABASE CONFIGURATION
# =============================

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '2704'
app.config['MYSQL_DB'] = 'Academic_ops'

mysql = MySQL(app)

# =============================
# HOME & LOGIN
# =============================

@app.route('/')
def home():
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()
        cursor.close()

        if user:
            session['role'] = user[4]
            return redirect('/dashboard')
        else:
            return "Invalid Credentials"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# =============================
# DASHBOARD (WITH STATISTICS)
# =============================

@app.route('/dashboard')
def dashboard():
    if 'role' in session:
        cursor = mysql.connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM attendance")
        total_attendance = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM marks")
        total_marks = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT student_id
                FROM marks
                GROUP BY student_id
                HAVING AVG(marks) >= 40
            ) AS passed_students
        """)
        total_passed = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT student_id
                FROM marks
                GROUP BY student_id
                HAVING AVG(marks) < 40
            ) AS failed_students
        """)
        total_failed = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM (
        SELECT students.id
        FROM students
        LEFT JOIN marks ON students.id = marks.student_id
        LEFT JOIN attendance ON students.id = attendance.student_id
        GROUP BY students.id
        HAVING 
            AVG(marks.marks) < 40 
            OR (SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END)
                / COUNT(attendance.id)) * 100 < 75
    ) AS risky
""")

        at_risk = cursor.fetchone()[0]

        cursor.close()

        return render_template(
            'dashboard.html',
            role=session['role'],
            total_students=total_students,
            total_attendance=total_attendance,
            total_marks=total_marks,
            total_passed=total_passed,
            total_failed=total_failed,
            at_risk=at_risk
        )

    return redirect('/login')

# =============================
# STUDENT MODULE (FULL CRUD)
# =============================

@app.route('/students')
def students():
    if 'role' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM students")
        data = cursor.fetchall()
        cursor.close()
        return render_template('students.html', students=data)
    return redirect('/login')


@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if 'role' in session:
        if request.method == 'POST':
            name = request.form['name']
            roll = request.form['roll']
            branch = request.form['branch']
            year = request.form['year']

            cursor = mysql.connection.cursor()
            cursor.execute(
                "INSERT INTO students (name, roll_number, branch, year) VALUES (%s, %s, %s, %s)",
                (name, roll, branch, year)
            )
            mysql.connection.commit()
            cursor.close()

            return redirect('/students')

        return render_template('add_student.html')

    return redirect('/login')


@app.route('/edit_student/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if 'role' in session:
        cursor = mysql.connection.cursor()

        if request.method == 'POST':
            name = request.form['name']
            roll = request.form['roll']
            branch = request.form['branch']
            year = request.form['year']

            cursor.execute("""
                UPDATE students 
                SET name=%s, roll_number=%s, branch=%s, year=%s 
                WHERE id=%s
            """, (name, roll, branch, year, id))

            mysql.connection.commit()
            cursor.close()
            return redirect('/students')

        cursor.execute("SELECT * FROM students WHERE id=%s", (id,))
        student = cursor.fetchone()
        cursor.close()

        return render_template('edit_student.html', student=student)

    return redirect('/login')


@app.route('/delete_student/<int:id>')
def delete_student(id):
    if 'role' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM students WHERE id=%s", (id,))
        mysql.connection.commit()
        cursor.close()
        return redirect('/students')
    return redirect('/login')

# =============================
# ATTENDANCE MODULE
# =============================

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    today = date.today().strftime('%Y-%m-%d')
    if 'role' in session:
        cursor = mysql.connection.cursor()

        if request.method == 'POST':
            selected_date = request.form['date']

            if selected_date != today:
                return "Invalid date! Only today's attendance allowed."
            student_id = request.form['student_id']
            subject = request.form['subject']
            attendance_date = request.form['date']
            status = request.form['status']

            cursor.execute("""
                INSERT INTO attendance (student_id, subject, date, status)
                VALUES (%s, %s, %s, %s)
            """, (student_id, subject, date, status))

            mysql.connection.commit()

        cursor.execute("""
            SELECT attendance.id, students.name, students.roll_number,
                   attendance.subject, attendance.date, attendance.status
            FROM attendance
            JOIN students ON attendance.student_id = students.id
        """)
        records = cursor.fetchall()

        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        cursor.close()

        return render_template('attendance.html', students=students, records=records, today=today)

    return redirect('/login')


@app.route('/attendance_report')
def attendance_report():
    if 'role' in session:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT students.name,
           students.roll_number,
           COUNT(attendance.id) AS total_classes,
           SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END) AS present_count,
           (SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END)
            / COUNT(attendance.id)) * 100 AS percentage,
           CASE 
               WHEN (SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END)
                    / COUNT(attendance.id)) * 100 < 75 THEN 'Low'
               ELSE 'Safe'
           END AS status
    FROM attendance
    JOIN students ON attendance.student_id = students.id
    GROUP BY students.id
""")

        report = cursor.fetchall()
        cursor.close()

        return render_template('attendance_report.html', report=report)

    return redirect('/login')

# =============================
# MARKS MODULE
# =============================

@app.route('/marks', methods=['GET', 'POST'])
def marks():
    if 'role' in session:
        cursor = mysql.connection.cursor()

        if request.method == 'POST':
            student_id = request.form['student_id']
            subject = request.form['subject']
            mark = request.form['marks']

            cursor.execute("""
                INSERT INTO marks (student_id, subject, marks)
                VALUES (%s, %s, %s)
            """, (student_id, subject, mark))

            mysql.connection.commit()

        cursor.execute("""
            SELECT marks.id, students.name, students.roll_number,
                   marks.subject, marks.marks
            FROM marks
            JOIN students ON marks.student_id = students.id
        """)
        records = cursor.fetchall()

        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        cursor.close()

        return render_template(
            'marks.html',
            students=students,
            records=records
        )

    return redirect('/login')


@app.route('/result_report')
def result_report():
    if 'role' in session:
        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT students.name,
           students.roll_number,
           SUM(marks.marks) AS total,
           AVG(marks.marks) AS average,
           CASE 
               WHEN AVG(marks.marks) >= 40 THEN 'Pass'
               ELSE 'Fail'
           END AS result,
           CASE
               WHEN AVG(marks.marks) >= 75 THEN 'Excellent'
               WHEN AVG(marks.marks) >= 50 THEN 'Average'
               ELSE 'Poor'
           END AS performance
    FROM marks
    JOIN students ON marks.student_id = students.id
    GROUP BY students.id
""")

        report = cursor.fetchall()
        cursor.close()

        return render_template('result_report.html', report=report)

    return redirect('/login')

@app.route('/at_risk')
def at_risk_students():
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT students.name,
           students.roll_number,
           IFNULL(AVG(marks.marks), 0),
           IFNULL(
               (SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END)
                / COUNT(attendance.id)) * 100,
               0
           )
    FROM students
    LEFT JOIN marks ON students.id = marks.student_id
    LEFT JOIN attendance ON students.id = attendance.student_id
    GROUP BY students.id
    HAVING 
        IFNULL(AVG(marks.marks), 0) < 40 
        OR IFNULL(
            (SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END)
             / COUNT(attendance.id)) * 100,
            0
        ) < 75
""")

    data = cursor.fetchall()

    return render_template('at_risk.html', data=data)


# =============================
# RUN APP
# =============================

if __name__ == "__main__":
    app.run(debug=True)