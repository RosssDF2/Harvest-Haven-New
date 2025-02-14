from urllib.request import Request

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import EnhancedDatabaseManager
import shelve

profile_bp = Blueprint('profile', __name__)
db_manager = EnhancedDatabaseManager()

@profile_bp.route('/')
def home():
    """Redirect to profile page."""
    if 'user_id' in session:
        return redirect(url_for('profile.profile'))
    return redirect(url_for('profile.login'))

@profile_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Log in or create an account."""
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        users = db_manager.get_users()

        if action == 'login':
            user = users.get(username)
            if user and user.get('password') == password:
                session['user_id'] = username
                session['role'] = user['role']
                flash(f"Welcome back, {user['name']}!", "success")
                # Redirect to the appropriate profile page based on role
                return redirect(url_for('profile.profile'))
            flash("Invalid username or password.", "error")

        elif action == 'create_account':
            if username in users:
                flash("Username already exists.", "error")
            elif role not in ['customer', 'farmer']:
                flash("Invalid role selected.", "error")
            else:
                db_manager.create_profile(
                    username, name=username, email=f"{username}@example.com", role=role, points=100, password=password
                )
                session['user_id'] = username
                session['role'] = role
                flash("Account created successfully!", "success")
                return redirect(url_for('profile.profile'))

    return render_template('profile_login.html')

@profile_bp.route('/reset_password')
def reset_request():
    return render_template('reset_request.html',title='Reset Request',form=form)


@profile_bp.route('/profile')
@profile_bp.route('/profile')
@profile_bp.route('/profile')
def profile():
    """Display user profile."""
    if 'user_id' not in session:
        return redirect(url_for('profile.login'))

    user_id = session['user_id']
    user = db_manager.get_users().get(user_id)
    nav_options = db_manager.get_nav_options(session['role'])

    if not user:
        flash("User not found.", "error")
        return redirect(url_for('profile.login'))

    user_points = user.get("points", 0)
    user_balance = round(user.get("balance", 0), 2)
    transactions = db_manager.get_transactions(user_id)
    return_history = db_manager.get_return_transactions(user_id)

    if session['role'] == 'customer':
        return render_template(
            "customer_profile.html",
            user=user,
            nav_options=nav_options,
            user_points=user_points,
            user_balance=user_balance,
            transactions=transactions,
            return_history=return_history,
        )
    elif session['role'] == 'farmer':
        return render_template(
            "farmer_profile.html",
            user=user,
            nav_options=nav_options,
            user_points=user_points,
            user_balance=user_balance,
        )
    else:
        flash("Invalid role.", "error")
        return redirect(url_for('profile.login'))




@profile_bp.route('/logout')
def logout():
    """Log out the user."""
    session.clear()  # Clear the session to log out
    flash("You have been logged out.", "success")
    return redirect(url_for('profile.login'))

@profile_bp.route('/add_points', methods=['POST'])
def add_points():
    """Allow farmers to add points to a customer from the farmer profile."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add points.", "error")
        return redirect(url_for('profile.profile'))

    username = request.form.get('username')
    points_to_add = request.form.get('points')

    if not username or not points_to_add:
        flash("Both username and points are required.", "error")
        return redirect(url_for('profile.profile'))

    try:
        points_to_add = int(points_to_add)
        users = db_manager.get_users()

        if username in users:
            users[username]["points"] += points_to_add

            # Save the users dictionary directly to the database
            with shelve.open(db_manager.db_name, writeback=True) as db:
                db["users"] = users

            flash(f"Added {points_to_add} points to {username}!", "success")
        else:
            flash(f"User {username} not found.", "error")

    except ValueError:
        flash("Invalid points input. Please enter a valid number.", "error")

    return redirect(url_for('profile.profile'))
