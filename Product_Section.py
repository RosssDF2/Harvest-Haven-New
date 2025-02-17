from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager


product_bp = Blueprint('products', __name__)
db_manager = EnhancedDatabaseManager()

@product_bp.route('/', methods=['GET'])
def home():
    """Main product page with category filtering."""
    """Main product page with category filtering."""
    user_id = session.get('user_id')
    user_role = session.get('role')
    user = db_manager.get_users().get(user_id, {})

    # ✅ Get balance and points (For Customers)
    user_balance = user.get("balance", 0)
    user_points = user.get("points", 0)

    # ✅ Get navigation options for the role
    nav_data = db_manager.get_nav_options(user_role)
    nav_options = nav_data["nav"]
    dropdown_options = nav_data["dropdown"]

    # Get all products
    products = db_manager.get_products()

    # Get selected category from query parameters
    selected_category = request.args.get('category', '')

    # Convert products dictionary into a list with IDs
    products_with_ids = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
    ]

    # Apply category filtering if a category is selected
    if selected_category and selected_category != "All":
        products_with_ids = [product for product in products_with_ids if product["category"] == selected_category]

    if user_role == 'customer':
        user_data = db_manager.get_users().get(user_id, {})
        user_balance = user_data.get("balance", 0)
        user_points = user_data.get("points", 0)

        return render_template(
            "customer_products.html",
            products=products_with_ids,
            nav_options=nav_options,
            dropdown_options=dropdown_options,
            selected_category=selected_category,
            user_balance=user_balance,
            user_points=user_points
        )

    elif user_role == 'farmer':
        # Show only the logged-in farmer's products
        owned_products = [product for product in products_with_ids if product.get("farmer_id") == user_id]

        return render_template(
            "farmer_products.html",
            products=owned_products,
            nav_options=nav_options,
            dropdown_options=dropdown_options
        )


import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads/"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@product_bp.route('/add_product', methods=['POST'])
def add_product():
    """Allow farmers to add products with images."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add products.", "error")
        return redirect(url_for('products.home'))

    name = request.form.get('name')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity'))
    category = request.form.get('category')
    nutritional_facts = request.form.get('nutritional_facts')
    user_id = session.get('user_id')

    # ✅ Handle Image Upload
    image_file = request.files.get('image')
    image_url = "static/uploads/placeholder.png"  # Default image

    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        file_extension = filename.split('.')[-1].lower()

        if file_extension in ALLOWED_EXTENSIONS:
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(image_path)
            image_url = image_path  # ✅ Store correct image URL

    products = db_manager.get_products()
    product_id = max(products.keys(), default=0) + 1

    products[product_id] = {
        "name": name,
        "price": price,
        "quantity": quantity,
        "category": category,
        "nutritional_facts": nutritional_facts,
        "image_url": image_url,
        "farmer_id": user_id
    }

    db_manager.save_products(products)
    flash("Product added successfully!", "success")
    return redirect(url_for('products.home'))

@product_bp.route('/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    """Allow farmers to update only their own products, including images."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update products.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    product = products.get(product_id)

    if not product or product['farmer_id'] != session.get('user_id'):
        flash("Unauthorized access: You cannot update this product.", "error")
        return redirect(url_for('products.home'))

    product['name'] = request.form.get('name')
    product['price'] = float(request.form.get('price'))
    product['quantity'] = int(request.form.get('quantity'))
    product['category'] = request.form.get('category')
    product['nutritional_facts'] = request.form.get('nutritional_facts', product.get('nutritional_facts', ''))

    # ✅ Handle Image Upload
    image_file = request.files.get('image')
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        file_extension = filename.split('.')[-1].lower()

        if file_extension in ALLOWED_EXTENSIONS:
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(image_path)
            product["image_url"] = image_path  # ✅ Update image URL in database

    products[product_id] = product
    db_manager.save_products(products)

    flash(f"Product '{product['name']}' updated successfully!", "success")
    return redirect(url_for('products.home'))

@product_bp.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Allow farmers to delete only their own products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can delete products.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    product = products.get(product_id)

    if not product or product['farmer_id'] != session.get('user_id'):
        flash("Unauthorized access: You cannot delete this product.", "error")
        return redirect(url_for('products.home'))

    del products[product_id]
    db_manager.save_products(products)
    flash("Product deleted successfully.", "success")

    return redirect(url_for('products.home'))

@product_bp.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    """Add a product to the customer's cart with correct quantity handling."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can add to cart.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    product = products.get(product_id)

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('products.home'))

    try:
        quantity = int(request.form.get("quantity", 1))
        if quantity < 1:
            flash("Quantity must be at least 1.", "error")
            return redirect(url_for('products.home'))
    except ValueError:
        flash("Invalid quantity entered.", "error")
        return redirect(url_for('products.home'))

    cart = session.get('cart', [])

    # ✅ Check if the item already exists in the cart and update its quantity
    existing_item = next((item for item in cart if item["id"] == product_id), None)

    if existing_item:
        existing_item["quantity"] += quantity  # ✅ Update quantity instead of replacing
    else:
        cart.append({"id": product_id, "name": product['name'], "price": product['price'], "quantity": quantity})

    session['cart'] = cart

    flash(f"'{product['name']}' added to cart! Quantity: {quantity}", "success")
    return redirect(url_for('products.home'))


@product_bp.route('/filter_products', methods=['GET'])
def filter_products():
    """Filter products by category."""
    category = request.args.get('category')
    products = db_manager.get_products()

    filtered_products = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
        if product_data["category"] == category or category == "All"
    ]

    return render_template("customer_products.html", products=filtered_products)

@product_bp.route('/view_cart')
def view_cart():
    """Display the customer's cart."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can view the cart.", "error")
        return redirect(url_for('products.home'))

    cart = session.get('cart', [])
    return render_template("cart.html", cart=cart)

@product_bp.route('/clear_cart', methods=['POST'])
def clear_cart():
    """Clear the customer's cart."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can clear the cart.", "error")
        return redirect(url_for('products.home'))

    session['cart'] = []
    flash("Cart cleared successfully!", "success")
    return redirect(url_for('view_cart'))

@product_bp.route('/checkout', methods=['POST'])
def checkout():
    """Process the checkout for a customer."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can checkout.", "error")
        return redirect(url_for('products.home'))

    cart = session.get('cart', [])

    if not cart:
        flash("Your cart is empty!", "error")
        return redirect(url_for('view_cart'))

    # Process payment logic (not implemented here)
    session['cart'] = []
    flash("Checkout successful!", "success")
    return redirect(url_for('products.home'))

@product_bp.route('/search', methods=['GET'])
def search_products():
    """Search for products by name."""
    query = request.args.get('query', '').strip().lower()
    products = db_manager.get_products()

    # Filter products based on query
    searched_products = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
        if query in product_data["name"].lower()
    ]

    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)

    return render_template(
        "customer_products.html",
        products=searched_products,
        nav_options=nav_options,
        selected_category="All"
    )
@product_bp.route('/search_farmer_products', methods=['GET'])
def search_farmer_products():
    """Allow farmers to search their own products by name."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can search their products.", "error")
        return redirect(url_for('products.home'))

    query = request.args.get('query', '').strip().lower()
    user_id = session.get('user_id')
    products = db_manager.get_products()

    # Get only products belonging to the logged-in farmer
    farmer_products = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
        if product_data["farmer_id"] == user_id
    ]

    # Filter products based on search query
    searched_products = [product for product in farmer_products if query in product["name"].lower()]

    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)

    return render_template(
        "farmer_products.html",
        products=searched_products,
        nav_options=nav_options
    )