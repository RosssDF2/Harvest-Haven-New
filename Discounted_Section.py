import os
from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
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
    """Main discounted products page with optional filtering and search."""
    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)

    # Retrieve discounted items from the database
    discounted_items = db_manager.get_all_items()

    # Get filtering options from query parameters
    selected_category = request.args.get('category')
    search_query = request.args.get('search', '').strip().lower()

    if selected_category:
        # Filter discounted items by category
        discounted_items = {
            item_id: item
            for item_id, item in discounted_items.items()
            if item.get('category') == selected_category
        }

    if search_query:
        # Filter discounted items by search query
        discounted_items = {
            item_id: item
            for item_id, item in discounted_items.items()
            if search_query in item.get('name', '').lower()
        }

    # Include item IDs for template rendering
    discounted_items_with_ids = [
        {"id": item_id, **item_data}
        for item_id, item_data in discounted_items.items()
    ]

    if user_role == 'customer':
        return render_template(
            "customer_discounted_products.html",
            items=discounted_items_with_ids,
            nav_options=nav_options,
            selected_category=selected_category,
            search_query=search_query
        )
    elif user_role == 'farmer':
        return render_template(
            "farmer_discounted_products.html",
            items=discounted_items_with_ids,
            nav_options=nav_options,
        )


@discounted_bp.route('/add_discounted', methods=['POST'])
def add_discounted():
    """Allow farmers to add discounted products with an image."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add discounted products.", "error")
        return redirect(url_for('discounted.home'))

    # Retrieve form data
    name = request.form.get('name')
    price = request.form.get('price')
    stock = request.form.get('stock')
    category = request.form.get('category')
    expiry_date = request.form.get('expiry_date')  # New field
    image = request.files.get('image')

    # Validate inputs
    if not name or not price or not stock or not category or not expiry_date or not image:
        flash("All fields, including an image and expiry date, are required.", "error")
        return redirect(url_for('discounted.home'))

    if not allowed_file(image.filename):
        flash("Invalid image format. Allowed formats: png, jpg, jpeg, gif.", "error")
        return redirect(url_for('discounted.home'))

    try:
        # Save the image
        filename = secure_filename(image.filename)
        image.save(os.path.join(UPLOAD_FOLDER, filename))

        # Add the new discounted product to the database
        discounted_items = db_manager.get_all_items()
        item_id = max(discounted_items.keys(), default=0) + 1
        discounted_items[item_id] = {
            "name": f"Discounted {name}",
            "price": float(price),
            "stock": int(stock),
            "category": category,
            "expiry_date": expiry_date,  # New field
            "image_url": f"/static/uploads/{filename}",
        }
        db_manager.save_items(discounted_items)

        flash(f"Discounted product '{name}' added successfully!", "success")
    except Exception as e:
        flash(f"Error adding discounted product: {e}", "error")
    return redirect(url_for('discounted.home'))

def remove_expired_products():
    """Automatically remove discounted products that have expired."""
    discounted_items = db_manager.get_all_items()
    current_date = datetime.now().date()  # Get today's date

    expired_items = [
        item_id for item_id, item in discounted_items.items()
        if datetime.strptime(item.get("expiry_date", ""), "%Y-%m-%d").date() < current_date
    ]

    if expired_items:
        for item_id in expired_items:
            del discounted_items[item_id]

        db_manager.save_items(discounted_items)
        print(f"Removed expired products: {expired_items}")

@discounted_bp.route('/update_discounted/<int:item_id>', methods=['POST'])
def update_discounted(item_id):
    """Update discounted item details, including its image."""
    discounted_items = db_manager.get_all_items()

    if item_id not in discounted_items:
        flash("Item not found.", "error")
        return redirect(url_for('discounted.home'))

    # Retrieve form inputs
    name = request.form.get('name')
    price = request.form.get('price')
    stock = request.form.get('stock')
    category = request.form.get('category')
    expiry_date = request.form.get('expiry_date')  # New field
    image = request.files.get('image')

    if not name or not price or not stock or not category or not expiry_date:
        flash("All fields (except image) are required.", "error")
        return redirect(url_for('discounted.home'))

    try:
        # Update discounted item details
        item = discounted_items[item_id]
        item['name'] = name
        item['price'] = float(price)
        item['stock'] = int(stock)
        item['category'] = category
        item['expiry_date'] = expiry_date  # New field

        # Save new image if provided
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
            item['image_url'] = f"/static/uploads/{filename}"

        discounted_items[item_id] = item
        db_manager.save_items(discounted_items)

        flash(f"Discounted product '{name}' updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating discounted product: {e}", "error")
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
    db_manager.add_transaction(user_id, item['name'], total_price, quantity)

    flash(f"Successfully purchased {quantity}x '{item['name']}' for ${total_price:.2f}.", "success")
    return redirect(url_for('discounted.home'))
