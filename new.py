import streamlit as st
import re
import pyodbc
import hashlib
import random
import string
from datetime import datetime, timedelta
import pandas as pd
import time
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
import matplotlib.pyplot as plt
import plotly.express as px
from PIL import Image
import io

# ===== CONFIGURATION =====
PRESET_ADMIN = {
    "username": "admin",
    "password": "Admin@123"  # Change before deployment
}
DEFAULT_PASSWORD = "Temp@123"  # Default for staff and customers

AIRPORTS = [
    "JFK - New York",
    "LAX - Los Angeles",
    "ORD - Chicago",
    "DFW - Dallas",
    "SFO - San Francisco",
    "ATL - Atlanta",
    "DEN - Denver",
    "SEA - Seattle",
    "MIA - Miami",
    "BOS - Boston"
]

AIRCRAFT_TYPES = [
    "Boeing 737",
    "Boeing 787",
    "Airbus A320",
    "Airbus A380",
    "Embraer E190"
]

SEAT_CLASSES = ["Economy", "Premium Economy", "Business", "First"]

SEAT_PRICE_MULTIPLIERS = {
    "Economy": 1.0,
    "Premium Economy": 1.5,
    "Business": 2.5,
    "First": 4.0
}

# ===== DATABASE FUNCTIONS =====
def connect_db():
    try:
        server = 'DESKTOP-O93TIKV\SQLEXPRESS'
        database = 'AirlineBooking_dbms'
        conn = pyodbc.connect(
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            'Trusted_Connection=yes;'
        )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

def init_db():
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Create tables with SQL Server syntax
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='admins' AND xtype='U')
            CREATE TABLE admins (
                id INT IDENTITY(1,1) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='staff' AND xtype='U')
            CREATE TABLE staff (
                id INT IDENTITY(1,1) PRIMARY KEY,
                staff_id VARCHAR(20) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                must_change_pass BIT DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='customers' AND xtype='U')
            CREATE TABLE customers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                passport_no VARCHAR(20) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                date_of_birth DATE NOT NULL,
                nationality VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                phone VARCHAR(20) NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                must_change_pass BIT DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                loyalty_points INT DEFAULT 0
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='aircraft' AND xtype='U')
            CREATE TABLE aircraft (
                id INT IDENTITY(1,1) PRIMARY KEY,
                registration_no VARCHAR(20) UNIQUE NOT NULL,
                aircraft_type VARCHAR(100) NOT NULL,
                total_seats INT NOT NULL,
                economy_seats INT NOT NULL,
                premium_economy_seats INT NOT NULL,
                business_seats INT NOT NULL,
                first_seats INT NOT NULL,
                last_maintenance DATE NOT NULL,
                next_maintenance DATE NOT NULL
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='flights' AND xtype='U')
            CREATE TABLE flights (
                id INT IDENTITY(1,1) PRIMARY KEY,
                flight_no VARCHAR(10) NOT NULL,
                departure_airport VARCHAR(10) NOT NULL,
                arrival_airport VARCHAR(10) NOT NULL,
                departure_time DATETIME NOT NULL,
                arrival_time DATETIME NOT NULL,
                aircraft_reg VARCHAR(20) NOT NULL,  # Changed from aircraft_id to aircraft_reg
                base_price DECIMAL(10,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'Scheduled' CHECK (status IN ('Scheduled','Boarding','Departed','Arrived','Cancelled','Delayed')),
                FOREIGN KEY (aircraft_reg) REFERENCES aircraft(registration_no)  # Changed foreign key reference
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bookings' AND xtype='U')
            CREATE TABLE bookings (
                id INT IDENTITY(1,1) PRIMARY KEY,
                booking_ref VARCHAR(10) UNIQUE NOT NULL,
                customer_id INT NOT NULL,
                flight_id INT NOT NULL,
                booking_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                seat_class VARCHAR(20) NOT NULL,
                seat_count INT NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'Confirmed' CHECK (status IN ('Confirmed','Cancelled','Completed')),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (flight_id) REFERENCES flights(id)
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='passengers' AND xtype='U')
            CREATE TABLE passengers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                booking_id INT NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                passport_no VARCHAR(20) NOT NULL,
                date_of_birth DATE NOT NULL,
                nationality VARCHAR(100) NOT NULL,
                seat_number VARCHAR(10),
                special_requests VARCHAR(500),  # Changed from TEXT to VARCHAR
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='payments' AND xtype='U')
            CREATE TABLE payments (
                id INT IDENTITY(1,1) PRIMARY KEY,
                booking_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                payment_method VARCHAR(50) NOT NULL,
                transaction_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'Completed' CHECK (status IN ('Pending','Completed','Failed','Refunded')),
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='flight_seats' AND xtype='U')
            CREATE TABLE flight_seats (
                id INT IDENTITY(1,1) PRIMARY KEY,
                flight_id INT NOT NULL,
                seat_number VARCHAR(10) NOT NULL,
                seat_class VARCHAR(20) NOT NULL,
                is_available BIT DEFAULT 1,
                booking_id INT,
                UNIQUE (flight_id, seat_number),
                FOREIGN KEY (flight_id) REFERENCES flights(id),
                FOREIGN KEY (booking_id) REFERENCES bookings(id)
            )
        """)
        
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='promotions' AND xtype='U')
            CREATE TABLE promotions (
                id INT IDENTITY(1,1) PRIMARY KEY,
                code VARCHAR(20) UNIQUE NOT NULL,
                description VARCHAR(500) NOT NULL,  # Changed from TEXT to VARCHAR
                discount_percent DECIMAL(5,2) NOT NULL,
                valid_from DATE NOT NULL,
                valid_to DATE NOT NULL,
                max_uses INT,
                current_uses INT DEFAULT 0
            )
        """)
        
        # Insert preset admin if not exists
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM admins WHERE username = ?)
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
        """, (PRESET_ADMIN["username"], PRESET_ADMIN["username"], hash_password(PRESET_ADMIN["password"])))
        
        # Insert sample promotions
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM promotions WHERE code = 'WELCOME10')
            INSERT INTO promotions (code, description, discount_percent, valid_from, valid_to, max_uses)
            VALUES ('WELCOME10', '10% discount for new customers', 10.00, ?, ?, 100)
        """, (datetime.now().date(), datetime.now().date() + timedelta(days=365)))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"🔴 Database Initialization Failed: {e}")
        return False
    finally:
        conn.close()

# ===== UTILITY FUNCTIONS =====
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_username(name):
    base = name.lower().replace(" ", "")
    suffix = ''.join(random.choices(string.digits, k=2))
    return f"{base}{suffix}"

def generate_staff_id():
    return 'S' + ''.join(random.choices(string.digits, k=5))

def generate_booking_ref():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def validate_email(email):
    return '@' in email and '.' in email.split('@')[-1]

def validate_phone(phone):
    return phone.isdigit() and len(phone) >= 10

def validate_passport(passport_no):
    return len(passport_no) >= 6 and passport_no.isalnum()

def validate_date_of_birth(dob):
    return dob < datetime.now().date()

def validate_flight_dates(departure, arrival):
    return departure < arrival and departure > datetime.now()

def calculate_flight_duration(departure, arrival):
    duration = arrival - departure
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    return f"{hours}h {minutes}m"

# ===== AUTHENTICATION FUNCTIONS =====
def admin_login(username, password):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Check preset admin credentials first
        if username == PRESET_ADMIN["username"] and password == PRESET_ADMIN["password"]:
            return {"username": username, "password_hash": hash_password(password)}
        
        # Check database
        cursor.execute("""
            SELECT * FROM admins 
            WHERE username = ? AND password_hash = ?
        """, (username, hash_password(password)))
        
        columns = [column[0] for column in cursor.description]
        admin = cursor.fetchone()
        if admin:
            return dict(zip(columns, admin))
        return None
    except Exception as e:
        st.error(f"🔴 Login Error: {e}")
        return None
    finally:
        conn.close()

def generate_ticket_pdf(booking_details):
    """Generate PDF ticket for a booking"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add airline logo (placeholder)
    pdf.cell(200, 10, txt="Airline Booking System", ln=1, align='C')
    pdf.cell(200, 10, txt="E-Ticket", ln=1, align='C')
    pdf.ln(10)
    
    # Booking info
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt=f"Booking Reference: {booking_details['booking_ref']}", ln=1)
    pdf.set_font("Arial", size=12)
    
    # Flight info
    pdf.cell(200, 10, txt=f"Flight: {booking_details['flight_no']}", ln=1)
    pdf.cell(200, 10, txt=f"From: {booking_details['departure_airport']}", ln=1)
    pdf.cell(200, 10, txt=f"To: {booking_details['arrival_airport']}", ln=1)
    pdf.cell(200, 10, txt=f"Departure: {booking_details['departure_time'].strftime('%Y-%m-%d %H:%M')}", ln=1)
    pdf.cell(200, 10, txt=f"Arrival: {booking_details['arrival_time'].strftime('%Y-%m-%d %H:%M')}", ln=1)
    pdf.cell(200, 10, txt=f"Class: {booking_details['seat_class']}", ln=1)
    pdf.ln(10)
    
    # Passenger info
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Passenger(s)", ln=1)
    pdf.set_font("Arial", size=12)
    
    for pax in booking_details['passengers']:
        pdf.cell(200, 10, txt=f"Name: {pax['name']}", ln=1)
        pdf.cell(200, 10, txt=f"Passport: {pax['passport']}", ln=1)
        if pax['seat']:
            pdf.cell(200, 10, txt=f"Seat: {pax['seat']}", ln=1)
        pdf.ln(5)
    
    # Payment info
    if 'payment' in booking_details:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Payment Details", ln=1)
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Amount: ${booking_details['payment']['amount']:.2f}", ln=1)
        pdf.cell(200, 10, txt=f"Method: {booking_details['payment']['method']}", ln=1)
        pdf.cell(200, 10, txt=f"Status: {booking_details['payment']['status']}", ln=1)
    
    # Generate unique filename
    filename = f"ticket_{booking_details['booking_ref']}.pdf"
    pdf.output(filename)
    return filename

def send_email(to_email, subject, body, attachment_path=None):
    """Send email with optional attachment"""
    try:
        # Configure your email settings (use environment variables in production)
        sender_email = "bookings@airline.com"
        password = "email_password"  
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path:
            with open(attachment_path, "rb") as f:
                attach = MIMEApplication(f.read(), _subtype="pdf")
                attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                msg.attach(attach)
        
        # Send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def visualize_seat_map(flight_id, seat_class):
    """Create a visual seat map for selection"""
    seats = get_available_seats(flight_id, seat_class)
    
    if not seats:
        st.warning("No available seats in this class")
        return []
    
    # Create a grid layout based on seat class
    if seat_class == "Economy":
        cols = 6  # ABC DEF
    elif seat_class == "Premium Economy":
        cols = 4  # AB CD
    else:  # Business or First
        cols = 2  # A (aisle) B
    
    # Group seats by row
    seat_rows = {}
    for seat in seats:
        # Extract row number (assuming format like "12A" or "P3B")
        if seat[0].isalpha():  # Premium seats like "P3B"
            row = seat[1:].rstrip('ABCDEF')
        else:
            row = seat.rstrip('ABCDEF')
        
        if row not in seat_rows:
            seat_rows[row] = []
        seat_rows[row].append(seat)
    
    # Display seat map
    st.subheader("Seat Map")
    selected_seats = []
    
    for row, row_seats in seat_rows.items():
        cols = st.columns(len(row_seats) + 1)
        cols[0].write(f"Row {row}")
        
        for i, seat in enumerate(row_seats, 1):
            if cols[i].button(seat, key=f"seat_{seat}"):
                if seat in selected_seats:
                    selected_seats.remove(seat)
                else:
                    if len(selected_seats) >= st.session_state.get('passenger_count', 1):
                        st.warning(f"You can only select {st.session_state.get('passenger_count', 1)} seat(s)")
                    else:
                        selected_seats.append(seat)
                
                # Highlight selected seats
                if seat in selected_seats:
                    cols[i].button(f"✓ {seat}", key=f"selected_{seat}")
    
    return selected_seats

def get_flight_stats():
    """Get statistics for admin dashboard"""
    conn = connect_db()
    if not conn:
        st.error("Failed to connect to database")
        return None
    
    try:
        cursor = conn.cursor()
        
        # Total bookings
        cursor.execute("SELECT COUNT(*) FROM bookings")
        total_bookings = cursor.fetchone()[0] or 0
        
        # Revenue (with NULL handling)
        cursor.execute("""
            SELECT ISNULL(SUM(total_amount), 0) 
            FROM bookings 
            WHERE status != 'Cancelled'
        """)
        total_revenue = cursor.fetchone()[0]
        
        # Flight status counts
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM flights 
            GROUP BY status
        """)
        flight_status = dict(cursor.fetchall())
        
        # Popular routes (by booking count)
        cursor.execute("""
            SELECT TOP 5 
                f.departure_airport, 
                f.arrival_airport, 
                COUNT(b.id) as booking_count
            FROM flights f
            LEFT JOIN bookings b ON f.id = b.flight_id
            GROUP BY f.departure_airport, f.arrival_airport
            ORDER BY booking_count DESC
        """)
        popular_routes = [
            {"route": f"{row[0]} → {row[1]}", "bookings": row[2]} 
            for row in cursor.fetchall()
        ]
        
        # Recent bookings with customer info
        cursor.execute("""
            SELECT TOP 5 
                b.booking_ref, 
                c.full_name, 
                f.flight_no, 
                f.departure_airport, 
                f.arrival_airport, 
                b.booking_date
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            JOIN flights f ON b.flight_id = f.id
            ORDER BY b.booking_date DESC
        """)
        recent_bookings = [
            {
                "booking_ref": row[0],
                "customer": row[1],
                "flight": row[2],
                "route": f"{row[3]} → {row[4]}", 
                "date": row[5]
            }
            for row in cursor.fetchall()
        ]
        
        return {
            'total_bookings': total_bookings,
            'total_revenue': total_revenue,
            'flight_status': flight_status,
            'popular_routes': popular_routes,
            'recent_bookings': recent_bookings
        }
        
    except pyodbc.Error as e:
        st.error(f"Database error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error getting stats: {str(e)}")
        return None
    finally:
        try:
            conn.close()
        except:
            pass

def get_customer_bookings(customer_id):
    """Get all bookings for a customer with flight details"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.booking_ref, b.booking_date, b.status,
                   f.flight_no, f.departure_airport, f.arrival_airport,
                   f.departure_time, f.arrival_time, b.seat_class,
                   b.seat_count, b.total_amount,
                   (SELECT COUNT(*) FROM passengers p WHERE p.booking_id = b.id) as passenger_count
            FROM bookings b
            JOIN flights f ON b.flight_id = f.id
            WHERE b.customer_id = ?
            ORDER BY f.departure_time DESC
        """, (customer_id,))
        
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Error getting customer bookings: {e}")
        return []
    finally:
        conn.close()


def staff_login(staff_id, password):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM staff WHERE staff_id = ? AND password_hash = ?", 
                      (staff_id, hash_password(password)))
        staff = cursor.fetchone()
        if staff:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, staff))
        return None
    except Exception as e:
        st.error(f"Staff login error: {e}")
        return None
    finally:
        conn.close()

def customer_login(username, password):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE username = ? AND password_hash = ?", 
                      (username, hash_password(password)))
        customer = cursor.fetchone()
        if customer:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, customer))
        return None
    except Exception as e:
        st.error(f"Customer login error: {e}")
        return None
    finally:
        conn.close()

def customer_exists(email, passport_no):
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM customers WHERE email = ? OR passport_no = ?", 
                      (email, passport_no))
        return cursor.fetchone() is not None
    except Exception as e:
        st.error(f"Customer exists check error: {e}")
        return False
    finally:
        conn.close()

def update_password(table, id_field, id_value, new_password):
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table} SET password_hash = ?, must_change_pass = 0 WHERE {id_field} = ?",
                     (hash_password(new_password), id_value))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        st.error(f"Password update error: {e}")
        return False
    finally:
        conn.close()

# ===== STAFF FUNCTIONS =====
def get_staff():
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT staff_id, full_name, email, role, created_at FROM staff ORDER BY created_at DESC")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Get staff error: {e}")
        return []
    finally:
        conn.close()

def add_staff(name, email, role):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        staff_id = generate_staff_id()
        cursor.execute("INSERT INTO staff (staff_id, full_name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                      (staff_id, name, email, hash_password(DEFAULT_PASSWORD), role))
        conn.commit()
        return staff_id
    except Exception as e:
        st.error(f"Add staff error: {e}")
        return None
    finally:
        conn.close()

def remove_staff(staff_id):
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM staff WHERE staff_id = ?", (staff_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        st.error(f"Remove staff error: {e}")
        return False
    finally:
        conn.close()

# ===== CUSTOMER FUNCTIONS =====
def register_customer(passport_no, name, dob, nationality, email, phone, password):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        username = generate_username(name)
        cursor.execute("""
            INSERT INTO customers (passport_no, full_name, date_of_birth, nationality, 
            email, phone, username, password_hash) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (passport_no, name, dob, nationality, email, phone, username, hash_password(password)))
        conn.commit()
        return username
    except Exception as e:
        st.error(f"Register customer error: {e}")
        return None
    finally:
        conn.close()

def get_customers():
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT passport_no, full_name, date_of_birth, nationality,
                   email, phone, username, created_at
            FROM customers
            ORDER BY created_at DESC
        """)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Get customers error: {e}")
        return []
    finally:
        conn.close()

def add_customer(passport_no, name, dob, nationality, email, phone):
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        username = generate_username(name)
        cursor.execute("""
            INSERT INTO customers (passport_no, full_name, date_of_birth, nationality,
            email, phone, username, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (passport_no, name, dob, nationality, email, phone, username, hash_password(DEFAULT_PASSWORD)))
        conn.commit()
        return username
    except Exception as e:
        st.error(f"Add customer error: {e}")
        return None
    finally:
        conn.close()

def remove_customer(passport_no):
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM customers WHERE passport_no = ?", (passport_no,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        st.error(f"Remove customer error: {e}")
        return False
    finally:
        conn.close()
# ===== AIRCRAFT FUNCTIONS =====
def get_aircraft():
    """Retrieve all aircraft from the database"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, registration_no, aircraft_type, total_seats,
                   economy_seats, premium_economy_seats, business_seats, first_seats,
                   last_maintenance, next_maintenance
            FROM aircraft
            ORDER BY registration_no
        """)
        
        # Ensure ID is properly cast to int
        columns = [column[0] for column in cursor.description]
        aircraft_list = []
        for row in cursor.fetchall():
            aircraft = dict(zip(columns, row))
            aircraft['id'] = int(aircraft['id'])  # Ensure ID is integer
            aircraft_list.append(aircraft)
        return aircraft_list
    except Exception as e:
        st.error(f"Error retrieving aircraft: {str(e)}")
        return []
    finally:
        conn.close()

def add_aircraft(reg_no, aircraft_type, economy, premium, business, first, last_maint):
    conn = connect_db()
    try:
        cursor = conn.cursor()
        total_seats = economy + premium + business + first
        next_maint = last_maint + timedelta(days=180)
        
        cursor.execute("""
            INSERT INTO aircraft (
                registration_no, aircraft_type, total_seats,
                economy_seats, premium_economy_seats, business_seats, first_seats,
                last_maintenance, next_maintenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reg_no.upper(), aircraft_type, total_seats,
            economy, premium, business, first,
            last_maint, next_maint
        ))
        conn.commit()
        st.success("Aircraft added successfully!")
        return True  # Changed from returning ID to just success status
    except pyodbc.IntegrityError:
        st.error("An aircraft with this registration number already exists")
        return False
    except Exception as e:
        st.error(f"Error adding aircraft: {str(e)}")
        return False
    finally:
        conn.close()

# ===== FLIGHT FUNCTIONS =====
def get_flights(status_filter=None):
    """Retrieve flights with optional status filter, using aircraft registration numbers"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                f.id, 
                f.flight_no, 
                f.departure_airport, 
                f.arrival_airport,
                f.departure_time, 
                f.arrival_time, 
                a.registration_no as aircraft_reg,
                a.aircraft_type, 
                f.base_price, 
                f.status,
                (SELECT COUNT(*) FROM flight_seats fs 
                 WHERE fs.flight_id = f.id AND fs.is_available = 1) as available_seats
            FROM flights f
            JOIN aircraft a ON f.aircraft_id = a.id
        """
        params = []
        
        if status_filter:
            query += " WHERE f.status = ?"
            params.append(status_filter)
            
        query += " ORDER BY f.departure_time"
        cursor.execute(query, params)
        
        columns = [column[0] for column in cursor.description]
        flights = []
        for row in cursor.fetchall():
            flight = dict(zip(columns, row))
            # Convert datetime strings to datetime objects if needed
            if isinstance(flight['departure_time'], str):
                flight['departure_time'] = datetime.strptime(flight['departure_time'], '%Y-%m-%d %H:%M:%S')
            if isinstance(flight['arrival_time'], str):
                flight['arrival_time'] = datetime.strptime(flight['arrival_time'], '%Y-%m-%d %H:%M:%S')
            flights.append(flight)
        
        return flights
    except Exception as e:
        st.error(f"Error retrieving flights: {str(e)}")
        return []
    finally:
        conn.close()
def get_available_flights(departure_airport=None, arrival_airport=None, date=None):
    """Get available flights with optional filters, using aircraft registration numbers"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                f.id, 
                f.flight_no, 
                f.departure_airport, 
                f.arrival_airport,
                f.departure_time, 
                f.arrival_time, 
                f.aircraft_reg,
                a.aircraft_type, 
                f.base_price, 
                f.status,
                (SELECT COUNT(*) FROM flight_seats fs 
                 WHERE fs.flight_id = f.id AND fs.is_available = 1) as available_seats
            FROM flights f
            JOIN aircraft a ON f.aircraft_reg = a.registration_no
            WHERE f.status = 'Scheduled'
        """
        params = []
        
        if departure_airport:
            query += " AND f.departure_airport = ?"
            params.append(departure_airport)
        if arrival_airport:
            query += " AND f.arrival_airport = ?"
            params.append(arrival_airport)
        if date:
            query += " AND CAST(f.departure_time AS DATE) = ?"
            params.append(date)
        
        query += " ORDER BY f.departure_time"
        cursor.execute(query, params)
        
        columns = [column[0] for column in cursor.description]
        flights = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Filter out flights with no available seats
        return [flight for flight in flights if flight['available_seats'] > 0]
    except Exception as e:
        st.error(f"Error retrieving available flights: {str(e)}")
        return []
    finally:
        conn.close()
def get_flight_details(flight_id):
    """Get detailed information about a specific flight using aircraft registration number"""
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Get basic flight info - now joining on aircraft_reg instead of aircraft_id
        cursor.execute("""
            SELECT f.*, a.registration_no, a.aircraft_type,
                   a.economy_seats, a.premium_economy_seats,
                   a.business_seats, a.first_seats
            FROM flights f
            JOIN aircraft a ON f.aircraft_reg = a.registration_no
            WHERE f.id = ?
        """, (flight_id,))
        
        flight = cursor.fetchone()
        if not flight:
            return None
        
        columns = [column[0] for column in cursor.description]
        flight_dict = dict(zip(columns, flight))
        
        # Get seat availability by class (unchanged as it uses flight_id which is correct)
        cursor.execute("""
            SELECT seat_class, COUNT(*) as total,
                   SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available
            FROM flight_seats
            WHERE flight_id = ?
            GROUP BY seat_class
        """, (flight_id,))
        
        flight_dict['seat_availability'] = {
            row.seat_class: {'total': row.total, 'available': row.available}
            for row in cursor.fetchall()
        }
        
        return flight_dict
    except Exception as e:
        st.error(f"Error retrieving flight details: {str(e)}")
        return None
    finally:
        conn.close()

def get_available_seats(flight_id, seat_class):
    """Get list of available seats for a specific flight and class"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT seat_number
            FROM flight_seats
            WHERE flight_id = ? 
            AND seat_class = ? 
            AND is_available = 1
            ORDER BY seat_number
        """, (flight_id, seat_class))
        
        return [row.seat_number for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Error retrieving available seats: {str(e)}")
        return []
    finally:
        conn.close()
def add_flight(flight_no, dep_airport, arr_airport, departure_datetime, arrival_datetime, aircraft_reg, base_price):
    """
    Adds a new flight to the system using aircraft registration numbers instead of IDs
    with comprehensive validation and seat creation
    """
    # Validate all required fields are provided
    if not all([flight_no, dep_airport, arr_airport, departure_datetime, arrival_datetime, aircraft_reg, base_price]):
        st.error("All required fields must be filled")
        return False

    try:
        # Validate flight number format (2-3 letters + 1-4 numbers)
        flight_no = str(flight_no).strip().upper()
        if not re.match(r'^[A-Z]{2,3}\d{1,4}$', flight_no):
            st.error("Flight number must be 2-3 letters followed by 1-4 numbers (e.g., AA123)")
            return False

        # Validate airport codes (3 letters)
        dep_airport_code = dep_airport[:3].strip().upper()
        arr_airport_code = arr_airport[:3].strip().upper()
        
        if len(dep_airport_code) != 3 or not dep_airport_code.isalpha():
            st.error("Departure airport must be a 3-letter code")
            return False
        if len(arr_airport_code) != 3 or not arr_airport_code.isalpha():
            st.error("Arrival airport must be a 3-letter code")
            return False
        if dep_airport_code == arr_airport_code:
            st.error("Departure and arrival airports cannot be the same")
            return False

        # Validate dates and times
        if departure_datetime >= arrival_datetime:
            st.error("Arrival must be after departure")
            return False
        if (arrival_datetime - departure_datetime) < timedelta(minutes=30):
            st.error("Flight duration must be at least 30 minutes")
            return False
        if departure_datetime < datetime.now() - timedelta(hours=1):
            st.error("Departure cannot be in the past")
            return False

        # Validate base price
        try:
            base_price = round(float(base_price), 2)
            if base_price <= 0:
                st.error("Base price must be greater than 0")
                return False
        except ValueError:
            st.error("Base price must be a valid number")
            return False

        conn = connect_db()
        if not conn:
            st.error("Database connection failed")
            return False

        cursor = conn.cursor()

        try:
            # Verify aircraft exists using registration number
            cursor.execute("SELECT aircraft_type FROM aircraft WHERE registration_no = ?", (aircraft_reg,))
            aircraft_data = cursor.fetchone()
            if not aircraft_data:
                st.error("Selected aircraft does not exist")
                return False

            aircraft_type = aircraft_data[0]

            # Check for duplicate flight number
            cursor.execute("SELECT id FROM flights WHERE flight_no = ?", (flight_no,))
            if cursor.fetchone():
                st.error(f"Flight {flight_no} already exists")
                return False

            # Check aircraft availability using registration number
            cursor.execute("""
                SELECT flight_no FROM flights 
                WHERE aircraft_reg = ? 
                AND (
                    (departure_time BETWEEN ? AND ?)
                    OR (arrival_time BETWEEN ? AND ?)
                    OR (? BETWEEN departure_time AND arrival_time)
                    OR (? BETWEEN departure_time AND arrival_time)
                )
            """, (
                aircraft_reg,
                departure_datetime - timedelta(minutes=30),
                arrival_datetime + timedelta(minutes=30),
                departure_datetime - timedelta(minutes=30),
                arrival_datetime + timedelta(minutes=30),
                departure_datetime,
                arrival_datetime
            ))
            
            conflicting_flight = cursor.fetchone()
            if conflicting_flight:
                st.error(f"Aircraft is already booked for flight {conflicting_flight[0]} during this time period")
                return False

            # Insert flight record using registration number
            cursor.execute("""
                INSERT INTO flights (
                    flight_no, departure_airport, arrival_airport,
                    departure_time, arrival_time, aircraft_reg, base_price, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Scheduled')
            """, (
                flight_no,
                dep_airport_code,
                arr_airport_code,
                departure_datetime,
                arrival_datetime,
                aircraft_reg,
                base_price
            ))

            # Get the newly created flight ID
            cursor.execute("SELECT SCOPE_IDENTITY()")
            flight_id = cursor.fetchone()[0]
            if not flight_id:
                st.error("Failed to create flight record")
                conn.rollback()
                return False

            # Get aircraft seat configuration using registration number
            cursor.execute("""
                SELECT economy_seats, premium_economy_seats, business_seats, first_seats 
                FROM aircraft WHERE registration_no = ?
            """, (aircraft_reg,))
            seats = cursor.fetchone()
            if not seats:
                st.error("Could not retrieve aircraft seat configuration")
                conn.rollback()
                return False

            # Create seat configuration mapping
            seat_configurations = [
                ('Economy', seats[0], ['A', 'B', 'C', 'D', 'E', 'F']),
                ('Premium Economy', seats[1], ['A', 'B', 'C', 'D']),
                ('Business', seats[2], ['A', 'B']),
                ('First', seats[3], ['A'])
            ]

            # Create all seats for the flight
            for class_name, seat_count, letters in seat_configurations:
                prefix = {
                    'Premium Economy': 'P',
                    'Business': 'B',
                    'First': 'F'
                }.get(class_name, '')
                
                rows = (seat_count + len(letters) - 1) // len(letters)
                
                for row in range(1, rows + 1):
                    for letter in letters[:seat_count - (row-1)*len(letters)]:
                        seat_number = f"{prefix}{row}{letter}" if prefix else f"{row}{letter}"
                        try:
                            cursor.execute("""
                                INSERT INTO flight_seats (
                                    flight_id, seat_number, seat_class, is_available
                                ) VALUES (?, ?, ?, 1)
                            """, (flight_id, seat_number, class_name))
                        except Exception as e:
                            st.error(f"Failed to create seat {seat_number}: {str(e)}")
                            conn.rollback()
                            return False

            conn.commit()
            
            st.success(f"""
                ✈️ Flight {flight_no} successfully added!
                • Route: {dep_airport_code} → {arr_airport_code}
                • Departure: {departure_datetime.strftime('%Y-%m-%d %H:%M')}
                • Arrival: {arrival_datetime.strftime('%Y-%m-%d %H:%M')}
                • Aircraft: {aircraft_reg} ({aircraft_type})
                • Base Price: ${base_price:.2f}
            """)
            return True

        except pyodbc.Error as e:
            st.error(f"Database error: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return False
def update_flight_status(flight_id, new_status):
    """Update the status of a flight"""
    valid_statuses = ['Scheduled', 'Boarding', 'Departed', 'Arrived', 'Cancelled', 'Delayed']
    if new_status not in valid_statuses:
        st.error(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return False
    
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE flights 
            SET status = ? 
            WHERE id = ?
        """, (new_status, flight_id))
        
        if cursor.rowcount == 0:
            st.error("Flight not found")
            return False
        
        conn.commit()
        st.success(f"Flight status updated to '{new_status}'")
        return True
    except Exception as e:
        st.error(f"Error updating flight status: {str(e)}")
        return False
    finally:
        conn.close()

# ===== BOOKING FUNCTIONS =====
def get_bookings(customer_id=None, flight_id=None):
    """Retrieve bookings with optional filters"""
    conn = connect_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT b.id, b.booking_ref, b.booking_date,
                   c.full_name as customer_name, c.passport_no,
                   f.flight_no, f.departure_airport, f.arrival_airport,
                   f.departure_time, f.arrival_time,
                   b.seat_class, b.seat_count, b.total_amount, b.status
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            JOIN flights f ON b.flight_id = f.id
        """
        params = []
        
        if customer_id:
            query += " WHERE b.customer_id = ?"
            params.append(customer_id)
        elif flight_id:
            query += " WHERE b.flight_id = ?"
            params.append(flight_id)
        
        query += " ORDER BY b.booking_date DESC"
        cursor.execute(query, params)
        
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"Error retrieving bookings: {str(e)}")
        return []
    finally:
        conn.close()

def get_booking_details(booking_id):
    """Get detailed information about a specific booking"""
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Get booking info
        cursor.execute("""
            SELECT b.*, c.full_name as customer_name, c.email as customer_email,
                   f.flight_no, f.departure_airport, f.arrival_airport,
                   f.departure_time, f.arrival_time, f.base_price
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            JOIN flights f ON b.flight_id = f.id
            WHERE b.id = ?
        """, (booking_id,))
        
        booking = cursor.fetchone()
        if not booking:
            return None
        
        columns = [column[0] for column in cursor.description]
        booking_dict = dict(zip(columns, booking))
        
        # Get passengers
        cursor.execute("""
            SELECT full_name, passport_no, date_of_birth,
                   nationality, seat_number, special_requests
            FROM passengers
            WHERE booking_id = ?
        """, (booking_id,))
        
        booking_dict['passengers'] = [{
            'name': row.full_name,
            'passport': row.passport_no,
            'dob': row.date_of_birth,
            'nationality': row.nationality,
            'seat': row.seat_number,
            'requests': row.special_requests
        } for row in cursor.fetchall()]
        
        # Get payment info
        cursor.execute("""
            SELECT amount, payment_date, payment_method, status
            FROM payments
            WHERE booking_id = ?
        """, (booking_id,))
        
        payment = cursor.fetchone()
        if payment:
            booking_dict['payment'] = {
                'amount': payment.amount,
                'date': payment.payment_date,
                'method': payment.payment_method,
                'status': payment.status
            }
        
        return booking_dict
    except Exception as e:
        st.error(f"Error retrieving booking details: {str(e)}")
        return None
    finally:
        conn.close()

def create_booking(customer_id, flight_id, passengers, seat_class, selected_seats=None):
    """Create a new booking"""
    if not passengers or len(passengers) == 0:
        st.error("At least one passenger is required")
        return None
    
    conn = connect_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Verify flight exists and get base price
        cursor.execute("""
            SELECT base_price, departure_time 
            FROM flights 
            WHERE id = ? AND status = 'Scheduled'
        """, (flight_id,))
        flight_data = cursor.fetchone()
        
        if not flight_data:
            st.error("Flight not available for booking")
            return None
        
        base_price = flight_data.base_price
        departure_time = flight_data.departure_time
        
        # Calculate total amount
        price_multiplier = SEAT_PRICE_MULTIPLIERS.get(seat_class, 1.0)
        total_amount = base_price * price_multiplier * len(passengers)
        booking_ref = generate_booking_ref()
        
        # Create booking
        cursor.execute("""
            INSERT INTO bookings (
                booking_ref, customer_id, flight_id,
                seat_class, seat_count, total_amount
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            booking_ref, customer_id, flight_id,
            seat_class, len(passengers), total_amount
        ))
        
        booking_id = cursor.execute("SELECT SCOPE_IDENTITY()").fetchone()[0]
        
        # Add passengers
        for i, passenger in enumerate(passengers):
            seat_number = selected_seats[i] if selected_seats and i < len(selected_seats) else None
            
            cursor.execute("""
                INSERT INTO passengers (
                    booking_id, full_name, passport_no,
                    date_of_birth, nationality, seat_number, special_requests
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                booking_id, passenger['name'], passenger['passport'],
                passenger['dob'], passenger['nationality'], 
                seat_number, passenger.get('requests', '')
            ))
            
            # Mark seat as occupied if assigned
            if seat_number:
                cursor.execute("""
                    UPDATE flight_seats
                    SET is_available = 0, booking_id = ?
                    WHERE flight_id = ? AND seat_number = ?
                """, (booking_id, flight_id, seat_number))
        
        # Record payment
        cursor.execute("""
            INSERT INTO payments (
                booking_id, amount, payment_method, status
            ) VALUES (?, ?, 'Credit Card', 'Completed')
        """, (booking_id, total_amount))
        
        conn.commit()
        st.success(f"Booking created successfully! Reference: {booking_ref}")
        return booking_ref
    except Exception as e:
        conn.rollback()
        st.error(f"Error creating booking: {str(e)}")
        return None
    finally:
        conn.close()

def cancel_booking(booking_id):
    """Cancel an existing booking"""
    conn = connect_db()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Get booking details
        cursor.execute("""
            SELECT flight_id, status 
            FROM bookings 
            WHERE id = ?
        """, (booking_id,))
        booking = cursor.fetchone()
        
        if not booking:
            st.error("Booking not found")
            return False
        
        if booking.status == 'Cancelled':
            st.error("Booking is already cancelled")
            return False
        
        # Free up seats
        cursor.execute("""
            UPDATE flight_seats
            SET is_available = 1, booking_id = NULL
            WHERE booking_id = ?
        """, (booking_id,))
        
        # Update booking status
        cursor.execute("""
            UPDATE bookings
            SET status = 'Cancelled'
            WHERE id = ?
        """, (booking_id,))
        
        # Update payment status
        cursor.execute("""
            UPDATE payments
            SET status = 'Refunded'
            WHERE booking_id = ?
        """, (booking_id,))
        
        conn.commit()
        st.success("Booking cancelled successfully")
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Error cancelling booking: {str(e)}")
        return False
    finally:
        conn.close()

# ===== STREAMLIT UI =====
def main():
    st.set_page_config(
        page_title="Airline Booking System",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS with premium styling
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
            
            :root {
                --sky-blue: #0077b6;
                --deep-ocean: #023e8a;
                --sunset-orange: #ff7b00;
                --cloud-white: #f8f9fa;
                --golden-sun: #ffd166;
                --twilight-purple: #6a4c93;
                --jet-black: #212529;
                --success-green: #06d6a0;
            }
            
            body, .stApp {
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }
            
            /* Main container styling */
            .main {
                background-color: rgba(255, 255, 255, 0.9);
                border-radius: 16px;
                box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
                backdrop-filter: blur(4px);
                border: 1px solid rgba(255, 255, 255, 0.18);
                margin: 1rem;
                padding: 1.5rem;
            }
            
            /* Header styling */
            .st-emotion-cache-10trblm {
                color: var(--deep-ocean);
                font-weight: 700;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                font-size: 2.5rem;
                background: linear-gradient(to right, var(--sky-blue), var(--twilight-purple));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            /* Button styling */
            .stButton>button {
                background: linear-gradient(45deg, var(--sky-blue), var(--deep-ocean));
                color: white;
                border-radius: 12px;
                padding: 0.75rem 1.5rem;
                border: none;
                font-weight: 600;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                box-shadow: 0 4px 8px rgba(0, 119, 182, 0.2);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0, 119, 182, 0.3);
                background: linear-gradient(45deg, var(--deep-ocean), var(--sky-blue));
            }
            
            /* Input fields */
            .stTextInput>div>div>input, 
            .stTextArea>div>div>textarea, 
            .stSelectbox>div>div>select,
            .stDateInput>div>div>input {
                background-color: rgba(255, 255, 255, 0.8);
                color: var(--jet-black);
                border-radius: 10px;
                border: 2px solid rgba(0, 119, 182, 0.2);
                padding: 0.75rem;
                transition: all 0.3s ease;
            }
            
            .stTextInput>div>div>input:focus, 
            .stTextArea>div>div>textarea:focus, 
            .stSelectbox>div>div>select:focus,
            .stDateInput>div>div>input:focus {
                border-color: var(--sky-blue);
                box-shadow: 0 0 0 2px rgba(0, 119, 182, 0.2);
            }
            
            /* Cards and containers */
            .st-expander, .custom-card {
                background: rgba(255, 255, 255, 0.8);
                border-radius: 16px;
                padding: 1.5rem;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.3);
                margin-bottom: 1.5rem;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                backdrop-filter: blur(5px);
            }
            
            .st-expander:hover, .custom-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
            }
            
            /* Tabs */
            .stTab>div>div>button {
                color: var(--jet-black);
                font-weight: 500;
                padding: 0.75rem 1.5rem;
                border-radius: 8px 8px 0 0;
                transition: all 0.3s ease;
            }
            
            .stTab>div>div>button[aria-selected="true"] {
                color: var(--sky-blue);
                background: rgba(0, 119, 182, 0.1);
                border-bottom: 3px solid var(--sky-blue);
            }
            
            /* Sidebar */
            .sidebar .sidebar-content {
                background: linear-gradient(180deg, var(--deep-ocean), var(--sky-blue));
                color: white;
                padding: 2rem 1rem;
                border-right: none;
            }
            
            /* Radio buttons in sidebar */
            .stRadio>div>label {
                color: white !important;
                font-weight: 500;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                transition: all 0.3s ease;
            }
            
            .stRadio>div>label:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .stRadio>div>div[aria-checked="true"]>label {
                background: rgba(255, 255, 255, 0.2);
                color: white !important;
            }
            
            /* DataFrame enhancements */
            .stDataFrame {
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            }
            
            /* Status messages */
            .stAlert {
                border-radius: 12px;
                font-weight: 500;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            }
            
            .stAlert.success {
                background: linear-gradient(135deg, rgba(6, 214, 160, 0.1), rgba(6, 214, 160, 0.2));
                border-left: 4px solid var(--success-green);
            }
            
            .stAlert.warning {
                background: linear-gradient(135deg, rgba(255, 184, 0, 0.1), rgba(255, 184, 0, 0.2));
                border-left: 4px solid var(--golden-sun);
            }
            
            .stAlert.error {
                background: linear-gradient(135deg, rgba(239, 71, 111, 0.1), rgba(239, 71, 111, 0.2));
                border-left: 4px solid #ef476f;
            }
            
            /* Footer */
            .footer {
                text-align: center;
                padding: 1.5rem;
                color: var(--jet-black);
                font-size: 0.9rem;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 12px;
                margin-top: 2rem;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            }
            
            /* Responsive */
            @media (max-width: 768px) {
                .st-expander, .custom-card {
                    padding: 1rem;
                }
                
                .stButton>button {
                    padding: 0.5rem 1rem;
                }
            }
        </style>
    """, unsafe_allow_html=True)

    # Premium Hero Section with animated gradient
    st.markdown("""
        <div style="
            padding: 3rem 0; 
            text-align: center;
            background: linear-gradient(135deg, #0077b6, #023e8a, #6a4c93);
            background-size: 200% 200%;
            animation: gradient 8s ease infinite;
            border-radius: 16px;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        ">
            <h1 style="
                color: white;
                font-size: 3rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                text-shadow: 1px 1px 3px rgba(0,0,0,0.2);
            ">✈️ Airline Booking System</h1>
            <p style="
                color: rgba(255,255,255,0.9);
                font-size: 1.3rem;
                max-width: 800px;
                margin: 0 auto;
            ">Experience the future of air travel with our seamless booking platform</p>
        </div>
        
        <style>
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize database and session
    if not init_db():
        st.error("Failed to initialize database")
        return
    
    if 'auth' not in st.session_state:
        st.session_state.auth = {
            'logged_in': False,
            'user_type': None,  # 'admin', 'staff', or 'customer'
            'user_data': None
        }
    
    # ===== AUTHENTICATION SCREENS =====
    if not st.session_state.auth['logged_in']:
        render_auth_screen()
    else:
        if st.session_state.auth['user_type'] == 'admin':
            render_admin_dashboard()
        elif st.session_state.auth['user_type'] == 'staff':
            render_staff_dashboard()
        else:
            render_customer_dashboard()

def render_auth_screen():
    st.title("✈️ Airline Booking System")
    st.markdown("---")
    
    # Create tabs for different login types
    tab1, tab2, tab3 = st.tabs(["Admin Login", "Staff Login", "Customer Login/Register"])
    
    with tab1:
        st.subheader("Admin Login")
        with st.form("admin_login"):
            user = st.text_input("Username", key="admin_user")
            pwd = st.text_input("Password", type="password", key="admin_pwd")
            
            if st.form_submit_button("Login", use_container_width=True):
                admin = admin_login(user, pwd)
                if admin:
                    st.session_state.auth = {
                        'logged_in': True,
                        'user_type': 'admin',
                        'user_data': admin
                    }
                    st.rerun()
                else:
                    st.error("Invalid admin credentials")
    
    with tab2:
        st.subheader("Staff Login")
        with st.form("staff_login"):
            staff_id = st.text_input("Staff ID", key="staff_id")
            pwd = st.text_input("Password", type="password", key="staff_pwd")
            
            if st.form_submit_button("Login", use_container_width=True):
                staff = staff_login(staff_id, pwd)
                if staff:
                    st.session_state.auth = {
                        'logged_in': True,
                        'user_type': 'staff',
                        'user_data': staff
                    }
                    st.rerun()
                else:
                    st.error("Invalid staff credentials")
    
    with tab3:
        # Customer section with login and registration
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Customer Login")
            with st.form("customer_login"):
                username = st.text_input("Username", key="cust_user")
                pwd = st.text_input("Password", type="password", key="cust_pwd")
                
                if st.form_submit_button("Login", use_container_width=True):
                    customer = customer_login(username, pwd)
                    if customer:
                        st.session_state.auth = {
                            'logged_in': True,
                            'user_type': 'customer',
                            'user_data': customer
                        }
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        
        with col2:
            st.subheader("New Customer Registration")
            with st.form("customer_registration"):
                passport = st.text_input("Passport Number*", key="reg_passport")
                name = st.text_input("Full Name*", key="reg_name")
                dob = st.date_input("Date of Birth*", 
                                  min_value=datetime(1900, 1, 1), 
                                  max_value=datetime.now(),
                                  key="reg_dob")
                nationality = st.text_input("Nationality*", key="reg_nationality")
                email = st.text_input("Email*", key="reg_email")
                phone = st.text_input("Phone Number*", key="reg_phone")
                password = st.text_input("Password*", type="password", key="reg_pwd")
                confirm = st.text_input("Confirm Password*", type="password", key="reg_confirm")
                
                if st.form_submit_button("Register", use_container_width=True):
                    # Validate all fields
                    if not all([passport, name, dob, nationality, email, phone, password, confirm]):
                        st.error("Please fill all required fields (*)")
                    elif not validate_passport(passport):
                        st.error("Invalid passport number (min 6 alphanumeric characters)")
                    elif not validate_email(email):
                        st.error("Invalid email address")
                    elif not validate_phone(phone):
                        st.error("Invalid phone number (min 10 digits)")
                    elif password != confirm:
                        st.error("Passwords don't match")
                    elif customer_exists(email, passport):
                        st.error("Customer with this email or passport already exists")
                    else:
                        username = register_customer(passport, name, dob, nationality, email, phone, password)
                        if username:
                            st.success(f"Registration successful! Your username is: {username}")
                            st.info("Please login with your new credentials")
def render_admin_dashboard():
    st.sidebar.title("Admin Dashboard")
    menu = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Manage Staff", "Manage Customers", "Manage Aircraft", "Manage Flights", "System Settings"],
        index=0
    )
    
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.auth = {
            'logged_in': False,
            'user_type': None,
            'user_data': None
        }
        st.rerun()
    
    st.title(f"Admin Panel - {menu}")
    
    if menu == "Dashboard":
        st.subheader("System Overview")
        
        stats = get_flight_stats()
        if stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Bookings", stats['total_bookings'])
            with col2:
                st.metric("Total Revenue", f"${stats['total_revenue']:,.2f}")
            with col3:
                st.metric("Active Flights", stats['flight_status'].get('Scheduled', 0))
            
            # Flight status pie chart
            st.subheader("Flight Status Distribution")
            if stats['flight_status']:
                fig = px.pie(
                    names=list(stats['flight_status'].keys()),
                    values=list(stats['flight_status'].values()),
                    hole=0.3
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Popular routes
            st.subheader("Top Routes")
            if stats['popular_routes']:
                routes = [r['route'] for r in stats['popular_routes']]
                counts = [r['bookings'] for r in stats['popular_routes']]
                
                fig = px.bar(
                    x=counts,
                    y=routes,
                    orientation='h',
                    labels={'x': 'Number of Bookings', 'y': 'Route'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Recent bookings
            st.subheader("Recent Bookings")
            if stats['recent_bookings']:
                df = pd.DataFrame(stats['recent_bookings'])
                st.dataframe(df)
    
    elif menu == "Manage Staff":
        tab1, tab2 = st.tabs(["Add Staff", "View/Remove Staff"])
        
        with tab1:
            with st.form("add_staff"):
                name = st.text_input("Full Name*")
                email = st.text_input("Email*")
                role = st.selectbox("Role*", ["Manager", "Agent", "Operations"])
                
                if st.form_submit_button("Add Staff", use_container_width=True):
                    if name and email and validate_email(email):
                        staff_id = add_staff(name, email, role)
                        if staff_id:
                            st.success(f"Staff added successfully! ID: {staff_id}")
                    else:
                        st.error("Please fill all required fields with valid data")
        
        with tab2:
            st.subheader("Current Staff")
            staff_list = get_staff()
            
            if staff_list:
                df = pd.DataFrame(staff_list)
                st.dataframe(df)
                
                with st.expander("Remove Staff"):
                    staff_id = st.selectbox(
                        "Select Staff ID to remove",
                        [s['staff_id'] for s in staff_list],
                        key="remove_staff"
                    )
                    
                    if st.button("Remove Staff", use_container_width=True):
                        if remove_staff(staff_id):
                            st.success("Staff removed successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to remove staff")
            else:
                st.info("No staff found")
    
    elif menu == "Manage Customers":
        tab1, tab2 = st.tabs(["Add Customer", "View/Remove Customers"])
        
        with tab1:
            with st.form("add_customer"):
                passport = st.text_input("Passport Number*")
                name = st.text_input("Full Name*")
                dob = st.date_input("Date of Birth*", min_value=datetime(1900, 1, 1), max_value=datetime.now())
                nationality = st.text_input("Nationality*")
                email = st.text_input("Email*")
                phone = st.text_input("Phone Number*")
                
                if st.form_submit_button("Add Customer", use_container_width=True):
                    if (passport and name and dob and nationality and email and phone and 
                        validate_passport(passport) and validate_email(email) and validate_phone(phone)):
                        username = add_customer(passport, name, dob, nationality, email, phone)
                        if username:
                            st.success(f"Customer added successfully! Username: {username}")
                    else:
                        st.error("Please fill all required fields with valid data")
        
        with tab2:
            st.subheader("Current Customers")
            customers = get_customers()
            
            if customers:
                df = pd.DataFrame(customers)
                st.dataframe(df)
                
                with st.expander("Remove Customer"):
                    passport = st.selectbox(
                        "Select Passport Number to remove",
                        [c['passport_no'] for c in customers],
                        key="remove_customer"
                    )
                    
                    if st.button("Remove Customer", use_container_width=True):
                        if remove_customer(passport):
                            st.success("Customer removed successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to remove customer")
            else:
                st.info("No customers found")
    
    elif menu == "Manage Aircraft":
        tab1, tab2 = st.tabs(["Add Aircraft", "View Aircraft"])
        
        with tab1:
            with st.form("add_aircraft"):
                reg_no = st.text_input("Registration Number*").strip().upper()
                aircraft_type = st.selectbox("Aircraft Type*", AIRCRAFT_TYPES)
                
                col1, col2 = st.columns(2)
                with col1:
                    economy = st.number_input("Economy Seats*", min_value=0, value=150)
                    premium = st.number_input("Premium Economy Seats*", min_value=0, value=30)
                with col2:
                    business = st.number_input("Business Seats*", min_value=0, value=20)
                    first = st.number_input("First Class Seats*", min_value=0, value=10)
                
                last_maint = st.date_input("Last Maintenance Date*")
                
                if st.form_submit_button("Add Aircraft", use_container_width=True):
                    if reg_no and aircraft_type and last_maint:
                        if add_aircraft(reg_no, aircraft_type, economy, premium, business, first, last_maint):
                            st.success("Aircraft added successfully!")
                    else:
                        st.error("Please fill all required fields")
        
        with tab2:
            st.subheader("Current Aircraft")
            aircraft_list = get_aircraft()
            
            if aircraft_list:
                df = pd.DataFrame(aircraft_list)
                st.dataframe(df)
            else:
                st.info("No aircraft found")
    
    elif menu == "Manage Flights":
        tab1, tab2, tab3 = st.tabs(["Add Flight", "View Flights", "Update Status"])
        
        with tab1:
            with st.form("add_flight"):
                aircraft_list = get_aircraft()
                
                flight_no = st.text_input("Flight Number (e.g., AA123)*").strip().upper()
                dep_airport = st.selectbox("Departure Airport*", AIRPORTS).split(" - ")[0]
                arr_airport = st.selectbox("Arrival Airport*", [a for a in AIRPORTS if a != dep_airport]).split(" - ")[0]
                
                col1, col2 = st.columns(2)
                with col1:
                    dep_date = st.date_input("Departure Date*", min_value=datetime.now())
                    dep_time = st.time_input("Departure Time*", value=datetime.now().time())
                with col2:
                    arr_date = st.date_input("Arrival Date*", min_value=dep_date)
                    arr_time = st.time_input("Arrival Time*", value=(datetime.now() + timedelta(hours=1)).time())
                
                # Combine date and time
                departure_datetime = datetime.combine(dep_date, dep_time)
                arrival_datetime = datetime.combine(arr_date, arr_time)
                
                # Aircraft selection using aircraft ID
                aircraft_id = st.selectbox(
                    "Aircraft*",
                    [(a['id'], f"{a['registration_no']} - {a['aircraft_type']}") for a in aircraft_list],
                    format_func=lambda x: x[1],
                    key="aircraft_select"
                )
                
                base_price = st.number_input("Base Price (Economy)*", min_value=0.0, value=200.0)
                
                if st.form_submit_button("Add Flight", use_container_width=True):
                    if add_flight(
                        flight_no=flight_no,
                        dep_airport=dep_airport,
                        arr_airport=arr_airport,
                        departure_datetime=departure_datetime,
                        arrival_datetime=arrival_datetime,
                        aircraft_id=aircraft_id[0],  # Get the ID from the tuple
                        base_price=base_price
                    ):
                        st.rerun()
        
        with tab2:
            st.subheader("Current Flights")
            flights = get_flights()
            
            if flights:
                df = pd.DataFrame(flights)
                st.dataframe(
                    df,
                    column_config={
                        "departure_time": st.column_config.DatetimeColumn("Departure"),
                        "arrival_time": st.column_config.DatetimeColumn("Arrival"),
                        "base_price": st.column_config.NumberColumn("Base Price", format="$%.2f")
                    }
                )
            else:
                st.info("No flights scheduled")
        
        with tab3:
            st.subheader("Update Flight Status")
            flights = get_flights()
            
            if flights:
                flight = st.selectbox(
                    "Select Flight",
                    [(f['id'], f"{f['flight_no']} - {f['status']}") for f in flights],
                    format_func=lambda x: x[1],
                    key="update_flight_status"
                )
                
                new_status = st.selectbox(
                    "New Status",
                    ["Scheduled", "Boarding", "Departed", "Arrived", "Cancelled", "Delayed"],
                    key="new_flight_status"
                )
                
                if st.button("Update Status", use_container_width=True):
                    if update_flight_status(flight[0], new_status):
                        st.success("Flight status updated successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to update flight status")
    
    elif menu == "System Settings":
        st.subheader("Admin Account Settings")
        
        with st.form("change_password"):
            current = st.text_input("Current Password*", type="password")
            new = st.text_input("New Password*", type="password")
            confirm = st.text_input("Confirm Password*", type="password")
            
            if st.form_submit_button("Change Password", use_container_width=True):
                if new != confirm:
                    st.error("New passwords don't match!")
                elif hash_password(current) != st.session_state.auth['user_data']['password_hash']:
                    st.error("Current password incorrect")
                elif update_password("admins", "username", PRESET_ADMIN["username"], new):
                    st.success("Password changed successfully!")
                    st.session_state.auth['user_data']['password_hash'] = hash_password(new)
                else:
                    st.error("Failed to update password")
def render_staff_dashboard():
    staff = st.session_state.auth['user_data']
    st.sidebar.title(f"Welcome, {staff['full_name']}")
    
    menu = st.sidebar.radio(
        "Menu",
        ["Search Flights", "Create Booking", "View Bookings", "Flight Management"],
        index=0
    )
    
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.auth = {
            'logged_in': False,
            'user_type': None,
            'user_data': None
        }
        st.rerun()
    
    st.title(f"Staff Portal - {menu}")
    
    if menu == "Search Flights":
        st.subheader("Flight Search")
        
        with st.form("flight_search"):
            col1, col2 = st.columns(2)
            with col1:
                dep_airport = st.selectbox(
                    "Departure Airport", 
                    [""] + [a.split(" - ")[0] for a in AIRPORTS],
                    key="staff_dep_airport"
                )
                flight_date = st.date_input("Date", datetime.now(), key="staff_flight_date")
            with col2:
                arr_airport = st.selectbox(
                    "Arrival Airport", 
                    [""] + [a.split(" - ")[0] for a in AIRPORTS],
                    key="staff_arr_airport"
                )
            
            if st.form_submit_button("Search", use_container_width=True):
                flights = get_available_flights(dep_airport, arr_airport, flight_date)
                
                if flights:
                    st.subheader("Available Flights")
                    
                    for flight in flights:
                        with st.expander(f"{flight['flight_no']}: {flight['departure_airport']} → {flight['arrival_airport']}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Departure:** {flight['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(f"**Arrival:** {flight['arrival_time'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(f"**Duration:** {calculate_flight_duration(flight['departure_time'], flight['arrival_time'])}")
                            with col2:
                                st.write(f"**Aircraft:** {flight['aircraft_type']}")
                                st.write(f"**Base Price:** ${flight['base_price']:.2f}")
                                st.write(f"**Available Seats:** {flight['available_seats']}")
                else:
                    st.info("No flights found matching your criteria")
    
    elif menu == "Create Booking":
        st.subheader("Create New Booking")
        
        # Step 1: Select Customer
        customers = get_customers()
        customer = st.selectbox(
            "Select Customer",
            [(c['passport_no'], f"{c['full_name']} ({c['passport_no']})") for c in customers],
            format_func=lambda x: x[1],
            key="booking_customer"
        )
        
        if customer:
            # Step 2: Select Flight
            flights = get_available_flights()
            flight = st.selectbox(
                "Select Flight",
                [(f['id'], f"{f['flight_no']}: {f['departure_airport']} → {f['arrival_airport']} on {f['departure_time'].strftime('%Y-%m-%d')}") for f in flights],
                format_func=lambda x: x[1],
                key="booking_flight"
            )
            
            if flight:
                flight_details = get_flight_details(flight[0])
                
                if flight_details:
                    # Step 3: Select Seat Class
                    seat_class = st.selectbox(
                        "Seat Class",
                        SEAT_CLASSES,
                        index=0,
                        key="booking_seat_class"
                    )
                    
                    # Show seat availability for selected class
                    if seat_class in flight_details['seat_availability']:
                        available = flight_details['seat_availability'][seat_class]['available']
                        st.write(f"**Available {seat_class} Seats:** {available}")
                        
                        # Step 4: Enter Passenger Details
                        passenger_count = st.number_input(
                            "Number of Passengers",
                            min_value=1,
                            max_value=available,
                            value=1,
                            key="booking_passenger_count"
                        )
                        
                        passengers = []
                        selected_seats = []
                        
                        # Visual seat selection
                        if seat_class and passenger_count:
                            st.session_state['passenger_count'] = passenger_count
                            selected_seats = visualize_seat_map(flight[0], seat_class)
                        
                        for i in range(passenger_count):
                            with st.expander(f"Passenger {i+1} Details"):
                                name = st.text_input(f"Full Name*", key=f"name_{i}")
                                passport = st.text_input(f"Passport Number*", key=f"passport_{i}")
                                dob = st.date_input(
                                    f"Date of Birth*", 
                                    min_value=datetime(1900, 1, 1), 
                                    max_value=datetime.now(),
                                    key=f"dob_{i}"
                                )
                                nationality = st.text_input(f"Nationality*", key=f"nationality_{i}")
                                
                                # Assign seat if available
                                seat = selected_seats[i] if i < len(selected_seats) else ""
                                st.text_input(f"Seat", value=seat, key=f"seat_{i}", disabled=True)
                                
                                passengers.append({
                                    'name': name,
                                    'passport': passport,
                                    'dob': dob,
                                    'nationality': nationality,
                                    'seat': seat
                                })
                        
                        # Payment method
                        payment_method = st.selectbox(
                            "Payment Method",
                            ["Credit Card", "Debit Card", "Cash"],
                            key="payment_method"
                        )
                        
                        # Calculate total price
                        total_amount = flight_details['base_price'] * SEAT_PRICE_MULTIPLIERS[seat_class] * passenger_count
                        st.write(f"**Total Amount:** ${total_amount:.2f}")
                        
                        # Confirm and book
                        if st.button("Create Booking", use_container_width=True, key="confirm_booking"):
                            # Validate passenger data
                            valid = True
                            for p in passengers:
                                if not p['name'] or not validate_passport(p['passport']):
                                    valid = False
                                    break
                            
                            if valid:
                                # Get customer ID
                                conn = connect_db()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    SELECT id FROM customers WHERE passport_no = ?
                                """, (customer[0],))
                                customer_id = cursor.fetchone()[0]
                                conn.close()
                                
                                # Create booking
                                booking_ref = create_booking(
                                    customer_id,
                                    flight[0],
                                    passengers,
                                    seat_class,
                                    [p['seat'] for p in passengers if p['seat']]
                                )
                                
                                if booking_ref:
                                    # Send confirmation email
                                    email_body = f"""
                                    Thank you for your booking!
                                    
                                    Booking Reference: {booking_ref}
                                    Flight: {flight_details['flight_no']}
                                    Departure: {flight_details['departure_time'].strftime('%Y-%m-%d %H:%M')}
                                    From: {flight_details['departure_airport']}
                                    To: {flight_details['arrival_airport']}
                                    
                                    Passengers: {passenger_count}
                                    Total Paid: ${total_amount:.2f}
                                    
                                    Please present this information at check-in.
                                    """
                                    
                                    send_email(
                                        [c for c in customers if c['passport_no'] == customer[0]][0]['email'],
                                        f"Booking Confirmation: {booking_ref}",
                                        email_body
                                    )
                                    
                                    st.success(f"Booking created successfully! Reference: {booking_ref}")
                            else:
                                st.error("Please fill all required passenger details correctly")
    
    elif menu == "View Bookings":
        st.subheader("All Bookings")
        bookings = get_bookings()
        
        if bookings:
            df = pd.DataFrame(bookings)
            st.dataframe(df)
            
            # Detailed view
            booking_id = st.selectbox(
                "Select Booking to View Details",
                [(b['id'], b['booking_ref']) for b in bookings],
                format_func=lambda x: x[1],
                key="view_booking"
            )
            
            if booking_id:
                details = get_booking_details(booking_id[0])
                
                if details:
                    st.subheader(f"Booking Details - {details['booking_ref']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Customer:** {details['customer_name']}")
                        st.write(f"**Email:** {details['customer_email']}")
                        st.write(f"**Booking Date:** {details['booking_date'].strftime('%Y-%m-%d %H:%M')}")
                    with col2:
                        st.write(f"**Flight:** {details['flight_no']}")
                        st.write(f"**Route:** {details['departure_airport']} → {details['arrival_airport']}")
                        st.write(f"**Departure:** {details['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                    
                    st.subheader("Passengers")
                    for i, pax in enumerate(details['passengers'], 1):
                        st.write(f"{i}. {pax['name']} ({pax['passport']}) - Seat: {pax['seat'] or 'Not assigned'}")
                    
                    st.subheader("Payment")
                    if 'payment' in details:
                        st.write(f"**Amount:** ${details['payment']['amount']:.2f}")
                        st.write(f"**Method:** {details['payment']['method']}")
                        st.write(f"**Status:** {details['payment']['status']}")
                    
                    # Generate ticket button
                    if st.button("Generate Ticket", key=f"ticket_{booking_id[0]}"):
                        ticket_file = generate_ticket_pdf(details)
                        
                        with open(ticket_file, "rb") as f:
                            st.download_button(
                                "Download Ticket",
                                f,
                                file_name=f"ticket_{details['booking_ref']}.pdf"
                            )
                        
                        # Clean up
                        os.remove(ticket_file)
                    
                    if st.button("Cancel Booking", use_container_width=True, key="cancel_booking"):
                        if cancel_booking(booking_id[0]):
                            st.success("Booking cancelled successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to cancel booking")
        else:
            st.info("No bookings found")
    
    elif menu == "Flight Management":
        st.subheader("Flight Management")
        
        flights = get_flights()
        if flights:
            flight = st.selectbox(
                "Select Flight",
                [(f['id'], f"{f['flight_no']}: {f['departure_airport']} → {f['arrival_airport']} on {f['departure_time'].strftime('%Y-%m-%d')}") for f in flights],
                format_func=lambda x: x[1],
                key="manage_flight"
            )
            
            if flight:
                details = get_flight_details(flight[0])
                
                if details:
                    st.subheader("Flight Details")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Flight Number:** {details['flight_no']}")
                        st.write(f"**Aircraft:** {details['aircraft_type']} ({details['registration_no']})")
                        st.write(f"**Departure:** {details['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                    with col2:
                        st.write(f"**Route:** {details['departure_airport']} → {details['arrival_airport']}")
                        st.write(f"**Arrival:** {details['arrival_time'].strftime('%Y-%m-%d %H:%M')}")
                        st.write(f"**Status:** {details['status']}")
                    
                    st.subheader("Seat Availability")
                    for cls, avail in details['seat_availability'].items():
                        st.write(f"{cls}: {avail['available']} of {avail['total']} available")
                    
                    st.subheader("Passenger Manifest")
                    bookings = get_bookings(flight_id=flight[0])
                    
                    if bookings:
                        manifest = []
                        for booking in bookings:
                            details = get_booking_details(booking['id'])
                            for pax in details['passengers']:
                                manifest.append({
                                    'Name': pax['name'],
                                    'Passport': pax['passport'],
                                    'Seat': pax['seat'],
                                    'Class': booking['seat_class'],
                                    'Booking Ref': booking['booking_ref']
                                })
                        
                        st.dataframe(pd.DataFrame(manifest))
                    else:
                        st.info("No passengers booked on this flight")
        
        # Update flight status
        st.subheader("Update Flight Status")
        if flights:
            flight = st.selectbox(
                "Select Flight to Update",
                [(f['id'], f"{f['flight_no']} - {f['status']}") for f in flights],
                format_func=lambda x: x[1],
                key="update_flight_status"
            )
            
            new_status = st.selectbox(
                "New Status",
                ["Scheduled", "Boarding", "Departed", "Arrived", "Cancelled", "Delayed"],
                key="new_flight_status"
            )
            
            if st.button("Update Status", use_container_width=True):
                if update_flight_status(flight[0], new_status):
                    st.success("Flight status updated successfully!")
                    st.rerun()
                else:
                    st.error("Failed to update flight status")
    
    # Password change option
    with st.sidebar.expander("Change Password"):
        with st.form("staff_change_pass"):
            current = st.text_input("Current Password", type="password", key="staff_current_pass")
            new = st.text_input("New Password", type="password", key="staff_new_pass")
            confirm = st.text_input("Confirm Password", type="password", key="staff_confirm_pass")
            
            if st.form_submit_button("Update Password", use_container_width=True):
                if new != confirm:
                    st.error("New passwords don't match!")
                elif hash_password(current) != staff['password_hash']:
                    st.error("Current password incorrect")
                elif update_password("staff", "staff_id", staff['staff_id'], new):
                    st.success("Password updated successfully!")
                    st.session_state.auth['user_data']['password_hash'] = hash_password(new)
                    st.session_state.auth['user_data']['must_change_pass'] = False
                else:
                    st.error("Failed to update password")

def render_customer_dashboard():
    customer = st.session_state.auth['user_data']
    st.sidebar.title(f"Welcome, {customer['full_name']}")
    
    menu = st.sidebar.radio(
        "Menu",
        ["Search Flights", "My Bookings", "My Profile"],
        index=0
    )
    
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.auth = {
            'logged_in': False,
            'user_type': None,
            'user_data': None
        }
        st.rerun()
    
    st.title(f"Customer Portal - {menu}")
    
    if menu == "Search Flights":
        st.subheader("Flight Search")
        
        with st.form("flight_search"):
            col1, col2 = st.columns(2)
            with col1:
                dep_airport = st.selectbox(
                    "Departure Airport", 
                    [""] + [a.split(" - ")[0] for a in AIRPORTS],
                    key="cust_dep_airport"
                )
                flight_date = st.date_input("Date", datetime.now(), key="cust_flight_date")
            with col2:
                arr_airport = st.selectbox(
                    "Arrival Airport", 
                    [""] + [a.split(" - ")[0] for a in AIRPORTS],
                    key="cust_arr_airport"
                )
            
            if st.form_submit_button("Search", use_container_width=True):
                flights = get_available_flights(dep_airport, arr_airport, flight_date)
                
                if flights:
                    st.subheader("Available Flights")
                    
                    for flight in flights:
                        with st.expander(f"{flight['flight_no']}: {flight['departure_airport']} → {flight['arrival_airport']}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Departure:** {flight['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(f"**Arrival:** {flight['arrival_time'].strftime('%Y-%m-%d %H:%M')}")
                                st.write(f"**Duration:** {calculate_flight_duration(flight['departure_time'], flight['arrival_time'])}")
                            with col2:
                                st.write(f"**Aircraft:** {flight['aircraft_type']}")
                                st.write(f"**Base Price:** ${flight['base_price']:.2f}")
                                st.write(f"**Available Seats:** {flight['available_seats']}")
                            
                            if st.button("Book This Flight", key=f"book_{flight['id']}"):
                                st.session_state['selected_flight'] = flight
                                st.rerun()
                else:
                    st.info("No flights found matching your criteria")
        
        if 'selected_flight' in st.session_state:
            flight = st.session_state.selected_flight
            st.subheader(f"Book Flight {flight['flight_no']}")
            
            flight_details = get_flight_details(flight['id'])
            
            if flight_details:
                seat_class = st.selectbox(
                    "Seat Class",
                    SEAT_CLASSES,
                    index=0,
                    key="cust_seat_class"
                )
                
                if seat_class in flight_details['seat_availability']:
                    available = flight_details['seat_availability'][seat_class]['available']
                    st.write(f"**Available {seat_class} Seats:** {available}")
                    
                    passenger_count = st.number_input(
                        "Number of Passengers",
                        min_value=1,
                        max_value=available,
                        value=1,
                        key="cust_passenger_count"
                    )
                    
                    passengers = []
                    selected_seats = []
                    
                    if seat_class and passenger_count:
                        st.session_state['passenger_count'] = passenger_count
                        selected_seats = visualize_seat_map(flight['id'], seat_class)
                    
                    for i in range(passenger_count):
                        with st.expander(f"Passenger {i+1} Details"):
                            name = st.text_input(f"Full Name*", key=f"cust_name_{i}")
                            passport = st.text_input(f"Passport Number*", key=f"cust_passport_{i}")
                            dob = st.date_input(
                                f"Date of Birth*", 
                                min_value=datetime(1900, 1, 1), 
                                max_value=datetime.now(),
                                key=f"cust_dob_{i}"
                            )
                            nationality = st.text_input(f"Nationality*", key=f"cust_nationality_{i}")
                            
                            seat = selected_seats[i] if i < len(selected_seats) else ""
                            st.text_input(f"Seat", value=seat, key=f"cust_seat_{i}", disabled=True)
                            
                            passengers.append({
                                'name': name,
                                'passport': passport,
                                'dob': dob,
                                'nationality': nationality,
                                'seat': seat
                            })
                    
                    promo_code = st.text_input("Promotion Code (optional)", key="promo_code")
                    discount = 0
                    
                    if promo_code:
                        conn = connect_db()
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT discount_percent FROM promotions 
                            WHERE code = ? AND valid_from <= ? AND valid_to >= ? 
                            AND (max_uses IS NULL OR current_uses < max_uses)
                        """, (promo_code, datetime.now().date(), datetime.now().date()))
                        promo = cursor.fetchone()
                        conn.close()
                        
                        if promo:
                            discount = promo[0]
                            st.success(f"Promo code applied! {discount}% discount")
                        else:
                            st.error("Invalid or expired promo code")
                    
                    base_amount = flight_details['base_price'] * SEAT_PRICE_MULTIPLIERS[seat_class] * passenger_count
                    discounted_amount = base_amount * (1 - discount/100)
                    st.write(f"**Total Amount:** ${discounted_amount:.2f} {'(with discount)' if discount else ''}")
                    
                    payment_method = st.selectbox(
                        "Payment Method",
                        ["Credit Card", "Debit Card", "PayPal"],
                        key="cust_payment_method"
                    )
                    
                    if st.button("Confirm Booking", use_container_width=True, key="cust_confirm_booking"):
                        valid = True
                        for p in passengers:
                            if not p['name'] or not validate_passport(p['passport']):
                                valid = False
                                break
                        
                        if valid:
                            booking_ref = create_booking(
                                customer['id'],
                                flight['id'],
                                passengers,
                                seat_class,
                                [p['seat'] for p in passengers if p['seat']]
                            )
                            
                            if booking_ref:
                                if promo_code and discount:
                                    conn = connect_db()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE promotions 
                                        SET current_uses = current_uses + 1
                                        WHERE code = ?
                                    """, (promo_code,))
                                    conn.commit()
                                    conn.close()
                                
                                points_earned = int(discounted_amount / 100) * 10
                                conn = connect_db()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE customers 
                                    SET loyalty_points = loyalty_points + ?
                                    WHERE id = ?
                                """, (points_earned, customer['id']))
                                conn.commit()
                                conn.close()
                                
                                st.session_state.auth['user_data']['loyalty_points'] += points_earned
                                
                                email_body = f"""
                                Thank you for your booking!
                                
                                Booking Reference: {booking_ref}
                                Flight: {flight['flight_no']}
                                Departure: {flight['departure_time'].strftime('%Y-%m-%d %H:%M')}
                                From: {flight['departure_airport']}
                                To: {flight['arrival_airport']}
                                
                                Passengers: {passenger_count}
                                Total Paid: ${discounted_amount:.2f}
                                Loyalty Points Earned: {points_earned}
                                
                                Please present this information at check-in.
                                """
                                
                                send_email(
                                    customer['email'],
                                    f"Booking Confirmation: {booking_ref}",
                                    email_body
                                )
                                
                                st.success(f"Booking created successfully! Reference: {booking_ref}")
                                st.info(f"You earned {points_earned} loyalty points!")
                                del st.session_state['selected_flight']
                                st.rerun()
                        else:
                            st.error("Please fill all passenger details correctly")
    
    elif menu == "My Bookings":
        st.subheader("My Bookings")
        bookings = get_customer_bookings(customer['id'])
        
        if bookings:
            for booking in bookings:
                with st.expander(f"Booking {booking['booking_ref']} - {booking['status']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Flight:** {booking['flight_no']}")
                        st.write(f"**Route:** {booking['departure_airport']} → {booking['arrival_airport']}")
                        st.write(f"**Passengers:** {booking['passenger_count']}")
                    with col2:
                        st.write(f"**Departure:** {booking['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                        st.write(f"**Class:** {booking['seat_class']}")
                        st.write(f"**Total Paid:** ${booking['total_amount']:.2f}")
                    
                    if st.button("View Details", key=f"view_{booking['id']}"):
                        booking_details = get_booking_details(booking['id'])
                        if booking_details:
                            st.session_state['view_booking'] = booking_details
                    
                    if (booking['status'] == 'Confirmed' and 
                        booking['departure_time'] > datetime.now()):
                        if st.button("Cancel Booking", key=f"cancel_{booking['id']}"):
                            if cancel_booking(booking['id']):
                                email_body = f"""
                                Your booking {booking['booking_ref']} has been cancelled.
                                
                                Flight: {booking['flight_no']}
                                Route: {booking['departure_airport']} → {booking['arrival_airport']}
                                Departure: {booking['departure_time'].strftime('%Y-%m-%d %H:%M')}
                                
                                Refund will be processed within 7-10 business days.
                                """
                                send_email(
                                    customer['email'],
                                    f"Booking Cancelled: {booking['booking_ref']}",
                                    email_body
                                )
                                st.success("Booking cancelled successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to cancel booking")
        
            if 'view_booking' in st.session_state:
                details = st.session_state['view_booking']
                st.subheader(f"Booking Details - {details['booking_ref']}")
                
                with st.container():
                    st.write(f"**Flight:** {details['flight_no']}")
                    st.write(f"**Route:** {details['departure_airport']} → {details['arrival_airport']}")
                    st.write(f"**Departure:** {details['departure_time'].strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Arrival:** {details['arrival_time'].strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Duration:** {calculate_flight_duration(details['departure_time'], details['arrival_time'])}")
                    st.write(f"**Class:** {details['seat_class']}")
                
                st.subheader("Passengers")
                for i, pax in enumerate(details['passengers'], 1):
                    st.write(f"{i}. {pax['name']} ({pax['passport']}) - Seat: {pax['seat'] or 'Not assigned'}")
                
                if 'payment' in details:
                    st.subheader("Payment")
                    st.write(f"**Amount:** ${details['payment']['amount']:.2f}")
                    st.write(f"**Method:** {details['payment']['method']}")
                    st.write(f"**Status:** {details['payment']['status']}")
                
                if st.button("Download E-Ticket"):
                    ticket_file = generate_ticket_pdf(details)
                    
                    email_body = f"""
                    Thank you for booking with us!
                    
                    Booking Reference: {details['booking_ref']}
                    Flight: {details['flight_no']}
                    Departure: {details['departure_time'].strftime('%Y-%m-%d %H:%M')}
                    
                    Your e-ticket is attached. Please present it at the airport.
                    """
                    
                    if send_email(
                        customer['email'],
                        f"Your E-Ticket: {details['booking_ref']}",
                        email_body,
                        ticket_file
                    ):
                        st.success("E-ticket sent to your email!")
                    else:
                        with open(ticket_file, "rb") as f:
                            st.download_button(
                                "Download Ticket",
                                f,
                                file_name=f"ticket_{details['booking_ref']}.pdf"
                            )
                    
                    os.remove(ticket_file)
                
                if st.button("Close Details"):
                    del st.session_state['view_booking']
                    st.rerun()
        else:
            st.info("You have no bookings yet")
    
    elif menu == "My Profile":
        st.subheader("My Profile")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {customer['full_name']}")
            st.write(f"**Passport:** {customer['passport_no']}")
            st.write(f"**Date of Birth:** {customer['date_of_birth'].strftime('%Y-%m-%d')}")
        with col2:
            st.write(f"**Nationality:** {customer['nationality']}")
            st.write(f"**Email:** {customer['email']}")
            st.write(f"**Phone:** {customer['phone']}")
        
        st.subheader("Loyalty Program")
        try:
            # Safely get and convert loyalty points
            loyalty_points = int(float(customer.get('loyalty_points', 0)))
            st.write(f"**Your Points:** {loyalty_points}")
            
            # Calculate progress with bounds checking
            progress_value = min(max(loyalty_points / 1000, 0), 1.0)  # Ensure between 0 and 1
            st.progress(progress_value)
            
            # Determine tier status
            if loyalty_points >= 1000:
                st.success("⭐ Silver Tier Member")
                next_tier = "Gold (2000 points)"
                points_needed = max(2000 - loyalty_points, 0)
            elif loyalty_points >= 500:
                st.info("🛫 Approaching Silver Tier")
                next_tier = "Silver (1000 points)"
                points_needed = max(1000 - loyalty_points, 0)
            else:
                st.warning("✈️ New Member")
                next_tier = "Silver (1000 points)"
                points_needed = max(1000 - loyalty_points, 0)
            
            st.caption(f"Earn {points_needed} more points to reach {next_tier}")
            
        except (TypeError, ValueError) as e:
            st.error("Error displaying loyalty points")
            st.write(f"**Your Points:** 0")
            st.progress(0)
            st.caption("Earn 1000 points to reach Silver status")
        
        with st.expander("Change Password"):
            with st.form("change_pass"):
                current = st.text_input("Current Password", type="password", key="cust_current_pass")
                new = st.text_input("New Password", type="password", key="cust_new_pass")
                confirm = st.text_input("Confirm Password", type="password", key="cust_confirm_pass")
                
                if st.form_submit_button("Update Password", use_container_width=True):
                    if new != confirm:
                        st.error("New passwords don't match!")
                    elif hash_password(current) != customer['password_hash']:
                        st.error("Current password incorrect")
                    elif update_password("customers", "username", customer['username'], new):
                        st.success("Password updated successfully!")
                        st.session_state.auth['user_data']['password_hash'] = hash_password(new)
                        st.session_state.auth['user_data']['must_change_pass'] = False
                    else:
                        st.error("Failed to update password")

if __name__ == "__main__":
    main()