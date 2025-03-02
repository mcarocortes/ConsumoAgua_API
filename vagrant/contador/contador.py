import numpy as np
import time  # Módulo time
import requests
import socket
import fcntl
import struct

# Función para obtener la IP de la interfaz de red
def get_ip(ifname):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
    except IOError:
        print("No se pudo obtener la IP de la interfaz.")
        return "0.0.0.0"

# Función gaussiana para modelar los picos de consumo
def gaussian(t, A, mu, sigma):
    return A * np.exp(-((t - mu)**2) / (2 * sigma**2))

# Función para simular el consumo de agua
def simulate_water_consumption():
    # Parámetros del modelo
    t = np.linspace(0, 24, 1440)  # Dividimos el día en minutos (24 horas * 60 minutos)
    current_time = time.localtime()
    hour = current_time.tm_hour + current_time.tm_min / 60  # Hora actual en formato decimal

    # Parámetros para los picos
    B = 0.05  # Consumo basal (litros/minuto)
    n_habitantes = 3  # Número de habitantes

    # Pico matutino
    A1 = 1.0 * n_habitantes
    mu1 = 7.5
    sigma1 = 0.5

    # Pico mediodía
    A2 = 0.8 * n_habitantes
    mu2 = 14.0
    sigma2 = 0.7

    # Pico nocturno
    A3 = 1.2 * n_habitantes
    mu3 = 21.0
    sigma3 = 0.6

    # Calculamos el consumo total
    consumo_matutino = gaussian(hour, A1, mu1, sigma1)
    consumo_mediodia = gaussian(hour, A2, mu2, sigma2)
    consumo_nocturno = gaussian(hour, A3, mu3, sigma3)

    # Consumo total sin ruido
    consumo_total = B + consumo_matutino + consumo_mediodia + consumo_nocturno

    # Añadimos un poco de ruido aleatorio
    ruido = np.random.normal(0, 0.05)
    pulso = max(consumo_total + ruido, 0)  # Evitamos valores negativos

    # Redondeamos el pulso a dos decimales
    pulso = round(pulso, 2)

    return pulso

# Función para enviar datos al servicio Flask
def send_data_to_flask(pulse, ip, client_id):
    url = "http://192.168.0.10:5000/api/pulsos"  # URL del endpoint de Flask
    
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')  # Formatea la fecha y hora actual
    data = {
        "ip": ip,
        "client_id": client_id,
        "tiempo": current_time,  
        "medida": pulse
    }

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("Datos enviados correctamente: ip={}, client_id={}, tiempo={}, medida={}".format(
    data["ip"], data["client_id"], data["tiempo"], data["medida"]))
        else:
            print("Error al enviar datos. Código:", response.status_code)
    except Exception as e:
        print("Error al enviar datos:", str(e))

# Función principal
if __name__ == "__main__":
    interface = 'enp0s8'  # Nombre de la interfaz de red
    ip = get_ip(interface)  # Obtiene la dirección IP de la máquina virtual
    client_id = ip.replace('.', '')  # Genera un ID de cliente basado en la IP

    pulso = simulate_water_consumption()  # Genera un pulso simulado
    send_data_to_flask(pulso, ip, client_id)  # Envía los datos al servicio Flask