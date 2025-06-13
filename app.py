from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests
import mercadopago

# --- 1. CONFIGURACIÓN DE MERCADO PAGO ---
# ¡¡REEMPLAZA ESTO CON TU ACCESS TOKEN!!
sdk = mercadopago.SDK("APP_USR-778410764560218-061221-fdda74fc8a02e531d07b634e006cae15-2491526457")
# --- 2. CATÁLOGO DE PRODUCTOS ---
# ¡¡REEMPLAZA ESTOS PRECIOS CON LOS REALES!!
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

# Reemplaza esto con la URL de tu Raspberry Pi
RASPBERRY_PI_URL = 'https://9e55-186-40-53-37.ngrok-free.app/guardar_qr'

# -----------------------------------------------
# RUTA RAÍZ
# -----------------------------------------------
@app.route('/')
def index():
    return "Servidor Flask en funcionamiento"

# -----------------------------------------------
# RUTA PARA CREAR LA PREFERENCIA DE PAGO
# -----------------------------------------------
@app.route('/crear_pago', methods=['POST'])
def crear_pago():
    try:
        data_request = request.get_json()
        pedido_id = data_request.get('pedido_id')
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
                "success": "https://mikelsouth.github.io/web_pi1/pago_exitoso",
                "failure": "https://mikelsouth.github.io/web_pi1/pago_fallido",
                "pending": "https://mikelsouth.github.io/web_pi1/pago_pendiente"
            },
            
            "auto_return": "approved",
            "external_reference": str(pedido_id)
        }

        preference_response = sdk.preference().create(preference_data)
        return jsonify({"preference_id": preference_response["response"]["id"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------
# RUTA PARA RECIBIR AVISOS DE PAGO (WEBHOOK)
# -----------------------------------------------
@app.route('/mercadopago-webhook', methods=['POST'])
def mercadopago_webhook():
    try:
        data = request.get_json()
        if data.get("type") == "payment":
            payment_id = data["data"]["id"]
            
            payment_info = sdk.payment().get(payment_id)
            payment = payment_info["response"]

            if payment["status"] == "approved":
                pedido_id = payment["external_reference"]
                print(f"Pago aprobado para pedido_id: {pedido_id}. Generando QR...")

                expiracion = 600
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
                    }, timeout=10)
                    print(f"QR para pedido_id: {pedido_id} enviado a la Raspberry Pi.")
                except Exception as e:
                    print(f"Error al enviar QR a la Raspberry Pi: {e}")

    except Exception as e:
        print(f"Error en webhook: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"}), 200

# -----------------------------------------------
# INICIAR EL SERVIDOR
# -----------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)








