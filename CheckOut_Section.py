from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

# Define the Blueprint for checkout
checkout_bp = Blueprint('checkout', __name__)

@checkout_bp.route('/checkout/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """Update product quantity in the cart."""
    try:
        quantity = int(request.form.get('quantity', 1))  # Default to 1 if no quantity specified
        if quantity < 1:
            flash("Quantity must be at least 1.", "error")
            return redirect(url_for('checkout.checkout'))
    except ValueError:
        flash("Invalid quantity entered.", "error")
        return redirect(url_for('checkout.checkout'))

    user = User(session.get('user_id'), session.get('role'))
    user.update_cart_quantity(product_id, quantity)

    flash("Cart updated.", "success")
    return redirect(url_for('checkout.checkout'))

@checkout_bp.route('/checkout/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    """Remove product from the cart."""
    user = User(session.get('user_id'), session.get('role'))
    user.remove_from_cart(product_id)

    flash("Item removed from cart.", "success")
    return redirect(url_for('checkout.checkout'))

@checkout_bp.route('/process_checkout', methods=['POST'])
def process_checkout():
    """Handle the checkout process."""
    name = request.form['name'].strip()
    address = request.form['address'].strip()
    card = request.form['card'].strip()
    postal_code = request.form['postal_code'].strip()

    if not name or not address or not card or not postal_code:
        flash("All fields are required.", "error")
        return redirect(url_for('checkout.checkout'))

    if not card.isdigit() or len(card) < 12:
        flash("Invalid card number.", "error")
        return redirect(url_for('checkout.checkout'))

    if not postal_code.isdigit():
        flash("Postal code must be numeric.", "error")
        return redirect(url_for('checkout.checkout'))

    # Store the billing info in the session
    session['billing_info'] = {
        'name': name,
        'address': address,
        'card': card,
        'postal_code': postal_code
    }

    # Example: save order to database, clear the cart, etc.
    session['cart'] = []  # Empty cart after checkout
    flash("Checkout successful!", "success")
    return redirect(url_for('checkout.confirmation'))  # Redirect to the confirmation page

@checkout_bp.route('/')
def checkout():
    """Display the checkout page."""
    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    balance = session.get('balance', 0)  # Ensure balance is retrieved from session
    return render_template('customer_checkout.html', cart_items=cart, total=total, balance=balance)

@checkout_bp.route('/confirmation')
def confirmation():
    """Display the confirmation page after checkout."""
    billing_info = session.get('billing_info', {})
    return render_template('customer_confirmation.html', billing_info=billing_info)

class User:
    """Represents a user and their actions."""

    def __init__(self, user_id, role):
        self.user_id = user_id
        self.role = role
        self.cart = session.get('cart', [])

    def add_to_cart(self, product_id, quantity):
        """Add a product to the user's cart."""
        if quantity < 1:
            flash("Quantity must be at least 1.", "error")
            return

        cart = session.get('cart', [])
        existing_item = next((item for item in cart if item['id'] == product_id), None)

        if existing_item:
            existing_item['quantity'] += quantity
        else:
            db_manager = EnhancedDatabaseManager()  # Make sure to instantiate the database manager
            product = db_manager.get_product_by_id(product_id)  # Assuming you have a method to fetch product by ID
            cart.append({'id': product_id, 'name': product['name'], 'price': product['price'], 'quantity': quantity})

        session['cart'] = cart

    def remove_from_cart(self, product_id):
        """Remove a product from the user's cart."""
        cart = session.get('cart', [])
        cart = [item for item in cart if item['id'] != product_id]
        session['cart'] = cart

    def update_cart_quantity(self, product_id, quantity):
        """Update the quantity of a product in the cart."""
        if quantity < 1:
            flash("Quantity must be at least 1.", "error")
            return

        cart = session.get('cart', [])
        for item in cart:
            if item['id'] == product_id:
                item['quantity'] = quantity
                break
        session['cart'] = cart
