from flask import Flask, jsonify, request
import qrcode
import time
from flask_cors import CORS
import base64
from io import BytesIO
import requests  # Para enviar el QR a la Raspberry Pi

# --- INICIO DE LA MODIFICACIÓN ---

# 1. Importar la librería de Mercado Pago
import mercadopago

# 2. Configurar el SDK con tu Access Token de PRUEBA
#    (¡¡Pega aquí el Access Token que obtuviste de tu Vendedor de Prueba!!)
sdk = mercadopago.SDK("APP_USR-778410764560218-061221-fdda74fc8a02e531d07b634e006cae15-2491526457")

# --- FIN DE LA MODIFICACIÓN ---

app = Flask(__name__)
CORS(app)

# Dirección IP de la Raspberry Pi donde se enviarán los datos del QR
RASPBERRY_PI_URL = 'https://9e55-186-40-53-37.ngrok-free.app/guardar_qr'
# -----------------------------------------------
# *Ruta raíz para verificar que el servidor está activo*
@app.route('/')
def index():
    return "Servidor Flask en funcionamiento"

# -----------------------------------------------
# *Ruta para generar un código QR y enviarlo tanto al cliente como a la Raspberry Pi*
@app.route('/generar_qr', methods=['POST'])
def generar_qr():
    try:
        # *Obtener datos del pedido desde la solicitud POST*
        data = request.get_json()

        if 'pedido_id' not in data or 'expiracion' not in data or 'telefono' not in data:
            return jsonify({'error': 'Faltan parámetros en la solicitud'}), 400

        pedido_id = data['pedido_id']
        expiracion = data['expiracion']
        telefono = data['telefono']

        # *Generar el contenido del QR como texto*
        qr_content = f"{pedido_id},{expiracion}"

        # *Crear la imagen del QR*
        qr = qrcode.make(qr_content)

        # *Convertir la imagen del QR a base64 para enviar al cliente*
        buffer = BytesIO()
        qr.save(buffer)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        # *Enviar los datos del QR a la Raspberry Pi*
        try:
            requests.post(RASPBERRY_PI_URL, json={
                'pedido_id': pedido_id,
                'expiracion': time.time() + expiracion,
                'qr_texto': qr_content
            }, timeout=5)
        except Exception as e:
            print(f"Error al enviar QR a la Raspberry Pi: {e}")

        # *Devolver el QR generado al cliente en formato base64*
        return jsonify({
            'pedido_id': pedido_id,
            'expiracion': time.time() + expiracion,
            'qr_base64': img_base64
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -----------------------------------------------
# *Iniciar el servidor Flask*
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
