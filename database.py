import shelve
import os
from datetime import datetime, timedelta

DATABASE_FILE = os.path.join(os.path.dirname(__file__), "central_database.db")


class EnhancedDatabaseManager:
    def __init__(self, db_name=DATABASE_FILE):
        self.db_name = db_name

    def initialize_database(self):
        """Initialize the database with default values."""
        with shelve.open(self.db_name, writeback=True) as db:
            # Default users
            if "users" not in db:
                db["users"] = {
                    "customer1": {
                        "name": "Customer 1",
                        "email": "customer1@example.com",
                        "role": "customer",
                        "points": 100,
                        "balance": 200.0,
                        "password": "customer123",
                    },
                    "farmer1": {
                        "name": "Farmer 1",
                        "email": "farmer1@example.com",
                        "role": "farmer",
                        "points": 200,
                        "balance": 500.0,
                        "password": "farmer123",
                    },
                    "farmer2": {
                        "name": "Farmer 2",
                        "email": "farmer2@example.com",
                        "role": "farmer",
                        "points": 150,
                        "balance": 300.0,
                        "password": "farmer123",
                    },
                }

            # Default products
            if "products" not in db:
                db["products"] = {
                    1: {
                        "name": "Carrot",
                        "price": 1.50,
                        "quantity": 100,
                        "category": "Vegetables",
                        "image_url": "placeholder.png",
                        "uploaded_by": "farmer1",  # Add the farmer's username
                    },
                    2: {
                        "name": "Tomato",
                        "price": 2.00,
                        "quantity": 50,
                        "category": "Vegetables",
                        "image_url": "placeholder.png",
                        "uploaded_by": "farmer2",
                    },
                }

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

    def get_users(self):
        """Retrieve all users."""
        with shelve.open(self.db_name) as db:
            return db.get("users", {})

    def get_farmer_notifications(self, farmer_id):
        """
        Fetch pending return requests for the specified farmer.
        :param farmer_id: ID of the farmer
        :return: List of return requests relevant to the farmer
        """
        with shelve.open(self.db_name) as db:
            # Get all return transactions
            return_transactions = db.get("return_transactions", {})
            products = db.get("products", {})
            farmer_returns = []

            # Loop through all return transactions
            for customer_id, transactions in return_transactions.items():
                for transaction in transactions:
                    # Find the product associated with the return
                    product_name = transaction.get("product_name")
                    for product_id, product_data in products.items():
                        # Check if the product belongs to the farmer
                        if product_data["name"] == product_name and product_data["uploaded_by"] == farmer_id:
                            farmer_returns.append({
                                "id": transaction.get("id"),  # Unique ID for the return (if available)
                                "product_name": product_name,
                                "quantity": transaction.get("quantity", 1),  # Default to 1 if not specified
                                "reason": transaction.get("reason"),
                                "customer_id": customer_id,
                            })

            return farmer_returns

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
                {"name": "Profile", "url": "/profile/profile"},  # Ensure this is included
                {"name": "Products", "url": "/products/"},
                {"name": "Discounted Products", "url": "/discounted/"},
                {"name": "Your Farm", "url": "/rewards/farmer_plant_a_future"},  # Added "Your Farm"
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
        """Save the updated products dictionary and ensure all have farmer_id."""
        with shelve.open(self.db_name, writeback=True) as db:
            for product_id, product in products.items():
                if "farmer_id" not in product:
                    product["farmer_id"] = product.get("uploaded_by", "unknown_farmer")
            db["products"] = products

    def get_products(self):
        """Retrieve all products and ensure each product has a farmer_id."""
        with shelve.open(self.db_name, writeback=True) as db:
            products = db.get("products", {})

            # ✅ Ensure every product has a farmer_id
            for product_id, product in products.items():
                if "farmer_id" not in product:
                    product["farmer_id"] = product.get("uploaded_by", "unknown_farmer")
            db["products"] = products  # Save changes

        return products


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
        :param email: Email address of the user
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
                                and product_data["uploaded_by"] == farmer_id
                                and transaction.get("status") == "pending"
                        ):
                            farmer_returns.append({
                                "id": product_id,
                                "product_name": product_name,
                                "quantity": transaction.get("quantity", 1),
                                "reason": transaction.get("reason"),
                                "customer_id": customer_id,
                            })

            return farmer_returns

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
                "status": "pending",  # Default status
                "instructions": None,  # Default instructions
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            print("Return Transactions for User:", return_transactions.get(user_id, []))


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












