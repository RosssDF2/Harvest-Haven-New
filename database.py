import shelve
import os
from datetime import datetime, timedelta

DATABASE_FILE = os.path.join(os.path.dirname(__file__), "central_database.db")


class EnhancedDatabaseManager:
    def __init__(self, db_name=DATABASE_FILE):
        self.db_name = db_name

    def initialize_database(self):
        """Initialize the database ONLY if it's empty to prevent resetting registrations."""
        with shelve.open(self.db_name, writeback=True) as db:
            if "users" not in db:
                db["users"] = {
                    "customer1": {"name": "Customer 1", "role": "customer", "points": 1000, "balance": 200.0,
                                  "password": "customer123"},
                    "farmer1": {"name": "Farmer 1", "role": "farmer", "points": 200, "balance": 500.0,
                                "password": "farmer123"},
                    "farmer2": {"name": "Farmer 2", "role": "farmer", "points": 150, "balance": 300.0,
                                "password": "farmer123"},
                }

            if "farmers_registered" not in db:  # ✅ This prevents overwriting the registrations
                db["farmers_registered"] = {}

            print("Database initialized without resetting existing values.")

            # Default products
            if "products" not in db:
                db["products"] = {
                    1: {"name": "Carrot", "price": 1.50, "quantity": 100, "category": "Vegetables",
                        "image_url": "placeholder.png", "uploaded_by": "farmer1", "farmer_id": "farmer1"},
                    2: {"name": "Tomato", "price": 2.00, "quantity": 50, "category": "Vegetables",
                        "image_url": "placeholder.png", "uploaded_by": "farmer2", "farmer_id": "farmer2"},
                }
                for product_id, product in db["products"].items():
                    if "farmer_id" not in product:
                        product["farmer_id"] = product.get("uploaded_by", "unknown_farmer")  # Assign dynamically
                db["products"] = db["products"]  # Save changes

                # Default ownership
                if "ownership" not in db:
                    db["ownership"] = {
                        "farmer1": {
                            "products": [1, 2, 3],
                            "returns": {},
                            "plants": [],
                            "watering_price": 5.0,  # Default watering price
                            "fertilizer_price": 10.0,  # Default fertilizer price
                        },
                        "customer1": {
                            "products": [],
                            "returns": {},
                            "plants": [],
                        },
                    }

            # Default rewards
            if "reward_products" not in db:
                db["reward_products"] = {
                    1: {"name": "Discounted Carrot", "points": 50, "quantity": 20},
                }

            print("Database initialized with default values.")

            if "discounted_items" not in db:
                db["discounted_items"] = {
                    1: {"name": "Discounted Carrot", "price": 1.00, "stock": 20},
                    2: {"name": "Discounted Tomato", "price": 1.50, "stock": 15},
                }

            if "tree_types" not in db:
                db["tree_types"] = {
                    "mango": {
                        "name": "Mango Tree",
                        "price": 5.0,  # Price in dollars
                        "investment_return": 50.0,  # Expected investment value in dollars
                    },
                    "avocado": {
                        "name": "Avocado Tree",
                        "price": 7.0,
                        "investment_return": 70.0,
                    },
                    "apple": {
                        "name": "Apple Tree",
                        "price": 6.0,
                        "investment_return": 60.0,
                    },
                }
            if "orders" not in db:
                db["orders"] = {}

            if "reports" not in db:
                db["reports"] = {}

            print("Database initialized with default values.")

    def get_users(self):
        """Retrieve all users."""
        with shelve.open(self.db_name) as db:
            return db.get("users", {})

    def register_farmer_for_future(self, farmer_id):
        """Marks a farmer as registered for Plant a Future."""
        with shelve.open(self.db_name, writeback=True) as db:
            if "farmers_registered" not in db:
                db["farmers_registered"] = {}  # Ensure the key exists
            farmers_registered = db["farmers_registered"]

            if farmer_id in farmers_registered:  # If already registered, do nothing
                print(f"DEBUG: Farmer {farmer_id} is already registered!")
                return

            farmers_registered[farmer_id] = True  # Mark as registered
            db["farmers_registered"] = farmers_registered
            db.sync()  # Force save to shelve
            print(f"DEBUG: Registered Farmer {farmer_id} Successfully!")

    def get_farmer_notifications(self, farmer_id):
        """Fetch pending return requests for the specified farmer."""
        with shelve.open(self.db_name) as db:
            return_transactions = db.get("return_transactions", {})
            products = db.get("products", {})
            farmer_returns = []

            for customer_id, transactions in return_transactions.items():
                for transaction in transactions:
                    product_name = transaction.get("product_name")
                    for product_id, product_data in products.items():
                        if (
                                product_data["name"] == product_name
                                and product_data.get(
                            "uploaded_by") == farmer_id  # Ensure only farmer's products are retrieved
                                and transaction.get("status", "pending") == "pending"
                        ):
                            farmer_returns.append({
                                "id": product_id,
                                "product_name": product_name,
                                "quantity": transaction.get("quantity", 1),
                                "reason": transaction.get("reason"),
                                "customer_id": customer_id,
                                "status": transaction.get("status", "pending"),
                            })

            print(f"DEBUG: Returns fetched for farmer {farmer_id}: {farmer_returns}")
            return farmer_returns

    def get_products(self):
        """Retrieve all products and ensure each product has a farmer_id."""
        with shelve.open(self.db_name, writeback=True) as db:
            products = db.get("products", {})

            # Ensure every product has a farmer_id
            for product_id, product in products.items():
                if "farmer_id" not in product:
                    product["farmer_id"] = product.get("uploaded_by",
                                                       "unknown_farmer")  # Assign based on uploader or default
            db["products"] = products  # Save changes

        return products

    def get_ownership(self, user_id):
        """Retrieve ownership details for a user."""
        with shelve.open(self.db_name) as db:
            ownership = db.get("ownership", {})
            user_ownership = ownership.get(user_id, {})
            # Ensure "returns" is initialized as a dictionary
            user_ownership.setdefault("returns", {})
            return user_ownership

    def get_reward_products(self):
        """Retrieve all reward products."""
        with shelve.open(self.db_name) as db:
            return db.get("reward_products", {})

    def get_nav_options(self, role):
        """Return navigation options based on user role."""
        nav_options = {
            "farmer": [
                {"name": "Profile", "url": "/profile/profile"},
                {"name": "Products", "url": "/products/"},
                {"name": "Discounted Products", "url": "/discounted/"},
                {"name": "Your Farm", "url": "/rewards/farmer_plant_a_future"},
                {"name": "Orders", "url": "/checkout/farmer_purchases"},  # ✅ Added Farmer Orders Section
                {"name": "Returns", "url": "/returns/farmer_returns"},
            ],
            "customer": [
                {"name": "Profile", "url": "/profile/profile"},
                {"name": "Products", "url": "/products/"},
                {"name": "Discounted Products", "url": "/discounted/"},
                {"name": "Rewards", "url": "/rewards/"},
                {"name": "Plant a Future", "url": "/rewards/plant_a_future"},
                {"name": "Returns", "url": "/returns/"},
                {"name": "Checkout", "url": "/checkout/"},
            ],
        }
        return nav_options.get(role, [])

    def get_all_items(self):
        """Retrieve all discounted items."""
        with shelve.open(self.db_name) as db:
            return db.get("discounted_items", {})

    def save_items(self, items):
        """Save the updated discounted items dictionary."""
        with shelve.open(self.db_name, writeback=True) as db:
            db["discounted_items"] = items

    def adjust_user_balance(self, user_id, balance_delta):
        """Adjust the user's balance."""
        with shelve.open(self.db_name, writeback=True) as db:
            users = db.get("users", {})
            user = users.get(user_id)

            if not user:
                raise ValueError(f"User with ID '{user_id}' not found.")

            new_balance = round(user.get("balance", 0) + balance_delta, 2)

            if new_balance < 0:
                raise ValueError("Insufficient balance for this transaction.")

            user["balance"] = new_balance
            users[user_id] = user
            db["users"] = users

    def update_ownership(self, user_id, category, item_id):
        """
        Add an item to a user's ownership in the specified category.

        :param user_id: ID of the user
        :param category: Category to update (e.g., "products", "returns", etc.)
        :param item_id: ID of the item to add
        """
        with shelve.open(self.db_name, writeback=True) as db:
            ownership = db.setdefault("ownership", {})
            user_ownership = ownership.setdefault(user_id, {})
            category_items = user_ownership.setdefault(category, [])

            if item_id not in category_items:
                category_items.append(item_id)

            db["ownership"] = ownership

    def add_transaction(self, user_id, product_name, amount, quantity):
        """
        Add a transaction to the user's history.

        :param user_id: ID of the user
        :param product_name: Name of the purchased product
        :param amount: Total cost of the transaction
        :param quantity: Quantity of the product purchased
        """
        with shelve.open(self.db_name, writeback=True) as db:
            transactions = db.setdefault("transactions", {})
            user_transactions = transactions.setdefault(user_id, [])

            user_transactions.append({
                "product_name": product_name,
                "amount": round(amount, 2),
                "quantity": quantity,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current date and time
            })

            db["transactions"] = transactions

    def get_transactions(self, user_id):
        """Retrieve the transaction history for a user."""
        try:
            with shelve.open(self.db_name) as db:
                transactions = db.get("transactions", {})
                return transactions.get(user_id, [])
        except Exception as e:
            print(f"Error reading transactions: {e}")
            return []

    def save_products(self, products):
        """Save the updated products dictionary."""
        with shelve.open(self.db_name, writeback=True) as db:
            db["products"] = products

    def get_products(self):
        """Retrieve all products."""
        with shelve.open(self.db_name) as db:
            return db.get("products", {})

    def add_transaction(self, user_id, product_name, amount, quantity):
        """
        Add a transaction to the user's history.

        :param user_id: ID of the user
        :param product_name: Name of the purchased or redeemed product
        :param amount: Total cost of the transaction (0 for redemptions)
        :param quantity: Quantity of the product purchased or redeemed
        """
        with shelve.open(self.db_name, writeback=True) as db:
            transactions = db.setdefault("transactions", {})
            user_transactions = transactions.setdefault(user_id, [])

            user_transactions.append({
                "product_name": product_name,
                "amount": round(amount, 2),  # Will be 0 for redemptions
                "quantity": quantity,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Current date and time
            })

            db["transactions"] = transactions

    def get_return_transactions(self, user_id):
        """
        Retrieve the return transaction history for a user.

        :param user_id: ID of the user
        :return: List of return transactions
        """
        with shelve.open(self.db_name) as db:
            return_transactions = db.get("return_transactions", {})
            return return_transactions.get(user_id, [])

    def create_profile(self, username, name, email, role, points, password):
        """
        Create a new user profile and save it to the database.

        :param username: Unique username for the user
        :param name: Full name of the user
        :param email: Email address of the usaer
        :param role: Role of the user (customer or farmer)
        :param points: Initial points for the user
        :param password: Password for the user
        """
        with shelve.open(self.db_name, writeback=True) as db:
            users = db.get("users", {})
            if username in users:
                raise ValueError(f"Username '{username}' already exists.")

            users[username] = {
                "name": name,
                "email": email,
                "role": role,
                "points": points,
                "balance": 0.0,  # Default balance for new accounts
                "password": password,
            }
            db["users"] = users

    def save_ownership(self, user_id, ownership):
        """
        Save updated ownership details for a user.

        :param user_id: ID of the user
        :param ownership: Updated ownership dictionary
        """
        with shelve.open(self.db_name, writeback=True) as db:
            all_ownership = db.get("ownership", {})
            all_ownership[user_id] = ownership
            db["ownership"] = all_ownership

    def add_return_transaction(self, user_id, product_name, reason):
        """
        Add a return transaction to the user's history.

        :param user_id: ID of the user
        :param product_name: Name of the returned product
        :param reason: Reason for the return
        """
        with shelve.open(self.db_name, writeback=True) as db:
            return_transactions = db.setdefault("return_transactions", {})
            user_returns = return_transactions.setdefault(user_id, [])
            user_returns.append({
                "product_name": product_name,
                "reason": reason,
                "status": "pending",  # Ensure status is set
                "instructions": None,  # Default instructions
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return_transactions[user_id] = user_returns
            db["return_transactions"] = return_transactions

        print("DEBUG: Return Transactions for User:", return_transactions.get(user_id, []))

    def save_users(self, users):
        """Save the updated users dictionary."""
        with shelve.open(self.db_name, writeback=True) as db:
            db["users"] = users

    def adjust_user_points(self, user_id, points_delta):
        """
        Adjust the user's points by adding or deducting points.

        :param user_id: ID of the user
        :param points_delta: Points to adjust (positive to add, negative to deduct)
        :raises ValueError: If the user does not exist or insufficient points
        """
        with shelve.open(self.db_name, writeback=True) as db:
            users = db.get("users", {})
            user = users.get(user_id)

            if not user:
                raise ValueError(f"User with ID '{user_id}' not found.")

            new_points = user.get("points", 0) + points_delta

            if new_points < 0:
                raise ValueError("Insufficient points for this transaction.")

            user["points"] = new_points
            users[user_id] = user
            db["users"] = users

    def submit_report(self, user_id, report_content, category):
        """Submit a report and save it to the database."""
        report_id = self.generate_report_id()

        report = {
            "user_id": user_id,
            "content": report_content,
            "category": category,
            "status": "pending",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        with shelve.open(self.db_name, writeback=True) as db:
            reports = db.get("reports", {})
            reports[report_id] = report
            db["reports"] = reports

        print(f"Report submitted with ID: {report_id}")
        return report_id

    def generate_report_id(self):
        """Generate a unique report ID."""
        with shelve.open(self.db_name) as db:
            reports = db.get("reports", {})
            return len(reports) + 1

    def get_reports(self, user_id=None, category=None):
        """Retrieve all reports, optionally filtered by user or category."""
        with shelve.open(self.db_name) as db:
            reports = db.get("reports", {})

        if user_id:
            reports = {k: v for k, v in reports.items() if v["user_id"] == user_id}

        if category:
            reports = {k: v for k, v in reports.items() if v["category"] == category}

        return reports

    def update_report_status(self, report_id, new_status):
        """Update the status of a report."""
        if new_status not in ["pending", "resolved", "closed"]:
            raise ValueError("Invalid status. Must be 'pending', 'resolved', or 'closed'.")

        with shelve.open(self.db_name, writeback=True) as db:
            reports = db.get("reports", {})
            if report_id in reports:
                reports[report_id]["status"] = new_status
                db["reports"] = reports
                print(f"Updated report {report_id} to status '{new_status}'")
                return reports[report_id]

    def save_products(self, products):
        """Save the updated products dictionary."""
        with shelve.open(self.db_name, writeback=True) as db:
            db["products"] = products

    def add_order(self, farmer_id, buyer_name, product_name, quantity, price):
        """Store order details under the respective farmer."""
        with shelve.open(self.db_name, writeback=True) as db:
            orders = db.setdefault("orders", {})  # Ensure "orders" key exists
            order_id = len([o for v in orders.values() for o in v]) + 1  # Generate unique order ID

            order = {
                "order_id": order_id,
                "farmer_id": farmer_id,
                "buyer_name": buyer_name,
                "product_name": product_name,
                "quantity": quantity,
                "price": price,
                "status": "Pending",
                "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            }

            # Store the order under the farmer's ID
            orders.setdefault(farmer_id, []).append(order)

            db["orders"] = orders  # Save changes

    def get_farmer_orders(self, farmer_id):
        """Retrieve all orders for a given farmer."""
        with shelve.open(self.db_name) as db:
            orders = db.get("orders", {})  # Ensure "orders" key exists
            farmer_orders = orders.get(farmer_id, [])
            print(f"DEBUG: Orders fetched for farmer {farmer_id}: {farmer_orders}")  # Debugging
            return farmer_orders  # Return orders for the specific farmer

    def update_device_status(self, device_id, status):
        """Updates the status of an IoT device."""
        with shelve.open(self.db_name, writeback=True) as db:
            if device_id in db.get("iot_devices", {}):
                db["iot_devices"][device_id]["status"] = status

    def move_plant_to_another_device(self, plant_id, farmer_id):
        """Moves a plant to another available IoT device under the same farmer."""
        with shelve.open(self.db_name, writeback=True) as db:
            available_devices = [
                device_id for device_id, device in db.get("iot_devices", {}).items()
                if device["farmer_id"] == farmer_id and device["status"] == "Active"
            ]
            if available_devices:
                new_device_id = available_devices[0]  # Move to the first available device
                db["plants"][plant_id]["device_id"] = new_device_id
                return new_device_id
            return None

    def log_failure(self, device_id, failure_type):
        """Logs a failure event for an IoT device."""
        with shelve.open(self.db_name, writeback=True) as db:
            failure_logs = db.setdefault("failures", {})
            failure_logs[device_id] = {
                "failure_type": failure_type,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Pending"
            }
            db["failures"] = failure_logs

    def check_and_refund_if_plant_dies(self, plant_id):
        """Checks if a plant has died and refunds the user if necessary."""
        with shelve.open(self.db_name, writeback=True) as db:
            plants = db.get("plants", {})
            users = db.get("users", {})
            if plant_id in plants and plants[plant_id]["status"] == "Dead":
                user_id = plants[plant_id]["user_id"]
                investment = plants[plant_id]["investment"]
                users[user_id]["balance"] += investment  # Refund the user
                del plants[plant_id]  # Remove the dead plant
                db["plants"] = plants
                db["users"] = users

    def register_iot_device(self, farmer_id, device_id):
        """Registers an IoT device to a farmer."""
        with shelve.open(self.db_name, writeback=True) as db:
            iot_devices = db.setdefault("iot_devices", {})

            # Ensure the farmer exists
            users = db.get("users", {})
            if farmer_id not in users or users[farmer_id]["role"] != "farmer":
                return {"error": "Farmer does not exist or is not a valid farmer."}

            # Store the IoT device under the farmer's ID
            iot_devices[device_id] = {
                "farmer_id": farmer_id,
                "status": "Active",
                "assigned_user": None  # Ensure device starts unassigned
            }
            db["iot_devices"] = iot_devices  # Save to database
            return {"message": f"IoT Device {device_id} registered successfully!"}

    def add_discounted_item(self, item_id, name, price, stock, days_until_expiry):
        """Add a new discounted item with an expiry date."""
        with shelve.open(self.db_name, writeback=True) as db:
            discounted_items = db.setdefault("discounted_items", {})
            discounted_items[item_id] = {
                "name": name,
                "price": price,
                "stock": stock,
                "expiry_date": (datetime.now() + timedelta(days=days_until_expiry)).strftime("%Y-%m-%d"),
            }
            db["discounted_items"] = discounted_items

    def get_valid_discounted_items(self):
        """Retrieve only valid (non-expired) discounted items."""
        with shelve.open(self.db_name, writeback=True) as db:
            discounted_items = db.get("discounted_items", {})
            today = datetime.now().strftime("%Y-%m-%d")

            valid_items = {
                item_id: item for item_id, item in discounted_items.items()
                if item["expiry_date"] >= today
            }

            # Optionally remove expired items
            db["discounted_items"] = valid_items

            return valid_items

    def get_discounted_items(self):
        """Retrieve all discounted items."""
        with shelve.open(self.db_name) as db:
            return db.get("discounted_items", {})

    def log_report(self, user_id, product_id, customer_id, issue):
        """
        Logs a report for a return issue.

        :param user_id: ID of the farmer who is reporting the issue
        :param product_id: ID of the product being reported
        :param customer_id: ID of the customer who made the return
        :param issue: Description of the issue
        """
        # Open the database (shelve or whatever you're using)
        with shelve.open("central_database.db", writeback=True) as db:
            # Get existing reports or create an empty dictionary if none exists
            reports = db.get("return_reports", {})

            # Create a new entry for the report under the customer's ID
            if customer_id not in reports:
                reports[customer_id] = []

            # Add the new report
            reports[customer_id].append({
                "product_id": product_id,
                "issue": issue,
                "reported_by": user_id,  # Who reported the issue
                "status": "reported",     # Optional: You can track the status of the report
            })

            # Save the reports back into the database
            db["return_reports"] = reports

