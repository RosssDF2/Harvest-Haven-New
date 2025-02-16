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

from flask import jsonify

@checkout_bp.route('/process_checkout', methods=['POST'])
def process_checkout():
    """Handle the checkout process with normal validation."""
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    postal_code = request.form.get('postal_code', '').strip()
    card = request.form.get('card', '').strip()
    card_name = request.form.get('card_name', '').strip()
    cvv = request.form.get('cvv', '').strip()
    expiry_date = request.form.get('expiry_date', '').strip()

    if len(name) < 3 or len(address) < 5:
        flash("Invalid name or address.", "error")
        return redirect(url_for('checkout.checkout'))

    if not postal_code.isdigit() or not (5 <= len(postal_code) <= 6):
        flash("Invalid postal code.", "error")
        return redirect(url_for('checkout.checkout'))

    if not card.isdigit() or not (12 <= len(card) <= 19):
        flash("Invalid card number.", "error")
        return redirect(url_for('checkout.checkout'))

    if not card_name.replace(" ", "").isalpha():
        flash("Invalid card name.", "error")
        return redirect(url_for('checkout.checkout'))

    if not cvv.isdigit() or not (3 <= len(cvv) <= 4):
        flash("Invalid CVV.", "error")
        return redirect(url_for('checkout.checkout'))

    import datetime, re
    expiry_pattern = re.compile(r"^(0[1-9]|1[0-2])\/\d{2}$")
    if not expiry_pattern.match(expiry_date):
        flash("Expiry date must be in MM/YY format.", "error")
        return redirect(url_for('checkout.checkout'))

    exp_month, exp_year = map(int, expiry_date.split("/"))
    current_year = int(datetime.datetime.now().strftime("%y"))
    current_month = datetime.datetime.now().month

    if exp_year < current_year or (exp_year == current_year and exp_month < current_month):
        flash("Your card has expired.", "error")
        return redirect(url_for('checkout.checkout'))

    # Store billing info and cart in session for confirmation page
    session['billing_info'] = {
        'name': name,
        'address': address,
        'postal_code': postal_code,
        'card': f"**** **** **** {card[-4:]}"  # Masked card number
    }
    session['cart_items'] = session.get('cart', [])  # Save cart before clearing it
    session['total_price'] = sum(item['price'] * item['quantity'] for item in session['cart'])

    # Save transactions to database
    db_manager = EnhancedDatabaseManager()
    user_id = session.get('user_id')
    cart = session.get('cart', [])

    for item in cart:
        db_manager.add_transaction(
            user_id=user_id,
            product_name=item["name"],
            amount=item["price"] * item["quantity"],
            quantity=item["quantity"]
        )

    session['cart'] = []  # Clear cart after checkout

    flash("Checkout successful!", "success")
    return redirect(url_for('checkout.confirmation'))

@checkout_bp.route('/')
def checkout():
    """Display the checkout page."""
    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    user_id = session.get('user_id')
    users = EnhancedDatabaseManager().get_users()
    balance = users.get(user_id, {}).get("balance", 0)

    return render_template('customer_checkout.html', cart_items=cart, total=total, user_balance=balance)


@checkout_bp.route('/confirmation')
def confirmation():
    """Display the confirmation page after checkout."""
    billing_info = session.get('billing_info', {})
    cart_items = session.get('cart_items', [])  # Retrieve saved cart items
    total_price = session.get('total_price', 0)

    if not billing_info:
        flash("No checkout information found. Redirecting back to checkout.", "error")
        return redirect(url_for('checkout.checkout'))

    return render_template(
        'customer_confirmation.html',
        billing_info=billing_info,
        cart_items=cart_items,
        total=total_price
    )


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
