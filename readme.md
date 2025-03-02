# Simulación de Contadores de Agua con Vagrant, Python, SQL Server y Flask

El objetivo de esta práctica es simular contadores de agua utilizando máquinas virtuales, Python, CRON, SQL Server y Flask. A continuación, se describen los componentes y su configuración.

![Esquema](/images/1.png)

---

## 1. Enunciado

### Máquinas Virtuales (Vagrant)
- **Propósito**: Implementar un generador de pulsos de agua basado en un código de distribución de agua.
- Cada máquina virtual tendrá una IP única.
- Python instalado para ejecutar el script que genera los datos del contador.
- CRON configurado para ejecutar el script de Python cada 5 minutos.
- No necesitan PostgreSQL o SQL Server instalado. Solo necesitan poder enviar datos a la base de datos.

### Python
- **Propósito**:  Generar pulsos en base a al código de distribución de agua
- El script (`contador.py`) generará datos simulados (por ejemplo, un valor de pulso basado en el tiempo).
- Este script también se encargará de enviar los datos a Flask.

### CRON
- **Propósito**: Ejecutar el script de Python cada 5 minutos.
- Se generará en el Vagrantfile

### SQL Server
- **Propósito**:  Almacenar los datos enviados por Flask
- SSMS debe estar instalado en el host o en un servidor central.

### Flask
- **Propósito**: El servicio en Flask recibe los datos de los contadores (pulsos, IP, ID del cliente y hora) y los almacena en la base de datos.

- Flask debe estar en el host o en un servidor central, no en las máquinas virtuales.
- Crear una API simple para consultar los datos y enviarlos a la BBDD.

---

## 2. Creación de la Base de Datos SQL Server

1. Abrir **SQL Server Management Studio (SSMS)**.
2. Crear una nueva base de datos llamada `contadores`.
3. Crear una nueva tabla llamada `pulsos`:

```sql
USE [contadores]
GO

CREATE TABLE [dbo].[pulsos_vm](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[client_id] [nvarchar](20) NOT NULL,
	[ip] [nvarchar](15) NOT NULL,
	[tiempo] [datetime] NOT NULL,
	[medida] [decimal](10, 2) NOT NULL
)
```

4. Crear un usuario para que las máquinas virtuales puedan enviar datos:
   - **Login name**: `usr_cont`
   - **Password**: `pass123`
   - **Default database**: `contadores`

5. Configurar seguridad y accesos:
   - Botón derecho > Propiedades > Security > Seleccionar **SQL Server and Windows Authentication**.

6. Probar acceso:

```bash
sqlcmd -S 192.168.0.10\SQLEXPRESS -U usr_cont -P pass123 -d contadores -Q "SELECT @@version;"
sqlcmd -S 192.168.0.10\SQLEXPRESS -U usr_cont -P pass123 -d contadores -Q "SELECT * FROM pulsos"
```

---

## 3. Comprobar Conexiones de Host/SQL Server

Realizar pruebas en el host:

```bash
sqlcmd -S 192.168.0.10\SQLEXPRESS -U usr_cont -P pass123 -d contadores
```

Si existen problemas de conexión, seguir los pasos indicados en [este video](https://www.youtube.com/watch?v=G-5mFC-o6m0).

---

## 4. Script de Python para Generar pulsos

El script `contador.py` genera datos simulados y los envía a la base de datos.

```python
import numpy as np
import time  
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
            print("Datos enviados correctamente:", data)
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
```

---

## 5. Previos a la Creación de Máquina Virtual

1. Abrir **Visual Studio Code**.
2. Seleccionar entorno: `Ctrl + Shift + P` > `Python: Select Interpreter`.
3. Generar claves SSH:

```bash
ssh-keygen -t rsa -b 4096 -C "practica_contadorBucle" -f $HOME\.ssh\practica_contadorBucle
```

4. Otorgar permisos:

```bash
chmod 600 ~/.ssh/practica_contadorBucle
```

5. Verificar que se generaron las claves:

```bash
ls ~/.ssh/practica_contadorBucle*
```

6. Comandos para evitar posibles errores (ejecutar en PowerShell):

```bash
ssh-keygen -f "$env:USERPROFILE\.ssh\known_hosts" -R "192.168.88.10"
ssh-keygen -R 192.168.162.10 #IP DE LA MÁQUINA
ssh-keygen -R 127.0.0.1
ssh-keygen -R [127.0.0.1]:2222
```

---

## 6. Crear Máquina Virtual

1. Crear máquina Vagrant:

```bash
vagrant init
```

2. Configurar el `Vagrantfile` para generar un bucle de máquinas:

```ruby
Vagrant.configure("2") do |config|
  (1..3).each do |i|
    config.vm.define "vm#{i}" do |vm_config|
      # Especifica la caja base de Ubuntu
      vm_config.vm.box = "ubuntu/xenial64"

      # Configura una red privada con una IP fija
      vm_config.vm.network "private_network", ip: "192.168.162.#{i + 10}"

      # Configura los recursos de hardware
      vm_config.vm.provider "virtualbox" do |vb|
        vb.memory = "2048"  # 2 GB de memoria
        vb.cpus = 1         # 1 CPU
      end

      # Copia la clave pública generada en el host a la VM
      vm_config.vm.provision "file", source: "C:/Users/mcaro/.ssh/practica_contadorBucle.pub", destination: "/home/vagrant/.ssh/practica_contadorBucle.pub"

      # Configuración inicial del servidor SSH
      vm_config.vm.provision "shell", run: "once" do |s|
        s.inline = <<-SHELL
          # Actualizar e instalar dependencias
          apt-get update || (echo "Error al actualizar paquetes"; exit 1)
          apt-get install -y openssh-server python3 python3-pip cron || (echo "Error al instalar dependencias"; exit 1)
           # Configurar el servidor SSH para aceptar claves públicas
          sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config || (echo "Error al modificar sshd_config"; exit 1)
          sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config || (echo "Error al modificar sshd_config"; exit 1)
          echo "Configuración de SSH actualizada."

          # Crear el directorio .ssh si no existe
          mkdir -p /home/vagrant/.ssh || (echo "Error al crear directorio .ssh"; exit 1)
          chmod 700 /home/vagrant/.ssh || (echo "Error al cambiar permisos de .ssh"; exit 1)
          chown vagrant:vagrant /home/vagrant/.ssh || (echo "Error al cambiar propietario de .ssh"; exit 1)
          echo "Directorio .ssh configurado."

          # Verificar si el archivo de clave pública existe
          if [ ! -f /home/vagrant/.ssh/practica_contadorBucle.pub ]; then
            echo "El archivo de clave pública no existe"
            exit 1
          fi

          # Sobrescribir el contenido de authorized_keys con la clave pública
          cat /home/vagrant/.ssh/practica_contadorBucle.pub > /home/vagrant/.ssh/authorized_keys || (echo "Error al escribir authorized_keys"; exit 1)
          chmod 600 /home/vagrant/.ssh/authorized_keys || (echo "Error al cambiar permisos de authorized_keys"; exit 1)
          chown vagrant:vagrant /home/vagrant/.ssh/authorized_keys || (echo "Error al cambiar propietario de authorized_keys"; exit 1)
          echo "Clave pública configurada."

          # Reiniciar el servidor SSH
          systemctl restart sshd || (echo "Error al reiniciar sshd"; exit 1)

          # Desinstalar pip actual si es necesario
          python3 -m pip uninstall -y pip || echo "No se pudo desinstalar pip, continuando..."
          # Instalar una versión compatible de pip
          curl https://bootstrap.pypa.io/pip/3.5/get-pip.py -o get-pip.py || (echo "Error al descargar get-pip.py"; exit 1)
          python3 get-pip.py "pip==20.3.4" || (echo "Error al instalar pip 20.3.4"; exit 1)

          # Instalar numpy y requests
          pip3 install numpy requests || (echo "Error al instalar numpy o requests"; exit 1)
          echo "Dependencias instaladas correctamente."

          # Configurar el hostname
          echo "Setting hostname to vm#{i}"
          hostnamectl set-hostname vm#{i}
          echo "127.0.0.1 vm#{i}" >> /etc/hosts
          echo "Hostname configurado."
        SHELL
      end

      # Configuración de SSH Y CRON (siempre)
      vm_config.vm.provision "shell", run: "always" do |s|
        s.inline = <<-SHELL

          # Verificar la existencia de contador.py
          if [ ! -f /vagrant/contador/contador.py ]; then
            echo "Error: El archivo /vagrant/contador/contador.py no existe."
            exit 1
          fi

          # Dar permisos a contador.py
          chmod +x /vagrant/contador/contador.py || (echo "Error al dar permisos de ejecución a contador.py"; exit 1)
          echo "Script contador.py configurado."

          # Configurar CRON para ejecutar el script cada 1 minuto
          CRON_JOB="*/5 * * * * /usr/bin/python3 /vagrant/contador/contador.py >> /vagrant/contador.log 2>&1"
          if ! crontab -l | grep -Fxq "$CRON_JOB"; then
            # Configurar CRON para ejecutar el script cada 1 minuto
            (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
            echo "Tarea CRON configurada."
          else
            echo "La tarea CRON ya existe, no se agrega nuevamente."
          fi
        SHELL
      end

      # Evitar prompts de SSH y especificar la clave personalizada
      vm_config.ssh.private_key_path = ["C:/Users/mcaro/.ssh/practica_contadorBucle", "~/.vagrant.d/insecure_private_key"]
      # Evitar prompts de SSH
      vm_config.ssh.insert_key = false
      vm_config.ssh.extra_args = ["-o StrictHostKeyChecking=no", "-o UserKnownHostsFile=/dev/null"]
    end
  end
end

```
---
## 7. Configuración de Flask

1. Instalar Flask y dependencias en Host:

```bash
pip install Flask pyodbc
```
2. Crear archivo `requirements.txt`:
```bash
pip freeze > requirements.txt
```
3. Crear archivo `app.py`:

```python
from flask import Flask, jsonify, request
import pyodbc

app = Flask(__name__)

# Configuración de la conexión a SQL Server
def get_db_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.0.10\\SQLEXPRESS;"  
            "DATABASE=contadores;"  
            "UID=usr_cont;"  # Nombre de usuario
            "PWD=pass123;"  # Contraseña
        )
        print(f"¡Conexión exitosa!")
        return conn
    except:
        print(f"¡Conexión Fallida!")


# Ruta para recibir datos de los generadores de pulsos desde la VM
@app.route('/api/pulsos', methods=['POST'])
def recibir_datos():
    try:
        data = request.json
        medida = data.get("medida")
        ip = data.get("ip")
        client_id = data.get("client_id")
        time = data.get("tiempo")

        if not all([medida, ip, client_id, time]):
            return jsonify({"error": "Faltan datos"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO pulsos_vm (ip, client_id, tiempo, medida) VALUES (?, ?, CONVERT(datetime, ?, 120), ?)"
        cursor.execute(query, (ip,client_id, time, medida))
        
        conn.commit()
        conn.close()

        # Imprime los datos recibidos en la consola del servidor
        print(f"Datos recibidos: medida={medida}, ip={ip}, client_id={client_id}, tiempo={time}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Ruta para obtener todos los datos de la tabla
@app.route('/api/pulsos', methods=['GET'])
def obtener_datos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pulsos_vm")  # Reemplaza con tu tabla
        datos = cursor.fetchall()
        conn.close()

        # Convertir los datos a un formato JSON
        resultado = []
        for fila in datos:
            resultado.append({
                'id': fila[0],
                'ip': fila[1],
                'tiempo': fila[2],
                'medida': fila[3]
            })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ruta para obtener datos por IP
@app.route('/api/pulsos/<ip>', methods=['GET'])
def obtener_datos_por_ip(ip):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pulsos_vm WHERE ip = ?", ip)  # Reemplaza con tu tabla
        datos = cursor.fetchall()
        conn.close()

        # Convertir los datos a un formato JSON
        resultado = []
        for fila in datos:
            resultado.append({
                'id': fila[0],
                'ip': fila[1],
                'tiempo': fila[2],
                'medida': fila[3]
            })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Iniciar la aplicación Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

3. Ejecutar el servidor Flask en el terminal:

```bash
python app.py
```

---

## 8. Probar el Servicio con Postman

1. **Obtener todos los datos**:
   - Método: `GET`
   - URL: `http://localhost:5000/api/pulsos`

2. **Obtener datos por IP**:
   - Método: `GET`
   - URL: `http://localhost:5000/api/pulsos/192.168.162.10`

---

## 9. Acceder a Base de datos:

**Comprobar Pulsos enviados**:

  ![Esquema](/images/2.png)

