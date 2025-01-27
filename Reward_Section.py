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

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        plants = ownership.get("plants", [])
        farmers = {k: v for k, v in db["users"].items() if v["role"] == "farmer"}  # Filter farmers

        # Check for dead trees and notify the customer
        for tree in plants:
            if tree["phase"] == "Dead" and not tree.get("notified", False):
                farmer_id = tree.get("farmer_id")
                farmer_name = farmers.get(farmer_id, {}).get("name", "Unknown Farmer")
                flash(f"Your tree '{tree['type']}' was marked as dead by {farmer_name}. "
                      f"Reason: {tree.get('kill_reason', 'No reason provided')}", "info")
                tree["notified"] = True  # Mark as notified

        # Calculate remaining time for each tree
        current_time = datetime.now()
        for tree in plants:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            tree["time_remaining"] = max(30 - int(elapsed_time), 0)

        trees = {tree["id"]: tree for tree in plants}
        tree_types = db.get("tree_types", {})

    nav_options = db_manager.get_nav_options(session.get('role'))
    user_balance = db_manager.get_users().get(user_id, {}).get("balance", 0)
    user_points = db_manager.get_users().get(user_id, {}).get("points", 0)

    return render_template(
        "customer_plant_a_future.html",
        nav_options=nav_options,
        trees=trees,
        tree_types=tree_types,
        farmers=farmers,  # Pass farmers to the template
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

                # Remove the tree after claiming from both customer and farmer
                trees.remove(tree)

                # Remove the tree from the farmer's ownership
                farmer_id = tree.get("farmer_id")
                if farmer_id:
                    farmer_ownership = ownership.get(farmer_id, {})
                    farmer_trees = farmer_ownership.get("plants", [])
                    farmer_tree = next((t for t in farmer_trees if t["id"] == tree_id), None)
                    if farmer_tree:
                        farmer_trees.remove(farmer_tree)
                        ownership[farmer_id] = farmer_ownership

                # Save changes
                user_ownership["plants"] = trees
                db["users"] = users
                db["ownership"][user_id] = user_ownership
                db["ownership"] = ownership
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

    user_id = session.get('user_id')  # Customer ID
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    # Retrieve form data
    farmer_id = request.form.get('farmer_id')  # Farmer ID
    tree_type = request.form.get('tree_type')
    payment_method = request.form.get('payment_method')

    if not farmer_id or not tree_type or not payment_method:
        flash("Please select a farmer, tree type, and payment method.", "error")
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
        customer_trees = ownership.setdefault(user_id, {}).setdefault("plants", [])
        farmer_trees = ownership.setdefault(farmer_id, {}).setdefault("plants", [])
        new_tree_id = len(customer_trees) + 1
        new_tree = {
            "id": new_tree_id,
            "type": tree_info["name"],
            "phase": "Seedling",
            "health": 2,
            "planted_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "watered": False,
            "fertilized": False,
            "time_remaining": 30,
            "customer_id": user_id,  # Link to customer
            "farmer_id": farmer_id,  # Link to farmer
        }
        customer_trees.append(new_tree)
        farmer_trees.append(new_tree)

        # Save changes
        db["users"] = users
        db["ownership"] = ownership

    flash(f"Successfully planted a {tree_info['name']} with Farmer {farmer_id}!", "success")
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
    """Delete a tree from both the customer's and farmer's ownership."""
    user_id = session.get('user_id')
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        customer_ownership = ownership.get(user_id, {})
        customer_trees = customer_ownership.get("plants", [])

        # Find the tree in the customer's ownership
        tree = next((t for t in customer_trees if t["id"] == tree_id), None)
        if not tree:
            flash("Tree not found in your records.", "error")
            return redirect(url_for('rewards.plant_a_future'))

        # Remove the tree from the customer's ownership
        customer_trees.remove(tree)

        # Also remove the tree from the farmer's ownership
        farmer_id = tree.get("farmer_id")
        if farmer_id:
            farmer_ownership = ownership.get(farmer_id, {})
            farmer_trees = farmer_ownership.get("plants", [])
            farmer_tree = next((t for t in farmer_trees if t["id"] == tree_id), None)
            if farmer_tree:
                farmer_trees.remove(farmer_tree)

        # Save changes to the database
        ownership[user_id] = customer_ownership
        if farmer_id:
            ownership[farmer_id] = farmer_ownership
        db["ownership"] = ownership

    flash(f"Tree '{tree['type']}' has been deleted.", "success")
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

@reward_bp.route('/farmer_plant_a_future', methods=['GET'])
def farmer_plant_a_future():
    """Display all trees planted in the farmer's field."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can access this page.", "error")
        return redirect(url_for('profile.profile'))

    user_id = session.get('user_id')  # Farmer's ID
    if not user_id:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        plants = ownership.get("plants", [])
        users = db.get("users", {})  # Retrieve all users (customers and farmers)

        # Debugging print statements
        print(f"Farmer ID: {user_id}")
        print(f"Farmer Plants: {plants}")
        print(f"Users in Database: {users}")

        # Group trees by customer
        customers = {}
        for plant in plants:
            customer_id = plant.get("customer_id")
            if not customer_id:
                print(f"Plant {plant['id']} is missing customer_id")
                continue  # Skip if no customer_id is associated

            # Get customer data from the database
            customer = users.get(customer_id, {})
            if not customer:
                print(f"Customer ID {customer_id} not found in users")
                continue

            if customer_id not in customers:
                customers[customer_id] = {
                    "name": customer.get("name", "Unknown Customer"),
                    "email": customer.get("email", "No Email"),
                    "balance": customer.get("balance", 0),
                    "trees": [],
                }
            customers[customer_id]["trees"].append(plant)

    print(f"Final Grouped Customers: {customers}")  # Debug final grouping

    nav_options = db_manager.get_nav_options(session.get('role'))

    return render_template(
        "farmer_plant_a_future.html",
        nav_options=nav_options,
        customers=customers  # Pass grouped customer-tree data to the template
    )


    return render_template(
        "farmer_plant_a_future.html",
        nav_options=nav_options,
        customers=customers  # Pass grouped customer-tree data to the template
    )


@reward_bp.route('/update_tree_phase/<int:tree_id>', methods=['POST'])
def update_tree_phase(tree_id):
    """Allow farmers to update the stage of a tree."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update tree stages.", "error")
        return redirect(url_for('rewards.farmer_plant_a_future'))

    user_id = session.get('user_id')
    new_stage = request.form.get('new_stage')

    if not new_stage:
        flash("Please select a valid stage.", "error")
        return redirect(url_for('rewards.farmer_plant_a_future'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        tree = next((t for t in trees if t["id"] == tree_id), None)

        if not tree:
            flash("Tree not found.", "error")
            return redirect(url_for('rewards.farmer_plant_a_future'))

        tree["phase"] = new_stage
        flash(f"Tree stage updated to {new_stage}!", "success")

    return redirect(url_for('rewards.farmer_plant_a_future'))

@reward_bp.route('/mark_tree_dead/<int:tree_id>', methods=['POST'])
def mark_tree_dead(tree_id):
    """Allow farmers to mark a tree as dead with a reason."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can mark trees as dead.", "error")
        return redirect(url_for('rewards.farmer_plant_a_future'))

    user_id = session.get('user_id')  # Farmer's ID
    kill_reason = request.form.get('kill_reason')

    if not kill_reason:
        flash("Please provide a reason for killing the tree.", "error")
        return redirect(url_for('rewards.farmer_plant_a_future'))

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        farmer_ownership = ownership.get(user_id, {})
        farmer_trees = farmer_ownership.get("plants", [])

        # Find the tree in the farmer's ownership
        tree = next((t for t in farmer_trees if t["id"] == tree_id), None)
        if not tree:
            flash("Tree not found in your records.", "error")
            return redirect(url_for('rewards.farmer_plant_a_future'))

        # Mark the tree as dead in the farmer's ownership
        tree["phase"] = "Dead"
        tree["kill_reason"] = kill_reason

        # Update the tree in the customer's ownership
        customer_id = tree.get("customer_id")
        if customer_id:
            customer_ownership = ownership.get(customer_id, {})
            customer_trees = customer_ownership.get("plants", [])
            customer_tree = next((t for t in customer_trees if t["id"] == tree_id), None)
            if customer_tree:
                customer_tree["phase"] = "Dead"
                customer_tree["kill_reason"] = kill_reason

        # Save changes
        db["ownership"] = ownership

    flash(f"Tree '{tree['type']}' marked as dead. Reason: {kill_reason}", "success")
    return redirect(url_for('rewards.farmer_plant_a_future'))
