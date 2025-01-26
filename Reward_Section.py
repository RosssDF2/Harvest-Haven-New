from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from database import EnhancedDatabaseManager
import shelve
from datetime import datetime


reward_bp = Blueprint('rewards', __name__)
db_manager = EnhancedDatabaseManager()

POINTS_CONVERSION_RATE = 100  # $1 = 100 points

@reward_bp.route('/')
def rewards():
    """Display rewards available for customers."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can access rewards.", "error")
        return redirect(url_for('profile.profile'))

    user_points = db_manager.get_users().get(session.get('user_id'), {}).get("points", 0)
    products = db_manager.get_products()

    reward_products = [
        {
            "id": product_id,
            "name": product_data["name"],
            "points": int(product_data["price"] * POINTS_CONVERSION_RATE),
            "stock": product_data["quantity"],
            "image_url": product_data["image_url"],
        }
        for product_id, product_data in products.items()
    ]

    nav_options = db_manager.get_nav_options(session.get('role'))

    return render_template(
        "customer_rewards.html",
        products=reward_products,
        user_points=user_points,
        nav_options=nav_options,
    )


@reward_bp.route('/redeem/<int:product_id>', methods=['POST'])
def redeem_product(product_id):
    """Allow customers to redeem products with points."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can redeem rewards.", "error")
        return redirect(url_for('rewards.rewards'))

    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        users = db.get("users", {})
        products = db.get("products", {})
        ownership = db.setdefault("ownership", {})
        transactions = db.setdefault("transactions", {})

        user = users.get(user_id)
        product = products.get(product_id)

        if not user:
            flash("User not found.", "error")
            return redirect(url_for('rewards.rewards'))
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for('rewards.rewards'))

        required_points = int(product["price"] * POINTS_CONVERSION_RATE)

        if user["points"] < required_points:
            flash("Not enough points to redeem this product.", "error")
            return redirect(url_for('rewards.rewards'))
        if product["quantity"] <= 0:
            flash("This product is out of stock.", "error")
            return redirect(url_for('rewards.rewards'))

        # Deduct points and update stock
        user["points"] -= required_points
        product["quantity"] -= 1

        # Add the redeemed product to the user's ownership
        user_ownership = ownership.setdefault(user_id, {})
        owned_products = user_ownership.setdefault("products", [])
        owned_products.append(product_id)

        # Log transaction
        user_transactions = transactions.setdefault(user_id, [])
        user_transactions.append({
            "product_name": product["name"],
            "amount": 0,
            "quantity": 1,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Save changes back to the database
        db["users"] = users
        db["products"] = products
        db["ownership"] = ownership
        db["transactions"] = transactions

    flash(f"Successfully redeemed '{product['name']}'!", "success")
    return redirect(url_for('rewards.rewards'))





@reward_bp.route('/plant_a_future', methods=['GET'])
def plant_a_future():
    """Display the Plant a Future page for customers."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can access this page.", "error")
        return redirect(url_for('profile.profile'))

    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    # Fetch tree and ownership data
    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        plants = ownership.get("plants", [])

        # Ensure `trees` is a valid dictionary
        trees = {tree["id"]: tree for tree in plants if "id" in tree and "type" in tree}

        tree_types = db.get("tree_types", {})  # Fetch tree types from the database

    nav_options = db_manager.get_nav_options(session.get('role'))
    user_balance = db_manager.get_users().get(user_id, {}).get("balance", 0)
    user_points = db_manager.get_users().get(user_id, {}).get("points", 0)

    return render_template(
        "customer_plant_a_future.html",
        nav_options=nav_options,
        trees=trees,
        tree_types=tree_types,
        user_balance=user_balance,
        user_points=user_points,
        points_conversion_rate=POINTS_CONVERSION_RATE,
    )






@reward_bp.route('/update_tree/<int:tree_id>', methods=['POST'])
def update_tree(tree_id):
    user_id = session.get('user_id')
    ownership = db_manager.get_ownership(user_id)
    trees = ownership.get("plants", [])
    tree = next((t for t in trees if t["id"] == tree_id), None)

    if not tree:
        flash("Tree not found.", "error")
        return redirect(url_for('rewards.plant_a_future'))

    current_time = datetime.now()
    planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
    elapsed_time = (current_time - planted_time).seconds

    if elapsed_time >= 30:
        if not (tree["watered"] and tree["fertilized"]):
            tree["health"] -= 1
            if tree["health"] <= 0:
                flash("Your plant died due to neglect.", "error")
            else:
                flash("Your plant lost health due to neglect.", "warning")
        else:
            flash("Your plant is ready to move to the next phase!", "success")
            tree["is_ready"] = True  # Mark plant as ready

    # Save updates
    ownership["plants"] = trees
    db_manager.save_ownership(user_id, ownership)
    return redirect(url_for('rewards.plant_a_future'))


@reward_bp.route('/next_phase/<int:tree_id>', methods=['POST'])
def next_phase(tree_id):
    """Handle tree progression or claiming rewards for mature trees."""
    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        user_ownership = ownership.get(user_id, {})
        trees = user_ownership.get("plants", [])
        users = db.get("users", {})

        # Get the tree and user
        tree = next((t for t in trees if t["id"] == tree_id), None)
        user = users.get(user_id)

        if not tree or not user:
            flash("Tree or user not found.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Validate watering and fertilizing status for all phases, including Mature Tree
        if not tree["watered"] or not tree["fertilized"]:
            flash("Please water and fertilize the tree before proceeding!", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Handle claiming rewards for Mature Tree
        if tree["phase"] == "Mature Tree":
            tree_type = next((t for t_name, t in db.get("tree_types", {}).items() if t["name"] == tree["type"]), None)
            if tree_type:
                investment_return = tree_type["investment_return"]

                # Reward the user with 2x the investment return
                user["balance"] += investment_return * 2
                flash(f"Congratulations! You claimed ${investment_return * 2:.2f} for your mature tree.", "success")

                # Remove the tree after claiming
                trees.remove(tree)

                # Save changes
                user_ownership["plants"] = trees
                db["users"] = users
                db["ownership"][user_id] = user_ownership
            else:
                flash("Tree type information not found. Unable to process claim.", "error")

            return redirect(url_for('rewards.plant_a_future'))

        # Handle progression to the next phase
        phases = ["Seedling", "Plant", "Growing Tree", "Mature Tree"]
        current_index = phases.index(tree["phase"])
        if current_index < len(phases) - 1:
            tree["phase"] = phases[current_index + 1]
            tree["watered"] = False
            tree["fertilized"] = False
            tree["planted_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tree["time_remaining"] = 30
            flash(f"Your tree has moved to the next phase: {tree['phase']}!", "success")

        # Save changes
        user_ownership["plants"] = trees
        db["ownership"][user_id] = user_ownership

    return redirect(url_for('rewards.plant_a_future'))





@reward_bp.route('/plant_tree', methods=['POST'])
def plant_tree():
    """Allow customers to plant a new tree."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can plant trees.", "error")
        return redirect(url_for('rewards.plant_a_future'))

    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    tree_type = request.form.get('tree_type')
    payment_method = request.form.get('payment_method')

    if not tree_type or not payment_method:
        flash("Please select a tree type and payment method.", "error")
        return redirect(url_for('rewards.plant_a_future'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        users = db.get("users", {})
        ownership = db.setdefault("ownership", {})

        user = users.get(user_id)
        tree_info = db["tree_types"].get(tree_type)

        if not tree_info:
            flash("Invalid tree type selected.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Validate payment
        tree_cost = tree_info["price"]
        if payment_method == "balance" and user["balance"] < tree_cost:
            flash("Insufficient balance to plant this tree.", "error")
            return redirect(url_for('rewards.plant_a_future'))
        elif payment_method == "points" and user["points"] < tree_cost * POINTS_CONVERSION_RATE:
            flash("Insufficient points to plant this tree.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Deduct payment
        if payment_method == "balance":
            user["balance"] -= tree_cost
        else:
            user["points"] -= tree_cost * POINTS_CONVERSION_RATE

        # Add the tree to ownership
        user_trees = ownership.setdefault(user_id, {}).setdefault("plants", [])
        new_tree_id = len(user_trees) + 1
        new_tree = {
            "id": new_tree_id,
            "type": tree_info["name"],
            "phase": "Seedling",
            "health": 2,
            "planted_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "watered": False,
            "fertilized": False,
            "time_remaining": 30,
        }
        user_trees.append(new_tree)

        # Save changes
        db["users"] = users
        db["ownership"] = ownership

    flash(f"Successfully planted a {tree_info['name']}!", "success")
    return redirect(url_for('rewards.plant_a_future'))



@reward_bp.route('/water_tree/<int:tree_id>', methods=['POST'])
def water_tree(tree_id):
    """Handle watering of a tree, deducting $5."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can water trees.", "error")
        return redirect(url_for('rewards.plant_a_future'))

    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        users = db.get("users", {})

        # Find the tree and user
        tree = next((t for t in trees if t["id"] == tree_id), None)
        user = users.get(user_id)

        if not tree or not user:
            flash("Tree or user not found.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Deduct $5 and water the tree
        if user["balance"] < 5:
            flash("Insufficient balance to water the tree.", "error")
        elif tree["watered"]:
            flash("This tree has already been watered for the current phase.", "info")
        else:
            user["balance"] -= 5
            tree["watered"] = True
            flash(f"Tree '{tree['type']}' watered successfully! ($5 deducted)", "success")

        # Save changes
        ownership["plants"] = trees
        db["ownership"][user_id] = ownership
        db["users"] = users

    return redirect(url_for('rewards.plant_a_future'))


@reward_bp.route('/fertilize_tree/<int:tree_id>', methods=['POST'])
def fertilize_tree(tree_id):
    """Handle fertilizing of a tree, deducting $10."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can fertilize trees.", "error")
        return redirect(url_for('rewards.plant_a_future'))

    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        users = db.get("users", {})

        # Find the tree and user
        tree = next((t for t in trees if t["id"] == tree_id), None)
        user = users.get(user_id)

        if not tree or not user:
            flash("Tree or user not found.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Deduct $10 and fertilize the tree
        if user["balance"] < 10:
            flash("Insufficient balance to fertilize the tree.", "error")
        elif tree["fertilized"]:
            flash("This tree has already been fertilized for the current phase.", "info")
        else:
            user["balance"] -= 10
            tree["fertilized"] = True
            flash(f"Tree '{tree['type']}' fertilized successfully! ($10 deducted)", "success")

        # Save changes
        ownership["plants"] = trees
        db["ownership"][user_id] = ownership
        db["users"] = users

    return redirect(url_for('rewards.plant_a_future'))


@reward_bp.route('/delete_tree/<int:tree_id>', methods=['POST'])
def delete_tree(tree_id):
    """Delete a tree from the user's ownership."""
    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])

        # Find and remove the tree
        tree = next((t for t in trees if t["id"] == tree_id), None)
        if tree:
            trees.remove(tree)
            flash(f"Tree '{tree['type']}' has been deleted.", "success")
        else:
            flash("Tree not found.", "error")

        # Save changes
        ownership["plants"] = trees
        db["ownership"][user_id] = ownership

    return redirect(url_for('rewards.plant_a_future'))

def update_tree_times(user_id):
    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        current_time = datetime.now()

        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            remaining_time = max(30 - elapsed_time, 0)  # 30 seconds per phase

            tree["time_remaining"] = int(remaining_time)  # Update time_remaining
            if remaining_time <= 0 and not (tree["watered"] and tree["fertilized"]):
                tree["health"] = 0  # Mark as dead if not fulfilled

        ownership["plants"] = trees
        db["ownership"][user_id] = ownership

@reward_bp.route('/get_trees', methods=['GET'])
def get_trees():
    """Return updated tree data for real-time countdown."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized access"}), 403

    with shelve.open(db_manager.db_name) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        current_time = datetime.now()

        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            tree["time_remaining"] = max(30 - elapsed_time, 0)  # Update time_remaining
            tree["next_phase_enabled"] = (
                tree["time_remaining"] <= 0 and tree["watered"] and tree["fertilized"]
            )  # Enable next phase only if timer is 0 and criteria are met
            if tree["time_remaining"] <= 0 and not (tree["watered"] and tree["fertilized"]):
                tree["health"] = 0  # Mark as dead if not fulfilled

    return jsonify({"trees": trees})
