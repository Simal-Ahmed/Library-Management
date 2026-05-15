from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from datetime import datetime
import mysql.connector
import io
import os



app = Flask(__name__)

LOAN_DAYS = 7
FINE_PER_DAY = 10

# DB Connection
db = mysql.connector.connect(
    host="localhost",
    user="SIMAL",
    password="Simal@123",
    database="library_db"
)

cursor = db.cursor()


@app.route('/')
def home():

    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT IFNULL(SUM(quantity), 0) FROM books")
    available_books = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM members")
    total_members = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM issued_books WHERE status='issued'")
    issued_books = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM issued_books WHERE status='returned'")
    returned_books = cursor.fetchone()[0]

    cursor.execute("SELECT IFNULL(SUM(amount), 0) FROM fines WHERE paid_status='unpaid'")
    pending_fines = cursor.fetchone()[0]

    cursor.execute("SELECT IFNULL(SUM(amount), 0) FROM fines WHERE paid_status='paid'")
    fine_collected = cursor.fetchone()[0]

    return render_template(
        'index.html',
        total_books=total_books,
        available_books=available_books,
        total_members=total_members,
        issued_books=issued_books,
        returned_books=returned_books,
        pending_fines=pending_fines,
        fine_collected=fine_collected
    )


# Add Book
@app.route('/add_book', methods=['GET', 'POST'])
def add_book():

    message = None
    message_type = None

    cursor.execute("""
        SELECT author_id, name
        FROM authors
        ORDER BY name
    """)
    authors = cursor.fetchall()

    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
        ORDER BY category_name
    """)
    categories = cursor.fetchall()

    if request.method == 'POST':
        title = request.form['title']
        author_id = request.form['author_id']
        category_id = request.form['category_id']
        quantity = int(request.form['quantity'])

        if quantity < 0:
            message = "Quantity cannot be negative."
            message_type = "error"

            return render_template(
                'add_book.html',
                message=message,
                message_type=message_type,
                authors=authors,
                categories=categories
            )

        cursor.execute(
            """
            INSERT INTO books (
                title,
                author_id,
                category_id,
                quantity
            )
            VALUES (%s, %s, %s, %s)
            """,
            (title, author_id, category_id, quantity)
        )

        db.commit()

        return redirect(url_for('home'))

    return render_template(
        'add_book.html',
        message=message,
        message_type=message_type,
        authors=authors,
        categories=categories
    )


# Add Member
@app.route('/add_member', methods=['GET', 'POST'])
def add_member():

    message = None
    message_type = None

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        cursor.execute(
            """
            INSERT INTO members (
                name,
                email,
                phone
            )
            VALUES (%s, %s, %s)
            """,
            (name, email, phone)
        )

        db.commit()

        return redirect(url_for('home'))

    return render_template(
        'add_member.html',
        message=message,
        message_type=message_type
    )


# Issue Book
@app.route('/issue_book', methods=['GET', 'POST'])
def issue_book():

    message = None
    message_type = None

    cursor.execute("""
        SELECT book_id, title, quantity
        FROM books
        ORDER BY title
    """)
    books = cursor.fetchall()

    cursor.execute("""
        SELECT member_id, name
        FROM members
        ORDER BY name
    """)
    members = cursor.fetchall()

    if request.method == 'POST':
        book_id = request.form['book_id']
        member_id = request.form['member_id']
        issue_date = request.form['issue_date']

        cursor.execute(
            "SELECT quantity FROM books WHERE book_id = %s",
            (book_id,)
        )

        book = cursor.fetchone()

        if book is None:
            message = "Invalid Book selected."
            message_type = "error"

            return render_template(
                'issue_book.html',
                message=message,
                message_type=message_type,
                books=books,
                members=members
            )

        available_quantity = book[0]

        if available_quantity <= 0:

            cursor.execute(f"""
                SELECT DATE_ADD(issue_date, INTERVAL {LOAN_DAYS} DAY)
                FROM issued_books
                WHERE book_id = %s AND status = 'issued'
                ORDER BY issue_date ASC
                LIMIT 1
            """, (book_id,))

            expected_date = cursor.fetchone()

            if expected_date:
                message = f"Book is currently not available. Please check after {expected_date[0]}."
            else:
                message = "Book is currently not available."

            message_type = "error"

            return render_template(
                'issue_book.html',
                message=message,
                message_type=message_type,
                books=books,
                members=members
            )

        cursor.execute(
            """
            INSERT INTO issued_books (
                book_id,
                member_id,
                issue_date,
                status
            )
            VALUES (%s, %s, %s, 'issued')
            """,
            (book_id, member_id, issue_date)
        )

        cursor.execute(
            "UPDATE books SET quantity = quantity - 1 WHERE book_id = %s",
            (book_id,)
        )

        db.commit()

        return redirect(url_for('home'))

    return render_template(
        'issue_book.html',
        message=message,
        message_type=message_type,
        books=books,
        members=members
    )


# Return Book
@app.route('/return_book', methods=['GET', 'POST'])
def return_book():

    message = None
    message_type = None

    cursor.execute("""
        SELECT 
            issued_books.issue_id,
            members.name,
            books.title,
            issued_books.issue_date
        FROM issued_books
        JOIN members ON issued_books.member_id = members.member_id
        JOIN books ON issued_books.book_id = books.book_id
        WHERE issued_books.status = 'issued'
        ORDER BY issued_books.issue_id DESC
    """)

    issued_records = cursor.fetchall()

    if request.method == 'POST':
        issue_id = request.form['issue_id']
        return_date = request.form['return_date']

        cursor.execute(
            """
            SELECT book_id, issue_date, status
            FROM issued_books
            WHERE issue_id=%s
            """,
            (issue_id,)
        )

        issue_data = cursor.fetchone()

        if issue_data is None:
            message = "Invalid issue record selected."
            message_type = "error"

            return render_template(
                'return_book.html',
                message=message,
                message_type=message_type,
                issued_records=issued_records
            )

        book_id = issue_data[0]
        issue_date = issue_data[1]
        current_status = issue_data[2]

        if current_status == 'returned':
            message = "This book has already been returned."
            message_type = "error"

            return render_template(
                'return_book.html',
                message=message,
                message_type=message_type,
                issued_records=issued_records
            )

        cursor.execute(
            """
            UPDATE issued_books
            SET return_date=%s,
                status='returned'
            WHERE issue_id=%s
            """,
            (return_date, issue_id)
        )

        cursor.execute(
            """
            UPDATE books
            SET quantity = quantity + 1
            WHERE book_id=%s
            """,
            (book_id,)
        )

        return_date_obj = datetime.strptime(
            return_date,
            "%Y-%m-%d"
        ).date()

        days = (return_date_obj - issue_date).days

        if days > LOAN_DAYS:
            fine_amount = (days - LOAN_DAYS) * FINE_PER_DAY

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

        return redirect(url_for('home'))

    return render_template(
        'return_book.html',
        message=message,
        message_type=message_type,
        issued_records=issued_records
    )


# View Fines
@app.route('/view_fines')
def view_fines():

    cursor.execute("""
        SELECT
            fines.fine_id,
            fines.issue_id,
            members.name,
            books.title,
            fines.amount,
            fines.paid_status
        FROM fines
        JOIN issued_books ON fines.issue_id = issued_books.issue_id
        JOIN members ON issued_books.member_id = members.member_id
        JOIN books ON issued_books.book_id = books.book_id
        ORDER BY fines.fine_id DESC
    """)

    fines_data = cursor.fetchall()

    return render_template(
        'view_fines.html',
        fines=fines_data
    )


# Pay Fine
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


# View Books
@app.route('/view_books')
def view_books():

    cursor.execute("""
        SELECT 
            books.book_id,
            books.title,
            authors.name,
            categories.category_name,
            books.quantity
        FROM books
        JOIN authors ON books.author_id = authors.author_id
        JOIN categories ON books.category_id = categories.category_id
        ORDER BY books.book_id DESC
    """)

    books = cursor.fetchall()

    return render_template(
        'view_books.html',
        books=books
    )


# View Members
@app.route('/view_members')
def view_members():

    error = request.args.get('error')

    cursor.execute("SELECT * FROM members")
    members = cursor.fetchall()

    return render_template(
        'view_members.html',
        members=members,
        error=error
    )


# Borrow Records
@app.route('/borrow_records')
def borrow_records():

    cursor.execute(f"""
        SELECT 
            issued_books.issue_id,
            members.name,
            books.title,
            issued_books.issue_date,
            DATE_ADD(issued_books.issue_date, INTERVAL {LOAN_DAYS} DAY) AS expected_return_date,
            issued_books.return_date,
            issued_books.status,
            CASE
                WHEN issued_books.status = 'issued'
                AND CURDATE() > DATE_ADD(issued_books.issue_date, INTERVAL {LOAN_DAYS} DAY)
                THEN 'overdue'
                ELSE 'not_overdue'
            END AS overdue_status
        FROM issued_books
        JOIN members ON issued_books.member_id = members.member_id
        JOIN books ON issued_books.book_id = books.book_id
        ORDER BY issued_books.issue_id DESC
    """)

    records = cursor.fetchall()

    return render_template(
        'borrow_records.html',
        records=records,
        loan_days=LOAN_DAYS
    )


# Reports
@app.route('/reports')
def reports():

    # Summary data
    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM members")
    total_members = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM issued_books
        WHERE status = 'issued'
    """)
    currently_issued = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM issued_books
        WHERE status = 'returned'
    """)
    returned_books = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT COUNT(*)
        FROM issued_books
        WHERE status = 'issued'
        AND CURDATE() > DATE_ADD(issue_date, INTERVAL {LOAN_DAYS} DAY)
    """)
    overdue_books = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM fines
        WHERE paid_status = 'paid'
    """)
    fine_collected = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM fines
        WHERE paid_status = 'unpaid'
    """)
    fine_due = cursor.fetchone()[0]

    # Detailed report data
    cursor.execute(f"""
        SELECT
            issued_books.issue_id,
            members.name,
            books.title,
            issued_books.issue_date,
            DATE_ADD(issued_books.issue_date, INTERVAL {LOAN_DAYS} DAY) AS expected_return_date,
            issued_books.return_date,
            issued_books.status,
            COALESCE(fines.amount, 0) AS fine_amount,
            COALESCE(fines.paid_status, 'No Fine') AS fine_status,
            CASE
                WHEN issued_books.status = 'issued'
                AND CURDATE() > DATE_ADD(issued_books.issue_date, INTERVAL {LOAN_DAYS} DAY)
                THEN 'overdue'
                ELSE 'not_overdue'
            END AS overdue_status
        FROM issued_books
        JOIN members ON issued_books.member_id = members.member_id
        JOIN books ON issued_books.book_id = books.book_id
        LEFT JOIN fines ON issued_books.issue_id = fines.issue_id
        ORDER BY issued_books.issue_id DESC
    """)


    report_data = cursor.fetchall()

    generated_on = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    return render_template(
    'reports.html',
    total_books=total_books,
    total_members=total_members,
    currently_issued=currently_issued,
    returned_books=returned_books,
    overdue_books=overdue_books,
    fine_collected=fine_collected,
    fine_due=fine_due,
    report_data=report_data,
    loan_days=LOAN_DAYS,
    generated_on=generated_on
)


@app.route('/generate_report_pdf')
def generate_report_pdf():

    generated_on = datetime.now().strftime("%d %b %Y,  %I:%M %p")
    report_date  = datetime.now().strftime("%d %B %Y")

    # ── same DB queries you already have ────────────────────────────────
    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM books")
    available_books = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM members")
    total_members = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM issued_books WHERE status='issued'")
    currently_issued = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM issued_books WHERE status='returned'")
    returned_books = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM issued_books
        WHERE status='issued'
        AND DATE_ADD(issue_date, INTERVAL %s DAY) < CURDATE()
    """, (LOAN_DAYS,))
    overdue_books = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount),0) FROM fines WHERE paid_status='unpaid'")
    fine_due = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount),0) FROM fines WHERE paid_status='paid'")
    fine_collected = cursor.fetchone()[0]

    cursor.execute("""
        SELECT ib.issue_id, m.name, b.title,
               ib.issue_date,
               DATE_ADD(ib.issue_date, INTERVAL %s DAY),
               ib.return_date, ib.status,
               COALESCE(f.amount, 0),
               COALESCE(f.paid_status, '-')
        FROM issued_books ib
        JOIN members m  ON ib.member_id = m.member_id
        JOIN books   b  ON ib.book_id   = b.book_id
        LEFT JOIN fines f ON ib.issue_id = f.issue_id
        ORDER BY ib.issue_id DESC
    """, (LOAN_DAYS,))
    borrow_records = cursor.fetchall()

    cursor.execute("""
        SELECT m.name, b.title, f.amount
        FROM fines f
        JOIN issued_books ib ON f.issue_id    = ib.issue_id
        JOIN members      m  ON ib.member_id  = m.member_id
        JOIN books        b  ON ib.book_id    = b.book_id
        WHERE f.paid_status = 'unpaid'
        ORDER BY f.fine_id DESC
    """)
    pending_fines     = cursor.fetchall()
    total_pending_fine = sum(row[2] for row in pending_fines)

    # ── palette ─────────────────────────────────────────────────────────
    BLACK      = colors.black
    DARK_GRAY  = colors.HexColor("#222222")
    MID_GRAY   = colors.HexColor("#555555")
    LIGHT_GRAY = colors.HexColor("#aaaaaa")
    TABLE_HEAD = colors.HexColor("#1a1a2e")
    ROW_ALT    = colors.HexColor("#f5f5f5")
    WHITE      = colors.white
    PAGE_W     = A4[0]
    MARGIN     = 25 * mm

    # ── style helpers ────────────────────────────────────────────────────
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    sLibName  = S("sLibName",  fontName="Times-Bold",   fontSize=17, textColor=BLACK,     leading=22, alignment=TA_CENTER)
    sBranch   = S("sBranch",   fontName="Times-Roman",  fontSize=9,  textColor=DARK_GRAY, leading=13, alignment=TA_CENTER)
    sRepTitle = S("sRepTitle", fontName="Times-Bold",   fontSize=13, textColor=BLACK,     leading=17, alignment=TA_CENTER, spaceBefore=4)
    sRepDate  = S("sRepDate",  fontName="Times-Roman",  fontSize=9,  textColor=MID_GRAY,  leading=12, alignment=TA_CENTER)
    sSect     = S("sSect",     fontName="Times-Bold",   fontSize=11, textColor=BLACK,     leading=14, spaceBefore=6)
    sBody     = S("sBody",     fontName="Times-Roman",  fontSize=9,  textColor=DARK_GRAY, leading=13, alignment=TA_JUSTIFY)
    sSmLbl    = S("sSmLbl",    fontName="Times-Roman",  fontSize=9,  textColor=DARK_GRAY, leading=12, alignment=TA_LEFT)
    sSmVal    = S("sSmVal",    fontName="Times-Bold",   fontSize=9,  textColor=BLACK,     leading=12, alignment=TA_RIGHT)
    sTH       = S("sTH",   fontName="Helvetica-Bold",  fontSize=7.5, textColor=WHITE,     leading=10, alignment=TA_CENTER)
    sTD       = S("sTD",   fontName="Helvetica",        fontSize=7.5, textColor=DARK_GRAY, leading=10, alignment=TA_CENTER)
    sTDL      = S("sTDL",  fontName="Helvetica",        fontSize=7.5, textColor=DARK_GRAY, leading=10, alignment=TA_LEFT)
    sTDB      = S("sTDB",  fontName="Helvetica-Bold",   fontSize=7.5, textColor=DARK_GRAY, leading=10, alignment=TA_CENTER)
    sSignLbl  = S("sSignLbl",  fontName="Times-Roman",  fontSize=9,  textColor=DARK_GRAY, leading=12, alignment=TA_LEFT)
    sSignLine = S("sSignLine", fontName="Times-Roman",  fontSize=9,  textColor=DARK_GRAY, leading=20, alignment=TA_LEFT)
    sSignRole = S("sSignRole", fontName="Times-Italic", fontSize=8,  textColor=MID_GRAY,  leading=11, alignment=TA_LEFT)

    # ── header / footer drawn on every page ──────────────────────────────
    def draw_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = A4
        y = h - MARGIN + 4*mm

        canvas_obj.setFont("Times-Bold", 17)
        canvas_obj.setFillColor(BLACK)
        canvas_obj.drawCentredString(w / 2, y, "Library Management System")

        canvas_obj.setFont("Times-Roman", 9)
        canvas_obj.setFillColor(DARK_GRAY)
        canvas_obj.drawCentredString(w / 2, y - 13, "Main Branch")

        canvas_obj.setStrokeColor(BLACK)
        canvas_obj.setLineWidth(1.2)
        canvas_obj.line(MARGIN, y - 20, w - MARGIN, y - 20)
        canvas_obj.setLineWidth(0.4)
        canvas_obj.line(MARGIN, y - 22.5, w - MARGIN, y - 22.5)

        # footer
        canvas_obj.setLineWidth(1)
        canvas_obj.line(MARGIN, 20*mm, w - MARGIN, 20*mm)
        canvas_obj.setLineWidth(0.3)
        canvas_obj.line(MARGIN, 19.2*mm, w - MARGIN, 19.2*mm)

        canvas_obj.setFont("Times-Roman", 7.5)
        canvas_obj.setFillColor(MID_GRAY)
        canvas_obj.drawString(MARGIN, 15.5*mm, "Library Management System  |  Confidential — For Internal Use Only")
        canvas_obj.drawCentredString(w / 2, 15.5*mm, report_date)
        canvas_obj.drawRightString(w - MARGIN, 15.5*mm, f"Page {doc_obj.page}")

        canvas_obj.setFont("Times-Roman", 6.5)
        canvas_obj.drawRightString(w - MARGIN, 11.5*mm, f"Generated on: {generated_on}")
        canvas_obj.restoreState()

    # ── build PDF into memory buffer ─────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=38*mm,   bottomMargin=30*mm,
        title=f"Library Report – {report_date}",
    )

    inner_w = PAGE_W - 2 * MARGIN
    story   = []

    # title block
    story.append(Paragraph("Daily Activity Report", sRepTitle))
    story.append(Paragraph(f"Date: {report_date}", sRepDate))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    story.append(Spacer(1, 5*mm))

    # ── 1. Summary ───────────────────────────────────────────────────────
    story.append(Paragraph("1.  Summary Overview", sSect))
    story.append(Spacer(1, 3*mm))

    summary_items = [
        ("Total Book Titles",    str(total_books)),
        ("Available Books",      str(available_books)),
        ("Total Members",        str(total_members)),
        ("Currently Issued",     str(currently_issued)),
        ("Returned Books",       str(returned_books)),
        ("Overdue Books",        str(overdue_books)),
        ("Pending Fines (Rs.)",  str(fine_due)),
        ("Fine Collected (Rs.)", str(fine_collected)),
    ]
    half = len(summary_items) // 2 + len(summary_items) % 2
    left_col  = summary_items[:half]
    right_col = summary_items[half:] + [("", "")] * (half - len(summary_items[half:]))

    def mini_tbl(items):
        rows = [[Paragraph(l, sSmLbl), Paragraph(v, sSmVal)] for l, v in items]
        t = Table(rows, colWidths=[55*mm, 20*mm])
        t.setStyle(TableStyle([
            ("LINEBELOW",     (0,0), (-1,-2), 0.3, LIGHT_GRAY),
            ("LINEBELOW",     (0,-1),(-1,-1), 0.6, BLACK),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 2),
            ("RIGHTPADDING",  (0,0), (-1,-1), 2),
        ]))
        return t

    col_w = (inner_w - 10*mm) / 2
    sum_tbl = Table([[mini_tbl(left_col), mini_tbl(right_col)]], colWidths=[col_w, col_w])
    sum_tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 7*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    story.append(Spacer(1, 5*mm))

    # ── 2. Borrow & Return Records ───────────────────────────────────────
    story.append(Paragraph("2.  Borrow and Return Records", sSect))
    story.append(Spacer(1, 3*mm))

    col_widths = [13*mm, 28*mm, 35*mm, 18*mm, 18*mm, 18*mm, 15*mm, 14*mm, 15*mm]
    headers    = ["Issue\nID", "Member", "Book Title", "Issue\nDate",
                  "Exp.\nReturn", "Return\nDate", "Status", "Fine\n(Rs.)", "Fine\nStatus"]

    rows = [[Paragraph(h, sTH) for h in headers]]
    for i, row in enumerate(borrow_records):
        ret_date   = str(row[5]) if row[5] else "—"
        fine_st    = str(row[8]).title() if row[8] != "-" else "—"
        rows.append([
            Paragraph(str(row[0]), sTDB),
            Paragraph(str(row[1]), sTDL),
            Paragraph(str(row[2]), sTDL),
            Paragraph(str(row[3]), sTD),
            Paragraph(str(row[4]), sTD),
            Paragraph(ret_date,    sTD),
            Paragraph(str(row[6]).title(), sTD),
            Paragraph(str(row[7]), sTDB),
            Paragraph(fine_st,     sTD),
        ])

    row_bg = [("BACKGROUND", (0,i), (-1,i), ROW_ALT if i % 2 == 0 else WHITE)
              for i in range(1, len(rows))]

    rec_tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    rec_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  TABLE_HEAD),
        ("LINEBELOW",     (0,0), (-1,0),  1.2, BLACK),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
        ("BOX",           (0,0), (-1,-1), 0.8, BLACK),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        *row_bg,
    ]))
    story.append(rec_tbl)
    story.append(Spacer(1, 7*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    story.append(Spacer(1, 5*mm))

    # ── 3. Pending Fine Summary ──────────────────────────────────────────
    story.append(Paragraph("3.  Pending Fine Summary", sSect))
    story.append(Spacer(1, 3*mm))

    fine_col_w = [55*mm, 80*mm, 38*mm]
    fine_rows  = [[Paragraph(h, sTH) for h in ["Member Name", "Book Title", "Fine Amount (Rs.)"]]]
    for member, book, amt in pending_fines:
        fine_rows.append([Paragraph(str(member), sTDL), Paragraph(str(book), sTDL), Paragraph(str(amt), sTDB)])
    fine_rows.append([
        Paragraph("", sTD),
        Paragraph("<b>Total Pending Fine</b>", S("tp", fontName="Times-Bold", fontSize=8.5, textColor=BLACK, leading=11, alignment=TA_RIGHT)),
        Paragraph(f"<b>Rs. {total_pending_fine}</b>", S("tv", fontName="Times-Bold", fontSize=8.5, textColor=BLACK, leading=11, alignment=TA_CENTER)),
    ])

    fine_row_bg = [("BACKGROUND", (0,i), (-1,i), ROW_ALT if i % 2 == 0 else WHITE)
                   for i in range(1, len(fine_rows) - 1)]
    fine_tbl = Table(fine_rows, colWidths=fine_col_w, repeatRows=1)
    fine_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),   TABLE_HEAD),
        ("LINEBELOW",     (0,0),  (-1,0),   1.2, BLACK),
        ("BACKGROUND",    (0,-1), (-1,-1),  colors.HexColor("#eeeeee")),
        ("LINEABOVE",     (0,-1), (-1,-1),  0.8, BLACK),
        ("LINEBELOW",     (0,-1), (-1,-1),  0.8, BLACK),
        ("GRID",          (0,0),  (-1,-2),  0.4, colors.HexColor("#cccccc")),
        ("BOX",           (0,0),  (-1,-1),  0.8, BLACK),
        ("TOPPADDING",    (0,0),  (-1,-1),  4),
        ("BOTTOMPADDING", (0,0),  (-1,-1),  4),
        ("LEFTPADDING",   (0,0),  (-1,-1),  5),
        ("RIGHTPADDING",  (0,0),  (-1,-1),  5),
        ("VALIGN",        (0,0),  (-1,-1),  "MIDDLE"),
        *fine_row_bg,
    ]))
    story.append(fine_tbl)
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    story.append(Spacer(1, 7*mm))

    # ── 4. Remarks ───────────────────────────────────────────────────────
    story.append(KeepTogether([
        Paragraph("4.  Remarks", sSect),
        Spacer(1, 3*mm),
        Paragraph(
            "This report summarizes the library borrowing activity, return records, overdue books, "
            "pending fines, and fine collection status. Members with pending fines are required to "
            "clear dues at the earliest. The librarian on duty should verify the report before submission.",
            sBody
        ),
        Spacer(1, 10*mm),
    ]))

    # ── 5. Authorization ─────────────────────────────────────────────────
    col_w3   = inner_w / 3
    sig_rows = [
        [Paragraph(l + ":", sSignLbl)  for l in ["Prepared by", "Verified by", "Approved by"]],
        [Paragraph("\n\n________________________", sSignLine) for _ in range(3)],
        [Paragraph(r, sSignRole)        for r in ["Library Staff", "Senior Librarian", "Head of Library"]],
        [Paragraph("Date: _____________", S("sd", fontName="Times-Roman", fontSize=8, textColor=MID_GRAY, leading=12, alignment=TA_LEFT)) for _ in range(3)],
    ]
    sig_tbl = Table(sig_rows, colWidths=[col_w3]*3)
    sig_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
    ]))
    story.append(KeepTogether([
        Paragraph("5.  Authorization", sSect),
        Spacer(1, 5*mm),
        sig_tbl,
    ]))

    # ── build and send ───────────────────────────────────────────────────
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)

    filename = f"Library_Report_{datetime.now().strftime('%d-%m-%Y')}.pdf"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/pdf")


# Add Author
@app.route('/add_author', methods=['GET', 'POST'])
def add_author():

    message = None
    message_type = None

    if request.method == 'POST':
        author_name = request.form['author_name']

        # Check if author already exists
        cursor.execute(
            """
            SELECT author_id
            FROM authors
            WHERE name = %s
            """,
            (author_name,)
        )

        existing_author = cursor.fetchone()

        if existing_author:
            message = "This author already exists."
            message_type = "error"

            return render_template(
                'add_author.html',
                message=message,
                message_type=message_type
            )

        cursor.execute(
            """
            INSERT INTO authors (name)
            VALUES (%s)
            """,
            (author_name,)
        )

        db.commit()

        return redirect(url_for('home'))

    return render_template(
        'add_author.html',
        message=message,
        message_type=message_type
    )


# Add Category
@app.route('/add_category', methods=['GET', 'POST'])
def add_category():

    message = None
    message_type = None

    if request.method == 'POST':
        category_name = request.form['category_name']

        # Check if category already exists
        cursor.execute(
            """
            SELECT category_id
            FROM categories
            WHERE category_name = %s
            """,
            (category_name,)
        )

        existing_category = cursor.fetchone()

        if existing_category:
            message = "This category already exists."
            message_type = "error"

            return render_template(
                'add_category.html',
                message=message,
                message_type=message_type
            )

        cursor.execute(
            """
            INSERT INTO categories (category_name)
            VALUES (%s)
            """,
            (category_name,)
        )

        db.commit()

        return redirect(url_for('home'))

    return render_template(
        'add_category.html',
        message=message,
        message_type=message_type
    )


# Delete Member
@app.route('/delete_member/<int:member_id>', methods=['POST'])
def delete_member(member_id):

    # Check if member has currently issued books
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM issued_books
        WHERE member_id = %s
        AND status = 'issued'
        """,
        (member_id,)
    )

    issued_count = cursor.fetchone()[0]

    if issued_count > 0:
        return redirect(url_for(
            'view_members',
            error='Cannot delete member. This member has currently issued books.'
        ))

    # Check if member has unpaid fines
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fines
        JOIN issued_books ON fines.issue_id = issued_books.issue_id
        WHERE issued_books.member_id = %s
        AND fines.paid_status = 'unpaid'
        """,
        (member_id,)
    )

    unpaid_fine_count = cursor.fetchone()[0]

    if unpaid_fine_count > 0:
        return redirect(url_for(
            'view_members',
            error='Cannot delete member. This member has unpaid fines.'
        ))

    # Check if member has any borrow history
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM issued_books
        WHERE member_id = %s
        """,
        (member_id,)
    )

    history_count = cursor.fetchone()[0]

    if history_count > 0:
        return redirect(url_for(
            'view_members',
            error='Cannot delete member. This member has previous borrow history, so deletion is not allowed to protect reports.'
        ))

    # Delete member only if no dependency exists
    cursor.execute(
        """
        DELETE FROM members
        WHERE member_id = %s
        """,
        (member_id,)
    )

    db.commit()

    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)