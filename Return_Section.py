from flask import Blueprint, render_template,jsonify, request, session, flash, redirect, url_for
from database import EnhancedDatabaseManager
import shelve

return_bp = Blueprint('returns', __name__)
db_manager = EnhancedDatabaseManager()

@return_bp.route('/')
def returns():
    """Display customer's purchased products for returns, grouped by product name."""
    if session.get('role') != 'customer':
        flash("Access denied! Only customers can access this page.", "error")
        return redirect(url_for('profile.profile'))

    user_id = session.get('user_id')
    ownership = db_manager.get_ownership(user_id)
    owned_products_ids = ownership.get("products", [])
    returned_items = ownership.get("returns", {})
    all_products = db_manager.get_products()

    grouped_products = {}
    for product_id in set(owned_products_ids):
        if product_id in all_products:
            product_name = all_products[product_id]["name"]
            total_purchased = owned_products_ids.count(product_id)
            total_returned = returned_items.get(product_id, 0)
            remaining_quantity = total_purchased - total_returned

            if remaining_quantity > 0:
                if product_name not in grouped_products:
                    grouped_products[product_name] = {
                        "id": product_id,
                        "name": product_name,
                        "remaining": 0,
                    }
                grouped_products[product_name]["remaining"] += remaining_quantity

    nav_options = db_manager.get_nav_options(session.get('role'))
    return render_template(
        "customer_returns.html",
        products=list(grouped_products.values()),
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

    farmer_id = session.get('user_id')
    returns = db_manager.get_farmer_notifications(farmer_id)  # Fetch pending returns for this farmer

    # Debugging: Print return list after fetching
    print(f"DEBUG: Returns fetched for farmer {farmer_id}:", returns)

    # Only show returns that are still pending
    pending_returns = [r for r in returns if r.get("status") == "pending"]

    print("DEBUG: Final Returns List Sent to Template:", pending_returns)

    nav_options = db_manager.get_nav_options(session.get('role'))
    return render_template(
        "farmer_returns.html",
        returns=pending_returns,
        nav_options=nav_options
    )



@return_bp.route('/handle_return', methods=['POST'])
def handle_return():
    """Handle farmer's decision to approve or reject a return."""
    if 'user_id' not in session or session.get('role') != 'farmer':
        flash("Unauthorized action.", "danger")
        return redirect(url_for('returns.farmer_returns'))

    action = request.form.get('action')  # Approve or Reject
    product_id = request.form.get('product_id')
    customer_id = request.form.get('customer_id')
    product_name = request.form.get('product_name')

    print(f"DEBUG: Received Data -> action={action}, product_id={product_id}, customer_id={customer_id}, product_name={product_name}")

    if not all([action, product_id, customer_id, product_name]):
        flash("Missing required fields. Please try again.", "danger")
        return redirect(url_for('returns.farmer_returns'))

    try:
        product_id = int(product_id) if product_id.isdigit() else None
        customer_id = str(customer_id)  # Keep customer_id as a string for lookup in the DB

        if product_id is None:
            raise ValueError("Invalid Product ID")
    except ValueError as e:
        print(f"DEBUG ERROR: {e}")
        flash("Invalid product ID.", "danger")
        return redirect(url_for('returns.farmer_returns'))

    # Open database and update return status
    with shelve.open("central_database.db", writeback=True) as db:
        return_transactions = db.get("return_transactions", {})

        if customer_id in return_transactions:
            customer_returns = return_transactions[customer_id]
            for return_item in customer_returns:
                if return_item.get("product_name") == product_name:
                    print(f"DEBUG BEFORE UPDATE: {return_item}")  # Print before change
                    return_item["status"] = "approved" if action == "approve" else "rejected"
                    print(f"DEBUG AFTER UPDATE: {return_item}")  # Print after change

            return_transactions[customer_id] = customer_returns
            db["return_transactions"] = return_transactions  # Save update
            print(f"DEBUG: Updated Returns List after {action}: {return_transactions[customer_id]}")

    # Flash success message
    flash(f"Return for '{product_name}' has been {action}.", "success")

    return redirect(url_for('returns.farmer_returns'))











