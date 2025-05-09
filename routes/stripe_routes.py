
from flask import Blueprint, jsonify, request, current_app
import stripe
from core.responses import api_error_response, api_success_response
from core.auth import auth_required

stripe_bp = Blueprint('stripe', __name__, url_prefix='/api/stripe')

@stripe_bp.before_request
def initialize_stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

@stripe_bp.route('/create-payment-intent', methods=['POST'])
@auth_required
def create_payment_intent():
    try:
        data = request.json
        amount = data.get('amount')
        
        if not amount:
            return api_error_response("Amount is required", 400)

        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency='usd'
        )
        
        return api_success_response({
            'clientSecret': intent.client_secret
        })

    except stripe.error.StripeError as e:
        return api_error_response(str(e), 400)
    except Exception as e:
        return api_error_response("An error occurred", 500)
