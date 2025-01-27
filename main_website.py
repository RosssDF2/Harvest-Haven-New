from flask import Flask, redirect, url_for
from Profile_Section import profile_bp
from Product_Section import product_bp
from Discounted_Section import discounted_bp
from CheckOut_Section import checkout_bp
from Reward_Section import reward_bp
from Return_Section import return_bp
from database import EnhancedDatabaseManager


import os

app = Flask(__name__)
app.secret_key = "master_secret_key"


# Configure file uploads
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')  # Save images in static/uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Ensure the upload folder exists


# Initialize the database
manager = EnhancedDatabaseManager()
manager.initialize_database()

# Register blueprints for each section
app.register_blueprint(profile_bp, url_prefix='/profile')
app.register_blueprint(product_bp, url_prefix='/products')
app.register_blueprint(discounted_bp, url_prefix='/discounted')
app.register_blueprint(checkout_bp, url_prefix='/checkout')
app.register_blueprint(reward_bp, url_prefix='/rewards')
app.register_blueprint(return_bp, url_prefix='/returns')

@app.route('/')
def index():
    """Redirect to profile section."""
    return redirect(url_for('profile.home'))

if __name__ == '__main__':
    app.run(debug=True)
