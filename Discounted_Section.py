import os
from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime
from database import EnhancedDatabaseManager

discounted_bp = Blueprint('discounted', __name__)
db_manager = EnhancedDatabaseManager()

# Config for file upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@discounted_bp.route('/', methods=['GET'])
def home():
    """Main discounted products page with filtering and search."""
    user_role = session.get('role')
    user_id = session.get('user_id')  # Get current logged-in user
    nav_options = db_manager.get_nav_options(user_role)

    remove_expired_products()
    discounted_items = db_manager.get_all_items()

    # If the user is a farmer, only show their own products
    if user_role == 'farmer':
        discounted_items = {
            item_id: item for item_id, item in discounted_items.items()
            if item.get('owner_id') == user_id
        }

    selected_category = request.args.get('category')
    search_query = request.args.get('search', '').strip().lower()

    if selected_category:
        discounted_items = {
            item_id: item for item_id, item in discounted_items.items()
            if item.get('category') == selected_category
        }

    if search_query:
        discounted_items = {
            item_id: item for item_id, item in discounted_items.items()
            if search_query in item.get('name', '').lower()
        }

    discounted_items_with_ids = [
        {"id": item_id, **item_data} for item_id, item_data in discounted_items.items()
    ]

    template = "customer_discounted_products.html" if user_role == 'customer' else "farmer_discounted_products.html"
    return render_template(template, items=discounted_items_with_ids, nav_options=nav_options)


@discounted_bp.route('/add_discounted', methods=['POST'])
def add_discounted():
    """Allow farmers to add their own discounted products."""
    user_id = session.get('user_id')
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add discounted products.", "error")
        return redirect(url_for('discounted.home'))

    name = request.form.get('name')
    price = request.form.get('price')
    stock = request.form.get('stock')
    category = request.form.get('category')
    expiry_date = request.form.get('expiry_date')
    image = request.files.get('image')

    if not all([name, price, stock, category, expiry_date, image]):
        flash("All fields, including an image and expiry date, are required.", "error")
        return redirect(url_for('discounted.home'))

    if not allowed_file(image.filename):
        flash("Invalid image format. Allowed formats: png, jpg, jpeg, gif.", "error")
        return redirect(url_for('discounted.home'))

    try:
        filename = secure_filename(image.filename)
        image.save(os.path.join(UPLOAD_FOLDER, filename))

        discounted_items = db_manager.get_all_items()
        item_id = max(discounted_items.keys(), default=0) + 1
        discounted_items[item_id] = {
            "name": f"Discounted {name}",
            "price": float(price),
            "stock": int(stock),
            "category": category,
            "expiry_date": expiry_date,
            "image_url": f"/static/uploads/{filename}",
            "owner_id": user_id  # Store the farmer's user ID
        }
        db_manager.save_items(discounted_items)

        flash(f"Discounted product '{name}' added successfully!", "success")
    except Exception as e:
        flash(f"Error adding discounted product: {e}", "error")

    return redirect(url_for('discounted.home'))


def remove_expired_products():
    """Automatically remove discounted products that have expired."""
    discounted_items = db_manager.get_all_items()
    current_datetime = datetime.now()

    expired_items = [
        item_id for item_id, item in discounted_items.items()
        if datetime.strptime(item.get("expiry_date", "")[:10], "%Y-%m-%d").date() < current_datetime.date()
    ]

    if expired_items:
        for item_id in expired_items:
            del discounted_items[item_id]

        db_manager.save_items(discounted_items)
        print(f"Removed expired products: {expired_items}")


@discounted_bp.route('/delete_discounted/<int:item_id>', methods=['POST'])
def delete_discounted(item_id):
    """Only allow the product owner to delete it."""
    user_id = session.get('user_id')

    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can delete discounted products.", "error")
        return redirect(url_for('discounted.home'))

    discounted_items = db_manager.get_all_items()

    if item_id not in discounted_items:
        flash("Product not found.", "error")
        return redirect(url_for('discounted.home'))

    if discounted_items[item_id].get("owner_id") != user_id:
        flash("You can only delete your own products!", "error")
        return redirect(url_for('discounted.home'))

    del discounted_items[item_id]
    db_manager.save_items(discounted_items)

    flash("Discounted product deleted successfully!", "success")
    return redirect(url_for('discounted.home'))


@discounted_bp.route('/update_discounted/<int:item_id>', methods=['POST'])
def update_discounted(item_id):
    """Only allow the product owner to update it."""
    user_id = session.get('user_id')

    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update discounted products.", "error")
        return redirect(url_for('discounted.home'))

    discounted_items = db_manager.get_all_items()

    if item_id not in discounted_items:
        flash("Product not found.", "error")
        return redirect(url_for('discounted.home'))

    if discounted_items[item_id].get("owner_id") != user_id:
        flash("You can only update your own products!", "error")
        return redirect(url_for('discounted.home'))

    # Retrieve updated values from the form
    price = request.form.get('price')
    stock = request.form.get('stock')
    expiry_date = request.form.get('expiry_date')
    category = request.form.get('category')
    image = request.files.get('image')

    try:
        if price:
            discounted_items[item_id]['price'] = float(price)
        if stock:
            discounted_items[item_id]['stock'] = int(stock)
        if expiry_date:
            discounted_items[item_id]['expiry_date'] = expiry_date
        if category:
            discounted_items[item_id]['category'] = category

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
            discounted_items[item_id]['image_url'] = f"/static/uploads/{filename}"

        db_manager.save_items(discounted_items)
        flash("Product updated successfully!", "success")

    except Exception as e:
        flash(f"Error updating product: {e}", "error")

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
    db_manager.add_transaction(user_id, item['name'], total_price, quantity)

    flash(f"Successfully purchased {quantity}x '{item['name']}' for ${total_price:.2f}.", "success")
    return redirect(url_for('discounted.home'))
