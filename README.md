# RedBus Clone - Bus Booking Website

A complete full-stack bus booking web application built with Python Flask, SQLite, and vanilla web technologies (HTML5, CSS3, JavaScript).

## Features
- **Modern UI**: Clean, responsive design with smooth animations.
- **Dark Mode**: Built-in dark mode support (toggles automatically or manually).
- **Search System**: Search buses by source, destination, and date.
- **Interactive Seat Selection**: Visual grid to pick seats and see live pricing.
- **Authentication**: Secure user login and registration.
- **Admin Panel**: Manage buses, routes, and view platform statistics.
- **E-Tickets**: Printable ticket generation with PNR.

## Prerequisites
- Python 3.8+
- pip

## Installation and Setup

1. **Clone the repository or navigate to the project directory:**
   ```bash
   cd "bus project"
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   ```bash
   python app.py
   ```
   *Note: On the first run, the SQLite database (`database.db`) will be created automatically and seeded with some initial data.*

5. **Access the Website:**
   Open your browser and navigate to: `http://127.0.0.1:5000`

## Admin Access
An admin account is created by default when the database is initialized:
- **Email**: admin@redbus.local
- **Password**: admin123

Use these credentials to log in and access the Admin Dashboard to add new buses and routes.
