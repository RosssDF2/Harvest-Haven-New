from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import EnhancedDatabaseManager

checkout_bp = Blueprint('checkout', __name__)
db_manager = EnhancedDatabaseManager()

@checkout_bp.route('/')
def checkout():
    """Display the customer's cart for checkout."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can checkout.", "error")
        return redirect(url_for('profile.profile'))

    nav_options = db_manager.get_nav_options(session.get('role'))
    cart_items = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    user_balance = round(db_manager.get_users().get(session.get('user_id'), {}).get("balance", 0), 2)

    return render_template(
        "customer_checkout.html",
        cart_items=cart_items,
        total=total,
        user_balance=user_balance,
        nav_options=nav_options,
    )



@checkout_bp.route('/process_checkout', methods=['POST'])
def process_checkout():
    """Process the customer's checkout."""
    user_id = session.get('user_id')
    if not user_id or session.get('role') != 'customer':
        flash("Unauthorized action.", "error")
        return redirect(url_for('checkout.checkout'))

    cart_items = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    user_balance = db_manager.get_users().get(user_id, {}).get("balance", 0)

    if user_balance < total:
        flash("Insufficient balance for checkout.", "error")
        return redirect(url_for('checkout.checkout'))

    db_manager.adjust_user_balance(user_id, -total)
    ownership = db_manager.get_ownership(user_id)

    # Update ownership["products"] and log transactions
    for item in cart_items:
        for _ in range(item['quantity']):
            ownership["products"].append(item['id'])  # Add product IDs to ownership

        # Log the transaction for the item
        db_manager.add_transaction(
            user_id=user_id,
            product_name=item['name'],
            amount=item['price'] * item['quantity'],
            quantity=item['quantity'],
        )

    db_manager.save_ownership(user_id, ownership)

    # Update inventory
    products = db_manager.get_products()
    for item in cart_items:
        if item['id'] in products:
            products[item['id']]['quantity'] -= item['quantity']
    db_manager.save_products(products)

    # Clear the cart
    session['cart'] = []
    flash("Checkout successful!", "success")
    return redirect(url_for('checkout.checkout'))



@checkout_bp.route('/add_to_cart_discounted/<int:item_id>', methods=['POST'])
def add_to_cart_discounted(item_id):
    """Add a discounted product to the customer's cart."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can add to cart.", "error")
        return redirect(url_for('discounted.home'))

    quantity = int(request.form.get('quantity', 1))
    discounted_items = db_manager.get_all_items()
    item = discounted_items.get(item_id)

    if not item:
        flash("Product not found.", "error")
        return redirect(url_for('discounted.home'))

    if item['stock'] < quantity:
        flash("Insufficient stock available.", "error")
        return redirect(url_for('discounted.home'))

    # Add the discounted product to the cart
    cart = session.get('cart', [])
    cart.append({
        "id": item_id,
        "name": item['name'],
        "price": item['price'],
        "quantity": quantity,
        "type": "discounted",  # Identify this as a discounted product
    })
    session['cart'] = cart

    flash(f"'{item['name']}' added to cart!", "success")
    return redirect(url_for('discounted.home'))




@checkout_bp.route('/farmer_purchases')
def farmer_purchases():
    """Allow farmers to view customer purchases."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can view this page.", "error")
        return redirect(url_for('profile.profile'))

    purchases = db_manager.get_transactions("customer1")  # Placeholder logic
    nav_options = db_manager.get_nav_options(session.get('role'))  # Ensure nav_options is included
    return render_template(
        "farmer_checkout.html",
        purchases=purchases,
        nav_options=nav_options  # Pass nav_options to the template
    )
