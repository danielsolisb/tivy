# CoreApps/appointments/waapi_utils.py
import requests
import json
import logging
from django.conf import settings
import re
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import hashlib # Necesario para SHA256

# Constantes para HKDF (generalmente fijas para WhatsApp media)
# Ajusta si la documentación indica otros valores
APP_INFO_IMAGE = b'WhatsApp Image Keys'
APP_INFO_VIDEO = b'WhatsApp Video Keys'
APP_INFO_AUDIO = b'WhatsApp Audio Keys'
APP_INFO_DOCUMENT = b'WhatsApp Document Keys'

logger = logging.getLogger(__name__)

# --- FUNCIÓN DE FORMATO (Añade '+') ---
def format_phone_number_for_api(phone_number):
    """
    Limpia y formatea un número al formato internacional CON '+'
    requerido por /api/send-message (ej: +5939XXXXXXXX).
    """
    if not phone_number:
        return None
    cleaned_number = re.sub(r'[^\d+]', '', str(phone_number))
    cleaned_number = cleaned_number.split('@')[0]
    if cleaned_number.startswith('+5939') and len(cleaned_number) == 13:
        return cleaned_number # Ya está correcto
    elif cleaned_number.startswith('5939') and len(cleaned_number) == 12:
        return '+' + cleaned_number # Añadir '+'
    elif cleaned_number.startswith('09') and len(cleaned_number) == 10:
        return '+593' + cleaned_number[1:] # Reemplazar '0' con '+593'
    elif cleaned_number.startswith('9') and len(cleaned_number) == 9:
         return '+593' + cleaned_number # Añadir '+593'
    else: # Intenta añadir '+' si parece internacional pero falta
         if len(cleaned_number) == 12 and cleaned_number.startswith('593'):
             return '+' + cleaned_number
    logger.warning(f"Número '{phone_number}' no pudo ser formateado a +593...")
    return None
# --- FIN FUNCIÓN DE FORMATO ---


# --- FUNCIÓN DE ENVÍO DEFINITIVA (CORREGIDA CON CURL) ---
def send_whatsapp_message(phone_number, message):
    """
    Envía un mensaje de texto vía /api/send-message de WASenderAPI.
    Retorna (True, response_data) o (False, error_message).
    """
    if not settings.WASENDERAPI_API_KEY:
        error_msg = "Error: WASENDERAPI_API_KEY no configurada."
        logger.error(error_msg)
        return False, error_msg

    formatted_phone_with_plus = format_phone_number_for_api(phone_number)
    if not formatted_phone_with_plus:
        error_msg = f"Error al formatear número: {phone_number} a +593..."
        logger.error(error_msg)
        return False, error_msg

    # --- ¡URL CORREGIDA SEGÚN CURL EXITOSO! ---
    api_url = "https://wasenderapi.com/api/send-message" # URL directa que funcionó

    headers = {
        'Authorization': f'Bearer {settings.WASENDERAPI_API_KEY}',
        'Content-Type': 'application/json',
    }
    # --- ¡PAYLOAD CORREGIDO SEGÚN CURL EXITOSO! ---
    payload = {
        'to': formatted_phone_with_plus, # Clave 'to' y número con '+'
        'text': message,              # Clave 'text'
    }

    logger.info(f"Intentando enviar mensaje a {formatted_phone_with_plus} vía WASenderAPI ({api_url})...")
    # logger.debug(f"Payload: {json.dumps(payload)}") # Descomentar si necesitas depurar

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=20)
        response.raise_for_status() # Lanza excepción para 4xx/5xx
        response_data = response.json()

        # Verificar éxito basado en la respuesta del curl ("success":true)
        if response.status_code in [200, 201] and response_data.get('success') is True:
            logger.info(f"Mensaje enviado exitosamente a {formatted_phone_with_plus}. Respuesta API: {response_data}")
            return True, response_data
        else:
            error_msg = f"Respuesta API no exitosa (Status {response.status_code}, Success={response_data.get('success')}): {response.text}"
            logger.error(error_msg)
            return False, response_data.get('message', error_msg)

    except requests.exceptions.HTTPError as http_err:
        error_body = http_err.response.text
        error_msg = f"Error HTTP {http_err.response.status_code} ({api_url}): {error_body}"
        logger.error(error_msg)
        try:
            error_details = http_err.response.json()
            return False, error_details.get('message', error_body)
        except json.JSONDecodeError:
             return False, error_body
    except requests.exceptions.RequestException as req_err: # Captura ConnectionError, Timeout, etc.
        error_msg = f"Error de red/conexión ({api_url}): {req_err}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error inesperado en send_whatsapp_message: {e}"
        logger.exception(error_msg)
        return False, error_msg

def hkdf_expand(key, info, length=32):
    """Deriva claves usando HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=bytes(32), # Sal de ceros
        info=info,
        backend=default_backend()
    )
    return hkdf.derive(key)

def decrypt_whatsapp_media(media_key_b64, encrypted_data, media_type='image'):
    """
    Desencripta los datos de medios de WhatsApp usando la mediaKey.
    media_type puede ser 'image', 'video', 'audio', 'document'.
    """
    try:
        media_key = base64.b64decode(media_key_b64)
        if len(media_key) != 32 + 32 + 32: # key + mac_key + ref_key (normalmente 32 bytes cada uno)
            logger.error(f"MediaKey tiene longitud inesperada: {len(media_key)} bytes.")
            # Intenta usar solo los primeros 32 bytes si la estructura es diferente
            if len(media_key) >= 32:
                media_key = media_key[:32]
            else:
                raise ValueError("MediaKey inválida para HKDF.")
            # Considera loguear media_key_b64 para depuración si sigue fallando

        # Seleccionar APP_INFO basado en el tipo de medio
        if media_type == 'image':
            app_info = APP_INFO_IMAGE
        elif media_type == 'video':
            app_info = APP_INFO_VIDEO
        elif media_type == 'audio':
            app_info = APP_INFO_AUDIO
        elif media_type == 'document':
            app_info = APP_INFO_DOCUMENT
        else:
            # Fallback o tipo genérico si es necesario, consulta la documentación si existe
            logger.warning(f"Tipo de medio desconocido '{media_type}', usando APP_INFO_IMAGE como fallback.")
            app_info = APP_INFO_IMAGE # O define un APP_INFO genérico

        # Derivar claves IV y Cipher Key usando HKDF
        # La documentación de WASender parece usar solo los primeros 32 bytes de la mediaKey para HKDF
        keys = hkdf_expand(media_key[:32], app_info, length=16 + 32) # 16 para IV, 32 para Cipher Key
        iv = keys[:16]
        cipher_key = keys[16:]

        # Separar los datos encriptados y el MAC
        # WhatsApp anexa un MAC de 10 bytes al final
        file_data = encrypted_data[:-10]
        mac_from_message = encrypted_data[-10:]

        # Crear el cifrador AES-CBC
        cipher = Cipher(algorithms.AES(cipher_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Desencriptar los datos
        decrypted_data_padded = decryptor.update(file_data) + decryptor.finalize()

        # Eliminar el padding PKCS7
        # El último byte indica cuántos bytes de padding hay
        padding_length = decrypted_data_padded[-1]
        if padding_length > len(decrypted_data_padded):
             raise ValueError("Padding inválido durante la desencriptación.")
        decrypted_data = decrypted_data_padded[:-padding_length]

        logger.info(f"Desencriptación exitosa para media_type '{media_type}'.")
        return decrypted_data

    except ValueError as ve:
        logger.error(f"Error de valor durante la desencriptación: {ve}")
        return None
    except Exception as e:
        logger.exception(f"Error inesperado durante la desencriptación de medios: {e}")
        return None