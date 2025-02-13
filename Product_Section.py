from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

product_bp = Blueprint('products', __name__)
db_manager = EnhancedDatabaseManager()

from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

product_bp = Blueprint('products', __name__)
db_manager = EnhancedDatabaseManager()

@product_bp.route('/')
def home():
    """Main product page."""
    user_id = session.get('user_id')
    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)

    products = db_manager.get_products()

    # Add product IDs to each product dictionary
    products_with_ids = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
    ]

    if user_role == 'customer':
        return render_template("customer_products.html", products=products_with_ids, nav_options=nav_options)

    elif user_role == 'farmer':
        # Show only the logged-in farmer's products
        owned_products = [product for product in products_with_ids if product["farmer_id"] == user_id]
        return render_template("farmer_products.html", products=owned_products, nav_options=nav_options)

@product_bp.route('/add_product', methods=['POST'])
def add_product():
    """Allow farmers to add products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add products.", "error")
        return redirect(url_for('products.home'))

    name = request.form.get('name')
    price = float(request.form.get('price'))
    quantity = int(request.form.get('quantity'))
    category = request.form.get('category')
    user_id = session.get('user_id')  # Assign the logged-in farmer ID

    products = db_manager.get_products()
    product_id = max(products.keys(), default=0) + 1

    products[product_id] = {
        "name": name,
        "price": price,
        "quantity": quantity,
        "category": category,
        "image_url": "placeholder.png",
        "farmer_id": user_id  # Store the farmer's ID
    }

    db_manager.save_products(products)
    flash("Product added successfully!", "success")
    return redirect(url_for('products.home'))


@product_bp.route('/update_product/<int:product_id>', methods=['GET', 'POST'])
def update_product(product_id):
    """Allow farmers to update only their own products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update products.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    product = products.get(product_id)

    if not product or product['farmer_id'] != session.get('user_id'):
        flash("Unauthorized access: You cannot update this product.", "error")
        return redirect(url_for('products.home'))

    if request.method == 'POST':
        product['name'] = request.form.get('name')
        product['price'] = float(request.form.get('price'))
        product['quantity'] = int(request.form.get('quantity'))
        products[product_id] = product
        db_manager.save_products(products)

        flash(f"Product '{product['name']}' updated successfully!", "success")
        return redirect(url_for('products.home'))

    return render_template("update_product.html", product=product)

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
    """Add a product to the customer's cart."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can add to cart.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    product = products.get(product_id)

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('products.home'))

    # Add the product to the customer's cart in the session
    cart = session.get('cart', [])
    cart.append({"id": product_id, "name": product['name'], "price": product['price'], "quantity": 1})
    session['cart'] = cart

    flash(f"'{product['name']}' added to cart!", "success")
    return redirect(url_for('products.home'))

