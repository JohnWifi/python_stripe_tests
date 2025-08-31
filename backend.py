import os
import stripe
from flask import Flask, redirect, request, jsonify, render_template
from flask_cors import CORS # Import CORS to handle cross-origin requests
from supabase import create_client, Client

url = "URL"
key = "key"
supabase: Client = create_client(url, key)

app = Flask(__name__)
# Enable CORS for all routes, allowing your local HTML/webview to access this API
CORS(app)

# --- Stripe Configuration ---
# IMPORTANT! Use environment variables for your secret keys in production
# export STRIPE_SECRET_KEY='sk_test_your_secret_key'
# export STRIPE_PUBLIC_KEY='pk_test_your_public_key'
# export STRIPE_WEBHOOK_SECRET='whsec_your_webhook_secret'
stripe.api_key = 'STRIPE_PUBLIC_KEY'
stripe_public_key = 'STRIPE_SECRET_KEY'
webhook_secret = 'STRIPE_WEBHOOK_SECRET'

# Configure your application domains for success and cancel URLs
# In a real environment, these would be your actual domain URLs
# Ensure this URL is accessible from the browser that will open on the Banana Pi
SUCCESS_URL = 'https://johnyidontknow3.pythonanywhere.com/success' # Change to your real IP/domain if not localhost
CANCEL_URL = "https://johnyidontknow3.pythonanywhere.com/cancel"    # Change to your real IP/domain if not localhost

# --- Simulated Accommodation Database ---
# In a real application, this would come from a database
alojamientos = {
    "casa_playa": {
        "name": "Casa de Playa",
        "price_usd_cents": 15000, # $150.00 USD
        "currency": "usd",
        "description": "Hermosa casa frente al mar con acceso automatizado.",
        "access_code": "12345" # Simulated access code
    },
    "apartamento_ciudad": {
        "name": "Apartamento Urbano",
        "price_usd_cents": 8000, # $80.00 USD
        "currency": "usd",
        "description": "Acogedor apartamento en el centro de la ciudad.",
        "access_code": "67890", # Simulated access code
    },
}

# --- API Routes ---

@app.route('/')
def index():
    """
    Main route to display the list of available accommodations.
    This route is for the backend to serve the main web page if accessed directly.
    The desktop app will use the /alojamientos route to get data.
    """
    return render_template('index.html', alojamientos=alojamientos, stripe_public_key=stripe_public_key)

@app.route('/alojamientos', methods=['GET'])
def get_alojamientos():
    """
    Endpoint for the desktop application to get the list of accommodations.
    """
    return jsonify(alojamientos)
@app.route('/register',methods=['GET','POST'])
def register():
    data = request.get_json()
    return_data = None
    if data.get('role') == 'land_lord':
        response = (supabase.table("LAND_LORDS").insert({"NAME":data.get('name'),"PASSWORD":data.get("password")}).execute())
        return_data = supabase.table("LAND_LORDS").select("*").eq("NAME",data.get('name')).limit(1).order("NAME",desc=True).execute()
    else:
        response = supabase.table("USERS").insert({"NAME":data.get('name'),"PASSWORD":data.get("password")}).execute()
        return_data = supabase.table("USERS").select("*").eq("NAME",data.get('name')).limit(1).order("NAME",desc=True).execute()
    return jsonify(return_data.data)
@app.route('/register_house',methods=['GET','POST'])
def register_house():
    data = request.get_json()
    return_data = None
    response = supabase.table("HOUSES").insert({"NAME":data.get('name'),"ADDRESS":data.get("ADDRESS"),"LON":data.get('lon'),"LAT":data.get("LAT"),"LAND_LORD_ID":data.get('land_lord_id')}).execute()
    return 'success'
@app.route('/houses', methods=['GET'])
def get_landlord_houses():
    try:
        # Consulta la tabla 'HOUSES' para obtener las casas de un LAND_LORD_ID específico
        response, count = (
            supabase.table('HOUSES')
            .select("*")
            .execute()
        )

        # Supabase devuelve una lista de diccionarios
        houses_data = response[1]

        # Si no hay casas para ese propietario, devuelve una lista vacía
        if not houses_data:
            return jsonify([])

        return jsonify(houses_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/login_user',methods=['POST'])
def login_user():
    data1 = request.get_json()
    name = data1.get('name')
    password = data1.get('password')
    response = supabase.table("USERS").select("NAME","id").eq("PASSWORD",password).execute()
    response2 = response.data
    return jsonify(response2)
@app.route('/get_user',methods=['POST'])
def get_user():
    data1 = request.get_json()
    id1 = data1.get('id')
    response = supabase.table("USERS").select("NAME").eq("id",id1).execute()
    response2 = response.data
    return jsonify(response2)
@app.route('/get_land_lord',methods=['POST'])
def get_land_lord():
    data1 = request.get_json()
    id1 = data1.get('id')
    response = supabase.table("LAND_LORDS").select("NAME").eq("id",id1).execute()
    response2 = response.data[0]['NAME']
    house_name = supabase.table("HOUSES").select("NAME","id").eq("LAND_LORD_ID",id1).execute()
    house_name_data = house_name.data[0]
    house_name_data_name = house_name_data["NAME"]
    house_name_id = house_name.data[0]
    house_name_id_2 = house_name_id['id']
    data_to_send = {'land_lord_name':response2,'house_name':house_name_data_name,'house_name_id':house_name_id_2}

    return jsonify(data_to_send)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Creates a Stripe Checkout session for a specific accommodation.
    This request would come from the desktop application.
    """
    data = request.get_json()
    alojamiento_id = data.get('alojamiento_id')

    if not alojamiento_id:
        return jsonify({"error": "Accommodation ID not provided"}), 400

    try:
        # Consulta la base de datos de Supabase para obtener la información de la casa
        response = supabase.table("HOUSES").select("NAME, ADDRESS, price_per_night").eq("id", alojamiento_id).single().execute()

        # El método .single() devuelve un solo objeto. Si no se encuentra, genera un error.
        house = response.data

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': house['NAME'],
                            'description': house['ADDRESS'],
                        },
                        # Stripe espera el precio en centavos, por lo que multiplicamos por 100
                        'unit_amount': int(house['price_per_night'] * 100),
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=CANCEL_URL,
            metadata={
                'alojamiento_id': alojamiento_id,
            }
        )
        # Return the session URL for the desktop app to open in the browser
        return jsonify({'checkout_url': checkout_session.url})
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify(error=str(e)), 500

@app.route('/success')
def success():
    """
    Success page after a completed payment.
    This is where the guest is redirected after paying.
    """
    session_id = request.args.get('session_id')
    if session_id:
        try:
            # Retrieve the session to verify its status
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                # Payment was successful
                alojamiento_id = session.metadata.get('alojamiento_id')

                # Obtén el código de acceso y el nombre de la casa de la base de datos
                response = supabase.table("HOUSES").select("NAME, ACCESS_CODE").eq("id", alojamiento_id).single().execute()
                house = response.data

                access_code = house['ACCESS_CODE']
                alojamiento_name = house['NAME']

                # Here you would send the access code to the Banana Pi
                # or display it securely to the user.
                # In a real system, this would involve a secure API call to the Banana Pi
                # or a centralized database that the Banana Pi queries.

                return render_template('success.html', access_code=access_code, alojamiento_name=alojamiento_name)
            else:
                return "Payment not completed. Please try again."
        except stripe.error.StripeError as e:
            return f"Error retrieving Stripe session: {e}"
    return "Payment successful, but payment session not found."

@app.route('/cancel')
def cancel():
    """
    Cancellation page if the user does not complete the payment.
    """
    return "Payment canceled. You can try the reservation again."

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint to receive webhook events from Stripe.
    CRITICAL for securely confirming payments and updating status.
    """
    payload = request.get_data()
    sig_header = request.headers.get('stripe-signature')
    event = None

    if webhook_secret is None:
        print("Webhook secret not set. Webhook verification will fail.")
        return 'Webhook secret not configured', 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        print(f"Webhook Error: Invalid payload: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(f"Webhook Error: Invalid signature: {e}")
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # This is where you confirm the payment and activate the Banana Pi
        print(f"Payment completed for session: {session.id}")
        print(f"Session metadata: %+v", session.metadata)

        alojamiento_id = session.metadata.get('alojamiento_id')

        # En un sistema real, aquí actualizarías el estado de la reserva en la base de datos
        # a 'pagada' y luego le darías el código de acceso a la Banana Pi.
        # Por ahora, solo lo imprimimos para fines de demostración.

        print(f"Activando el acceso para el alojamiento con ID {alojamiento_id}!")

    elif event['type'] == 'checkout.session.async_payment_succeeded':
        session = event['data']['object']
        print(f"Asynchronous payment successful for session: {session.id}")
        # Handle payments that are not instant (e.g., SEPA Direct Debit)

    elif event['type'] == 'checkout.session.async_payment_failed':
        session = event['data']['object']
        print(f"Asynchronous payment failed for session: {session.id}")
        # Handle failed asynchronous payments

    else:
        print('Unhandled event type {}'.format(event['type']))

    return jsonify(success=True)
