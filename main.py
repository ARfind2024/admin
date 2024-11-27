from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import os
from functools import wraps
from datetime import datetime


# Importar configuraciones
from auth_config import pyrebase_auth, config  # Usamos el config ajustado en auth_config.py
from api_client import APIClient

# Cargar variables de entorno
load_dotenv()

# Inicializar Firebase Admin SDK con variables de entorno
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT"),
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT"),
    })
    firebase_admin.initialize_app(cred)

# Inicializar cliente Firestore
db = firestore.client()

# Configurar API Client
def get_authorization_headers():
    id_token = session.get("idToken")
    return {"Authorization": f"Bearer {id_token}"} if id_token else {}

api_client = APIClient(base_url="https://arfindfranco-t22ijacwda-uc.a.run.app")

# Configurar Flask
app = Flask(__name__)
app.secret_key = 'arfind'



# LOGIN
@app.route('/', methods=['GET', 'POST'])
def handle_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            # Autenticación con Pyrebase
            user = pyrebase_auth.sign_in_with_email_and_password(username, password)
            id_token = user['idToken']
            print(f"ID Token generado: {id_token}")

            # Consultar Firestore para obtener datos adicionales
            empleados_ref = db.collection('empleados')
            query = empleados_ref.where('email', '==', username).stream()

            empleado_data = None
            for doc in query:
                empleado_data = doc.to_dict()
                break

            if empleado_data:
                session['nombreEmpleado'] = empleado_data['nombre']
                session['is_admin'] = empleado_data['is_admin']
                session['idToken'] = id_token

                return jsonify({"message": "Inicio de sesión exitoso", "idToken": id_token}), 200
            else:
                return jsonify({"message": "Empleado no encontrado en Firestore"}), 404

        except Exception as e:
            print(f"Error durante el inicio de sesión: {str(e)}")
            return jsonify({"message": "Error durante el inicio de sesión. Intente nuevamente."}), 401

    return render_template('login.html')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'idToken' not in session:
            return redirect(url_for('handle_login'))

        return f(*args, **kwargs)

    return decorated_function


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('handle_login'))


# DASHBOARD para Administradores
@app.route('/dashboard')
@login_required
def dashboard():
    if 'nombreEmpleado' not in session:
        return redirect(url_for('handle_login'))

    if not session.get('is_admin'):
        return redirect(url_for('dashboard2'))

    # Consultar datos desde Firestore
    pedidos_ref = db.collection('pedidos')
    dispositivos_ref = db.collection('dispositivos')
    planes_ref = db.collection('planes')
    empleados_ref = db.collection('empleados')

    try:
        # Datos específicos para administradores
        total_dispositivos = len(list(dispositivos_ref.stream()))
        total_planes = len(list(planes_ref.stream()))
        total_empleados = len(list(empleados_ref.stream()))
        total_admins = len(list(empleados_ref.where('is_admin', '==', True).stream()))
        pedidos_entregados = len(list(pedidos_ref.where('status', '==', 'Entregado').stream()))
        pedidos_no_entregados = len(list(pedidos_ref.where('status', '==', 'No Entregado').stream()))

        return render_template(
            'index.html',
            total_dispositivos=total_dispositivos,
            total_planes=total_planes,
            total_empleados=total_empleados,
            total_admins=total_admins,
            pedidos_entregados=pedidos_entregados,
            pedidos_no_entregados=pedidos_no_entregados
        )
    except Exception as e:
        print(f"Error al consultar datos: {e}")
        return "Error al cargar el dashboard", 500


# DASHBOARD para No Administradores
@app.route('/dashboard2')
def dashboard2():
    if 'nombreEmpleado' not in session:
        return redirect(url_for('handle_login'))

    if session.get('is_admin'):
        return redirect(url_for('dashboard'))

    # Consultar datos desde Firestore
    pedidos_ref = db.collection('pedidos')

    try:
        # Datos específicos para no administradores
        total_pedidos = len(list(pedidos_ref.stream()))
        pedidos_entregados = len(list(pedidos_ref.where('status', '==', 'Entregado').stream()))
        pedidos_no_entregados = len(list(pedidos_ref.where('status', '==', 'No Entregado').stream()))

        return render_template(
            'base.html',
            pedidos_totales=total_pedidos,
            pedidos_entregados=pedidos_entregados,
            pedidos_no_entregados=pedidos_no_entregados
        )
    except Exception as e:
        print(f"Error al consultar datos: {e}")
        return "Error al cargar el dashboard", 500


# RUTA PARA MOSTRAR EMPLEADOS
@app.route('/empleados', methods=['GET'])
@login_required
def empleados():
    try:
        # Solicitar datos desde el endpoint de la API
        response = api_client.get("empleados/getEmpleados")

        # Verificar si la respuesta es válida
        if response:
            # Extraer la lista de empleados del campo `data`
            empleados = response.get("data", [])
            return render_template('tb-empleados.html', empleados=empleados)
        else:
            return jsonify({"message": "Error al obtener empleados"}), 500
    except Exception as e:
        print(f"Error inesperado en empleados: {e}")
        return jsonify({"message": "Error interno del servidor"}), 500

# RUTA PARA AGREGAR EMPLEADO
@app.route('/empleados/agregar', methods=['GET', 'POST'])
@login_required
def agregar_empleado():
    error_message = None
    if request.method == 'POST':
        # Captura los datos enviados desde el formulario
        nombre = request.form.get('nombre')
        email = request.form.get('correo')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin')  # 'true' o 'false' como string

        # Imprime los datos para depuración
        print(f"Datos recibidos: Nombre={nombre}, Email={email}, Password={password}, is_admin={is_admin}")

        # Validar datos
        if not nombre or not email or not password or not is_admin:
            error_message = "Todos los campos son obligatorios."
            return render_template('agregar-empleado.html', error_message=error_message)

        if len(password) < 6:
            error_message = "La contraseña debe tener al menos 6 caracteres."
            return render_template('agregar-empleado.html', error_message=error_message)

        try:
            # Convertir is_admin a booleano
            is_admin = is_admin.lower() == 'true'

            # Llamar a la API para crear el empleado
            payload = {
                'nombre': nombre,
                'email': email,
                'password': password,
                'is_admin': is_admin
            }
            print(f"Payload enviado a la API: {payload}")  # Depuración

            response = api_client.post('empleados/createEmpleado', json=payload)
            if response:
                return redirect(url_for('empleados'))
            else:
                error_message = "Error al agregar el empleado."
        except Exception as e:
            print(f"Error al agregar empleado: {e}")
            error_message = "Ocurrió un error al procesar la solicitud."

    return render_template('agregar-empleado.html', error_message=error_message)


# RUTA PARA MODIFICAR EMPLEADO
@app.route('/empleados/editar/<string:id_empleado>', methods=['GET', 'POST'])
@login_required
def modificar_empleado(id_empleado):
    error_message = None

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('correo')
        is_admin = request.form.get('is_admin')  # 'true' o 'false' como string
        password = request.form.get('password')

        try:
            # Convertir is_admin a booleano
            is_admin = is_admin.lower() == 'true'

            # Crear el payload para enviar a la API
            payload = {
                'id': id_empleado,
                'nombre': nombre,
                'email': email,
                'is_admin': is_admin
            }

            # Añadir la contraseña al payload solo si está presente
            if password:
                if len(password) < 6:
                    error_message = "La contraseña debe tener al menos 6 caracteres."
                    return render_template('editar-empleado.html', error_message=error_message)
                payload['password'] = password

            # Imprimir el payload para depuración
            print(f"Payload enviado a la API para editar: {payload}")

            # Llamar a la API para actualizar el empleado
            response = api_client.put('empleados/updateEmpleado', json=payload)

            if response:
                return redirect(url_for('empleados'))
            else:
                error_message = response.get('message', 'Error desconocido al editar empleado.')

        except Exception as e:
            print(f"Error al editar empleado: {e}")
            return "Error al procesar la solicitud", 500

    try:
        # Obtener todos los empleados desde la API
        print("Obteniendo todos los empleados para buscar por ID...")
        response = api_client.get('empleados/getEmpleados')

        # Buscar el empleado por ID
        if response and 'data' in response:
            empleados = response['data']
            empleado_data = next((emp for emp in empleados if emp['id'] == id_empleado), None)

            if empleado_data:
                print(f"Datos obtenidos del empleado: {empleado_data}")
                return render_template('editar-empleado.html', empleado=empleado_data, error_message=error_message)
            else:
                return f"No se encontró un empleado con ID: {id_empleado}", 404
        else:
            return "Error al obtener empleados desde la API", 500

    except Exception as e:
        print(f"Error al cargar datos del empleado: {e}")
        return "Error interno al cargar los datos del empleado", 500




# RUTA PARA ELIMINAR EMPLEADO
@app.route('/empleados/eliminar/<string:id_empleado>', methods=['POST'])
@login_required
def eliminar_empleado(id_empleado):
    try:
        # Crear el payload con el ID del empleado
        payload = {'id': id_empleado}
        print(f"Payload enviado a la API para eliminar: {payload}")  # Depuración

        # Llamar a la API para eliminar el empleado
        response = api_client.delete('empleados/deleteEmpleado', json=payload)

        # Verificar si la respuesta es válida
        if response and response.get('message') == 'Empleado eliminado con éxito':
            print("Empleado eliminado correctamente.")
            return redirect(url_for('empleados', mensaje="Empleado eliminado con éxito"))
        else:
            error_message = response.get('message', 'Error desconocido al eliminar empleado.')
            print(f"Error al eliminar empleado: {error_message}")
            return redirect(url_for('empleados', mensaje=error_message))

    except Exception as e:
        print(f"Error al eliminar empleado: {e}")
        return redirect(url_for('empleados', mensaje="Error al procesar la solicitud"))

# PEDIDOS
@app.route('/pedidos', methods=['GET'])
@login_required
def pedidos():
    pedidos_list = []
    error_message = None

    try:
        # Solicitar datos desde la API
        response = api_client.get('pedidos')
        if isinstance(response, list):
            pedidos_list = response
        else:
            error_message = "Error inesperado al obtener los pedidos."
    except Exception as e:
        error_message = f"Error al obtener los pedidos: {e}"
        print(error_message)

    return render_template('tb-pedido.html', pedidos=pedidos_list, error_message=error_message)

@app.route('/modificar_pedido/<string:id_pedido>', methods=['GET', 'POST'])
def modificar_pedido(id_pedido):
    pedido_ref = db.collection('pedidos').document(id_pedido)

    if request.method == 'POST':
        # Capturar datos del formulario
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        items = request.form.get('items')
        status = request.form.get('status')
        userId = request.form.get('userId')

        # Imprimir los datos capturados
        print("Datos capturados del formulario:")
        print(f"Titulo: {titulo}, Descripción: {descripcion}, Items: {items}, Status: {status}, UserId: {userId}")

        # Actualizar los datos en Firestore
        pedido_ref.update({
            'titulo': titulo,
            'descripcion': descripcion,
            'items': items,
            'status': status,
            'userId': userId,
        })

        # Redirigir al listado de pedidos
        return redirect(url_for('pedidos'))

    # Obtener el pedido para prellenar el formulario
    pedido = pedido_ref.get()
    if pedido.exists:
        pedido_data = pedido.to_dict()
        pedido_data['createdAt'] = pedido_data['createdAt'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(pedido_data['createdAt'], datetime) else str(pedido_data['createdAt'])
        return render_template('editar-pedido.html', pedido=pedido_data, id_pedido=id_pedido)
    else:
        return "Pedido no encontrado", 404

@app.route('/eliminar_pedido/<string:id_pedido>', methods=['POST'])
def eliminar_pedido(id_pedido):
    pedido_ref = db.collection('pedidos').document(id_pedido)

    try:
        pedido_ref.delete()
        print(f"Pedido {id_pedido} eliminado con éxito.")
        return redirect(url_for('pedidos'))
    except Exception as e:
        print(f"Error al eliminar el pedido {id_pedido}: {e}")
        return "Error al eliminar el pedido", 500

# PRODUCTOS
@app.route('/productos', methods=['GET'])
@login_required
def productos():
    error_message = None
    productos = []

    try:
        # Llama a la API para obtener todos los productos
        response = api_client.get('productos/productos')
        if isinstance(response, list):  # La API devuelve una lista directamente
            productos = response
        else:
            error_message = "Error inesperado al obtener los productos."
    except Exception as e:
        error_message = f"Error al obtener los productos: {e}"
        print(error_message)

    return render_template('tb-productos.html', productos=productos, error_message=error_message)

@app.route('/agregar_producto', methods=['GET', 'POST'])
@login_required
def agregar_producto():
    error_message = None
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        tiny_descripcion = request.form.get('tinyDescripcion')

        if not (titulo and descripcion and precio):
            error_message = "Todos los campos obligatorios deben completarse."
        else:
            payload = {
                'titulo': titulo,
                'descripcion': descripcion,
                'precio': float(precio),
                'imagen': imagen,
                'tiny_descripcion': tiny_descripcion,
            }

            try:
                response = api_client.post('productos', json=payload)
                if response and response.get('message') == 'Producto agregado con éxito':
                    return redirect(url_for('productos'))
                else:
                    error_message = response.get('message', 'Error al agregar el producto.')
            except Exception as e:
                error_message = f"Error al agregar el producto: {e}"
                print(error_message)

    return render_template('agregar-producto.html', error_message=error_message)

@app.route('/modificar_producto/<string:id_producto>', methods=['GET', 'POST'])
@login_required
def modificar_producto(id_producto):
    error_message = None
    producto = {}

    if request.method == 'POST':
        # Capturar los datos enviados desde el formulario
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        tiny_descripcion = request.form.get('tinyDescripcion')

        # Crear el diccionario con los campos a actualizar
        updates = {
            'titulo': titulo,
            'descripcion': descripcion,
            'precio': float(precio) if precio else None,
            'imagen': imagen,
            'tiny_descripcion': tiny_descripcion,
        }

        # Enviar la solicitud PATCH a la API
        try:
            response = api_client.patch(f'productos/productos/{id_producto}', json=updates)
            if response and response.get('message') == 'Producto actualizado con éxito':
                return redirect(url_for('productos'))
            else:
                error_message = response.get('message', 'Error al actualizar el producto.')
        except Exception as e:
            error_message = f"Error al actualizar el producto: {e}"
            print(error_message)

    # Obtener los datos del producto desde la API
    try:
        response = api_client.get(f'productos/productos/{id_producto}')
        if response:
            producto = response
        else:
            error_message = "Error al cargar los datos del producto."
    except Exception as e:
        error_message = f"Error al cargar los datos del producto: {e}"
        print(error_message)

    return render_template('editar-producto.html', producto=producto, error_message=error_message)


@app.route('/eliminar_producto/<string:id_producto>', methods=['POST'])
@login_required
def eliminar_producto(id_producto):
    try:
        response = api_client.delete(f'productos/{id_producto}')
        if response and response.get('message') == 'Producto eliminado con éxito':
            return redirect(url_for('productos'))
        else:
            error_message = response.get('message', 'Error al eliminar el producto.')
            print(error_message)
            return redirect(url_for('productos', mensaje=error_message))
    except Exception as e:
        print(f"Error al eliminar el producto: {e}")
        return redirect(url_for('productos', mensaje="Error al procesar la solicitud"))

# DISPOSITIVOS
@app.route('/dispositivos', methods=['GET'])
@login_required
def dispositivos():
    error_message = None
    dispositivos = []

    try:
        # Llama a la API para obtener dispositivos
        response = api_client.get('dispositivos/getAllDispositivos')

        # Verifica si la respuesta es una lista directamente
        if isinstance(response, list):
            dispositivos = response
        else:
            error_message = "La API devolvió una respuesta inesperada."
    except Exception as e:
        error_message = f"Error al obtener dispositivos: {str(e)}"

    # Renderiza el template con los datos
    return render_template('tb-dispositivo.html', dispositivos=dispositivos, error_message=error_message)


@app.route('/agregar_dispositivo', methods=['GET', 'POST'])
@login_required
def agregar_dispositivo():
    error_message = None

    if request.method == 'POST':
        numero_telefonico = request.form.get('numero_telefonico')
        tipo_producto = request.form.get('tipo_producto')

        if not numero_telefonico or not tipo_producto:
            error_message = "Todos los campos son obligatorios."
        else:
            payload = {
                'numero_telefonico': numero_telefonico,
                'tipo_producto': tipo_producto
            }

            try:
                response = api_client.post('dispositivos/createDispositivo', json=payload)
                if response and response.get('message') == 'Dispositivo creado exitosamente':
                    return redirect(url_for('dispositivos'))
                else:
                    error_message = response.get('message', 'Error al agregar el dispositivo.')
            except Exception as e:
                error_message = f"Error al agregar el dispositivo: {str(e)}"

    # Obtener productos para el formulario
    productos_query = db.collection('productos').stream()
    productos = [{'id': doc.id, 'titulo': doc.to_dict().get('titulo')} for doc in productos_query]

    return render_template('agregar-dispositivo.html', productos=productos, error_message=error_message)


@app.route('/modificar_dispositivo/<string:id_dispositivo>', methods=['GET', 'POST'])
@login_required
def modificar_dispositivo(id_dispositivo):
    error_message = None
    dispositivo = {}

    if request.method == 'POST':
        numero_telefonico = request.form.get('numero_telefonico')
        plan_id = request.form.get('plan_id')

        # Crear un diccionario solo con los campos modificados
        updated_data = {}
        if numero_telefonico:
            updated_data['numero_telefonico'] = numero_telefonico
        if plan_id and plan_id != "N/A":
            updated_data['plan_id'] = plan_id

        # Validar que al menos un campo se actualice
        if not updated_data:
            error_message = "No se detectaron cambios para actualizar."
        else:
            payload = {
                'deviceId': id_dispositivo,
                'updatedData': updated_data
            }

            try:
                response = api_client.put('dispositivos/updateDispositivo', json=payload)
                if response and response.get('message') == 'Dispositivo actualizado exitosamente':
                    # Redirigir a la lista de dispositivos
                    return redirect(url_for('dispositivos'))
                else:
                    error_message = response.get('message', 'Error al actualizar el dispositivo.')
            except Exception as e:
                error_message = f"Error al actualizar el dispositivo: {str(e)}"

    # Si no es POST, obtener datos del dispositivo
    try:
        response = api_client.get('dispositivos/getAllDispositivos')
        if response:
            dispositivos = response
            dispositivo = next((d for d in dispositivos if d['id'] == id_dispositivo), None)

            # Manejar timestamps
            if dispositivo:
                if '_seconds' in dispositivo.get('fecha_creacion', {}):
                    dispositivo['fecha_creacion'] = datetime.fromtimestamp(
                        dispositivo['fecha_creacion']['_seconds']
                    ).strftime('%Y-%m-%d %H:%M:%S')
                if '_seconds' in dispositivo.get('ult_actualizacion', {}):
                    dispositivo['ult_actualizacion'] = datetime.fromtimestamp(
                        dispositivo['ult_actualizacion']['_seconds']
                    ).strftime('%Y-%m-%d %H:%M:%S')
            else:
                error_message = "Dispositivo no encontrado."
        else:
            error_message = "Error al obtener los dispositivos."
    except Exception as e:
        error_message = f"Error al cargar los datos del dispositivo: {str(e)}"

    return render_template('editar-dispositivo.html', dispositivo=dispositivo, error_message=error_message)







@app.route('/eliminar_dispositivo/<string:id_dispositivo>', methods=['POST'])
@login_required
def eliminar_dispositivo(id_dispositivo):
    try:
        # Crear el payload con el ID del dispositivo
        payload = {'deviceId': id_dispositivo}
        print(f"Payload enviado a la API para eliminar: {payload}")  # Depuración

        # Llamar a la API para eliminar el dispositivo
        response = api_client.delete('dispositivos/deleteDispositivo', json=payload)

        # Verificar si la respuesta es válida
        if response and response.get('message') == 'Dispositivo eliminado exitosamente':
            print("Dispositivo eliminado correctamente.")
            return redirect(url_for('dispositivos'))
        else:
            error_message = response.get('message', 'Error al eliminar el dispositivo.')
            print(f"Error al eliminar dispositivo: {error_message}")
            return redirect(url_for('dispositivos', mensaje=error_message))
    except Exception as e:
        print(f"Error al eliminar dispositivo: {e}")
        return redirect(url_for('dispositivos', mensaje="Error al procesar la solicitud"))




@app.route('/planes', methods=['GET'])
@login_required
def planes():
    mensaje = request.args.get('mensaje', None)
    try:
        response = api_client.get('planes/getPlanes')
        planes = response.get('data', []) if response else []
        return render_template('tb-planes.html', planes=planes, mensaje=mensaje)
    except Exception as e:
        print(f"Error al obtener planes: {e}")
        return render_template('tb-planes.html', planes=[], mensaje="Error al obtener los planes.")

@app.route('/planes/agregar', methods=['GET', 'POST'])
@login_required
def agregar_plan():
    error_message = None
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        descripcion = request.form.get('descripcion')
        refresco = request.form.get('refresco')
        cantidad_compartidos = request.form.get('cantidad_compartidos')
        imagen = request.form.get('imagen')

        # Validar que todos los campos sean obligatorios
        if not (nombre and precio and descripcion and refresco and cantidad_compartidos and imagen):
            error_message = "Todos los campos son obligatorios."
            return render_template('agregar-planes.html', error_message=error_message)

        try:
            # Convertir los datos a los tipos necesarios
            precio = float(precio)
            refresco = int(refresco)
            cantidad_compartidos = int(cantidad_compartidos)

            # Crear el payload para la API
            payload = {
                'nombre': nombre,
                'precio': precio,
                'descripcion': descripcion,
                'refresco': refresco,
                'cantidad_compartidos': cantidad_compartidos,
                'imagen': imagen
            }

            # Llamar a la API para crear el plan
            response = api_client.post('planes/createPlan', json=payload)

            if response and response.get('message') == 'Plan creado con éxito':
                return redirect(url_for('planes', mensaje="Plan agregado con éxito"))
            else:
                error_message = response.get('message', 'Error desconocido al agregar plan.')
        except Exception as e:
            print(f"Error al agregar plan: {e}")
            error_message = "Error al procesar la solicitud."

    return render_template('agregar-planes.html', error_message=error_message)



@app.route('/planes/editar/<id_plan>', methods=['GET', 'POST'])
@login_required
def modificar_plan(id_plan):
    error_message = None
    plan = {}

    try:
        # Llama al endpoint que obtiene todos los planes
        response = api_client.get('planes/getPlanes')
        if response and 'data' in response:
            # Filtra el plan por ID
            planes = response['data']
            plan = next((p for p in planes if p['id'] == id_plan), None)
            if not plan:
                error_message = "El plan no existe o no se pudo cargar."
        else:
            error_message = response.get('message', 'Error al obtener los planes.')
    except Exception as e:
        print(f"Error al cargar datos del plan: {e}")
        error_message = "Error al cargar datos del plan."

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = float(request.form.get('precio', 0))
        descripcion = request.form.get('descripcion')
        refresco = int(request.form.get('refresco', 0))
        cantidad_compartidos = int(request.form.get('cantidad_compartidos', 0))
        imagen = request.form.get('imagen')

        if not all([nombre, precio, descripcion, refresco, cantidad_compartidos, imagen]):
            error_message = "Todos los campos son obligatorios."
        else:
            try:
                payload = {
                    "id": id_plan,
                    "nombre": nombre,
                    "precio": precio,
                    "descripcion": descripcion,
                    "refresco": refresco,
                    "cantidad_compartidos": cantidad_compartidos,
                    "imagen": imagen,
                }
                update_response = api_client.put('planes/updatePlan', json=payload)
                if update_response.get('message') == 'Plan actualizado con éxito':
                    return redirect(url_for('planes'))
                else:
                    error_message = update_response.get('message', 'Error al actualizar el plan.')
            except Exception as e:
                print(f"Error al actualizar el plan: {e}")
                error_message = "Error al actualizar el plan."

    return render_template('editar-planes.html', plan=plan, error_message=error_message)




@app.route('/planes/eliminar/<string:id_plan>', methods=['POST'])
@login_required
def eliminar_plan(id_plan):
    try:
        # Crear el payload para eliminar el plan
        payload = {'id': id_plan}

        # Llamar a la API para eliminar el plan
        response = api_client.delete('planes/deletePlan', json=payload)

        if response and response.get('message') == 'Plan eliminado con éxito':
            return redirect(url_for('planes', mensaje="Plan eliminado con éxito"))
        else:
            error_message = response.get('message', 'Error desconocido al eliminar el plan.')
            print(f"Error al eliminar plan: {error_message}")
            return redirect(url_for('planes', mensaje=error_message))
    except Exception as e:
        print(f"Error al eliminar plan: {e}")
        return redirect(url_for('planes', mensaje="Error al procesar la solicitud"))
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(value):
    try:
        # Convertir segundos a un objeto datetime
        return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return "N/A"

if __name__ == '__main__':
    app.run(debug=True)
