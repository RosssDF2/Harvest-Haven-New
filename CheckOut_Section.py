from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

# Define the Blueprint for checkout
checkout_bp = Blueprint('checkout', __name__)

@checkout_bp.route('/checkout/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """Update product quantity in the session cart correctly."""
    try:
        quantity = int(request.form.get('quantity', 1))
        if quantity < 1:
            flash("Quantity must be at least 1.", "error")
            return redirect(url_for('checkout.checkout'))
    except ValueError:
        flash("Invalid quantity entered.", "error")
        return redirect(url_for('checkout.checkout'))

    cart = session.get('cart', [])

    # ✅ Find the item in the cart and update the quantity
    for item in cart:
        if item["id"] == product_id:
            item["quantity"] = quantity
            break  # ✅ Exit loop once updated

    session['cart'] = cart  # ✅ Save back to session
    flash("Cart updated.", "success")
    return redirect(url_for('checkout.checkout'))


@checkout_bp.route('/checkout/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    """Remove product from the cart and restore stock immediately."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can remove items.", "error")
        return redirect(url_for('checkout.checkout'))

    db_manager = EnhancedDatabaseManager()
    products = db_manager.get_products()
    cart = session.get('cart', [])

    item_to_remove = next((item for item in cart if item['id'] == product_id), None)

    if not item_to_remove:
        flash("Error: Item not found in cart.", "error")
        return redirect(url_for('checkout.checkout'))

    # ✅ Restore stock when removing from cart
    if product_id in products:
        products[product_id]["quantity"] += item_to_remove["quantity"]
        db_manager.save_products(products)  # ✅ Save updated stock

    # ✅ Remove from cart
    cart = [item for item in cart if item['id'] != product_id]
    session['cart'] = cart

    flash(f"Removed {item_to_remove['name']} from cart. Stock restored.", "success")
    return redirect(url_for('checkout.checkout'))


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

    # ✅ Ensure cart is initialized before using it
    cart = session.get('cart', [])  # ⬅️ FIX: Use .get() to avoid KeyError
    if not cart:
        flash("Your cart is empty. Please add items before checking out.", "error")
        return redirect(url_for('checkout.checkout'))

    # Store billing info and cart in session for confirmation page
    session['billing_info'] = {
        'name': name,
        'address': address,
        'postal_code': postal_code,
        'card': f"**** **** **** {card[-4:]}"  # Masked card number
    }
    session['cart_items'] = cart[:]  # ✅ Ensure cart items are copied before clearing
    session['total_price'] = sum(item['price'] * item['quantity'] for item in cart)

    # ✅ Save transactions to database
    db_manager = EnhancedDatabaseManager()
    user_id = session.get('user_id')

    # ✅ Update ownership so products appear in the returns section
    ownership = db_manager.get_ownership(user_id)
    ownership.setdefault("products", [])  # Ensure "products" key exists
    for item in cart:
        for _ in range(item["quantity"]):  # Add one entry per quantity purchased
            ownership["products"].append(item["id"])

    db_manager.save_ownership(user_id, ownership)  # Save updated ownership

    # ✅ Save the transaction
    for item in cart:
        db_manager.add_transaction(
            user_id=user_id,
            product_name=item["name"],
            amount=item["price"] * item["quantity"],
            quantity=item["quantity"]
        )

    session.pop('cart', None)  # ✅ Clear cart properly after checkout

    flash("Checkout successful!", "success")
    return redirect(url_for('checkout.confirmation'))


@checkout_bp.route('/')
def checkout():
    """Display the checkout page."""
    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    user_id = session.get('user_id')
    users = EnhancedDatabaseManager().get_users()

    # ✅ Fetch Balance & Points
    balance = users.get(user_id, {}).get("balance", 0)
    user_points = users.get(user_id, {}).get("points", 0)  # ✅ Fetch points

    # ✅ Get navigation options for customers
    nav_data = EnhancedDatabaseManager().get_nav_options('customer')
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    return render_template(
        'customer_checkout.html',
        cart_items=cart,
        total=total,
        user_balance=balance,
        user_points=user_points,  # ✅ Pass points to template
        nav_options=nav_options,
        dropdown_options=dropdown_options
    )


@checkout_bp.route('/confirmation')
def confirmation():
    """Display the confirmation page after checkout."""
    billing_info = session.get('billing_info', {})
    cart_items = session.get('cart_items', [])  # Retrieve saved cart items
    total_price = session.get('total_price', 0)

    if not billing_info:
        flash("No checkout information found. Redirecting back to checkout.", "error")
        return redirect(url_for('checkout.checkout'))

    # ✅ Get navigation options for customers
    nav_data = EnhancedDatabaseManager().get_nav_options('customer')
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    return render_template(
        'customer_confirmation.html',
        billing_info=billing_info,
        cart_items=cart_items,
        total=total_price,
        nav_options=nav_options,  # ✅ Ensures header works
        dropdown_options=dropdown_options  # ✅ Fix dropdown issue
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
        """Remove a product from the cart and update session."""
        cart = session.get('cart', [])
        cart = [item for item in cart if item['id'] != product_id]
        session['cart'] = cart  # ✅ Ensure session cart updates

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