from flask import Flask, render_template, request, redirect
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# DB Connection
db = mysql.connector.connect(
    host="localhost",
    user="SIMAL",
    password="Simal@123",
    database="library_db"
)

cursor = db.cursor()


# Home
@app.route('/')
def home():
    return render_template('index.html')


# Add Book
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author_id = request.form['author_id']
        category_id = request.form['category_id']
        quantity = request.form['quantity']

        query = """
        INSERT INTO books (title, author_id, category_id, quantity)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (title, author_id, category_id, quantity)
        )

        db.commit()

        return redirect('/')

    return render_template('add_book.html')


# Add Member
@app.route('/add_member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        query = """
        INSERT INTO members (name, email, phone)
        VALUES (%s, %s, %s)
        """

        cursor.execute(query, (name, email, phone))
        db.commit()

        return redirect('/')

    return render_template('add_member.html')


# Issue Book
@app.route('/issue_book', methods=['GET', 'POST'])
def issue_book():
    if request.method == 'POST':
        book_id = request.form['book_id']
        member_id = request.form['member_id']
        issue_date = request.form['issue_date']

        query = """
        INSERT INTO issued_books (
            book_id,
            member_id,
            issue_date,
            status
        )
        VALUES (%s, %s, %s, 'issued')
        """

        cursor.execute(
            query,
            (book_id, member_id, issue_date)
        )

        db.commit()

        return redirect('/')

    return render_template('issue_book.html')


# Return Book
@app.route('/return_book', methods=['GET', 'POST'])
def return_book():
    if request.method == 'POST':
        issue_id = request.form['issue_id']
        return_date = request.form['return_date']

        # Update return date + status
        cursor.execute(
            """
            UPDATE issued_books
            SET return_date=%s,
                status='returned'
            WHERE issue_id=%s
            """,
            (return_date, issue_id)
        )

        # Get issue date
        cursor.execute(
            """
            SELECT issue_date
            FROM issued_books
            WHERE issue_id=%s
            """,
            (issue_id,)
        )

        issue_date = cursor.fetchone()[0]

        # Calculate fine (₹10 per day after 7 days)
        return_date_obj = datetime.strptime(
            return_date,
            "%Y-%m-%d"
        ).date()

        days = (return_date_obj - issue_date).days

        fine_amount = 0

        if days > 7:
            fine_amount = (days - 7) * 10

            cursor.execute(
                """
                INSERT INTO fines (
                    issue_id,
                    amount,
                    paid_status
                )
                VALUES (%s, %s, 'unpaid')
                """,
                (issue_id, fine_amount)
            )

        db.commit()

        return redirect('/')

    return render_template('return_book.html')


# ---------------------------------------------------
# Add Route Properly in app.py
# Paste this BELOW your other routes and ABOVE:
# if __name__ == '__main__':
# ---------------------------------------------------

@app.route('/view_fines')
def view_fines():

    cursor.execute("""
        SELECT fine_id,
               issue_id,
               amount,
               paid_status
        FROM fines
    """)

    fines_data = cursor.fetchall()

    return render_template(
        'view_fines.html',
        fines=fines_data
    )


@app.route('/pay_fine/<int:fine_id>', methods=['POST'])
def pay_fine(fine_id):

    cursor.execute(
        """
        UPDATE fines
        SET paid_status='paid'
        WHERE fine_id=%s
        """,
        (fine_id,)
    )

    db.commit()

    return {'success': True}


if __name__ == '__main__':
    app.run(debug=True)