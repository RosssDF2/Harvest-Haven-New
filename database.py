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
                    "farmer1": {"products": [1, 2, 3], "returns": {}, "plants": []},
                    "customer1": {"products": [], "returns": {}, "plants": []},
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

    def get_products(self):
        """Retrieve all products."""
        with shelve.open(self.db_name) as db:
            return db.get("products", {})

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
                {"name": "Returns", "url": "/returns/farmer_returns"},
                {"name": "Checkout", "url": "/checkout/farmer_purchases"},
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




