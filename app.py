# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests
import mercadopago
import os


# ==============================================================================
# 2. CONFIGURACIÓN INICIAL
# ==============================================================================

# Lee el Access Token desde las Variables de Entorno de Render
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
if not MP_ACCESS_TOKEN:
    raise ValueError("La variable de entorno MP_ACCESS_TOKEN no está configurada.")
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# URL del servidor de la Raspberry Pi (asegúrate de que sea la correcta)
RASPBERRY_PI_URL = 'https://693d-191-126-172-169.ngrok-free.app/guardar_qr'

# --- Catálogo de Productos (Formato Ordenado) ---
CATALOGO_PRODUCTOS = {
    1:  {"nombre": "Coca Cola",         "precio": 1000},
    2:  {"nombre": "Papas Fritas",      "precio": 800},
    3:  {"nombre": "Galletas",          "precio": 600},
    4:  {"nombre": "Chocolates",        "precio": 1200},
    5:  {"nombre": "Jugos",             "precio": 900},
    6:  {"nombre": "Agua",              "precio": 700},
    7:  {"nombre": "Snacks",            "precio": 850},
    8:  {"nombre": "Café",              "precio": 1500},
    9:  {"nombre": "Té",                "precio": 1300},
    10: {"nombre": "Energizantes",      "precio": 1800},
    11: {"nombre": "Refrescos",         "precio": 950},
    12: {"nombre": "Leche",             "precio": 800},
    13: {"nombre": "Frutos Secos",      "precio": 2000},
    14: {"nombre": "Galletas Saladas",    "precio": 650},
    15: {"nombre": "Dulces",            "precio": 500}
}


# ==============================================================================
# 3. ALMACÉN TEMPORAL DE QRs
# ==============================================================================

# Diccionario en memoria para guardar temporalmente los QR generados por los webhooks.
# La llave será el 'payment_id' y el valor será la imagen del QR en base64.
QRs_GENERADOS = {}


# ==============================================================================
# 4. INICIALIZACIÓN DE LA APLICACIÓN FLASK
# ==============================================================================
app = Flask(__name__)
CORS(app)


# ==============================================================================
# 5. DEFINICIÓN DE RUTAS (ENDPOINTS)
# ==============================================================================

# ------------------------------------------------------------------------------
# FUNCIÓN: index
# RUTA: /
# PROPÓSITO: Es la ruta raíz. Sirve para verificar que el servidor está activo y 
#            es la que usa el "Health Check" de Render para mantenerlo despierto.
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    return "Servidor Flask en funcionamiento"

# ------------------------------------------------------------------------------
# FUNCIÓN: crear_pago
# RUTA: /crear_pago
# PROPÓSITO: Iniciar el proceso de cobro.
# QUIÉN LA LLAMA: La página web (frontend) cuando el cliente selecciona un producto 
#                y hace clic en "Pagar".
# QUÉ HACE: Recibe el ID del producto, busca su precio, y le pide a Mercado Pago 
#           que cree una "Preferencia de Pago".
# QUÉ DEVUELVE: Le devuelve a la página web un 'preference_id', que es el ID 
#               de la sesión de pago.
# ------------------------------------------------------------------------------
@app.route('/crear_pago', methods=['POST'])
def crear_pago():
    try:
        data_request = request.get_json()
        pedido_id = data_request.get('pedido_id')
        producto = CATALOGO_PRODUCTOS.get(int(pedido_id))
        if not producto: return jsonify({"error": "Producto no encontrado"}), 404
        
        preference_data = {
            "items": [{"title": producto["nombre"], "quantity": 1, "unit_price": producto["precio"]}],
            "back_urls": { "success": "https://mikelsouth.github.io/web_pi1/pago_exitoso.html" },
            "auto_return": "approved", "external_reference": str(pedido_id)
        }
        preference_response = sdk.preference().create(preference_data)
        return jsonify({"preference_id": preference_response["response"]["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# FUNCIÓN: mercadopago_webhook
# RUTA: /mercadopago-webhook
# PROPÓSITO: Recibir la confirmación de que un pago fue aprobado.
# QUIÉN LA LLAMA: El servidor de Mercado Pago, de forma automática y secreta,
#                después de que un cliente completa un pago.
# QUÉ HACE: Confirma que el pago está "aprobado", genera la información y la 
#           imagen del QR, la envía a la Raspberry Pi, y guarda la imagen en 
#           el almacén temporal.
# QUÉ DEVUELVE: Le devuelve un '200 OK' a Mercado Pago para decir "aviso recibido".
# ------------------------------------------------------------------------------
@app.route('/mercadopago-webhook', methods=['POST'])
def mercadopago_webhook():
    try:
        data = request.get_json()
        if data and data.get("type") == "payment":
            payment_id = data.get("data", {}).get("id")
            if not payment_id: return jsonify({"status": "ok"}), 200

            payment_info = sdk.payment().get(payment_id)
            payment = payment_info["response"]

            if payment.get("status") == "approved":
                pedido_id = payment.get("external_reference")
                expiracion = 600
                qr_content = f"{pedido_id},{expiracion}"
                
                qr = qrcode.make(qr_content)
                buffer = BytesIO()
                qr.save(buffer)
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

                try:
                    requests.post(RASPBERRY_PI_URL, json={'pedido_id': pedido_id, 'expiracion': time.time() + expiracion, 'qr_texto': qr_content}, timeout=10)
                    print(f"QR para pedido_id: {pedido_id} enviado a la Raspberry Pi.")
                except Exception as e:
                    print(f"Error al enviar QR a la Raspberry Pi: {e}")

                QRs_GENERADOS[str(payment_id)] = img_base64
                print(f"QR para payment_id: {payment_id} guardado en memoria.")

    except Exception as e:
        print(f"!!! ERROR INESPERADO EN EL WEBHOOK: {e}")
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 200

# ------------------------------------------------------------------------------
# FUNCIÓN: get_qr
# RUTA: /get-qr/<payment_id>
# PROPÓSITO: Entregar la imagen del QR al cliente que ya pagó.
# QUIÉN LA LLAMA: El JavaScript de la página 'pago_exitoso.html'.
# QUÉ HACE: Recibe un ID de pago, lo busca en el almacén temporal, y si lo 
#           encuentra, devuelve la imagen del QR.
# QUÉ DEVUELVE: Un JSON con la imagen del QR o un estado de "pendiente".
# ------------------------------------------------------------------------------
@app.route('/get-qr/<payment_id>')
def get_qr(payment_id):
    qr_image = QRs_GENERADOS.get(str(payment_id))
    if qr_image:
        return jsonify({"status": "found", "qr_base64": qr_image})
    else:
        return jsonify({"status": "pending"}), 202


# ==============================================================================
# 6. INICIO DEL SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
