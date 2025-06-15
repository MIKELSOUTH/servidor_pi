from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests
import mercadopago
import os # <-- SE AGREGA LA LIBRERÍA 'os' PARA LEER VARIABLES DE ENTORNO

# --- 1. CONFIGURACIÓN DE MERCADO PAGO ---
# --- MODIFICACIÓN: Ahora lee el Access Token de las variables de entorno de Render ---
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- MEJORA DE SEGURIDAD: AÑADE AQUÍ LA CLAVE SECRETA DE TU WEBHOOK ---
# --- MODIFICACIÓN: Ahora lee el Webhook Secret de las variables de entorno de Render ---
WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET")


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
# RUTA PARA RECIBIR AVISOS DE PAGO (WEBHOOK) - VERSIÓN FINAL MEJORADA
# -----------------------------------------------
@app.route('/mercadopago-webhook', methods=['POST'])
def mercadopago_webhook():
    print("\n--- INICIANDO WEBHOOK ---")
    
    # Verificación de Firma (Seguridad)
    signature = request.headers.get('x-signature')
    data_id = request.args.get('data.id')
    
    if WEBHOOK_SECRET and signature and data_id:
        print("1. Verificando firma del webhook...")
        try:
            sdk.utils().validate_signature(signature, data_id, WEBHOOK_SECRET)
            print("2. ¡Firma validada con éxito!")
        except Exception as e:
            print(f"!!! ERROR DE SEGURIDAD: Firma de webhook inválida. {e}")
            return jsonify({"status": "error", "message": "Invalid signature"}), 400

    try:
        data = request.get_json()
        print(f"3. DATOS RECIBIDOS: {data}")

        if data and data.get("type") == "payment":
            print("4. TIPO DE NOTIFICACIÓN: 'payment'. Correcto.")
            payment_id = data.get("data", {}).get("id")
            if not payment_id:
                print("!!! ERROR: El webhook es de tipo 'payment' pero no contiene un 'id'.")
                return jsonify({"status": "ok"}), 200

            print(f"5. ID DE PAGO EXTRAÍDO: {payment_id}")

            print("6. BUSCANDO INFORMACIÓN DEL PAGO EN MERCADO PAGO...")
            payment_info = sdk.payment().get(payment_id)
            payment = payment_info["response"]
            print(f"7. INFORMACIÓN RECIBIDA. ESTADO: {payment.get('status')}")

            if payment.get("status") == "approved":
                print("8. ¡PAGO APROBADO! Se procede a generar el QR.")
                pedido_id = payment.get("external_reference")
                print(f"9. ID DEL PEDIDO OBTENIDO: {pedido_id}")

                if not pedido_id:
                    print("!!! ERROR FATAL: No se encontró 'external_reference' en el pago.")
                    return jsonify({"status": "error"}), 500

                expiracion = 600
                qr_content = f"{pedido_id},{expiracion}"
                print(f"10. CONTENIDO DEL QR CREADO: '{qr_content}'")
                
                qr = qrcode.make(qr_content)
                buffer = BytesIO()
                qr.save(buffer)
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                print("11. IMAGEN QR CREADA EN MEMORIA.")
                
                print(f"12. ENVIANDO QR A RASPBERRY PI EN URL: {RASPBERRY_PI_URL}")
                try:
                    response_pi = requests.post(RASPBERRY_PI_URL, json={
                        'pedido_id': pedido_id,
                        'expiracion': time.time() + expiracion,
                        'qr_texto': qr_content
                    }, timeout=10)
                    print(f"13. RESPUESTA DE RASPBERRY PI: Código {response_pi.status_code}")
                    if response_pi.status_code != 200:
                        print(f"!!! ERROR: La Raspberry Pi respondió con un error: {response_pi.text}")
                except requests.exceptions.RequestException as e:
                    print(f"!!! ERROR DE CONEXIÓN: No se pudo contactar a la Raspberry Pi: {e}")
            else:
                print(f"8. PAGO NO APROBADO (Estado: {payment.get('status')}). No se genera QR.")
        else:
            print("4. Notificación ignorada (no es de tipo 'payment' o no tiene datos).")

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
