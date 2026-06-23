import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_bus_booking_key_for_development_only'
DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create Tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                phone TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                number TEXT NOT NULL,
                operator TEXT NOT NULL,
                type TEXT NOT NULL, -- AC / Non-AC
                layout TEXT NOT NULL, -- Sleeper / Seater
                total_seats INTEGER NOT NULL,
                price_per_seat REAL NOT NULL,
                ratings REAL DEFAULT 0.0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id INTEGER,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (bus_id) REFERENCES buses (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                route_id INTEGER,
                total_price REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (route_id) REFERENCES routes (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS passengers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                seat_number TEXT NOT NULL,
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                transaction_id TEXT,
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            )
        ''')
        
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        admin = cursor.fetchone()
        if not admin:
            admin_hash = generate_password_hash('admin123')
            cursor.execute("INSERT INTO users (name, email, password_hash, role, phone) VALUES (?, ?, ?, ?, ?)",
                           ('Admin User', 'admin@redbus.local', admin_hash, 'admin', '0000000000'))
            
        # Seed some initial buses and routes if none exist
        cursor.execute("SELECT count(*) FROM buses")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO buses (name, number, operator, type, layout, total_seats, price_per_seat, ratings) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           ('Volvo Express', 'MH-12-AB-1234', 'VRL Travels', 'AC', 'Sleeper', 30, 1500.0, 4.5))
            bus_id_1 = cursor.lastrowid
            cursor.execute("INSERT INTO buses (name, number, operator, type, layout, total_seats, price_per_seat, ratings) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           ('City Runner', 'KA-01-CD-5678', 'SRS Travels', 'Non-AC', 'Seater', 40, 800.0, 4.0))
            bus_id_2 = cursor.lastrowid
            
            # Future dates for seed routes
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute("INSERT INTO routes (bus_id, source, destination, departure_time, arrival_time, date) VALUES (?, ?, ?, ?, ?, ?)",
                           (bus_id_1, 'Mumbai', 'Pune', '08:00', '12:00', tomorrow))
            cursor.execute("INSERT INTO routes (bus_id, source, destination, departure_time, arrival_time, date) VALUES (?, ?, ?, ?, ?, ?)",
                           (bus_id_2, 'Delhi', 'Jaipur', '22:00', '04:00', tomorrow))

        db.commit()

@app.before_request
def initialize_database():
    if not os.path.exists(DATABASE):
        init_db()
        print("Initialized database with seed data.")

# --- Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Context Processor ---
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    return dict(current_user=user)

# --- Routes ---

@app.route('/')
def index():
    # Get distinct source and destinations for the search form
    db = get_db()
    sources = db.execute("SELECT DISTINCT source FROM routes").fetchall()
    destinations = db.execute("SELECT DISTINCT destination FROM routes").fetchall()
    return render_template('index.html', sources=sources, destinations=destinations)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if email exists
        user = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            flash('Email address already registered.', 'danger')
            return redirect(url_for('register'))
        
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (name, email, password_hash, phone) VALUES (?, ?, ?, ?)",
                       (name, email, password_hash, phone))
        db.commit()
        
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            if user['role'] == 'admin':
                return redirect(next_page or url_for('admin_dashboard'))
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/search')
def search():
    source = request.args.get('source', '')
    destination = request.args.get('destination', '')
    date = request.args.get('date', '')
    
    db = get_db()
    query = """
        SELECT r.id as route_id, r.source, r.destination, r.departure_time, r.arrival_time, r.date,
               b.id as bus_id, b.name as bus_name, b.number, b.operator, b.type, b.layout, 
               b.total_seats, b.price_per_seat, b.ratings
        FROM routes r
        JOIN buses b ON r.bus_id = b.id
        WHERE 1=1
    """
    params = []
    if source:
        query += " AND r.source = ?"
        params.append(source)
    if destination:
        query += " AND r.destination = ?"
        params.append(destination)
    if date:
        query += " AND r.date = ?"
        params.append(date)
        
    results = db.execute(query, params).fetchall()
    
    return render_template('search_results.html', results=results, source=source, destination=destination, date=date)

@app.route('/bus/<int:route_id>')
def bus_details(route_id):
    db = get_db()
    
    route_info = db.execute("""
        SELECT r.id as route_id, r.source, r.destination, r.departure_time, r.arrival_time, r.date,
               b.id as bus_id, b.name as bus_name, b.number, b.operator, b.type, b.layout, 
               b.total_seats, b.price_per_seat, b.ratings
        FROM routes r
        JOIN buses b ON r.bus_id = b.id
        WHERE r.id = ?
    """, (route_id,)).fetchone()
    
    if not route_info:
        flash('Route not found.', 'danger')
        return redirect(url_for('index'))
        
    # Find booked seats for this route
    booked_seats_query = db.execute("""
        SELECT p.seat_number 
        FROM passengers p
        JOIN bookings b ON p.booking_id = b.id
        WHERE b.route_id = ? AND b.status IN ('confirmed', 'pending')
    """, (route_id,)).fetchall()
    
    booked_seats = [row['seat_number'] for row in booked_seats_query]
    
    return render_template('bus_details.html', route=route_info, booked_seats=booked_seats)

@app.route('/book/<int:route_id>', methods=['POST'])
@login_required
def book(route_id):
    seats = request.form.getlist('seats[]')
    if not seats:
        flash('Please select at least one seat.', 'danger')
        return redirect(url_for('bus_details', route_id=route_id))
        
    db = get_db()
    route = db.execute("SELECT r.*, b.price_per_seat FROM routes r JOIN buses b ON r.bus_id = b.id WHERE r.id = ?", (route_id,)).fetchone()
    
    if not route:
        flash('Route not found.', 'danger')
        return redirect(url_for('index'))
        
    # Check if seats are already booked
    placeholders = ', '.join(['?'] * len(seats))
    query = f"""
        SELECT p.seat_number 
        FROM passengers p
        JOIN bookings b ON p.booking_id = b.id
        WHERE b.route_id = ? AND b.status IN ('confirmed', 'pending') AND p.seat_number IN ({placeholders})
    """
    already_booked = db.execute(query, [route_id] + seats).fetchall()
    
    if already_booked:
        flash('One or more selected seats are already booked.', 'danger')
        return redirect(url_for('bus_details', route_id=route_id))
        
    total_price = len(seats) * route['price_per_seat']
    
    # Store temporary booking in session for passenger details step
    session['temp_booking'] = {
        'route_id': route_id,
        'seats': seats,
        'total_price': total_price
    }
    
    return render_template('passenger_details.html', route=route, seats=seats, total_price=total_price)

@app.route('/process_passenger_details', methods=['POST'])
@login_required
def process_passenger_details():
    if 'temp_booking' not in session:
        return redirect(url_for('index'))
        
    temp_booking = session['temp_booking']
    seats = temp_booking['seats']
    
    passengers_info = []
    for i, seat in enumerate(seats):
        name = request.form.get(f'name_{i}')
        age = request.form.get(f'age_{i}')
        gender = request.form.get(f'gender_{i}')
        
        passengers_info.append({
            'seat_number': seat,
            'name': name,
            'age': age,
            'gender': gender
        })
        
    session['temp_booking']['passengers'] = passengers_info
    
    return redirect(url_for('payment'))

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if 'temp_booking' not in session:
        return redirect(url_for('index'))
        
    temp_booking = session['temp_booking']
    
    if request.method == 'POST':
        # Simulate payment processing
        db = get_db()
        cursor = db.cursor()
        
        # 1. Create booking
        cursor.execute("INSERT INTO bookings (user_id, route_id, total_price, status) VALUES (?, ?, ?, ?)",
                       (session['user_id'], temp_booking['route_id'], temp_booking['total_price'], 'confirmed'))
        booking_id = cursor.lastrowid
        
        # 2. Add passengers
        for p in temp_booking['passengers']:
            cursor.execute("INSERT INTO passengers (booking_id, name, age, gender, seat_number) VALUES (?, ?, ?, ?, ?)",
                           (booking_id, p['name'], p['age'], p['gender'], p['seat_number']))
                           
        # 3. Add payment record
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{booking_id}"
        cursor.execute("INSERT INTO payments (booking_id, amount, status, transaction_id) VALUES (?, ?, ?, ?)",
                       (booking_id, temp_booking['total_price'], 'success', transaction_id))
                       
        db.commit()
        session.pop('temp_booking', None)
        
        flash('Payment successful! Booking confirmed.', 'success')
        return redirect(url_for('ticket', booking_id=booking_id))
        
    return render_template('payment.html', amount=temp_booking['total_price'])

@app.route('/ticket/<int:booking_id>')
@login_required
def ticket(booking_id):
    db = get_db()
    
    # Check if booking belongs to user or if admin
    booking = db.execute("""
        SELECT b.*, r.source, r.destination, r.departure_time, r.arrival_time, r.date,
               bus.name as bus_name, bus.number as bus_number, bus.operator
        FROM bookings b
        JOIN routes r ON b.route_id = r.id
        JOIN buses bus ON r.bus_id = bus.id
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    
    if not booking:
        flash('Booking not found.', 'danger')
        return redirect(url_for('dashboard'))
        
    if booking['user_id'] != session['user_id'] and session.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('dashboard'))
        
    passengers = db.execute("SELECT * FROM passengers WHERE booking_id = ?", (booking_id,)).fetchall()
    payment = db.execute("SELECT * FROM payments WHERE booking_id = ?", (booking_id,)).fetchone()
    
    return render_template('ticket.html', booking=booking, passengers=passengers, payment=payment)

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    bookings = db.execute("""
        SELECT b.id as booking_id, b.total_price, b.status, b.booking_date,
               r.source, r.destination, r.date as journey_date,
               bus.operator, bus.name as bus_name
        FROM bookings b
        JOIN routes r ON b.route_id = r.id
        JOIN buses bus ON r.bus_id = bus.id
        WHERE b.user_id = ?
        ORDER BY b.booking_date DESC
    """, (session['user_id'],)).fetchall()
    
    return render_template('dashboard.html', user=user, bookings=bookings)

@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    db = get_db()
    cursor = db.cursor()
    
    # Check ownership
    booking = cursor.execute("SELECT * FROM bookings WHERE id = ? AND user_id = ?", (booking_id, session['user_id'])).fetchone()
    
    if not booking:
        flash('Booking not found or unauthorized.', 'danger')
    elif booking['status'] == 'cancelled':
        flash('Booking is already cancelled.', 'warning')
    else:
        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        cursor.execute("UPDATE payments SET status = 'refunded' WHERE booking_id = ?", (booking_id,))
        db.commit()
        flash('Booking cancelled successfully. Amount will be refunded.', 'success')
        
    return redirect(url_for('dashboard'))

# --- Admin Routes ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {}
    stats['total_users'] = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    stats['total_buses'] = db.execute("SELECT COUNT(*) FROM buses").fetchone()[0]
    stats['total_routes'] = db.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
    stats['total_bookings'] = db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    
    recent_bookings = db.execute("""
        SELECT b.id, b.total_price, b.status, b.booking_date, u.name as user_name
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        ORDER BY b.booking_date DESC LIMIT 5
    """).fetchall()
    
    return render_template('admin_dashboard.html', stats=stats, recent_bookings=recent_bookings)

@app.route('/admin/buses', methods=['GET', 'POST'])
@admin_required
def admin_buses():
    db = get_db()
    if request.method == 'POST':
        name = request.form['name']
        number = request.form['number']
        operator = request.form['operator']
        b_type = request.form['type']
        layout = request.form['layout']
        total_seats = int(request.form['total_seats'])
        price_per_seat = float(request.form['price_per_seat'])
        
        db.execute("""
            INSERT INTO buses (name, number, operator, type, layout, total_seats, price_per_seat)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, number, operator, b_type, layout, total_seats, price_per_seat))
        db.commit()
        flash('Bus added successfully.', 'success')
        return redirect(url_for('admin_buses'))
        
    buses = db.execute("SELECT * FROM buses").fetchall()
    return render_template('admin_buses.html', buses=buses)

@app.route('/admin/routes', methods=['GET', 'POST'])
@admin_required
def admin_routes():
    db = get_db()
    if request.method == 'POST':
        bus_id = request.form['bus_id']
        source = request.form['source']
        destination = request.form['destination']
        dep_time = request.form['departure_time']
        arr_time = request.form['arrival_time']
        date = request.form['date']
        
        db.execute("""
            INSERT INTO routes (bus_id, source, destination, departure_time, arrival_time, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (bus_id, source, destination, dep_time, arr_time, date))
        db.commit()
        flash('Route added successfully.', 'success')
        return redirect(url_for('admin_routes'))
        
    routes = db.execute("""
        SELECT r.*, b.name as bus_name, b.number as bus_number
        FROM routes r
        JOIN buses b ON r.bus_id = b.id
    """).fetchall()
    buses = db.execute("SELECT id, name, number FROM buses").fetchall()
    return render_template('admin_routes.html', routes=routes, buses=buses)


if __name__ == '__main__':
    # Initialize DB before running
    if not os.path.exists(DATABASE):
        with app.app_context():
            init_db()
            print("Initialized database with seed data.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
