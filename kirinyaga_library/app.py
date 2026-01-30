import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# PostgreSQL Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kirinyaga-library-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 
    'postgresql://database_url_d5bv_user:INEeDgbttbhfuajl1kk6WK08t86BqrFG@dpg-d5u44oogjchc73bdvi9g-a/database_url_d5bv')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20,
}

db = SQLAlchemy(app)

# Database Models (Updated for PostgreSQL compatibility)
class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100), nullable=False, index=True)
    isbn = db.Column(db.String(13), unique=True, nullable=False, index=True)
    publisher = db.Column(db.String(100))
    publication_year = db.Column(db.Integer)
    category = db.Column(db.String(50))
    edition = db.Column(db.String(20))
    total_copies = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)
    shelf_location = db.Column(db.String(20))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    keywords = db.Column(db.String(500))
    
    # Relationships
    transactions = db.relationship('Transaction', backref='book', lazy=True, cascade='all, delete-orphan')


class Member(db.Model):
    __tablename__ = 'members'
    
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    course = db.Column(db.String(100))
    year_of_study = db.Column(db.Integer)
    registration_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    membership_type = db.Column(db.String(20), default='student')  # student, staff, faculty
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')  # active, suspended, graduated
    address = db.Column(db.Text)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='member', lazy=True, cascade='all, delete-orphan')
    fines = db.relationship('Fine', backref='member', lazy=True)


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default='librarian')  # admin, librarian
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='issued_by', lazy=True)


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    return_date = db.Column(db.DateTime)
    fine_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='issued')  # issued, returned, overdue
    renewed = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    
    # Relationships
    fine_details = db.relationship('Fine', backref='transaction', lazy=True, cascade='all, delete-orphan')


class Fine(db.Model):
    __tablename__ = 'fines'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'))
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'))
    amount = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, paid, waived
    due_date = db.Column(db.DateTime)
    payment_date = db.Column(db.DateTime)
    payment_method = db.Column(db.String(50))
    receipt_number = db.Column(db.String(50))
    notes = db.Column(db.Text)


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

        if user and check_password_hash(user.password, password) and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['full_name'] = f"{user.first_name} {user.last_name}"
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
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
    total_members = Member.query.filter_by(status='active').count()
    issued_books = Transaction.query.filter_by(status='issued').count()
    
    # Calculate overdue books
    overdue_books = Transaction.query.filter(
        Transaction.due_date < datetime.utcnow(),
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

    # Today's statistics
    today = datetime.utcnow().date()
    todays_issues = Transaction.query.filter(
        db.func.date(Transaction.issue_date) == today
    ).count()
    
    todays_returns = Transaction.query.filter(
        db.func.date(Transaction.return_date) == today
    ).count()

    return render_template('dashboard.html',
                         total_books=total_books,
                         total_members=total_members,
                         issued_books=issued_books,
                         overdue_books=overdue_books,
                         recent_transactions=recent_transactions,
                         popular_books=popular_books,
                         todays_issues=todays_issues,
                         todays_returns=todays_returns)


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
            (Book.isbn.ilike(f'%{search}%')) |
            (Book.book_id.ilike(f'%{search}%'))
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
            # Generate book ID if not provided
            book_id = request.form.get('book_id')
            if not book_id:
                # Generate book ID: B + year + sequence
                year = datetime.utcnow().year
                last_book = Book.query.filter(
                    Book.book_id.like(f'B{year}%')
                ).order_by(Book.id.desc()).first()
                
                if last_book and last_book.book_id.startswith(f'B{year}'):
                    seq = int(last_book.book_id[5:]) + 1
                else:
                    seq = 1
                
                book_id = f'B{year}{seq:04d}'
            
            book = Book(
                book_id=book_id,
                title=request.form.get('title'),
                author=request.form.get('author'),
                isbn=request.form.get('isbn'),
                publisher=request.form.get('publisher'),
                publication_year=request.form.get('publication_year'),
                category=request.form.get('category'),
                edition=request.form.get('edition'),
                total_copies=int(request.form.get('total_copies', 1)),
                available_copies=int(request.form.get('total_copies', 1)),
                shelf_location=request.form.get('shelf_location'),
                description=request.form.get('description'),
                keywords=request.form.get('keywords')
            )
            
            db.session.add(book)
            db.session.commit()
            flash(f'Book added successfully! Book ID: {book_id}', 'success')
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
    status = request.args.get('status', '')
    
    query = Member.query
    
    if search:
        query = query.filter(
            (Member.first_name.ilike(f'%{search}%')) |
            (Member.last_name.ilike(f'%{search}%')) |
            (Member.registration_number.ilike(f'%{search}%')) |
            (Member.member_id.ilike(f'%{search}%'))
        )
    
    if department:
        query = query.filter(Member.department == department)
    
    if status:
        query = query.filter(Member.status == status)
    
    members = query.order_by(Member.first_name).all()
    departments = db.session.query(Member.department).distinct().all()
    
    return render_template('members.html', members=members, departments=departments)


@app.route('/add_member', methods=['GET', 'POST'])
@login_required
def add_member():
    if request.method == 'POST':
        try:
            # Generate member ID if not provided
            member_id = request.form.get('member_id')
            if not member_id:
                # Generate member ID based on type
                member_type = request.form.get('membership_type', 'student')
                year = datetime.utcnow().year
                
                if member_type == 'student':
                    prefix = 'STU'
                elif member_type == 'staff':
                    prefix = 'STAFF'
                else:
                    prefix = 'FAC'
                
                last_member = Member.query.filter(
                    Member.member_id.like(f'{prefix}{year}%')
                ).order_by(Member.id.desc()).first()
                
                if last_member and last_member.member_id.startswith(f'{prefix}{year}'):
                    seq = int(last_member.member_id[len(prefix)+4:]) + 1
                else:
                    seq = 1
                
                member_id = f'{prefix}{year}{seq:04d}'
            
            member = Member(
                member_id=member_id,
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                department=request.form.get('department'),
                course=request.form.get('course'),
                year_of_study=request.form.get('year_of_study'),
                registration_number=request.form.get('registration_number'),
                membership_type=request.form.get('membership_type', 'student'),
                address=request.form.get('address'),
                status='active'
            )
            
            db.session.add(member)
            db.session.commit()
            flash(f'Member added successfully! Member ID: {member_id}', 'success')
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
        
        if member.status != 'active':
            flash('Member account is not active!', 'danger')
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
        transaction_id = f"TRX{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        due_date = datetime.utcnow() + timedelta(days=14)
        
        transaction = Transaction(
            transaction_id=transaction_id,
            book_id=book.id,
            member_id=member.id,
            issued_by=session['user_id'],
            due_date=due_date
        )
        
        book.available_copies -= 1
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Book issued successfully! Transaction ID: {transaction_id}. Due date: {due_date.strftime("%Y-%m-%d")}', 'success')
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
        if datetime.utcnow() > transaction.due_date:
            days_overdue = (datetime.utcnow() - transaction.due_date).days
            fine_amount = days_overdue * 10  # KES 10 per day
            
            # Create fine record
            fine = Fine(
                transaction_id=transaction.id,
                member_id=transaction.member_id,
                amount=fine_amount,
                due_date=datetime.utcnow()
            )
            db.session.add(fine)
        
        transaction.status = 'returned'
        transaction.return_date = datetime.utcnow()
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
            (Transaction.transaction_id.ilike(f'%{search}%')) |
            (Member.member_id.ilike(f'%{search}%'))
        )
    
    transactions = query.order_by(Transaction.issue_date.desc()).all()
    
    return render_template('transactions.html', transactions=transactions, now=datetime.utcnow())


@app.route('/reports')
@login_required
def reports():
    # Generate various reports
    books_by_category = db.session.query(
        Book.category,
        db.func.count(Book.id).label('count')
    ).group_by(Book.category).all()
    
    monthly_issues = db.session.query(
        db.func.date_trunc('month', Transaction.issue_date).label('month'),
        db.func.count(Transaction.id).label('count')
    ).group_by('month').order_by(db.desc('month')).limit(12).all()
    
    overdue_books = Transaction.query.filter(
        Transaction.due_date < datetime.utcnow(),
        Transaction.status == 'issued'
    ).all()
    
    top_members = db.session.query(
        Member,
        db.func.count(Transaction.id).label('borrow_count')
    ).join(Transaction).group_by(Member.id).order_by(
        db.desc('borrow_count')
    ).limit(10).all()
    
    # Department-wise statistics
    department_stats = db.session.query(
        Member.department,
        db.func.count(Member.id).label('member_count'),
        db.func.count(Transaction.id).label('issue_count')
    ).outerjoin(Transaction).group_by(Member.department).all()
    
    return render_template('reports.html',
                         books_by_category=books_by_category,
                         monthly_issues=monthly_issues,
                         overdue_books=overdue_books,
                         top_members=top_members,
                         department_stats=department_stats,
                         now=datetime.utcnow())


@app.route('/api/books/search')
@login_required
def api_search_books():
    query = request.args.get('q', '')
    books = Book.query.filter(
        (Book.title.ilike(f'%{query}%')) |
        (Book.author.ilike(f'%{query}%')) |
        (Book.book_id.ilike(f'%{query}%')) |
        (Book.isbn.ilike(f'%{query}%'))
    ).limit(10).all()
    
    results = [{
        'id': book.book_id,
        'text': f"{book.title} by {book.author} (Available: {book.available_copies}/{book.total_copies})"
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
    ).filter(Member.status == 'active').limit(10).all()
    
    results = [{
        'id': member.member_id,
        'text': f"{member.first_name} {member.last_name} - {member.registration_number} ({member.membership_type})"
    } for member in members]
    
    return jsonify({'results': results})


# Initialize database and admin user
def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@kirinyaga.ac.ke',
                password=generate_password_hash('admin123'),
                first_name='Library',
                last_name='Administrator',
                role='admin',
                department='Library',
                phone='+254 723 123 456'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created: admin / admin123")
        else:
            print("✅ Database already initialized")


if __name__ == '__main__':
    init_db()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run the application
    app.run(host='0.0.0.0', port=port, debug=True)
