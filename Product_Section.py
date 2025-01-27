import os
from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
from database import EnhancedDatabaseManager

product_bp = Blueprint('products', __name__)
db_manager = EnhancedDatabaseManager()

# config for file upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@product_bp.route('/', methods=['GET'])
def home():
    """Main product page with optional filtering."""
    user_role = session.get('role')
    nav_options = db_manager.get_nav_options(user_role)

    # retrieve products from db
    products = db_manager.get_products()
    users = db_manager.get_users()  # Retrieve user data for product uploader

    # to get selected categ from query para
    selected_category = request.args.get('category')

    if selected_category:
        # to filter products by category
        products = {
            pid: pdata
            for pid, pdata in products.items()
            if pdata['category'] == selected_category
        }

    # to have products with IDs and uploader names
    products_with_ids = [
        {"id": product_id, **product_data}
        for product_id, product_data in products.items()
    ]

    # profile login (cust, farmer separate)
    if user_role == 'customer':
        return render_template(
            "customer_products.html",
            products=products_with_ids,
            nav_options=nav_options,
            selected_category=selected_category,
        )
    elif user_role == 'farmer':
        return render_template(
            "farmer_products.html",
            products=products_with_ids,
            nav_options=nav_options,
        )
    else:
        flash("Unauthorized access.", "error")
        return redirect(url_for('profile.login'))

#FARMER SIDE
@product_bp.route('/add_product', methods=['POST'])
def add_product():
    """Allow farmers to add new products with an image."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can add products.", "error")
        return redirect(url_for('products.home'))

    # to get form data
    name = request.form.get('name')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    category = request.form.get('category')
    image = request.files.get('image')  # to get uploaded image file

    # validate inputs
    if not name or not price or not quantity or not category or not image:
        flash("All fields, including an image, are required.", "error")
        return redirect(url_for('products.home'))

    if not allowed_file(image.filename):
        flash("Invalid image format. Allowed formats: png, jpg, jpeg, gif.", "error")
        return redirect(url_for('products.home'))

    try:
        # to save images
        filename = secure_filename(image.filename)
        image.save(os.path.join(UPLOAD_FOLDER, filename))

        #
        price = float(price)
        quantity = int(quantity)

        # to add product to db
        products = db_manager.get_products()
        product_id = max(products.keys(), default=0) + 1
        products[product_id] = {
            "name": name,
            "price": price,
            "quantity": quantity,
            "category": category,
            "image_url": f"/static/uploads/{filename}",  # Save the image path
            "uploaded_by": session.get('user_id'),
        }
        db_manager.save_products(products)

        flash(f"Product '{name}' added successfully!", "success")
    except Exception as e:
        flash(f"Error adding product: {e}", "error")
    return redirect(url_for('products.home'))


@product_bp.route('/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    """Allow farmers to update existing products, including their images."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can update products.", "error")
        return redirect(url_for('products.home'))

    # get product from db
    products = db_manager.get_products()
    product = products.get(product_id)

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('products.home'))

    # to retrieve form data
    name = request.form.get('name')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    category = request.form.get('category')
    image = request.files.get('image')

    if not name or not price or not quantity or not category:
        flash("All fields (except image) are required.", "error")
        return redirect(url_for('products.home'))

    try:
        # update of product details
        product['name'] = name
        product['price'] = float(price)
        product['quantity'] = int(quantity)
        product['category'] = category

        # to save if new image updated
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
            product['image_url'] = f"/static/uploads/{filename}"

        products[product_id] = product
        db_manager.save_products(products)

        flash(f"Product '{product['name']}' updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating product: {e}", "error")
    return redirect(url_for('products.home'))


@product_bp.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Allow farmers to delete products."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can delete products.", "error")
        return redirect(url_for('products.home'))

    products = db_manager.get_products()
    if product_id in products:
        del products[product_id]
        db_manager.save_products(products)

        flash("Product deleted successfully!", "success")
    else:
        flash("Product not found.", "error")

    return redirect(url_for('products.home'))

#CUSTOMER SIDE
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


    try:
        quantity = int(request.form.get('quantity'))
        if quantity <= 0 or quantity > product['quantity']:
            flash("Invalid quantity selected.", "error")
            return redirect(url_for('products.home'))
    except ValueError:
        flash("Invalid quantity input.", "error")
        return redirect(url_for('products.home'))

    # Add product to the cust's cart in the session
    cart = session.get('cart', [])
    cart.append({"id": product_id, "name": product['name'], "price": product['price'], "quantity": quantity})
    session['cart'] = cart

    flash(f"'{product['name']}' ({quantity}x) added to cart!", "success")
    return redirect(url_for('products.home'))