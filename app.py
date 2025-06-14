from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests
import mercadopago

# --- 1. CONFIGURACIÓN DE MERCADO PAGO ---
sdk = mercadopago.SDK("APP_USR-778410764560218-061221-fdda74fc8a02e531d07b634e006cae15-2491526457")

# --- 2. CATÁLOGO DE PRODUCTOS ---
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

# URL de tu Raspberry Pi
RASPBERRY_PI_URL = 'https://2f6e-191-125-159-220.ngrok-free.app/guardar_qr'

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
        
        # AJUSTE PARA SOLUCIONAR ERROR 404: Se agrega .html al final de las URLs
        preference_data = {
            "items": [
                {
                    "title": producto["nombre"],
                    "quantity": 1,
                    "unit_price": producto["precio"]
                }
            ],
            "back_urls": {
                "success": "https://mikelsouth.github.io/web_pi1/pago_exitoso.html",
                "failure": "https://mikelsouth.github.io/web_pi1/pago_fallido.html",
                "pending": "https://mikelsouth.github.io/web_pi1/pago_pendiente.html"
            },
            "auto_return": "approved",
            "external_reference": str(pedido_id)
        }

        preference_response = sdk.preference().create(preference_data)
        return jsonify({"preference_id": preference_response["response"]["id"]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------
# RUTA PARA RECIBIR AVISOS DE PAGO (WEBHOOK) CON DIAGNÓSTICO DETALLADO
# -----------------------------------------------
@app.route('/mercadopago-webhook', methods=['POST'])
def mercadopago_webhook():
    print("\n--- INICIANDO WEBHOOK ---")
    try:
        data = request.get_json()
        print(f"1. DATOS RECIBIDOS: {data}")

        if data and data.get("type") == "payment":
            print("2. TIPO DE NOTIFICACIÓN: 'payment'. Correcto.")
            payment_id = data["data"]["id"]
            print(f"3. ID DE PAGO EXTRAÍDO: {payment_id}")

            print("4. BUSCANDO INFORMACIÓN DEL PAGO EN MERCADO PAGO...")
            payment_info = sdk.payment().get(payment_id)
            payment = payment_info["response"]
            print(f"5. INFORMACIÓN RECIBIDA. ESTADO: {payment.get('status')}")

            if payment.get("status") == "approved":
                print("6. ¡PAGO APROBADO! Se procede a generar el QR.")
                pedido_id = payment.get("external_reference")
                print(f"7. ID DEL PEDIDO OBTENIDO: {pedido_id}")

                if not pedido_id:
                    print("!!! ERROR FATAL: No se encontró 'external_reference' en el pago.")
                    return jsonify({"status": "error"}), 500

                expiracion = 600
                qr_content = f"{pedido_id},{expiracion}"
                print(f"8. CONTENIDO DEL QR CREADO: '{qr_content}'")
                
                qr = qrcode.make(qr_content)
                buffer = BytesIO()
                qr.save(buffer)
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                print("9. IMAGEN QR CREADA EN MEMORIA.")
                
                print(f"10. ENVIANDO QR A RASPBERRY PI EN URL: {RASPBERRY_PI_URL}")
                try:
                    response_pi = requests.post(RASPBERRY_PI_URL, json={
                        'pedido_id': pedido_id,
                        'expiracion': time.time() + expiracion,
                        'qr_texto': qr_content
                    }, timeout=10)
                    print(f"11. RESPUESTA DE RASPBERRY PI: Código {response_pi.status_code}")
                    if response_pi.status_code != 200:
                        print(f"!!! ERROR: La Raspberry Pi respondió con un error: {response_pi.text}")
                except requests.exceptions.RequestException as e:
                    print(f"!!! ERROR DE CONEXIÓN: No se pudo contactar a la Raspberry Pi: {e}")
            else:
                print(f"6. PAGO NO APROBADO (Estado: {payment.get('status')}). No se genera QR.")
        else:
            print("2. Notificación ignorada (no es de tipo 'payment').")

    except Exception as e:
        print(f"!!! ERROR INESPERADO EN EL WEBHOOK: {e}")
        return jsonify({"error": str(e)}), 500

    print("--- FIN DEL WEBHOOK ---")
    return jsonify({"status": "ok"}), 200

# -----------------------------------------------
# INICIAR EL SERVIDOR
# -----------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
