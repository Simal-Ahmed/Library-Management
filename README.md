# 📚 Library Management System

A full-stack **Library Management System** built with **Flask** and **MySQL** as a DBMS mini project. Manage books, members, borrow records, fines, and generate professional daily activity reports — all from a single clean dashboard.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Setup and Installation](#setup-and-installation)
- [Usage](#usage)
- [PDF Report](#pdf-report)
- [Screenshots](#screenshots)
- [Known Limitations](#known-limitations)
- [License](#license)

---

## Overview

This project is a web-based library management application that handles the complete lifecycle of library operations — from registering members and adding books, to issuing, returning, tracking overdue records, collecting fines, and generating a downloadable end-of-day PDF report.

Built as a college DBMS mini project using **Python Flask** for the backend and **MySQL** for the relational database.

---

## Features

### 📖 Book Management
- Add books with author, category, and quantity
- View all books with availability status
- Quantity auto-updates on issue and return
- Search books by title, author, or category

### 👤 Member Management
- Register new library members (name, email, phone)
- View all members with search
- Safe delete — blocked if member has active issues, unpaid fines, or borrow history

### 🔄 Borrow Operations
- Issue available books to members with issue date
- Tracks expected return date (7-day loan period)
- Return books with actual return date
- Overdue detection — flags books past expected return date

### 💰 Fine Management
- Auto-calculates fine on return: **₹10 per extra day** after 7 days
- View all fines with member name, book, amount, and payment status
- Pay fine with confirmation dialog and live status update

### 📊 Reports
- Web-based end-of-day activity report with summary stats
- Searchable transaction table with issue ID, member, book, dates, status, fine, and overdue columns
- **Downloadable professional PDF report** (Times New Roman, Word-style layout) with:
  - Summary overview
  - Full borrow/return records table
  - Pending fine summary
  - Remarks section
  - Authorization sign-off block with header and footer on every page

### 🏗️ Setup Pages
- Add Authors (with duplicate check)
- Add Categories (with duplicate check)
- Authors and categories are linked to books via foreign keys

---

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Backend    | Python 3, Flask                     |
| Database   | MySQL 8                             |
| ORM/DB     | mysql-connector-python              |
| PDF        | ReportLab                           |
| Frontend   | HTML5, CSS3 (custom dark theme)     |
| Templating | Jinja2 (Flask)                      |

---

## Project Structure

```
library_project/
│
├── app.py
├── library_db.sql
├── README.md
│
├── templates/
│   ├── index.html
│   ├── navbar.html
│   ├── add_book.html
│   ├── add_member.html
│   ├── add_author.html
│   ├── add_category.html
│   ├── view_books.html
│   ├── view_members.html
│   ├── issue_book.html
│   ├── return_book.html
│   ├── view_fines.html
│   ├── borrow_records.html
│   └── reports.html
│
└── static/
    └── style.css
```

---

## Database Schema

```
authors        — author_id, name
categories     — category_id, category_name
books          — book_id, title, author_id (FK), category_id (FK), quantity
members        — member_id, name, email, phone
issued_books   — issue_id, book_id (FK), member_id (FK), issue_date, return_date, status
fines          — fine_id, issue_id (FK), amount, paid_status
```

**Relationships:**
- `books` → `authors` (many-to-one)
- `books` → `categories` (many-to-one)
- `issued_books` → `books` (many-to-one)
- `issued_books` → `members` (many-to-one)
- `fines` → `issued_books` (one-to-one)

---

## Setup and Installation

### Prerequisites

- Python 3.8 or higher
- MySQL 8.0 or higher
- pip

### Step 1 — Clone the repository

```bash
git clone https://github.com/Simal-Ahmed/Library-Management.git
cd Library-Management
```

### Step 2 — Install Python dependencies

```bash
pip install flask mysql-connector-python reportlab
```

### Step 3 — Set up the database

Log in to MySQL and run the provided SQL dump:

```bash
mysql -u root -p
```

```sql
CREATE DATABASE IF NOT EXISTS library_db;
USE library_db;
SOURCE library_db.sql;
```

Or import directly from the terminal:

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS library_db;"
mysql -u root -p library_db < library_db.sql
```

This will create all tables and seed authors and categories automatically.

### Step 4 — Configure database credentials

Open `app.py` and update the connection block with your MySQL credentials:

```python
db = mysql.connector.connect(
    host="localhost",
    user="your_mysql_username",
    password="your_mysql_password",
    database="library_db"
)
```

### Step 5 — Run the application

```bash
python app.py
```

Open your browser and go to:

```
http://127.0.0.1:5000
```

---

## Usage

### Getting started after setup:

1. **Add categories** — Go to *Add Category* and add book genres (e.g., Science, Fiction)
2. **Add authors** — Go to *Add Author* and add author names
3. **Add books** — Go to *Add Book*, select author and category, enter quantity
4. **Add members** — Go to *Add Member*, fill in name, email, and phone
5. **Issue a book** — Go to *Issue Book*, select book and member, set issue date
6. **Return a book** — Go to *Return Book*, select the issued record, enter return date
7. **Pay fines** — Go to *View Fines* and click *Pay Now* on unpaid records
8. **Generate report** — Go to *Reports* and click *Generate PDF Report*

### Fine calculation rule:
- Loan period: **7 days**
- Fine rate: **₹10 per day** after the 7-day window
- Example: Returned on day 11 → (11 − 7) × ₹10 = **₹40 fine**

---

## PDF Report

Clicking **Generate PDF Report** on the Reports page triggers the `/generate_report_pdf` route, which:

1. Queries live data from the database
2. Builds a professional A4 PDF using ReportLab with:
   - **Header** — library name + double rule on every page
   - **Footer** — confidential notice, report date, page number on every page
   - **Section 1** — Summary overview (two-column table)
   - **Section 2** — Full borrow/return records table (9 columns, alternating row shading)
   - **Section 3** — Pending fine summary with total row
   - **Section 4** — Remarks paragraph
   - **Section 5** — Authorization block (Prepared by / Verified by / Approved by)
3. Streams the PDF directly to the browser as a download — **nothing is saved on disk**

---

## Known Limitations

- The global MySQL `cursor` is shared across requests — not safe for concurrent users in production. For production use, switch to a connection pool (e.g., `mysql.connector.pooling` or SQLAlchemy).
- No login or authentication — this is an admin-only local tool intended for college project demonstration.
- `int(request.form['quantity'])` in `add_book` can raise `ValueError` if the form is bypassed. Add a try/except for robustness.
- The database connection may drop after MySQL's `wait_timeout` (8 hours by default). Restart the app or add a reconnect guard for long-running sessions.

---

## License

This project is created for academic and learning purposes.

---

> Built as a DBMS Mini Project — Flask + MySQL  
> Feel free to fork, use, or improve it.
