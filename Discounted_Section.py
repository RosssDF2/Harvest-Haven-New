from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

discounted_bp = Blueprint('discounted', __name__)
db_manager = EnhancedDatabaseManager()

@discounted_bp.route('/')
def home():
    """Main discounted products page."""
    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)
    discounted_items = db_manager.get_all_items()

    # Add item IDs for template rendering
    discounted_items_with_ids = [
        {"id": item_id, **item_data}
        for item_id, item_data in discounted_items.items()
    ]

    if user_role == 'customer':
        return render_template(
            "customer_discounted_products.html",
            items=discounted_items_with_ids,
            nav_options=nav_options,
        )
    elif user_role == 'farmer':
        return render_template(
            "farmer_discounted_products.html",
            items=discounted_items_with_ids,
            nav_options=nav_options,
        )

@discounted_bp.route('/add_discounted', methods=['POST'])
def add_discounted():
    """Allow farmers to add discounted products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add discounted products.", "error")
        return redirect(url_for('discounted.home'))

    name = request.form.get('name')
    price = float(request.form.get('price'))
    stock = int(request.form.get('stock'))

    # Generate a new discounted item ID
    discounted_items = db_manager.get_all_items()
    item_id = max(discounted_items.keys(), default=0) + 1

    # Add discounted product
    discounted_items[item_id] = {
        "name": f"Discounted {name}",
        "price": price,
        "stock": stock,
    }
    db_manager.save_items(discounted_items)

    flash(f"Discounted product '{name}' added successfully!", "success")
    return redirect(url_for('discounted.home'))

@discounted_bp.route('/update_discounted/<int:item_id>', methods=['POST'])
def update_discounted(item_id):
    """Update a discounted product."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update discounted products.", "error")
        return redirect(url_for('discounted.home'))

    discounted_items = db_manager.get_all_items()
    if item_id not in discounted_items:
        flash("Discounted product not found.", "error")
        return redirect(url_for('discounted.home'))

    discounted_items[item_id]['name'] = request.form.get('name')
    discounted_items[item_id]['price'] = float(request.form.get('price'))
    discounted_items[item_id]['stock'] = int(request.form.get('stock'))
    db_manager.save_items(discounted_items)

    flash("Discounted product updated successfully!", "success")
    return redirect(url_for('discounted.home'))

@discounted_bp.route('/delete_discounted/<int:item_id>', methods=['POST'])
def delete_discounted(item_id):
    """Delete a discounted product."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can delete discounted products.", "error")
        return redirect(url_for('discounted.home'))

    discounted_items = db_manager.get_all_items()
    if item_id in discounted_items:
        del discounted_items[item_id]
        db_manager.save_items(discounted_items)
        flash("Discounted product deleted successfully!", "success")
    else:
        flash("Discounted product not found.", "error")

    return redirect(url_for('discounted.home'))

@discounted_bp.route('/buy_discounted/<int:item_id>', methods=['POST'])
def buy_discounted(item_id):
    """Allow customers to buy discounted products."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can buy discounted products.", "error")
        return redirect(url_for('discounted.home'))

    quantity = int(request.form.get('quantity', 1))
    discounted_items = db_manager.get_all_items()
    item = discounted_items.get(item_id)

    if not item:
        flash("Product not found.", "error")
        return redirect(url_for('discounted.home'))

    total_price = item['price'] * quantity
    user_id = session.get('user_id')
    user_balance = db_manager.get_users().get(user_id, {}).get("balance", 0)

    if user_balance < total_price:
        flash("Insufficient balance to complete the purchase.", "error")
        return redirect(url_for('discounted.home'))

    if item['stock'] < quantity:
        flash("Insufficient stock available.", "error")
        return redirect(url_for('discounted.home'))

    # Update the item stock
    item['stock'] -= quantity
    discounted_items[item_id] = item
    db_manager.save_items(discounted_items)

    # Update the user's balance and log the transaction
    db_manager.adjust_user_balance(user_id, -total_price)
    db_manager.add_transaction(user_id, item['name'], total_price)

    flash(f"Successfully purchased {quantity}x '{item['name']}' for ${total_price:.2f}.", "success")
    return redirect(url_for('discounted.home'))
