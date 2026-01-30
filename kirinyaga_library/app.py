from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kirinyaga-library-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Database Models
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    publisher = db.Column(db.String(100))
    publication_year = db.Column(db.Integer)
    category = db.Column(db.String(50))
    edition = db.Column(db.String(20))
    total_copies = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)
    shelf_location = db.Column(db.String(20))
    date_added = db.Column(db.DateTime, default=datetime.now)


class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    course = db.Column(db.String(100))
    registration_number = db.Column(db.String(50), unique=True)
    membership_type = db.Column(db.String(20), default='student')  # student, staff, faculty
    join_date = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='active')  # active, suspended, graduated


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='librarian')  # admin, librarian
    created_at = db.Column(db.DateTime, default=datetime.now)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(30), unique=True, nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.now)
    due_date = db.Column(db.DateTime)
    return_date = db.Column(db.DateTime)
    fine_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='issued')  # issued, returned, overdue
    renewed = db.Column(db.Integer, default=0)

    book = db.relationship('Book', backref='transactions')
    member = db.relationship('Member', backref='transactions')


class Fine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'))
    amount = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, paid, waived
    due_date = db.Column(db.DateTime)
    payment_date = db.Column(db.DateTime)

    transaction = db.relationship('Transaction', backref='fine_details')


# Authentication Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Get statistics
    total_books = Book.query.count()
    total_members = Member.query.count()
    issued_books = Transaction.query.filter_by(status='issued').count()
    overdue_books = Transaction.query.filter(
        Transaction.due_date < datetime.now(),
        Transaction.status == 'issued'
    ).count()

    # Recent transactions
    recent_transactions = Transaction.query.order_by(
        Transaction.issue_date.desc()
    ).limit(10).all()

    # Popular books
    popular_books = db.session.query(
        Book, db.func.count(Transaction.id).label('issue_count')
    ).join(Transaction).group_by(Book.id).order_by(
        db.desc('issue_count')
    ).limit(5).all()

    return render_template('dashboard.html',
                           total_books=total_books,
                           total_members=total_members,
                           issued_books=issued_books,
                           overdue_books=overdue_books,
                           recent_transactions=recent_transactions,
                           popular_books=popular_books)


@app.route('/books')
@login_required
def books():
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    query = Book.query

    if search:
        query = query.filter(
            (Book.title.ilike(f'%{search}%')) |
            (Book.author.ilike(f'%{search}%')) |
            (Book.isbn.ilike(f'%{search}%'))
        )

    if category:
        query = query.filter(Book.category == category)

    books = query.order_by(Book.title).all()
    categories = db.session.query(Book.category).distinct().all()

    return render_template('books.html', books=books, categories=categories)


@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        try:
            book = Book(
                book_id=request.form.get('book_id'),
                title=request.form.get('title'),
                author=request.form.get('author'),
                isbn=request.form.get('isbn'),
                publisher=request.form.get('publisher'),
                publication_year=request.form.get('publication_year'),
                category=request.form.get('category'),
                edition=request.form.get('edition'),
                total_copies=int(request.form.get('total_copies', 1)),
                available_copies=int(request.form.get('total_copies', 1)),
                shelf_location=request.form.get('shelf_location')
            )

            db.session.add(book)
            db.session.commit()
            flash('Book added successfully!', 'success')
            return redirect(url_for('books'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding book: {str(e)}', 'danger')

    return render_template('add_book.html')


@app.route('/members')
@login_required
def members():
    search = request.args.get('search', '')
    department = request.args.get('department', '')

    query = Member.query

    if search:
        query = query.filter(
            (Member.first_name.ilike(f'%{search}%')) |
            (Member.last_name.ilike(f'%{search}%')) |
            (Member.registration_number.ilike(f'%{search}%'))
        )

    if department:
        query = query.filter(Member.department == department)

    members = query.order_by(Member.first_name).all()
    departments = db.session.query(Member.department).distinct().all()

    return render_template('members.html', members=members, departments=departments)


@app.route('/add_member', methods=['GET', 'POST'])
@login_required
def add_member():
    if request.method == 'POST':
        try:
            member = Member(
                member_id=request.form.get('member_id'),
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                department=request.form.get('department'),
                course=request.form.get('course'),
                registration_number=request.form.get('registration_number'),
                membership_type=request.form.get('membership_type', 'student')
            )

            db.session.add(member)
            db.session.commit()
            flash('Member added successfully!', 'success')
            return redirect(url_for('members'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding member: {str(e)}', 'danger')

    return render_template('add_member.html')


@app.route('/issue_book', methods=['GET', 'POST'])
@login_required
def issue_book():
    if request.method == 'POST':
        book_id = request.form.get('book_id')
        member_id = request.form.get('member_id')

        book = Book.query.filter_by(book_id=book_id).first()
        member = Member.query.filter_by(member_id=member_id).first()

        if not book:
            flash('Book not found!', 'danger')
            return redirect(url_for('issue_book'))

        if not member:
            flash('Member not found!', 'danger')
            return redirect(url_for('issue_book'))

        if book.available_copies <= 0:
            flash('No copies available!', 'danger')
            return redirect(url_for('issue_book'))

        # Check if member has already borrowed this book
        existing = Transaction.query.filter_by(
            book_id=book.id,
            member_id=member.id,
            status='issued'
        ).first()

        if existing:
            flash('Member already has this book!', 'danger')
            return redirect(url_for('issue_book'))

        # Check member's borrowing limit
        borrowed_count = Transaction.query.filter_by(
            member_id=member.id,
            status='issued'
        ).count()

        max_books = 5 if member.membership_type == 'student' else 10
        if borrowed_count >= max_books:
            flash(f'Member has reached borrowing limit ({max_books} books)', 'danger')
            return redirect(url_for('issue_book'))

        # Create transaction
        transaction_id = f"TRX{datetime.now().strftime('%Y%m%d%H%M%S')}"
        due_date = datetime.now() + timedelta(days=14)

        transaction = Transaction(
            transaction_id=transaction_id,
            book_id=book.id,
            member_id=member.id,
            due_date=due_date
        )

        book.available_copies -= 1
        db.session.add(transaction)
        db.session.commit()

        flash(f'Book issued successfully! Transaction ID: {transaction_id}', 'success')
        return redirect(url_for('transactions'))

    return render_template('issue_book.html')


@app.route('/return_book', methods=['GET', 'POST'])
@login_required
def return_book():
    if request.method == 'POST':
        transaction_id = request.form.get('transaction_id')

        transaction = Transaction.query.filter_by(
            transaction_id=transaction_id,
            status='issued'
        ).first()

        if not transaction:
            flash('Transaction not found or book already returned!', 'danger')
            return redirect(url_for('return_book'))

        # Calculate fine if overdue
        fine_amount = 0
        if datetime.now() > transaction.due_date:
            days_overdue = (datetime.now() - transaction.due_date).days
            fine_amount = days_overdue * 10  # KES 10 per day

            # Create fine record
            fine = Fine(
                transaction_id=transaction.id,
                member_id=transaction.member_id,
                amount=fine_amount,
                due_date=datetime.now()
            )
            db.session.add(fine)

        transaction.status = 'returned'
        transaction.return_date = datetime.now()
        transaction.fine_amount = fine_amount

        # Update book availability
        book = Book.query.get(transaction.book_id)
        book.available_copies += 1

        db.session.commit()

        if fine_amount > 0:
            flash(f'Book returned successfully! Fine: KES {fine_amount}', 'warning')
        else:
            flash('Book returned successfully!', 'success')

        return redirect(url_for('transactions'))

    return render_template('return_book.html')


@app.route('/transactions')
@login_required
def transactions():
    status = request.args.get('status', '')
    search = request.args.get('search', '')

    query = Transaction.query

    if status:
        query = query.filter(Transaction.status == status)

    if search:
        query = query.join(Member).filter(
            (Member.first_name.ilike(f'%{search}%')) |
            (Member.last_name.ilike(f'%{search}%')) |
            (Transaction.transaction_id.ilike(f'%{search}%'))
        )

    transactions = query.order_by(Transaction.issue_date.desc()).all()

    return render_template('transactions.html', transactions=transactions)


@app.route('/reports')
@login_required
def reports():
    # Generate various reports
    books_by_category = db.session.query(
        Book.category,
        db.func.count(Book.id).label('count')
    ).group_by(Book.category).all()

    monthly_issues = db.session.query(
        db.func.strftime('%Y-%m', Transaction.issue_date).label('month'),
        db.func.count(Transaction.id).label('count')
    ).group_by('month').order_by(db.desc('month')).limit(12).all()

    overdue_books = Transaction.query.filter(
        Transaction.due_date < datetime.now(),
        Transaction.status == 'issued'
    ).all()

    top_members = db.session.query(
        Member,
        db.func.count(Transaction.id).label('borrow_count')
    ).join(Transaction).group_by(Member.id).order_by(
        db.desc('borrow_count')
    ).limit(10).all()

    return render_template('reports.html',
                           books_by_category=books_by_category,
                           monthly_issues=monthly_issues,
                           overdue_books=overdue_books,
                           top_members=top_members)


@app.route('/api/books/search')
@login_required
def api_search_books():
    query = request.args.get('q', '')
    books = Book.query.filter(
        (Book.title.ilike(f'%{query}%')) |
        (Book.author.ilike(f'%{query}%')) |
        (Book.book_id.ilike(f'%{query}%'))
    ).limit(10).all()

    results = [{
        'id': book.book_id,
        'text': f"{book.title} by {book.author} (Available: {book.available_copies})"
    } for book in books]

    return jsonify({'results': results})


@app.route('/api/members/search')
@login_required
def api_search_members():
    query = request.args.get('q', '')
    members = Member.query.filter(
        (Member.first_name.ilike(f'%{query}%')) |
        (Member.last_name.ilike(f'%{query}%')) |
        (Member.member_id.ilike(f'%{query}%')) |
        (Member.registration_number.ilike(f'%{query}%'))
    ).limit(10).all()

    results = [{
        'id': member.member_id,
        'text': f"{member.first_name} {member.last_name} - {member.registration_number}"
    } for member in members]

    return jsonify({'results': results})


# Initialize database and admin user
def init_db():
    with app.app_context():
        db.create_all()

        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@kirinyaga.ac.ke',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin / admin123")


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)