from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

reward_bp = Blueprint('rewards', __name__)
db_manager = EnhancedDatabaseManager()

@reward_bp.route('/')
def rewards():
    """Display rewards available for customers."""
    reward_products = db_manager.get_reward_products()
    nav_options = db_manager.get_nav_options(session.get('role'))
    user_points = db_manager.get_users().get(session.get('user_id'), {}).get("points", 0)

    return render_template(
        "customer_rewards.html",
        products=reward_products.values(),
        user_points=user_points,
        nav_options=nav_options,
    )

@reward_bp.route('/add_reward', methods=['POST'])
def add_reward():
    """Allow farmers to add reward products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add rewards.", "error")
        return redirect(url_for('rewards.rewards'))

    name = request.form.get('name')
    points = int(request.form.get('points'))
    quantity = int(request.form.get('quantity'))

    reward_products = db_manager.get_reward_products()
    product_id = max(reward_products.keys(), default=0) + 1

    db_manager.add_reward_product(product_id, name, points, quantity)
    flash(f"Reward '{name}' added successfully!", "success")
    return redirect(url_for('rewards.rewards'))

@reward_bp.route('/plant_a_future', methods=['GET'])
def plant_a_future():
    """Display the Plant a Future page for customers."""
    nav_options = db_manager.get_nav_options(session.get('role'))
    plants = db_manager.get_ownership(session['user_id']).get("plants", [])

    return render_template(
        "customer_plant_future.html",
        plants=plants,
        nav_options=nav_options,
    )
