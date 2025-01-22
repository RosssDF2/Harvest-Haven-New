from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager

return_bp = Blueprint('returns', __name__)
db_manager = EnhancedDatabaseManager()

@return_bp.route('/')
def returns():
    """Display customer's purchased products for returns."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can access this page.", "error")
        return redirect(url_for('profile.profile'))

    user_id = session.get('user_id')
    ownership = db_manager.get_ownership(user_id)
    owned_products_ids = ownership.get("products", [])
    returned_items = ownership.get("returns", {})
    all_products = db_manager.get_products()

    # Prepare items for the return section
    purchased_products = []
    for product_id in owned_products_ids:
        if product_id in all_products:
            total_purchased = owned_products_ids.count(product_id)
            total_returned = returned_items.get(product_id, 0)

            if total_returned < total_purchased:
                purchased_products.append({
                    "id": product_id,
                    "name": all_products[product_id]["name"],
                    "remaining": total_purchased - total_returned
                })

    nav_options = db_manager.get_nav_options(session.get('role'))
    print("Purchased Products for Returns:", purchased_products)  # Debugging Output
    return render_template(
        "customer_returns.html",
        products=purchased_products,
        nav_options=nav_options,
    )



@return_bp.route('/submit_return', methods=['POST'])
def submit_return():
    """Allow customers to submit a return request."""
    if session.get('role') != 'customer':
        flash("Unauthorized action.", "error")
        return redirect(url_for('returns.returns'))

    user_id = session.get('user_id')
    product_id = int(request.form.get('product_id'))
    quantity = int(request.form.get('quantity'))
    reason = request.form.get('reason')

    # Update ownership["returns"]
    ownership = db_manager.get_ownership(user_id)
    ownership["returns"] = ownership.get("returns", {})
    ownership["returns"][product_id] = ownership["returns"].get(product_id, 0) + quantity
    db_manager.save_ownership(user_id, ownership)

    # Log the return transaction
    product_name = db_manager.get_products()[product_id]["name"]
    db_manager.add_return_transaction(
        user_id=user_id,
        product_name=product_name,
        reason=reason
    )

    flash(f"Successfully returned {quantity}x '{product_name}'.", "success")
    return redirect(url_for('returns.returns'))



@return_bp.route('/farmer_returns')
def farmer_returns():
    """Display customer returns for farmers."""
    if session.get('role') != 'farmer':
        flash("Access denied! Only farmers can view this page.", "error")
        return redirect(url_for('profile.home'))

    returns = db_manager.get_ownership(session.get('user_id')).get("returns", [])
    return render_template("farmer_returns.html", returns=returns)
