from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests
import mercadopago

# --- 1. CONFIGURACIÓN DE MERCADO PAGO ---
# ¡¡REEMPLAZA ESTO CON TU ACCESS TOKEN DE PRUEBA!!
sdk = mercadopago.SDK("APP_USR-xxxxxxxx-xxxxxx-xxxxxxxx")

# --- 2. CATÁLOGO DE PRODUCTOS ---
# ¡¡IMPORTANTE!! Debes editar los precios de tus productos aquí.
CATALOGO_PRODUCTOS = {
    1: {"nombre": "Coca Cola", "precio": 1000},
    2: {"nombre": "Papas Fritas", "precio": 800},
    3: {"nombre": "Galletas", "precio": 600},
    4: {"nombre": "Chocolates", "precio": 1200},
    5: {"nombre": "Jugos", "precio": 900},
    6: {"nombre": "Agua", "precio": 700},
    7: {"nombre": "Snacks", "precio": 850},
    8: {"nombre": "Café", "precio": 1500},
    9: {"nombre": "Té", "precio": 1300},
    10: {"nombre": "Energizantes", "precio": 1800},
    11: {"nombre": "Refrescos", "precio": 950},
    12: {"nombre": "Leche", "precio": 800},
    13: {"nombre": "Frutos Secos", "precio": 2000},
    14: {"nombre": "Galletas Saladas", "precio": 650},
    15: {"nombre": "Dulces", "precio": 500}
}

app = Flask(__name__)
CORS(app)

# Dirección IP de la Raspberry Pi
RASPBERRY_PI_URL = 'https://19e2-191-126-170-134.ngrok-free.app/guardar_qr'

# -----------------------------------------------
# RUTA RAÍZ
# -----------------------------------------------
@app.route('/')
def index():
    return "Servidor Flask en funcionamiento con Mercado Pago"

# -----------------------------------------------
# RUTA PARA CREAR LA PREFERENCIA DE PAGO
# -----------------------------------------------
@app.route('/crear_pago', methods=['POST'])
def crear_pago():
    try:
        data_request = request.get_json()
        pedido_id = data_request.get('pedido_id')

        if not pedido_id:
            return jsonify({"error": "Falta pedido_id"}), 400

        producto = CATALOGO_PRODUCTOS.get(int(pedido_id))
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404
        
        preference_data = {
            "items": [
                {
                    "title": producto["nombre"],
                    "quantity": 1,
                    "unit_price": producto["precio"]
                }
            ],
            "back_urls": {
                "success": "https://www.tu-sitio-web.com/pago_exitoso",
                "failure": "https://www.tu-sitio-web.com/pago_fallido",
                "pending": "https://www.tu-sitio-web.com/pago_pendiente"
            },
            "auto_return": "approved",
            "external_reference": str(pedido_id)
        }

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        return jsonify({"preference_id": preference["id"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------
# RUTA ORIGINAL PARA GENERAR QR
# -----------------------------------------------
@app.route('/generar_qr', methods=['POST'])
def generar_qr():
    try:
        data = request.get_json()
        if 'pedido_id' not in data or 'expiracion' not in data or 'telefono' not in data:
            return jsonify({'error': 'Faltan parámetros en la solicitud'}), 400

        pedido_id = data['pedido_id']
        expiracion = data['expiracion']
        telefono = data['telefono']

        qr_content = f"{pedido_id},{expiracion}"
        qr = qrcode.make(qr_content)
        buffer = BytesIO()
        qr.save(buffer)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        try:
            requests.post(RASPBERRY_PI_URL, json={
                'pedido_id': pedido_id,
                'expiracion': time.time() + expiracion,
                'qr_texto': qr_content
            }, timeout=5)
        except Exception as e:
            print(f"Error al enviar QR a la Raspberry Pi: {e}")

        return jsonify({
            'pedido_id': pedido_id,
            'expiracion': time.time() + expiracion,
            'qr_base64': img_base64
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -----------------------------------------------
# INICIAR EL SERVIDOR
# -----------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
