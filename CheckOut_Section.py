from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import EnhancedDatabaseManager

checkout_bp = Blueprint('checkout', __name__)

class User:
    """Represents a user and their actions."""
    def __init__(self, user_id, role):
        self.user_id = user_id
        self.role = role
        self.cart = session.get('cart', [])
        self.db_manager = EnhancedDatabaseManager()

    def get_balance(self):
        """Retrieve the user's balance."""
        return self.db_manager.get_users().get(self.user_id, {}).get("balance", 0)

    def adjust_balance(self, amount):
        """Adjust the user's balance."""
        self.db_manager.adjust_user_balance(self.user_id, amount)

    def clear_cart(self):
        """Clear the user's cart."""
        session['cart'] = []

    def get_nav_options(self):
        """Retrieve navigation options based on the user's role."""
        return self.db_manager.get_nav_options(self.role)

    def get_ownership(self):
        """Retrieve the user's ownership information."""
        return self.db_manager.get_ownership(self.user_id)

    def save_ownership(self, ownership):
        """Save updated ownership data."""
        self.db_manager.save_ownership(self.user_id, ownership)


class CheckoutManager:
    """Handles checkout and cart-related operations."""
    def __init__(self):
        self.db_manager = EnhancedDatabaseManager()

    def calculate_total(self, cart_items):
        """Calculate the total cost of items in the cart."""
        return sum(item['price'] * item['quantity'] for item in cart_items)

    def process_cart(self, user, cart_items, total):
        """Process the checkout and update inventory and ownership."""
        ownership = user.get_ownership()

        for item in cart_items:
            for _ in range(item['quantity']):
                ownership["products"].append(item['id'])  # Add product IDs to ownership

            # Log the transaction
            self.db_manager.add_transaction(
                user_id=user.user_id,
                product_name=item['name'],
                amount=item['price'] * item['quantity'],
                quantity=item['quantity'],
            )

        # Save updated ownership
        user.save_ownership(ownership)

        # Update inventory
        products = self.db_manager.get_products()
        for item in cart_items:
            if item['id'] in products:
                products[item['id']]['quantity'] -= item['quantity']
        self.db_manager.save_products(products)


# Routes and logic
@checkout_bp.route('/')
def checkout():
    """Display the customer's cart for checkout."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can checkout.", "error")
        return redirect(url_for('profile.profile'))

    user = User(session.get('user_id'), session.get('role'))
    total = CheckoutManager().calculate_total(user.cart)
    user_balance = round(user.get_balance(), 2)

    return render_template(
        "customer_checkout.html",
        cart_items=user.cart,
        total=total,
        user_balance=user_balance,
        nav_options=user.get_nav_options(),
    )


@checkout_bp.route('/process_checkout', methods=['POST'])
def process_checkout():
    """Process the customer's checkout."""
    user = User(session.get('user_id'), session.get('role'))

    if user.role != 'customer':
        flash("Unauthorized action.", "error")
        return redirect(url_for('checkout.checkout'))

    cart_items = user.cart
    total = CheckoutManager().calculate_total(cart_items)

    if user.get_balance() < total:
        flash("Insufficient balance for checkout.", "error")
        return redirect(url_for('checkout.checkout'))

    # Store billing info from the form
    billing_info = {
        "name": request.form.get("name"),
        "billing_address": request.form.get("address"),
        "card_number": request.form.get("card")[-4:],  # Save only the last 4 digits for security
        "postal_code": request.form.get("postal_code"),
    }
    session['billing_info'] = billing_info

    # Adjust balance and process the cart
    user.adjust_balance(-total)
    CheckoutManager().process_cart(user, cart_items, total)

    # Redirect to confirmation page with session data
    return redirect(url_for('checkout.confirmation'))



@checkout_bp.route('/add_to_cart_discounted/<int:item_id>', methods=['POST'])
def add_to_cart_discounted(item_id):
    """Add a discounted product to the customer's cart."""
    user = User(session.get('user_id'), session.get('role'))
    if user.role != 'customer':
        flash("Access denied! Only customers can add to cart.", "error")
        return redirect(url_for('discounted.home'))

    quantity = int(request.form.get('quantity', 1))
    item = user.db_manager.get_all_items().get(item_id)

    if not item:
        flash("Product not found.", "error")
        return redirect(url_for('discounted.home'))

    if item['stock'] < quantity:
        flash("Insufficient stock available.", "error")
        return redirect(url_for('discounted.home'))

    # Add the item to the user's cart
    user.cart.append({
        "id": item_id,
        "name": item['name'],
        "price": item['price'],
        "quantity": quantity,
        "type": "discounted",
    })
    session['cart'] = user.cart

    flash(f"'{item['name']}' added to cart!", "success")
    return redirect(url_for('discounted.home'))


@checkout_bp.route('/farmer_purchases')
def farmer_purchases():
    """Allow farmers to view customer purchases."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can view this page.", "error")
        return redirect(url_for('profile.home'))

    user = User(session.get('user_id'), session.get('role'))
    purchases = user.get_ownership().get("products", [])
    return render_template("farmer_checkout.html", purchases=purchases)
@checkout_bp.route('/confirmation', methods=['GET', 'POST'])
def confirmation():
    """Display the order confirmation page and handle order confirmation."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can access this page.", "error")
        return redirect(url_for('profile.profile'))

    # Retrieve data from session
    cart_items = session.get('cart', [])
    billing_info = session.get('billing_info', {})
    total = sum(item['price'] * item['quantity'] for item in cart_items)

    if request.method == 'POST':
        # Process order confirmation
        session['cart'] = []  # Clear the cart
        session.pop('billing_info', None)  # Clear billing info
        flash("Thank you for your order! It has been successfully placed.", "success")
        return redirect(url_for('products.home'))  # Redirect to products page

    return render_template(
        "customer_confirmation.html",
        cart_items=cart_items,
        billing_info=billing_info,
        total=total,
    )
