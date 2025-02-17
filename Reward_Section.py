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

    user_id = session.get('user_id')
    users = db_manager.get_users()
    user = users.get(user_id, {})

    # ✅ Fetch navigation options (both main nav & dropdown)
    nav_data = db_manager.get_nav_options(session.get('role'))
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]  # ✅ Ensure dropdown menu works

    # ✅ Fetch products & format them for rewards page
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

    return render_template(
        "customer_rewards.html",
        products=reward_products,
        user_points=user.get("points", 0),
        user_balance=user.get("balance", 0),
        nav_options=nav_options,  # ✅ Fix: Pass navigation options
        dropdown_options=dropdown_options  # ✅ Fix: Pass dropdown options
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
        farmers = {k: v for k, v in db["users"].items() if v.get("role") == "farmer"}  # Filter farmers

        # ✅ Check for dead trees and notify the customer
        for tree in plants:
            if tree["phase"] == "Dead" and not tree.get("notified", False):
                farmer_id = tree.get("farmer_id")
                farmer_name = farmers.get(farmer_id, {}).get("name", "Unknown Farmer")
                flash(f"Your tree '{tree['type']}' was marked as dead by {farmer_name}. "
                      f"Reason: {tree.get('kill_reason', 'No reason provided')}", "info")
                tree["notified"] = True  # ✅ Mark as notified

        # ✅ Calculate remaining time for each tree
        current_time = datetime.now()
        for tree in plants:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            tree["time_remaining"] = max(30 - int(elapsed_time), 0)

        trees = {tree["id"]: tree for tree in plants}
        tree_types = db.get("tree_types", {})

    # ✅ Get navigation options
    nav_data = db_manager.get_nav_options(session.get('role'))
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    user = db_manager.get_users().get(user_id, {})
    user_balance = user.get("balance", 0)
    user_points = user.get("points", 0)

    return render_template(
        "customer_plant_a_future.html",
        nav_options=nav_options,
        dropdown_options=dropdown_options,
        trees=trees,
        tree_types=tree_types,
        farmers=farmers,  # ✅ Pass farmers to the template
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

    # ✅ Debugging logs
    print(f"DEBUG: Checking tree {tree_id} for user {user_id}")
    print(f"DEBUG: Watered - {tree['watered']}, Fertilized - {tree['fertilized']}, Health - {tree['health']}")

    if elapsed_time >= 30:
        if not (tree["watered"] and tree["fertilized"]):
            tree["health"] -= 1
            print(f"WARNING: Tree {tree_id} lost health! New health: {tree['health']}")
            if tree["health"] <= 0:
                tree["phase"] = "Dead"
                print(f"ERROR: Tree {tree_id} has died due to neglect!")
                flash("Your plant died due to neglect.", "error")
            else:
                flash("Your plant lost health due to neglect.", "warning")
        else:
            print(f"SUCCESS: Tree {tree_id} is ready for the next phase!")
            flash("Your plant is ready to move to the next phase!", "success")
            tree["is_ready"] = True  # ✅ Mark tree as ready for next phase

    # Save updates
    ownership["plants"] = trees
    db_manager.save_ownership(user_id, ownership)
    return redirect(url_for('rewards.plant_a_future'))


@reward_bp.route('/next_phase/<tree_id>', methods=['POST'])
def next_phase(tree_id):
    """Move tree to the next phase if both watering and fertilizing are completed."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized access."}), 403

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        user_ownership = ownership.get(user_id, {})
        trees = user_ownership.get("plants", [])
        users = db.get("users", {})

        tree = next((t for t in trees if str(t["id"]) == str(tree_id)), None)
        user = users.get(user_id)

        if not tree or not user:
            print(f"ERROR: Tree {tree_id} or user {user_id} not found!")
            return jsonify({"error": "Tree or user not found."}), 404

        print(f"DEBUG: Processing next phase for Tree {tree_id} - Current Phase: {tree['phase']}")
        print(f"DEBUG: Watered: {tree['watered']}, Fertilized: {tree['fertilized']}")

        if not tree["watered"] or not tree["fertilized"]:
            print(f"ERROR: Tree {tree_id} cannot progress! Watered: {tree['watered']}, Fertilized: {tree['fertilized']}")
            return jsonify({"error": "Please water and fertilize the tree before proceeding!"}), 400

        # Handle claiming rewards for Mature Tree
        if tree["phase"] == "Mature Tree":
            tree_type = db.get("tree_types", {}).get(tree["type"])
            if tree_type:
                investment_return = tree_type["investment_return"]
                user["balance"] += investment_return * 2

                print(f"SUCCESS: User {user_id} earned ${investment_return * 2} for Mature Tree!")
                trees.remove(tree)  # ✅ Remove mature tree

                user_ownership["plants"] = trees
                db["users"] = users
                db["ownership"][user_id] = user_ownership
                db["ownership"] = ownership

                return jsonify({"message": f"Tree fully grown! You earned ${investment_return * 2}!", "new_balance": user["balance"]})

        # Move to next phase
        phases = ["Seedling", "Plant", "Growing Tree", "Mature Tree"]
        current_index = phases.index(tree["phase"])
        if current_index < len(phases) - 1:
            tree["phase"] = phases[current_index + 1]
            tree["watered"] = False
            tree["fertilized"] = False
            tree["planted_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tree["time_remaining"] = 10  # ✅ Reset time

            print(f"SUCCESS: Tree {tree_id} moved to next phase: {tree['phase']}")

            return jsonify(
                {"message": f"Tree has moved to the next phase: {tree['phase']}!", "new_phase": tree["phase"]})

    return jsonify({"error": "Unable to progress tree to next phase."}), 400




@reward_bp.route('/plant_tree', methods=['POST'])
def plant_tree():
    """Allows customers to plant a tree and assigns an available IoT device."""
    if session.get('role') != 'customer':
        return jsonify({"error": "Access denied! Only customers can plant trees."}), 403

    user_id = session.get('user_id')
    tree_type = request.form.get('tree_type')
    farmer_id = request.form.get('farmer_id')

    if not tree_type or not farmer_id:
        return jsonify({"error": "Missing tree type or farmer selection."}), 400

    with shelve.open(db_manager.db_name, writeback=True) as db:
        iot_devices = db.get("iot_devices", {})
        ownership = db.get("ownership", {})
        users = db.get("users", {})

        # Find an available IoT device from the selected farmer
        available_device = None
        for device_id, device_data in iot_devices.items():
            if device_data["farmer_id"] == farmer_id and device_data["assigned_user"] is None:
                available_device = device_id
                break

        if not available_device:
            return jsonify({"error": "No available IoT devices from this farmer."}), 400

        # Register the tree under the user's ownership
        tree_id = f"tree_{len(ownership.get(user_id, {}).get('plants', [])) + 1}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Store as string

        new_tree = {
            "id": tree_id,
            "type": tree_type,
            "phase": "Seedling",
            "health": 100,
            "planted_on": current_time,
            "watered": False,
            "fertilized": False,
            "time_remaining": 10,  # ✅ Start at 10 seconds
            "farmer_id": farmer_id,
            "farmer_name": users.get(farmer_id, {}).get("name", "Unknown Farmer"),
            "customer_id": user_id,
            "device_id": available_device
        }

        # Store tree in user's ownership
        if user_id not in ownership:
            ownership[user_id] = {"plants": []}
        ownership[user_id]["plants"].append(new_tree)

        # Assign the tree to the selected IoT device
        iot_devices[available_device]["assigned_user"] = user_id

        # Save changes
        db["ownership"] = ownership
        db["iot_devices"] = iot_devices

        print(f"DEBUG: Tree {tree_id} added with time_remaining: {new_tree['time_remaining']}")

    return jsonify(
        {"message": "Tree planted successfully!", "tree_id": tree_id, "time_remaining": new_tree["time_remaining"]})


@reward_bp.route('/water_tree/<tree_id>', methods=['POST'])
def water_tree(tree_id):
    """Handles watering a tree and deducts $2 from the user's balance."""
    if session.get('role') != 'customer':
        return jsonify({"error": "Access denied! Only customers can water trees."}), 403

    user_id = session.get('user_id')

    with shelve.open(db_manager.db_name, writeback=True) as db:
        users = db.get("users", {})
        ownership = db.get("ownership", {})
        user_ownership = ownership.get(user_id, {})
        trees = user_ownership.get("plants", [])

        # ✅ Log all trees for debugging
        print(f"DEBUG: All trees for user {user_id}: {trees}")

        tree = next((t for t in trees if str(t["id"]) == str(tree_id)), None)
        user = users.get(user_id)

        if not tree or not user:
            print(f"ERROR: Tree {tree_id} or user {user_id} not found in database!")  # ✅ Debug log
            return jsonify({"error": "Tree or user not found."}), 404

        if user["balance"] < 2:
            return jsonify({"error": "Insufficient balance to water the tree."}), 400

        if tree["watered"]:
            return jsonify({"error": "Tree already watered for this phase."}), 400

        # Deduct balance and update tree status
        user["balance"] -= 2
        tree["watered"] = True
        db["users"] = users
        db["ownership"][user_id] = user_ownership

    return jsonify({"message": "Tree watered successfully!", "new_balance": user["balance"]})


@reward_bp.route('/fertilize_tree/<tree_id>', methods=['POST'])
def fertilize_tree(tree_id):
    """Handles fertilizing a tree and deducts $5 from the user's balance."""
    if session.get('role') != 'customer':
        return jsonify({"error": "Access denied! Only customers can fertilize trees."}), 403

    user_id = session.get('user_id')

    with shelve.open(db_manager.db_name, writeback=True) as db:
        users = db.get("users", {})
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])

        tree = next((t for t in trees if str(t["id"]) == str(tree_id)), None)  # ✅ Ensure matching tree ID
        user = users.get(user_id)

        if not tree or not user:
            return jsonify({"error": "Tree or user not found."}), 404

        if user["balance"] < 5:
            return jsonify({"error": "Insufficient balance to fertilize the tree."}), 400

        if tree["fertilized"]:
            return jsonify({"error": "Tree already fertilized for this phase."}), 400

        # Deduct balance and update tree status
        user["balance"] -= 5
        tree["fertilized"] = True
        db["users"] = users
        db["ownership"][user_id] = ownership

    return jsonify({"message": "Tree fertilized successfully!", "new_balance": user["balance"]})


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
    """Update tree timers, remove dead trees, and free IoT devices."""
    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        iot_devices = db.get("iot_devices", {})

        current_time = datetime.now()
        alive_trees = []  # Store trees that are still alive
        removed_tree_ids = []  # Store IDs of trees that will be deleted

        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            remaining_time = max(30 - elapsed_time, 0)  # ✅ Set countdown to 30 seconds

            tree["time_remaining"] = int(remaining_time)

            if remaining_time <= 0 and not (tree["watered"] and tree["fertilized"]):
                # 🌱 **Mark tree as dead**
                tree["health"] = 0
                removed_tree_ids.append(tree["id"])

                # 🌱 **Free up the IoT device**
                device_id = tree.get("device_id")
                if device_id and device_id in iot_devices:
                    iot_devices[device_id]["assigned_user"] = None  # ✅ Make IoT device available
                    print(f"DEBUG: IoT Device {device_id} is now free.")

                print(f"DEBUG: Tree {tree['id']} has died and will be removed.")
            else:
                # 🌱 **Keep only alive trees**
                alive_trees.append(tree)

        # Save updated tree ownership
        ownership["plants"] = alive_trees
        db["ownership"][user_id] = ownership
        db["iot_devices"] = iot_devices  # ✅ Update freed IoT devices

        return removed_tree_ids  # ✅ Return list of deleted tree IDs


@reward_bp.route('/get_trees', methods=['GET'])
def get_trees():
    """Return updated tree data for real-time countdown."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized access"}), 403

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        current_time = datetime.now()

        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()

            if elapsed_time < 0:
                elapsed_time = 0  # Prevent negative time

            tree["time_remaining"] = max(30 - int(elapsed_time), 0)

            tree["next_phase_enabled"] = (
                    tree["time_remaining"] <= 0 and tree["watered"] and tree["fertilized"]
            )

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

        # ✅ Group trees by customer
        customers = {}
        for plant in plants:
            customer_id = plant.get("customer_id")
            if not customer_id:
                continue  # Skip if no customer_id is associated

            # Get customer data from the database
            customer = users.get(customer_id, {})
            if not customer:
                continue

            if customer_id not in customers:
                customers[customer_id] = {
                    "name": customer.get("name", "Unknown Customer"),
                    "email": customer.get("email", "No Email"),
                    "trees": [],  # ✅ Removed balance (Farmers don’t need it)
                }
            customers[customer_id]["trees"].append(plant)

    # ✅ Get navigation options
    nav_data = db_manager.get_nav_options(session.get('role'))
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    return render_template(
        "farmer_plant_a_future.html",
        nav_options=nav_options,
        dropdown_options=dropdown_options,
        customers=customers  # ✅ Pass grouped customer-tree data to the template
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


@reward_bp.route('/admin/trigger_failure', methods=['POST'])
def trigger_failure():
    """Allows admin to trigger a failure for a selected IoT device."""
    if session.get('role') != 'admin':
        return jsonify({"error": "Access denied! Only admin can trigger failures."}), 403

    device_id = request.form.get('device_id')
    failure_type = request.form.get('failure_type')

    if not device_id or not failure_type:
        return jsonify({"error": "Missing device ID or failure type."}), 400

    db_manager.log_failure(device_id, failure_type)
    db_manager.update_device_status(device_id, "Faulty")
    return jsonify({"message": "Failure triggered successfully."}), 200


@reward_bp.route('/farmer/move_plant', methods=['POST'])
def move_plant():
    """Allows a farmer to move a plant to another available IoT device."""
    if session.get('role') != 'farmer':
        return jsonify({"error": "Access denied! Only farmers can move plants."}), 403

    plant_id = request.form.get('plant_id')
    farmer_id = session.get('user_id')

    new_device_id = db_manager.move_plant_to_another_device(plant_id, farmer_id)
    if new_device_id:
        return jsonify({"message": f"Plant moved to IoT device {new_device_id}."}), 200
    return jsonify({"error": "No available IoT devices to move the plant."}), 400


@reward_bp.route('/check_plant_risk', methods=['GET'])
def check_plant_risk():
    """Checks if any plants are at risk due to IoT failures."""
    with shelve.open(db_manager.db_name) as db:
        plants = db.get("plants", {})
        iot_devices = db.get("iot_devices", {})
        at_risk_plants = []

        for plant_id, plant in plants.items():
            device_id = plant.get("device_id")
            if device_id and iot_devices.get(device_id, {}).get("status") == "Faulty":
                at_risk_plants.append({"plant_id": plant_id, "type": plant["type"], "status": "At Risk"})

        return jsonify({"at_risk_plants": at_risk_plants})


@reward_bp.route('/admin_panel', methods=['GET'])
def admin_panel():
    """Render the admin panel for IoT failure simulation."""
    if session.get('role') != 'admin':
        flash("Access denied! Only admins can access this page.", "error")
        return redirect(url_for('profile.profile'))

    return render_template("admin_panel.html")

    return render_template("admin_panel.html")


@reward_bp.route('/farmer/register_iot_device', methods=['POST'])
def register_iot_device():
    """Allows farmers to register an IoT device ONLY IF they registered for Plant a Future."""
    if session.get('role') != 'farmer':
        return jsonify({"error": "Access denied! Only farmers can register IoT devices."}), 403

    farmer_id = session.get('user_id')
    device_id = request.form.get('device_id')

    with shelve.open(db_manager.db_name, writeback=True) as db:
        farmers_registered = db.get("farmers_registered", {})

        if farmer_id not in farmers_registered:
            return jsonify({"error": "You must register for Plant a Future before adding IoT devices."}), 400

        iot_devices = db.setdefault("iot_devices", {})

        if device_id in iot_devices:
            return jsonify({"error": "Device ID already exists."}), 400

        iot_devices[device_id] = {
            "farmer_id": farmer_id,
            "status": "Active",
            "assigned_user": None
        }
        db["iot_devices"] = iot_devices

    return jsonify({"message": f"IoT Device {device_id} registered successfully!"}), 200


@reward_bp.route('/get_farmers_with_iot', methods=['GET'])
def get_farmers_with_iot():
    """Fetches farmers who have registered IoT devices and returns them."""
    with shelve.open(db_manager.db_name) as db:
        users = db.get("users", {})
        iot_devices = db.get("iot_devices", {})

        farmers_with_devices = set()
        for device_id, device in iot_devices.items():
            if "farmer_id" in device and device["farmer_id"] in users:
                farmers_with_devices.add(device["farmer_id"])

        farmers_list = [
            {"id": farmer_id, "name": users[farmer_id]["name"]}
            for farmer_id in farmers_with_devices if farmer_id in users
        ]

    print(f"DEBUG: Farmers with IoT devices: {farmers_list}")  # ✅ Debugging

    return jsonify({"farmers": farmers_list})


@reward_bp.route('/get_customer_trees', methods=['GET'])
def get_customer_trees():
    """Fetches trees planted by the customer and updates countdown, ensuring time persistence."""
    if session.get('role') != 'customer':
        return jsonify({"error": "Access denied! Only customers can view their trees."}), 403

    user_id = session.get('user_id')

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])
        users = db.get("users", {})

        current_time = datetime.now()

        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()

            if "time_remaining" not in tree or tree["time_remaining"] > 0:
                tree["time_remaining"] = max(10 - int(elapsed_time), 0)

            # ✅ Ensure water and fertilize states persist
            if "watered" not in tree:
                tree["watered"] = False
            if "fertilized" not in tree:
                tree["fertilized"] = False

            # ✅ Save the new time_remaining back to the database (so it persists)
            db["ownership"][user_id]["plants"] = trees

            # ✅ Fix missing farmer names
            if "farmer_name" not in tree:
                farmer_id = tree.get("farmer_id")
                tree["farmer_name"] = users.get(farmer_id, {}).get("name", "Unknown Farmer")

        return jsonify({"trees": trees})



@reward_bp.route('/get_available_iot_devices', methods=['GET'])
def get_available_iot_devices():
    """Fetches available IoT devices for the selected farmer (for customers)."""
    farmer_id = request.args.get('farmer_id')  # ✅ Get farmer ID from request

    if not farmer_id:
        return jsonify({"error": "Missing farmer ID"}), 400  # ✅ Prevents empty request

    with shelve.open(db_manager.db_name) as db:
        iot_devices = db.get("iot_devices", {})

        # Find available IoT devices for this farmer
        available_devices = [
            {"id": device_id, "status": device["status"]}
            for device_id, device in iot_devices.items()
            if device["farmer_id"] == farmer_id and device["assigned_user"] is None  # ✅ Only unassigned devices
        ]

    print(f"DEBUG: Available IoT Devices for Farmer {farmer_id}: {available_devices}")  # ✅ Debugging

    return jsonify({"devices": available_devices})


@reward_bp.route('/farmer/register_future', methods=['POST'])
def register_farmer_future():
    """Allows farmers to register for Plant a Future before adding IoT devices."""
    if session.get('role') != 'farmer':
        return jsonify({"error": "Access denied! Only farmers can register for Plant a Future."}), 403

    farmer_id = session.get('user_id')

    db_manager.register_farmer_for_future(farmer_id)

    session['registered_for_future'] = True  # Store in Flask session

    return jsonify({"message": "You have successfully registered for Plant a Future!"}), 200


@reward_bp.route('/farmer/check_future_registration', methods=['GET'])
def check_farmer_registration():
    """Checks if the farmer has registered for Plant a Future."""
    if session.get('role') != 'farmer':
        return jsonify({"error": "Access denied! Only farmers can check registration status."}), 403

    farmer_id = session.get('user_id')

    with shelve.open(db_manager.db_name) as db:
        farmers_registered = db.get("farmers_registered", {})

    print(f"DEBUG: Farmers Registered in DB: {farmers_registered}")  # Check all registered farmers
    print(f"DEBUG: Is {farmer_id} registered? -> {farmer_id in farmers_registered}")  # Check specific farmer

    return jsonify({"registered": farmer_id in farmers_registered})


def register_farmer_for_future(self, farmer_id):
    """Marks a farmer as registered for Plant a Future and ENSURES persistence."""
    with shelve.open(self.db_name, writeback=True) as db:
        farmers_registered = db.setdefault("farmers_registered", {})

        if farmer_id in farmers_registered:
            print(f"DEBUG: Farmer {farmer_id} is already registered!")
            return

        farmers_registered[farmer_id] = True  # Mark as registered
        db["farmers_registered"] = farmers_registered
        db.sync()  # ✅ Force save immediately
        print(f"DEBUG: Registered Farmer {farmer_id} Successfully!")


@reward_bp.route('/get_registered_farmers', methods=['GET'])
def get_registered_farmers():
    """Fetches farmers who have registered for 'Plant a Future'."""
    with shelve.open(db_manager.db_name) as db:
        farmers_registered = db.get("farmers_registered", {})

        farmers_list = [
            {"id": farmer_id, "name": farmer_id}  # Change farmer_id to name if you store names separately
            for farmer_id in farmers_registered
        ]

    print(f"DEBUG: Registered Farmers: {farmers_list}")  # ✅ Debugging

    return jsonify({"farmers": farmers_list})


@reward_bp.route('/get_farmer_iot_devices', methods=['GET'])
def get_farmer_iot_devices():
    """Fetches all IoT devices registered by the logged-in farmer."""
    if session.get('role') != 'farmer':  # ✅ Only farmers can call this API
        return jsonify({"error": "Access denied! Only farmers can view their IoT devices."}), 403

    farmer_id = session.get('user_id')

    with shelve.open(db_manager.db_name) as db:
        iot_devices = db.get("iot_devices", {})

        # Retrieve ALL IoT devices for this farmer
        farmer_devices = [
            {"id": device_id, "status": device["status"], "assigned_user": device["assigned_user"]}
            for device_id, device in iot_devices.items()
            if device["farmer_id"] == farmer_id
        ]

    print(f"DEBUG: IoT Devices for Farmer {farmer_id}: {farmer_devices}")  # ✅ Debugging

    return jsonify({"devices": farmer_devices})


@reward_bp.route("/get_balance", methods=["GET"])
def get_balance():
    """Fetch the user's updated balance and planted trees."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    with shelve.open(db_manager.db_name) as db:
        users = db.get("users", {})
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])

        # Get the user's balance
        user_balance = users.get(user_id, {}).get("balance", 0)

        # Calculate remaining time for each tree
        current_time = datetime.now()
        tree_data = []
        for tree in trees:
            planted_time = datetime.strptime(tree["planted_on"], "%Y-%m-%d %H:%M:%S")
            elapsed_time = (current_time - planted_time).total_seconds()
            time_remaining = max(30 - elapsed_time, 0)

            tree_data.append({
                "id": tree["id"],
                "type": tree["type"],
                "phase": tree["phase"],
                "health": tree["health"],
                "device_id": tree["device_id"],
                "time_remaining": int(time_remaining)  # ✅ Persist countdown time
            })

    return jsonify({"balance": user_balance, "trees": tree_data})


@reward_bp.route('/remove_tree/<tree_id>/<device_id>', methods=['DELETE'])
def remove_tree(tree_id, device_id):
    """Removes a tree from the customer and frees the IoT device."""
    if session.get('role') != 'customer':
        return jsonify({"error": "Access denied! Only customers can remove trees."}), 403

    user_id = session.get('user_id')

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        iot_devices = db.get("iot_devices", {})

        # 🔍 Find the user's trees
        if user_id in ownership and "plants" in ownership[user_id]:
            trees = ownership[user_id]["plants"]

            # ✅ Remove the tree from the user's list
            updated_trees = [tree for tree in trees if tree["id"] != tree_id]
            ownership[user_id]["plants"] = updated_trees

            # ✅ Free up the IoT device
            if device_id in iot_devices:
                iot_devices[device_id]["assigned_user"] = None  # ✅ Device is now free

            # Save changes
            db["ownership"] = ownership
            db["iot_devices"] = iot_devices

            print(f"DEBUG: Tree {tree_id} removed. IoT device {device_id} is now available.")

            return jsonify({"message": "Tree removed successfully!"})

    return jsonify({"error": "Tree not found!"}), 404


@reward_bp.route('/update_time_remaining/<tree_id>', methods=['POST'])
def update_time_remaining(tree_id):
    """Updates the time remaining for a tree."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized access"}), 403

    data = request.get_json()
    new_time_remaining = data.get("time_remaining", None)

    if new_time_remaining is None:
        return jsonify({"error": "Invalid time value"}), 400

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {}).get(user_id, {})
        trees = ownership.get("plants", [])

        tree = next((t for t in trees if t["id"] == tree_id), None)
        if not tree:
            return jsonify({"error": "Tree not found."}), 404

        tree["time_remaining"] = new_time_remaining
        db["ownership"][user_id] = ownership  # ✅ Save update

    return jsonify({"message": "Time remaining updated successfully!"})

@reward_bp.route('/claim_tree/<tree_id>', methods=['POST'])
def claim_tree(tree_id):
    """Claim rewards for a fully grown Mature Tree and remove it from the IoT device."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized access."}), 403

    with shelve.open(db_manager.db_name, writeback=True) as db:
        ownership = db.get("ownership", {})
        user_ownership = ownership.get(user_id, {})
        trees = user_ownership.get("plants", [])
        users = db.get("users", {})
        iot_devices = db.get("iot_devices", {})

        tree = next((t for t in trees if str(t["id"]) == str(tree_id)), None)
        user = users.get(user_id)

        if not tree or not user:
            print(f"ERROR: Tree {tree_id} or user {user_id} not found!")
            return jsonify({"error": "Tree or user not found."}), 404

        if tree["phase"] != "Mature Tree":
            print(f"ERROR: Tree {tree_id} is not fully grown!")
            return jsonify({"error": "Tree is not fully grown yet!"}), 400

        tree_type = db.get("tree_types", {}).get(tree["type"])
        if not tree_type:
            print(f"ERROR: Tree type not found for Tree {tree_id}!")
            return jsonify({"error": "Tree type not found!"}), 400

        # Reward user with 2x investment return
        investment_return = tree_type["investment_return"]
        user["balance"] += investment_return * 2

        print(f"SUCCESS: User {user_id} earned ${investment_return * 2} for Mature Tree!")
        trees.remove(tree)  # ✅ Remove mature tree from user ownership

        # Remove tree from IoT device
        device_id = tree.get("device_id")
        if device_id and device_id in iot_devices:
            iot_devices[device_id]["assigned_user"] = None  # ✅ Free up IoT device
            print(f"INFO: IoT device {device_id} is now available again.")

        # Save changes
        user_ownership["plants"] = trees
        db["users"] = users
        db["ownership"][user_id] = user_ownership
        db["iot_devices"] = iot_devices

        return jsonify({"message": f"Tree fully grown! You earned ${investment_return * 2}!", "new_balance": user["balance"]})

# Reward_Section.py

@reward_bp.route('/get_farmer_customers_trees', methods=['GET'])
def get_farmer_customers_trees():
    """Fetch all trees assigned to the logged-in farmer's IoT devices."""
    if session.get('role') != 'farmer':
        return jsonify({"error": "Access denied! Only farmers can view assigned plants."}), 403

    farmer_id = session.get('user_id')
    with shelve.open(db_manager.db_name) as db:
        ownership = db.get("ownership", {})
        trees = []

        # Get all customer-planted trees linked to the farmer
        for user_id, user_data in ownership.items():
            for tree in user_data.get("plants", []):
                if tree.get("farmer_id") == farmer_id:
                    trees.append({
                        "id": tree["id"],
                        "type": tree["type"],
                        "customer_name": db.get("users", {}).get(user_id, {}).get("name", "Unknown"),
                        "device_id": tree["device_id"],
                        "phase": tree["phase"],
                        "health": tree["health"],
                        "watered": tree["watered"],
                        "fertilized": tree["fertilized"]
                    })

    return jsonify({"trees": trees})


@reward_bp.route('/add_balance')
def add_balance():
    """Display the Add Balance page."""
    if 'user_id' not in session:
        return redirect(url_for('profile.login'))

    user_id = session['user_id']
    user = db_manager.get_users().get(user_id)

    # ✅ Get balance & points from database
    user_balance = user.get("balance", 0)
    user_points = user.get("points", 0)

    # ✅ Get nav options for the user role
    nav_data = db_manager.get_nav_options(session.get('role'))
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    return render_template(
        "add_balance.html",
        user_balance=user_balance,
        user_points=user_points,
        nav_options=nav_options,
        dropdown_options=dropdown_options
    )


@reward_bp.route('/balance_checkout/<int:amount>', methods=['POST'])
def balance_checkout(amount):
    """Display the balance checkout page."""
    if 'user_id' not in session:
        return redirect(url_for('profile.login'))

    user_id = session['user_id']
    user = db_manager.get_users().get(user_id)

    # ✅ Get balance & points from database
    user_balance = user.get("balance", 0)
    user_points = user.get("points", 0)

    # ✅ Get nav options for the user role
    nav_data = db_manager.get_nav_options(session.get('role'))
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    return render_template(
        "balance_checkout.html",
        amount=amount,
        user_balance=user_balance,
        user_points=user_points,
        nav_options=nav_options,
        dropdown_options=dropdown_options
    )


@reward_bp.route('/process_balance_checkout', methods=['POST'])
def process_balance_checkout():
    """Handle balance addition and payment validation."""
    if 'user_id' not in session:
        return redirect(url_for('profile.login'))

    user_id = session['user_id']
    amount = int(request.form.get('amount', 0))

    # ✅ Validate Card Details
    card = request.form.get('card', '').strip()
    card_name = request.form.get('card_name', '').strip()
    cvv = request.form.get('cvv', '').strip()
    expiry_date = request.form.get('expiry_date', '').strip()

    errors = []
    if not card.isdigit() or not (12 <= len(card) <= 19):
        errors.append("Card number must be between 12 to 19 digits.")
    if not card_name.replace(" ", "").isalpha():
        errors.append("Name on card must contain only letters.")
    if not cvv.isdigit() or not (3 <= len(cvv) <= 4):
        errors.append("CVV must be 3 or 4 digits.")
    if not expiry_date or not ("/" in expiry_date and len(expiry_date) == 5):
        errors.append("Expiry date must be in MM/YY format.")

    # ✅ If validation fails, return errors & keep header visible
    if errors:
        return render_template(
            "balance_checkout.html",
            amount=amount,
            errors=errors,
            success=None,
            user_balance=db_manager.get_users().get(user_id, {}).get("balance", 0),
            user_points=db_manager.get_users().get(user_id, {}).get("points", 0),
            **db_manager.get_nav_options(session.get('role'))  # ✅ Pass navigation options
        )

    # ✅ Update User Balance
    db_manager.adjust_user_balance(user_id, amount)

    # ✅ Refresh balance
    user = db_manager.get_users().get(user_id)
    new_balance = user["balance"]

    return render_template(
        "balance_checkout.html",
        amount=amount,
        success=f"Successfully added ${amount}!",
        new_balance=new_balance,
        hide_form=True,  # ✅ Signal to hide the form
        **db_manager.get_nav_options(session.get('role'))  # ✅ Pass navigation options
    )

@reward_bp.route('/add_points/<int:points_amount>', methods=['POST'])
def add_points(points_amount):
    """Allow users to purchase points using their balance."""
    if 'user_id' not in session:
        return redirect(url_for('profile.login'))

    user_id = session['user_id']
    user = db_manager.get_users().get(user_id)

    # ✅ Define cost based on selected points package
    points_cost_map = {200: 2, 1000: 10, 5000: 50}
    cost = points_cost_map.get(points_amount, None)

    if cost is None:
        flash("Invalid points package.", "error")
        return redirect(url_for('rewards.add_balance'))

    # ✅ Validate if user has enough balance
    if user["balance"] < cost:
        return render_template(
            "add_balance.html",
            user_balance=user["balance"],
            user_points=user["points"],
            error=f"Insufficient balance. You need ${cost} to buy {points_amount} points.",
            **db_manager.get_nav_options(session.get('role'))
        )

    # ✅ Deduct balance and add points
    db_manager.adjust_user_balance(user_id, -cost)  # Deduct balance
    db_manager.adjust_user_points(user_id, points_amount)  # Add points

    # ✅ Refresh balance & points
    user = db_manager.get_users().get(user_id)
    new_balance = user["balance"]
    new_points = user["points"]

    return render_template(
        "add_balance.html",
        user_balance=new_balance,
        user_points=new_points,
        success=f"Successfully added {points_amount} points!",
        **db_manager.get_nav_options(session.get('role'))
    )

