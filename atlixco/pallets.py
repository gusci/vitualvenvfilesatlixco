#!/usr/bin/python
# -*- coding: utf-8 -*-
import cStringIO
import os
import re
import socket
import unicodedata

import fitz
import MySQLdb
import openpyxl
import pycurl
import requests
from flask import (  # jsonify,
    Flask,
    Response,
    flash,
    g,
    json,
    redirect,
    render_template,
    request,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash

# ----- INIT Configuration Values ------------------------------------------- #
UrlOB = "https://www.almacenaje.123sourcing.com/openbravo"
urlserver = "http://daslabels.123sourcing.com"
# urlserver='127.0.0.1:9000'
app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
app.secret_key = "why would I tell you my secret key?"

TCP_IP = os.environ.get("IPTEC")
TCP_IP2 = os.environ.get("IPTEC2")
TCP_IPM = os.environ.get("IPTECM")
global_org = os.environ.get("org")
global_alm = os.environ.get("alm")
global_whkey = os.environ.get("whkey")
TCP_PORT = 9100

pdf_directory_path = "/home/pi/todo-api/palletsatlixco/static/pdfs"
xlsx_directory_path = "/home/pi/todo-api/palletsatlixco/static/xlsx"
if os.environ.get("pdf_directory_path"):
    pdf_directory_path = os.environ.get("pdf_directory_path")
if os.environ.get("xlsx_directory_path"):
    xlsx_directory_path = os.environ.get("xlsx_directory_path")

connect_to_printers = True
if os.environ.get("connect_to_printers"):
    connect_to_printers = False

if os.environ.get("URL_LOCAL_DAS"):
    urlserver = os.environ.get("URL_LOCAL_DAS")

_dbConnectionType = "production"
if os.environ.get("PALLETSATLIXCO_DB"):
    PALLETSATLIXCO_DB = os.environ.get("PALLETSATLIXCO_DB")
    _dbConnectionType = "development"
else:
    PALLETSATLIXCO_DB = "terminalpallets"

if os.environ.get("PALLETSATLIXCO_DB_HOST"):
    PALLETSATLIXCO_DB_HOST = os.environ.get("PALLETSATLIXCO_DB_HOST")
else:
    PALLETSATLIXCO_DB_HOST = "127.0.0.1"

if os.environ.get("PALLETSATLIXCO_DB_PORT"):
    PALLETSATLIXCO_DB_PORT = os.environ.get("PALLETSATLIXCO_DB_PORT")
else:
    PALLETSATLIXCO_DB_PORT = 3306

if os.environ.get("PALLETSATLIXCO_DB_USER"):
    PALLETSATLIXCO_DB_USER = os.environ.get("PALLETSATLIXCO_DB_USER")
else:
    PALLETSATLIXCO_DB_USER = "pallets"

if os.environ.get("PALLETSATLIXCO_DB_PASSWD"):
    PALLETSATLIXCO_DB_PASSWD = os.environ.get("PALLETSATLIXCO_DB_PASSWD")
else:
    PALLETSATLIXCO_DB_PASSWD = "4hwsh4o96"


@app.before_request
def db_connect():
    """
    Realiza la conexion con la base de datos.
    """
    g.conn = MySQLdb.connect(
        host=PALLETSATLIXCO_DB_HOST,
        user=PALLETSATLIXCO_DB_USER,
        passwd=PALLETSATLIXCO_DB_PASSWD,
        db=PALLETSATLIXCO_DB,
        port=int(PALLETSATLIXCO_DB_PORT),
        charset="utf8",
        use_unicode=True,
    )
    g.cursor = g.conn.cursor()


@app.after_request
def db_disconnect(response):
    """
    Cerrar la conexion con la base de datos.
    """
    g.cursor.close()
    g.conn.close()
    return response


@app.route("/")
def main():
    """
    Abre la pagina principal (/).
    """
    return render_template("index.html")


@app.route("/logout")
def logout():
    """
    Cierra la sesion del usuario activo.
    """
    session.pop("user", None)
    return redirect("/")


# -------- END Configuration Values -------- #

# -------- INIT Get Datas Services -------- #
# --- Obtener Lista de Materiales de OB --- #
@app.route("/fflask/MaterialesBlob", methods=["GET"])
def get_MaterialesBlob():
    """
    Actualiza la lista de materiales de la tabla tbl_materials
    Parametros: _org: Id organizacion.
    Retorno: Texto donde "OK" es operacion correcta.
    """
    try:
        _org = int(session.get("org"))

        g.cursor.callproc("sp_getDatasOrg", (_org,))
        Org_Datas = g.cursor.fetchall()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        for GetMaterials in Org_Datas:
            # id_Org = int(GetMaterials[0])
            buf = cStringIO.StringIO()
            url = (
                UrlOB
                + "/org.openbravo.service.json.jsonrest"
                + "/Product?_where=organization='"
                + str(GetMaterials[2])
                + "'"
            )
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(pycurl.HTTPHEADER, ["Authorization:" + str(GetMaterials[3])])
            c.setopt(c.WRITEFUNCTION, buf.write)
            c.perform()
            data = buf.getvalue()
            decoded = json.loads(data)
            datos = decoded["response"]["data"]
            g.cursor.callproc("sp_truncateMaterials", (_org,))
            g.conn.commit()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            i = 0
            for material in datos:
                if i <= len(datos):
                    print (str(decoded["response"]["data"][i]))
                    nombre = str(decoded["response"]["data"][i]["name"].encode("utf-8"))
                    id_m = str(decoded["response"]["data"][i]["id"].encode("utf-8"))
                    uOM = str(decoded["response"]["data"][i]["uOM"].encode("utf-8"))
                    org_Key = str(
                        decoded["response"]["data"][i]["organization"].encode("utf-8")
                    )
                    #                    id_ = str(
                    #                        decoded["response"]["data"][i]["id"].encode("utf-8")
                    #                    )
                    i += 1
                    g.cursor.callproc(
                        "sp_InsertAllMaterials", (id_m, nombre, uOM, org_Key)
                    )
        g.conn.commit()
        g.cursor.close()
        return json.dumps("OK")
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()
    resp = Response("Done", status=201, mimetype="application/json")
    return resp


# Obtener lista de materiales para la remision #
@app.route("/getMaterialsBlob", methods=["GET", "POST"])
def getMaterialsBlob():
    try:
        _org = session.get("org")
        g.cursor.callproc("sp_GetMaterialesBlob", (_org,))
        result = g.cursor.fetchall()

        # response = []
        materials_dict = []
        for material in result:
            material_dict = material[0]
            materials_dict.append(material_dict)

        return json.dumps(materials_dict)

    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()
    resp = Response("Done", status=201, mimetype="application/json")
    return resp


# -------- END Get Datas Services -------- #
# -------- INIT Login and sigin -------- #
@app.route("/validateLogin", methods=["POST"])
def validateLogin():
    """
    Valida el inicio de sesion de un usuario.
    Parametros:
        _username: Email de usuario.
        _password: contraseña.
        _org: Id organizacion.
    Retorno: Te redirecciona a la pagina
    principal de la aplicacion.
    """
    try:
        _username = request.form["inputEmail"]
        _password = request.form["inputPassword"]
        _org = request.form["org"]
        g.cursor.callproc(
            "sp_validateLogin",
            (
                _username,
                _org,
            ),
        )
        data = g.cursor.fetchall()

        if data:
            if check_password_hash(str(data[0][3]), _password):
                session["user"] = data[0][0]
                session["username"] = data[0][1]
                session["org"] = _org
                session["orgname"] = data[0][6]
                session["mail"] = data[0][2]
                session["orgkey"] = data[0][7]

                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetPrintersByUserLogin", (int(data[0][0]),))
                datasPrinter = g.cursor.fetchall()
                g.cursor.close()
                session["TCP_IPM"] = os.environ.get(str(datasPrinter[0][0]))
                session["NamePrinterContainer"] = str(datasPrinter[0][2])
                session["IdPrinterContainer"] = int(data[0][4])
                session["TCP_IP"] = os.environ.get(str(datasPrinter[0][1]))
                session["NamePrinterPacking"] = str(datasPrinter[0][3])
                session["IdPrinterPacking"] = int(data[0][5])
                return redirect("/userHome")
            else:
                flash("warning:: Password Incorrecto.")
                return redirect("/showSignin")
        else:
            flash("warning:: Correo Eletronico Incorrecto.")
            return redirect("/showSignin")

    except Exception as e:
        flash("warning:: " + str(e))
        return redirect("/showSignin")


@app.route("/showSignUp")
def showSignUp():
    """
    Vista donde podemos crear un nuevo usuario.
    Parametros:
    Retorno: renderiza a signup.html con dos arreglos correspondiente
    a los tipos de impresora disponibles en la aplicacion.
    """
    g.cursor.callproc(
        "sp_GetPrintersByLabelSize",
        ("Contenedor",),
    )
    datasPrinterContainer = g.cursor.fetchall()
    g.cursor.close()

    ContainersPrinters = []
    for Printer in datasPrinterContainer:
        ContainersPrinters.append(
            [
                (Printer[0]),
                (Printer[1]),
                (Printer[2]),
                (Printer[3]),
            ]
        )

    g.cursor = g.conn.cursor()
    g.cursor.callproc(
        "sp_GetPrintersByLabelSize",
        ("UnidadEmpaque",),
    )
    datasPrinterPackingUnit = g.cursor.fetchall()
    g.cursor.close()

    PackingUnitsPrinters = []
    for Printer in datasPrinterPackingUnit:
        PackingUnitsPrinters.append(
            [
                (Printer[0]),
                (Printer[1]),
                (Printer[2]),
                (Printer[3]),
            ]
        )

    return render_template(
        "signup.html",
        PrintersContainer=ContainersPrinters,
        PrintersPackingUnits=PackingUnitsPrinters,
    )


@app.route("/signUp", methods=["POST", "GET"])
def signUp():
    """
    Crea un nuevo registro de usuario.
    Parametros:
        _name: Nombre usuario.
        _email: Correo eletronico.
        _password: contraseña.
        _printerContainer: Id impresora para contenedores.
        _printerPackingUnit: Id impresora para unidades de empaque.
    Retorno: Objeto Json donde "status":"OK" es oprecion correcta.
    """
    try:
        _name = request.form["inputName"]
        _email = request.form["inputEmail"]
        _password = request.form["inputPassword"]
        _printerContainer = request.form["ContainerPrinter"]
        _printerPackingUnit = request.form["PackingUnitPrinter"]

        if _name and _email and _password and _printerContainer and _printerPackingUnit:

            _hashed_password = generate_password_hash(_password)
            g.cursor.callproc("sp_createUser", (_name, _email, _hashed_password))
            data = g.cursor.fetchall()

            if not data:
                g.conn.commit()
                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_AddUserPrinters",
                    (
                        _printerContainer,
                        _printerPackingUnit,
                        _email,
                    ),
                )
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Enter the required fields"})

    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/showSignin")
def showSignin():
    g.cursor.callproc("sp_getIDOrganizations")
    data = g.cursor.fetchall()
    orgs = []
    for org in data:
        orgs.append([int(org[0]), str(org[1])])
    return render_template("signin.html", orgs=orgs)


# -------- END Login and sigin -------- #
# -------- INIT User Home -------- #
@app.route("/userHome")
def userHome():
    if session.get("user"):
        return render_template(
            "userHome.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return redirect("/showSignin")


# --- obtener todos lista de remisiones Preparadas --- #
@app.route("/getAllPreparedRemission", methods=["POST"])
def getAllPreparedRemission():
    """
    Obtitne todos los contenderoes con estado prepared_remission = 1
    y estado finish_remission = 0.
    Parametros:
        _user: Id usuario.
        _limit: Limite de resultados a mostrar.
        _offset: Numero de paginacion para buscar resultados.
        _org: Id Organizacion.
    Retorno: Objeto Json de lista de contendores con sus atributos.
    """
    try:
        if session.get("user"):
            _user = session.get("user")
            _limit = request.form["limit"]
            _offset = request.form["offset"]
            _org = session.get("org")

            g.cursor.execute(
                "call sp_GetPreparedRemission(%s,%s,%s,%s,@p_total)",
                (_limit, _offset, _org, _user),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Remission": "Remision o Doc.:Transporte",
                    "Type": "Tipo",
                    "DateR": "Fecha",
                    "Org": "Organizacion",
                    "container": "Contenedor",
                }
            ]
            for material in materials:
                if int(material[7]) > 0:
                    material_dict = {
                        "Id": material[0],
                        "Remission": material[1],
                        "Type": material[2],
                        "DateR": str(material[3]),
                        "Org": material[4],
                        "container": str(material[5]),
                        "PackingId": int(material[6]),
                    }
                    materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})
            return json.dumps(response)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/showNewRemission")
def showNewRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    return render_template("newremission.html")


@app.route("/NewRemission", methods=["POST"])
def NewRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))
            _remision = str(request.form["remision"])
            _org = session.get("org")
            _user = session.get("user")

            g.cursor.callproc("sp_addRemission", (_remision, _org, _user))
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNewRemission")
                data = g.cursor.fetchall()
                g.cursor.close()
                _container = str(data[0][2])

                b = (
                    b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
                    + _container
                    + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
                    + _container
                    + """|}
          {XS;I,0004,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)
                s.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


@app.route("/PrintTiketContainer", methods=["POST"])
def PrintTiketContainer():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IPM"), TCP_PORT))
        if session.get("user"):
            _id = request.form["id"]

            g.cursor.callproc("sp_PrintQrContainer", (_id,))
            result = g.cursor.fetchall()
            _container = str(result[0][0])

            b = (
                b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
                + _container
                + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
                + _container
                + """|}
          {XS;I,0004,0002C6101|}"""
            )
            g.cursor.close()
            if connect_to_printers:
                s.send(b)
            s.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e) + " Impresora No canectada ip invalida"})


@app.route("/getallProductsByRemission", methods=["POST"])
def getallProductsByRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _org = session.get("org")
            remision = request.form["remision"]
            print (remision)
            g.cursor.execute("call sp_GetProductsByRemission(%s,%s)", (remision, _org))
            materials = g.cursor.fetchall()
            g.cursor.close()
            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Material": material[1],
                    "Peso": str(material[2]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        print (e)
        return json.dumps(str(e))


@app.route("/Addproducto", methods=["POST", "GET"])
def Addproducto():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _material = request.form["material"]
            _w_net = request.form["peso"]
            _id = request.form["idr"]
            _Org = session.get("org")

            g.cursor.callproc(
                "sp_addProductsByRemission", (_material, _w_net, _Org, _id)
            )
            data = g.cursor.fetchall()

            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "An error occurred!"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


@app.route("/getProductsRById", methods=["POST"])
def getProductsRById():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")
            g.cursor.callproc("sp_GetProductsRById", (_id, _user))
            result = g.cursor.fetchall()
            material = []
            material.append(
                {
                    "Id": str(result[0][0]),
                    "Material": result[0][1],
                    "Width": str(result[0][2]),
                }
            )

            return json.dumps(material)
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


# ----- Actializar ProductbyRemission -------------#
@app.route("/updateProductbyRemission", methods=["POST"])
def updateProductbyRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _user = session.get("user")
            _product_id = request.form["id"]
            _material = request.form["material"]
            _peso_neto = request.form["peso"]

            g.cursor.callproc(
                "sp_updateProductByRemission",
                (_product_id, _material, _peso_neto, _user),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "ERROR"})
    except Exception:
        return json.dumps({"status": "Unauthorized access"})
    return json.dumps({"status": "OK"})


# ---- Elimiar Productos de lista de Remision --- #
@app.route("/deleteProductsByRemission", methods=["POST"])
def deleteProductsByRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")
            g.cursor.callproc("sp_deleProductsByRemission", (_id, _user))
            result = g.cursor.fetchall()
            if not result:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "An Error occured"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


# --- obtener todas las remisiones no Preparadas --- #
@app.route("/getAllUnPreparedRemission", methods=["POST"])
def getAllUnPreparedRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _user = session.get("user")
            _limit = request.form["limit"]
            _offset = request.form["offset"]
            _org = session.get("org")

            g.cursor.execute(
                "call sp_GetUnPreparedRemission(%s,%s,%s,%s,@p_total)",
                (_limit, _offset, _org, _user),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Remission": material[1],
                    "Type": material[2],
                    "DateR": str(material[3]),
                    "org": material[4],
                    "container": str(material[5]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})

            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        return json.dumps(str(e))


@app.route("/getNumRemissionByEditOrg", methods=["POST"])
def getNumRemissionByEditOrg():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            # _user = session.get("user")
            print (_id)
            g.cursor.callproc("sp_GetNumRemissionByEditOrg", (_id,))
            result = g.cursor.fetchall()

            material = []
            material.append(
                {
                    "Id": _id,
                    "Remission": str(result[0][0]),
                    "Organization": str(result[0][2]),
                }
            )

            return json.dumps(material)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/getNumRemissionByEdit", methods=["POST"])
def getNumRemissionByEdit():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["remision"]
            print ("2 _id", _id)

            g.cursor.callproc("sp_GetNumRemissionByEditOrg", (_id,))
            data = g.cursor.fetchall()
            g.cursor.close()
            return render_template(
                "addprodutsremission.html",
                rms=str(data[0][0]),
                org=session["orgname"],
                idr=_id,
                container=str(data[0][3]),
            )
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/finishRemission", methods=["POST"])
def finishRemission():
    """
    Dudo Posiblemente en fuera de uso el dia 2020-09-11
    dar de baja el dia 2020-03-11 si no se sigue utilizando.
    actualiza un contenedor con estado prepared_remission = 1
    el cual indica fin del etiquetado unidades de empaque
    para el contendor y listo para ser enviado sus datos a DASlabel.
    Parametros:
        _id: Id del contenedor.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["remision"]

            g.cursor.callproc("sp_finishRemission", (_id,))
            data = g.cursor.fetchall()

            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


# Obtener Remision por Id para Actualizar mediante un Modal
# el numero de remision #
@app.route("/getNumRemissionById", methods=["POST"])
def getNumRemissionById():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")

            g.cursor.callproc("sp_GetNumRemissionById", (_id, _user))
            result = g.cursor.fetchall()

            material = []
            material.append({"Id": str(result[0][0]), "Remission": str(result[0][1])})

            return json.dumps(material)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


# ----- Actializar Numero de Remission -------------#
@app.route("/updateNumRemission", methods=["POST"])
def updateNumRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            # _user = session.get("user")
            _id = request.form["id"]
            _num = request.form["number"]

            g.cursor.callproc("sp_EditNumRemission", (_id, _num))
            data = g.cursor.fetchall()
            g.cursor.close()

            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "ERROR"})
    except Exception:
        return json.dumps({"status": "Unauthorized access"})
    return json.dumps({"status": "OK"})


# ----- Actializar Numero de Remission y/o Organizacion -------------#
@app.route("/updateRemissionNumorOrg", methods=["POST", "GET"])
def updateRemissionNumorOrg():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _num = request.form["number"]
            _org = session.get("orgname")

            g.cursor.callproc("sp_EditRemissionNumorOrg", (_id, _num, _org))
            data = g.cursor.fetchall()
            g.cursor.close()
            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "ERROR"})
    except Exception:
        return json.dumps({"status": "Unauthorized access"})
    return json.dumps({"status": "OK"})


# -------- END New Remition Funtions -------- #

# -------- INIT Add Pallets In Remission -------- #
# Obtener Numero de Remision  para Agregarles Los Palets Correspondientes #
@app.route("/getNumRemission", methods=["POST"])
def getNumRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["remision"]
            _user = session.get("user")
            g.cursor.callproc("sp_GetNumRemission", (_id, _user))
            result = g.cursor.fetchall()

            if not result:
                return render_template(
                    "error.html", error="Acceso no authorizado en la remision"
                )
            if str(result[0][0]) == "None":
                return render_template(
                    "error.html", error="Acceso no authorizado en la remision"
                )
            # numeroderemision = result[0][0]
            # ObtenerPallets = result[0][0]
            return redirect("/showAddPalet")
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


# --- Mostrar AddPalet --- #
@app.route("/showAddPalet")
def showAddPalet():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    _Ruta = request.args.get("ID")
    _id = str(_Ruta.split("--")[0])
    print ("_id", _id)
    _num = str(_Ruta.split("--")[1])
    print ("_num", _num)
    _container = str(_Ruta.split("--")[2])
    print ("_container", _container)
    return render_template("addPalets.html", rmplt=_num, ID=_id, container=_container)


# Obtener lista de materiales para la remision #
@app.route("/getMaterialsBlobByRemission", methods=["GET", "POST"])
def getMaterialsBlobByRemission():
    """
    Dudo  Fecha fuera de funcion: 2020-09-03
    Fecha para Retirar de produccion: 2021-01-03
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        _RNumber = request.form["rm"]

        g.cursor.callproc("sp_GetMaterialesBlobByRemission", (_RNumber,))
        result = g.cursor.fetchall()

        # response = []
        materials_dict = []
        for material in result:
            material_dict = material[0]
            materials_dict.append(material_dict)

        return json.dumps(materials_dict)

    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()
    resp = Response("Done", status=201, mimetype="application/json")
    return resp


def elimina_tildes(cadena):
    s = "".join(
        (
            c
            for c in unicodedata.normalize("NFD", unicode(cadena))
            if unicodedata.category(c) != "Mn"
        )
    )
    return s.decode()


# ---- Crear Nuevo registro de Pallet --- #
@app.route("/NewPallet", methods=["POST"])  # noqa
def NewPallet():
    """Imprime la etiqueta de un material que es agregado a una remisión.
    También incluye la ubicación del material en la etiqueta.
    """
    try:
        s = socket.socket()
        if session.get("user"):
            _user = session.get("user")
            _numRemision = request.form["remision"]
            _idRemision = request.form["id"]
            _numtikets = int(request.form["ntikets"])
            _true_printer = int(request.form["true_printer"])
            if (
                _numRemision != "0"
                or _numRemision != 0
                or _numRemision is not None
                or _idRemision != "0"
                or _idRemision != 0
                or _idRemision is not None
            ):
                if connect_to_printers:
                    if _true_printer == 1:
                        s.connect((TCP_IP, TCP_PORT))
                    elif _true_printer == 2:
                        s.connect((TCP_IP2, TCP_PORT))

                _material = request.form["material"]
                _neto = request.form["neto"]
                _lote = request.form["lote"]
                _bruto = 0

                g.cursor.callproc("sp_GetLocation", (_material,))
                locat = g.cursor.fetchall()

                locat1 = ""
                if len(locat) == 1:
                    locat1 = locat[0][0]
                elif len(locat) > 1:
                    for i in locat:
                        locat1 = locat1 + " " + i[0]

                materialkey = (_material).split(" ")[0]
                Descripcion = "Desc:" + str(
                    re.sub(
                        r"[^a-zA-Z0-9]+",
                        " ",
                        _material.replace(materialkey, ""),
                    )
                )
                txt1 = Descripcion
                txt2 = ""
                if len(Descripcion) > 41:
                    txt1 = Descripcion[:40] + "-"
                    txt2 = Descripcion[40:]
                    txt1 = elimina_tildes(txt1)
                    txt2 = elimina_tildes(txt2)
                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNumRemission", (_idRemision, _user))
                result = g.cursor.fetchall()
                print (_user, result, _idRemision)
                if not result or str(result[0][0]) == "None":
                    return json.dumps({"status": "Acceso no autorizado en la remisión"})
                remisionNum = result[0][0]
                g.cursor.close()

                if _numRemision != remisionNum:
                    return json.dumps({"status": "ERRORNUM2"})

                for _tiket in range(_numtikets):
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc(
                        "sp_CreateNewPalet", (materialkey, _neto, _idRemision)
                    )
                    data = g.cursor.fetchall()

                    if not data:
                        g.conn.commit()

                    g.cursor.close()
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc("sp_GetLastPaletByEdit", (_numRemision,))
                    datap = g.cursor.fetchall()
                    pallet = str(datap[0][2])
                    g.cursor.close()

                    g.cursor = g.conn.cursor()
                    g.cursor.callproc(
                        "sp_UpdateLastPalet",
                        (_numRemision, _material, _neto, _bruto, _lote),
                    )
                    datasr = g.cursor.fetchall()
                    if not datasr and locat1 == "":
                        g.conn.commit()
                        b = (
                            b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                            + pallet
                            + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                            + materialkey
                            + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                            + _neto
                            + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                            + txt1
                            + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                            + txt2
                            + """|}
                  {PV02;0004,0493,0025,0025,J,00,B=Ubicacion: """
                            + locat1
                            + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                            + pallet
                            + """_"""
                            + str(_user)
                            + """|}
                  {XS;I,0001,0002C6101|}"""
                        )
                        if connect_to_printers:
                            s.send(b)
                        g.cursor.close()
                    elif not datasr and locat1 != "":
                        g.conn.commit()
                        b = (
                            b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                            + pallet
                            + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                            + materialkey
                            + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                            + _neto
                            + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                            + txt1
                            + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                            + txt2
                            + """|}
                  {PV02;0004,0493,0025,0025,J,00,B=Ubicacion: """
                            + locat1
                            + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                            + pallet
                            + """_"""
                            + str(_user)
                            + """|}
                  {XS;I,0001,0002C6101|}"""
                        )
                        if connect_to_printers:
                            s.send(b)
                        g.cursor.close()
                s.close()

                return json.dumps({"status": "OK"})

            else:
                return json.dumps({"status": "ERRORNUM1"})
        else:
            return json.dumps({"status": "ERRORSESSION"})

    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


@app.route("/getgamesalocation", methods=["GET", "POST"])
def getgamesalocation():
    """Solicita la ubicación de los materiales al sistema de DasLabels.
    Las ubicaciones se almacenan en la tabla 'tbl_locations' por medio del
    stored procedure 'sp_UpdateLocation'
    """
    try:
        if session.get("user"):

            _org = session.get("org")
            g.cursor.callproc("sp_GetMaterialesBlob", (_org,))
            result = g.cursor.fetchall()
            prueba = os.popen(
                "curl -X GET http://daslabels.123sourcing.com/"
                "get_all_stock_gamesa_by_location?product="
            )
            output = json.loads(prueba.read())
            print (len(output))
            print (len(output["response"]))
            for i in result:

                a = i[0].split(" ")[0]
                material = i[0]
                loc2 = ""
                for j in output["response"]:
                    if j["producto"] == a:
                        loc2 = j["location"][12:]

                        g.cursor = g.conn.cursor()
                        g.cursor.callproc(
                            "sp_UpdateLocation",
                            (
                                material,
                                loc2,
                            ),
                        )
                        g.conn.commit()

            return json.dumps(
                {"status": "La Ubicación del Material" " Se Actualizó Correctamente"}
            )
        else:
            return json.dumps({"status": "Acceso no Autorizado"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/RePrintTicket", methods=["POST", "GET"])
def RePrintTicket():
    try:
        return render_template("re_print_ticket.html")
    except Exception as error:
        flash(error)
        render_template("userHome.html")


@app.route("/ReprintTicketPallet", methods=["POST"])
def ReprintTicketPallet():
    """ Prints packaging unit (unidad de empaque) labels"""
    try:
        s = socket.socket()
        if connect_to_printers:
            ip_printer = str(session.get("TCP_IP"))
            s.connect((ip_printer, TCP_PORT))
        if session.get("user"):
            print ("===== START METHOD ===== ")
            # _user = session.get("user")

            _ticket = str(request.form["ticket"]).replace(" ", "")
            sendData = json.dumps({"status": 1, "response": [{"ticket": _ticket}]})
            print (sendData)

            buf = cStringIO.StringIO()
            url = urlserver + "/fflask/GetPalletsToReprint"
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(
                pycurl.HTTPHEADER,
                ["Accept: application/json", "Content-Type: application/json"],
            )
            c.setopt(pycurl.POST, 1)
            c.setopt(pycurl.POSTFIELDS, sendData)
            c.setopt(c.WRITEFUNCTION, buf.write)
            c.perform()
            data = buf.getvalue()
            decoded = json.loads(data)

            if not decoded:
                s.close()
                flash("danger:: Etiqueta no encontrada: " + str(_ticket))
                return redirect("/RePrintTicket")

            b = (
                b"""{C|}
            {XB01;0635,0070,T,H,18,A,0,M2="""
                + str(decoded[0]["ticket"])
                + """|}
            {PV01;0010,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
            {PV02;0010,0258,0030,0050,J,00,B=Ref:"""
                + str(decoded[0]["gmid"])
                + """|}
            {PV02;0010,0323,0030,0050,J,00,B=Cant.Packing: """
                + str(decoded[0]["qty"])
                + """|}
            {PV02;0010,0383,0025,0045,J,00,B=Desc: """
                + str(decoded[0]["description"])
                + """|}
            {PV02;0640,0450,0025,0045,J,00,B="""
                + str(decoded[0]["ticket"])
                + """|}
            {XS;I,0001,0002C6101|}"""
            )
            print (b)
            if connect_to_printers:
                s.send(b)
            s.close()

            flash("success::Se imprimio correctamente: " + str(_ticket))
            return redirect("/RePrintTicket")
        else:
            flash("ususario no autorizado")
            # return json.dumps({'status':'ERRORSESSION'})
            return redirect("/RePrintTicket", 302, Response("Bien"))

    except Exception as e:
        print (e)
        flash(e)
        # return json.dumps({'status':str(e)})
        return redirect("/RePrintTicket")


@app.route("/RePrintTicketContainer", methods=["POST", "GET"])
def RePrintTicketContainer():
    try:
        return render_template("re_print_ticket_container.html")
    except Exception as error:
        flash(error)
        render_template("userHome.html")


@app.route("/RePrintTiketContainer", methods=["POST"])
def RePrintTiketContainer():
    try:
        print ("ip", session.get("TCP_IPM"))
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IPM"), TCP_PORT))
        if session.get("user"):
            _ticket = str(request.form["ticket"]).replace(" ", "")

            b = (
                b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
                + str(_ticket)
                + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
                + str(_ticket)
                + """|}
          {XS;I,0004,0002C6101|}"""
            )
            print (b)
            g.cursor.close()
            if connect_to_printers:
                s.send(b)
            s.close()
            flash("success::Se iprimio correctamente " + str(_ticket) + "!!")
            return redirect("/RePrintTicketContainer")

        else:
            flash("Unauthorized Access")
            return redirect("/RePrintTicketContainer")
    except Exception as e:
        print (e)
        flash(str(e) + " Impresora No canectada ip invalida")
        return redirect("/RePrintTicketContainer")


# ---- Crear Nuevo registro de Pallet --- #
@app.route("/NewTiketProduct", methods=["POST"])
def NewTiketProduct():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IP"), TCP_PORT))
        if session.get("user"):
            _material = request.form["material"]
            _material = elimina_tildes(_material)
            materialkey = (_material).split(" ")[0]
            Descripcion = "Desc:" + _material.replace(materialkey, "")
            txt1 = Descripcion
            txt2 = ""
            if len(Descripcion) > 32:
                txt1 = Descripcion[:32] + "-"
                txt2 = Descripcion[32:]

            b = (
                b"""{C|}
              {PV01;0004,0170,0080,0140,J,00,B="""
                + materialkey
                + """|}
              {PV02;0004,0320,0060,0100,J,00,B="""
                + txt1
                + """|}
              {PV02;0004,0450,0060,0100,J,00,B="""
                + txt2
                + """|}
              {XS;I,0001,0002C4000|}"""
            )
            print (b)
            if connect_to_printers:
                s.send(b)
            s.close()

            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "ERRORSESSION"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# ---- obtener defectos para adddefects.html ---- #
@app.route("/getFirstPalets", methods=["POST"])
def getFirstPalets():
    try:

        if session.get("user"):
            # _user = session.get("user")
            _limit = 99999
            _offset = request.form["offset"]
            # _total_records = 0
            _id = request.form["id"]

            # Se agrego el mismo stored procedure (2) pero sin la funcion de
            # contador, ya que retrasa el proceso hasta 10 minutos. Este
            # contador conto, en promedio 575231250 elementos.
            # En su lugar, la variable (outPar) que almacena este resultado
            #  se le asigno un valor de 10000
            # g.cursor.execute('call sp_GetPalets(%s,%s,%s,@p_total)',
            # (_limit,_offset,_id))
            g.cursor.execute("call sp_GetPalets2(%s,%s,%s)", (_limit, _offset, _id))
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Code": str(material[1]),
                    "Material": material[2],
                    "Neto": str(material[3]),
                    "Date": str(material[4]),
                    "Gross": str(material[5]),
                    "LotOrg": str(material[6]),
                    "Status": str(material[7]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            # g.cursor.execute('SELECT @p_total')
            # outParam = g.cursor.fetchone()
            outParam = 10000
            # response.append({'total':outParam[0]})
            response.append({"total": outParam})

            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        print (e)
        return json.dumps(str(e))


# Obtener Datos del palet para editar#
@app.route("/getNumPaletByEdit", methods=["POST"])
def getNumPaletByEdit():
    try:
        if session.get("user"):
            _user = session.get("user")
            _id = request.form["id"]
            g.cursor.callproc("sp_GetPaletById", (_id, _user))
            result = g.cursor.fetchall()

            material = []
            material.append(
                {
                    "Id": str(result[0][0]),
                    "Pallet": str(result[0][1]),
                    "Remision": str(result[0][2]),
                    "Material": str(result[0][3]),
                    "Gross": str(result[0][4]),
                    "Net": str(result[0][5]),
                    "Lot": str(result[0][6]),
                }
            )
            return json.dumps(material)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintTiketPalet", methods=["POST"])
def PrintTiketPalet():
    try:
        s = socket.socket()
        ip_printer = str(session.get("TCP_IP"))
        if connect_to_printers:
            s.connect((ip_printer, TCP_PORT))
        if session.get("user"):
            _user = session.get("user")
            _id = request.form["id"]

            g.cursor.callproc("sp_GetPaletById", (_id, _user))
            result = g.cursor.fetchall()
            pallet = str(result[0][1])
            _material = elimina_tildes(result[0][3])
            materialkey = (_material).split(" ")[0]
            Descripcion = "Desc:" + _material.replace(materialkey, "")
            _neto = str(result[0][5])
            txt1 = Descripcion
            txt2 = ""
            if len(Descripcion) > 41:
                txt1 = Descripcion[:40] + "-"
                txt2 = Descripcion[40:]

            b = (
                b"""{C|}
            {XB01;0635,0070,T,H,18,A,0,M2="""
                + str(pallet)
                + """|}
            {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
            {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                + str(materialkey)
                + """|}
            {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                + str(_neto)
                + """|}
            {PV02;0004,0383,0025,0045,J,00,B="""
                + str(txt1)
                + """|}
            {PV02;0004,0443,0025,0045,J,00,B="""
                + str(txt2)
                + """|}
            {PV02;0640,0450,0025,0045,J,00,B="""
                + str(pallet)
                + """_"""
                + str(_user)
                + """|}
            {XS;I,0001,0002C6101|}"""
            )
            # g.cursor.close()
            if connect_to_printers:
                s.send(b)
            s.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e) + " Impresora No canectada ip invalida"})


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintOutTiketPalet", methods=["POST"])
def PrintOutTiketPalet():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IP"), TCP_PORT))
        if session.get("user"):
            _user = session.get("user")
            _id = request.form["id"]

            g.cursor.callproc("sp_GetPaletById", (_id, _user))
            result = g.cursor.fetchall()
            pallet = str(result[0][1])
            _material = elimina_tildes(result[0][3])
            materialkey = (_material).split(" ")[0]
            Descripcion = "Desc:" + _material.replace(materialkey, "")
            _neto = str(result[0][5])
            txt1 = Descripcion
            txt2 = ""
            if len(Descripcion) > 41:
                txt1 = Descripcion[:40] + "-"
                txt2 = Descripcion[40:]

            b = (
                b"""{C|}
            {XB01;0635,0070,T,H,18,A,0,M2="""
                + pallet
                + """|}
            {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
            {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                + materialkey
                + """|}
            {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                + _neto
                + """|}
            {PV02;0004,0383,0025,0045,J,00,B="""
                + txt1
                + """|}
            {PV02;0004,0443,0025,0045,J,00,B="""
                + txt2
                + """|}
            {PV02;0640,0450,0025,0045,J,00,B="""
                + pallet
                + """_"""
                + _user
                + """|}
            {XS;I,0001,0002C6101|}"""
            )
            g.cursor.close()
            print (b)
            if connect_to_printers:
                s.send(b)
            s.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e) + " Impresora No canectada ip invalida"})


# ---- Elimiar pallet en Ubicar --- #
@app.route("/deleteNewPallet", methods=["POST"])
def deleteNewPallet():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar de produccion: 2020-12-07
    De lo contrarior Borrar estas lineas comentadas.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            # _user = session.get("user")

            g.cursor.callproc("sp_deletNewPallet", (_id,))
            result = g.cursor.fetchall()

            if not result:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "An Error occured"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


# ---------- END Pallets ----------------------------------------------------#

# ---------- Init Add Data Curl Palets --------------------------------------#
# ---- Enviar Pallet Finalizados a Monitor ---- #
@app.route("/SendPallets", methods=["POST"])
def SendPallets():
    """
    Funcion que se utiliza para el envio de pallets
    de una remision al sistema DASLabels.
    Parametros:
        _id: El id de la nueva remision generada
        _user: Id Usuario.
        _org: Id o KEY Organizacion OB.
    Retorno:
        Devuelve el status en formato json
        En caso de ser satisfactorio el envio de datos:
        return json.dumps({'status':'OK'})
        En caso de ser fallido el envio de datos:
        return json.dumps({'status':'Error Al Mandar Datos'})
        Si la sesion caduca:
        return json.dump({'status':'Unauthorized Access'})
        Si ocurre un error durante el proceso:
        return json.dumps({'status':str(e)})
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")
            _org = session.get("orgkey")

            g.cursor.callproc("sp_GetAlmName")
            NameAlm = g.cursor.fetchone()
            g.cursor.close()
            if not NameAlm:
                return json.dumps({"status": "Nombre almacen no localizado"})

            Alm = str(NameAlm[0])

            g.cursor = g.conn.cursor()
            g.cursor.callproc("sp_finishRemission", (_id,))
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
            else:
                return json.dumps({"status": str(data[0][0])})

            g.cursor = g.conn.cursor()
            g.cursor.callproc("sp_getdatapalets", (_id, _user))
            DatasPallets = g.cursor.fetchall()
            if not DatasPallets:
                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_finishFullRemission", (_id, _user))
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})

            Remision = DatasPallets[0][7]
            g.cursor.close()

            g.cursor = g.conn.cursor()
            json_send = []

            url = urlserver + "/fflask/AddDatasPalletsPT"
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(
                pycurl.HTTPHEADER,
                ["Accept: application/json", "Content-Type: application/json"],
            )
            c.setopt(pycurl.POST, 1)
            for datapllt in DatasPallets:
                if str(datapllt[9]) == "0":
                    buf = cStringIO.StringIO()
                    all_product = {
                        "paletcode": str(datapllt[2]),
                        "productkey": str(datapllt[3]),
                        "palettype": Alm,
                        "lotdow": str(datapllt[5]),
                        "netweight": str(datapllt[6]),
                        "remision": str(Remision),
                    }
                    json_send.append(all_product)
                    DataPalletsjson = json.dumps(
                        {"status": 1, "response": [all_product]}
                    )
                    c.setopt(pycurl.POSTFIELDS, DataPalletsjson)
                    c.setopt(c.WRITEFUNCTION, buf.write)
                    c.perform()
                    if str(buf.getvalue()) != "Added":
                        return json.dumps({"status": "Error Al Mandar Datos"})
                    else:
                        buf.close()

            funtionCloseAddPalletsToDas = CloseRemissionInDAS(str(Remision), Alm)
            if str(funtionCloseAddPalletsToDas) != "OK":
                return json.dumps({"status": str(funtionCloseAddPalletsToDas)})

            funtionAddPalletToOB = SendToExecuteAddPalettesToOB(Remision, Alm, _org)
            if str(funtionAddPalletToOB) != "OK":
                return json.dumps({"status": str(funtionAddPalletToOB)})

            g.cursor.callproc("sp_finishFullRemission", (_id, _user))
            g.conn.commit()
            g.cursor.close()
            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


def CloseRemissionInDAS(Remision, Alm):
    """
    Envia al sistema DAS a que la remision que se creo con
    el parametro Remision, se cambiado su estatus(campo):
    addpallets_finish a 2 el cual indica que todos los datos de pallets
    que pertenecen a esta remision ya se enviaron a DAS.
    Parametros:
        Remision: Numero de remision,
        Alm: Almacen origen.
    Retorno: Texto donde "OK" la operacion fue exitosa.
    curl -i -H "Content-Type: application/json" -X POST \
        -d '{"Remision":"MP100000000","Alm":"SG1"}' \
            http://127.0.0.1:9000/api/EndInboundReferral
    """
    try:
        url = urlserver + "/api/EndInboundReferral"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        buf = cStringIO.StringIO()
        DataPalletsjson = json.dumps(
            {
                "status": 1,
                "Remision": Remision,
                "Alm": Alm,
            }
        )
        c.setopt(pycurl.POSTFIELDS, DataPalletsjson)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()
        if str(buf.getvalue()) != "Added":
            return "Error al cerrar el envio de datos"
        else:
            buf.close()
            return "OK"

    except Exception as e:
        return str(e)


def SendToExecuteAddPalettesToOB(Remision, Alm, _org):
    """
    Envia al sistema DAS la orden de subir los datos de
    pallets pertenecientes a la remision numero : Remision.
    Al sistema Open Bravo.
    Parametros:
        Remision: Numero de remision,
        Alm: Almacen origen.
        _org: Id organizacion OB.
    Retorno: Texto donde "OK" la operacion fue exitosa.
    curl -i -H "Content-Type: application/json" -X POST \
    -d '{"Remision":"SG6141_9000852931","Alm":"SG1",\
        "Org":"DA2ABCEEBCC24A7C9D2B2BE337CADAE3"}' \
    http://127.0.0.1:9000/api/ExecuteAddPalletsToOB
    """
    try:
        url = urlserver + "/api/ExecuteAddPalletsToOB"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        buf = cStringIO.StringIO()
        DataPalletsjson = json.dumps(
            {"status": 1, "Remision": Remision, "Alm": Alm, "Org": _org}
        )
        c.setopt(pycurl.POSTFIELDS, DataPalletsjson)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()
        if str(buf.getvalue()) != "OK":
            return "Error al cerrar el envio de datos"
        else:
            buf.close()
            return "OK"

    except Exception as e:
        return str(e)


# ---- Enviar Pallet Finalizados a Monitor ---- #
@app.route("/SendPalletsByMultiRemision", methods=["POST"])
def SendPalletsByMultiRemision():
    try:
        if session.get("user"):
            _user = session.get("user")
            _value = request.form["value"]

            for varid in _value.split(","):
                _id = varid.replace('"', "")
                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_getdatapalets",
                    (
                        _id,
                        _user,
                    ),
                )
                # g.cursor.callproc("sp_getdatapalets",(_id,))
                DatasPallets = g.cursor.fetchall()
                if not DatasPallets:
                    g.cursor.close()
                    pass
                else:
                    Remision = DatasPallets[0][7]
                    g.cursor.close()

                    g.cursor = g.conn.cursor()
                    json_send = []
                    for datapllt in DatasPallets:
                        all_product = {
                            "paletcode": str(datapllt[2]),
                            "productkey": str(datapllt[3]),
                            "palettype": str(datapllt[4]),
                            "lotdow": str(datapllt[5]),
                            "netweight": str(datapllt[6]),
                            "remision": str(Remision),
                        }
                        json_send.append(all_product)
                        DataPalletsjson = json.dumps(
                            {"status": 1, "response": [all_product]}
                        )
                        buf = cStringIO.StringIO()
                        url = urlserver + "/fflask/AddDatasPalletsPT"
                        c = pycurl.Curl()
                        c.setopt(pycurl.URL, url)
                        c.setopt(
                            pycurl.HTTPHEADER,
                            [
                                "Accept: application/json",
                                "Content-Type: application/json",
                            ],
                        )
                        c.setopt(pycurl.POST, 1)
                        c.setopt(pycurl.POSTFIELDS, DataPalletsjson)
                        c.setopt(c.WRITEFUNCTION, buf.write)
                        c.perform()
                        if str(buf.getvalue()) != "Added":
                            return json.dumps({"status": "Error Al Mandar Datos"})
                        else:
                            buf.close()

                    g.cursor.callproc("sp_finishFullRemission", (_id, _user))
                    g.conn.commit()
                    g.cursor.close()
            # numeroderemision = "0"
            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# ---------- END Data Curl Palets ------------------------------------------#

# ----------Init Finish Remitions ------------------------------------------#
# --- template de lista de remisiones finalisadas --- #
@app.route("/showFinishRemission")
def showFinishRemission():
    """
    Vista donde podemos concultar los contenedores que ya se enviaron a DASlabels.
    Parametros:
    Retorno: Renderiza finishremission.html
    """
    return render_template(
        "finishremission.html",
        session_user_name=session["username"],
        orgname=session["orgname"],
    )


# --- obtener todas las remisiones no Finalizadas --- #
@app.route("/getAllFinishRemission", methods=["POST"])
def getAllFinishRemission():
    """
    Obtiene la lista de contenedores las cuales ya han sido enviados a DASlabels.
    Parametros:
        _limit: limite de registros por paginacion.
        _offset: numero de registro donde iniciar busqueda.
        _org: Id organizacion.
    Retorno: Objeto Json con la lista de contenedores enviados a DASlabels.
    """
    try:
        if session.get("user"):
            _limit = request.form["limit"]
            _offset = request.form["offset"]
            _org = session.get("org")

            g.cursor.execute(
                "call sp_GetFinishRemission(%s,%s,%s,@p_total)",
                (_limit, _offset, _org),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Remission": "#Remision",
                    "Type": "E/S",
                    "Date": "Fecha finalizado",
                    "Org": "Organizacion",
                    "Conte": "Contenedor",
                }
            ]
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Remission": material[1],
                    "Type": material[2],
                    "Date": str(material[3]),
                    "Org": material[4],
                    "Conte": str(material[5]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})

            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        print (e)
        return json.dumps(str(e))


# --- obtener todas las remisiones no Finalizadas --- #
@app.route("/getOneFinishRemission", methods=["POST"])
def getOneFinishRemission():
    try:
        if session.get("user"):
            _container = request.form["contenedor"]

            g.cursor.execute("call sp_GetOneFinishRemission(%s)", (_container,))
            materials = g.cursor.fetchall()
            g.cursor.close()
            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Remission": material[1],
                    "Type": material[2],
                    "Date": str(material[3]),
                    "Org": material[4],
                    "Conte": str(material[5]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)

            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        return json.dumps(str(e))


# Obtener Datos del una remision finalizada #
@app.route("/restoredFinishRemision", methods=["POST"])
def restoredFinishRemision():
    try:
        if session.get("user"):
            _id = request.form["id"]
            g.cursor.callproc("sp_getdataFinishRemision", (_id,))
            result = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            print (result[0][0])
            sendDatas = json.dumps(
                {
                    "status": 1,
                    "response": [{"idremision": str(result[0][0]), "type": "SG1"}],
                }
            )
            buf = cStringIO.StringIO()
            url = urlserver + "/fflask/CheckRemisionStatus"
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(
                pycurl.HTTPHEADER,
                ["Accept: application/json", "Content-Type: application/json"],
            )
            c.setopt(pycurl.POST, 1)
            c.setopt(pycurl.POSTFIELDS, sendDatas)
            c.setopt(c.WRITEFUNCTION, buf.write)
            c.perform()
            data = str(buf.getvalue())
            if data not in ("0", "1"):
                buf.close()
                return json.dumps({"status": data})
            elif data != "0":
                buf.close()
                return json.dumps({"status": "Esta remision ya fue finalizado en OB"})

            g.cursor.callproc("sp_restoredFinishRemision", (_id, data))
            result = g.cursor.fetchall()
            g.conn.commit()
            g.cursor.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


# Obtener Datos del una remision finalizada #
@app.route("/getNumFinishRemission", methods=["POST"])
def getNumFinishRemission():
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")
            # numeroderemision = "0"
            Remision = []
            g.cursor.callproc("sp_GetNumRemission", (_id, _user))
            result = g.cursor.fetchall()
            if not result:
                return json.dumps("Acceso no authorizado en la remision")
            if str(result[0][0]) == "None":
                return json.dumps("Acceso no authorizado en la remision")

            Remision.append({"total": result[0][1], "remision": result[0][0]})
            return json.dumps(Remision)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        return json.dumps(str(e))


# ---- obtener Palets de una remision Finalizada ---- #
@app.route("/getFinishPalets", methods=["POST"])
def getFinishPalets():
    try:
        if session.get("user"):
            # _user = session.get("user")
            _limit = 99999
            _offset = 0
            # _total_records = 0
            _numFR = request.form["id"]

            # g.cursor.execute('call sp_GetPalets(%s,%s,%s,@p_total)',
            # (_limit,_offset,_numFR))
            g.cursor.execute("call sp_GetPalets2(%s,%s,%s)", (_limit, _offset, _numFR))
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Code": str(material[1]),
                    "Material": material[2],
                    "Peso": str(material[3]),
                    "Date": str(material[4]),
                    "Neto": str(material[5]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            # g.cursor.execute('SELECT @p_total')
            outParam = 10000
            response.append({"total": outParam})

            return json.dumps(response)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


# ---- Obtener Materiaes en un input ---- #
@app.route("/getContainerBlob", methods=["POST"])
def getContainerBlob():
    try:
        g.cursor.callproc("sp_GetFinishContainersBlob", ())
        result = g.cursor.fetchall()
        # response = []
        materials_dict = []
        for material in result:
            material_dict = material[0]
            materials_dict.append(material_dict)
        return json.dumps(materials_dict)

    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


# ---------- END Finish Remitions  -----------------------------------------#


# ----------------- END Materials Orgs -------------------------------------#

# --- Template para agregar Nueva material --- #
@app.route("/ShowAddNewProduct")
def ShowAddNewProduct():
    if session.get("user"):
        return render_template("addproduct.html")
    else:
        return render_template("error.html", error="Unauthorized Access")


# ---- Agregar Material a la remision --- #
@app.route("/AddNewProduct", methods=["POST"])
def AddNewProduct():
    try:
        print ("inicia addnewproduct")
        if session.get("user"):
            print ("usuario correcto")
            _org = int(session.get("org"))
            _Gmid = str(request.form["gmid"].replace(" ", ""))
            _Desc = elimina_tildes(request.form["desc"])
            _Desc = str(_Desc)
            _Name = _Gmid + " " + _Desc
            g.cursor.callproc("sp_getDatasOrg", (_org,))
            Org_Datas = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            for GetMaterials in Org_Datas:
                print ("inicia for")
                id_Org = int(GetMaterials[0])
                print (
                    "id_org",
                    id_Org,
                    str(GetMaterials[2]),
                    str(GetMaterials[3]),
                )
                # buf = cStringIO.StringIO()
                url = (
                    UrlOB
                    + "/org.openbravo.service.json.jsonrest"
                    + "/Product?_where=organization='"
                    + str(GetMaterials[2])
                    + "'%20and%20searchKey='"
                    + _Gmid
                    + "'"
                )
                print ("url", url)
                ddd = requests.get(url, headers={"Authorization": str(GetMaterials[3])})
                print ("ddd", ddd)
                # c = pycurl.Curl()
                # c.setopt(pycurl.URL,url)
                # c.setopt(pycurl.HTTPHEADER, ['authorization: '
                #          +str(GetMaterials[3])])
                # c.setopt(c.WRITEFUNCTION, buf.write)
                # c.perform()
                # data=(buf.getvalue())
                data = ddd.text
                print ("data", data)
                decoded = json.loads(data)
                datos = decoded["response"]["data"]
                if str(decoded["response"]["totalRows"]) == "0":
                    DataPalletsjson = json.dumps(
                        {
                            "data": {
                                "searchKey": _Gmid,
                                "name": _Name,
                                "description": _Desc,
                                "client": "A7A127362BC248F998C69752EEC17EC2",
                                "organization": "DA2ABCEEBCC24A7C9D2B2BE337CADAE3",
                                "active": "true",
                                "stocked": "true",
                                "purchase": "true",
                                "sale": "true",
                                "productCategory": "6200E98563D0418EAEBEC074007174A6",
                                "taxCategory": "B7364E40393A4B9DA9686F99C86E700D",
                                "uOM": "100",
                                "attributeSet": "10C1D70379FB4CD5AEE5A2D222F02E6A",
                            }
                        }
                    )
                    print ("DataPalletsjson", DataPalletsjson)
                    url = (
                        "https://www.almacenaje.123sourcing.com"
                        "/openbravo/org.openbravo.service.json.jsonrest"
                        "/Product"
                    )
                    ccc = requests.post(
                        url,
                        headers={
                            "Authorization": "Basic V2ViU2VydmljZXNTaWVtZW5z"
                            "R2FtZXNhOnQldHhlJXY0KmVCWQ=="
                        },
                        data=DataPalletsjson,
                    )
                    # buf = cStringIO.StringIO()
                    # c = pycurl.Curl()
                    # c.setopt(pycurl.URL,url)
                    # c.setopt(pycurl.HTTPHEADER, ['Authorization : "
                    # "Basic"
                    # ' V2ViU2VydmljZXNTaWVtZW5zR2FtZXNhOnQldHhlJXY0KmVCWQ=='
                    # ,'Content-Type: application/json' ])
                    # c.setopt(pycurl.POST,1)
                    # c.setopt(pycurl.POSTFIELDS, DataPalletsjson)
                    # c.setopt(c.WRITEFUNCTION, buf.write)
                    # c.perform()
                    decoded = json.loads(ccc.text)
                    print ("decoded", decoded)

                    if str(decoded["response"]["status"]) == "0":
                        nombre = str(
                            decoded["response"]["data"][0]["name"].encode("utf-8")
                        )
                        id_m = str(decoded["response"]["data"][0]["id"].encode("utf-8"))
                        uOM = str(decoded["response"]["data"][0]["uOM"].encode("utf-8"))
                        org_Key = str(
                            decoded["response"]["data"][0]["organization"].encode(
                                "utf-8"
                            )
                        )
                        # id_ = str(
                        #     decoded["response"]["data"][0]["id"].encode(
                        #         "utf-8"
                        #     )
                        # )

                        g.cursor.callproc(
                            "sp_InsertAllMaterials",
                            (id_m, nombre, uOM, org_Key),
                        )
                        datas = g.cursor.fetchall()
                        if not datas:
                            g.conn.commit()
                            g.cursor.close()
                            print ("Eso es todo")
                            return json.dumps({"status": "OK"})
                        else:
                            return json.dumps({"status": str(datas[0][0])})
                    else:
                        return json.dumps(
                            {"status": str(decoded["response"]["error"]["message"])}
                        )
                i = 0
                for material in datos:
                    if i <= len(datos):
                        print (str(decoded["response"]["data"][i]))
                        nombre = str(
                            decoded["response"]["data"][i]["name"].encode("utf-8")
                        )
                        id_m = str(decoded["response"]["data"][i]["id"].encode("utf-8"))
                        uOM = str(decoded["response"]["data"][i]["uOM"].encode("utf-8"))
                        org_Key = str(
                            decoded["response"]["data"][i]["organization"].encode(
                                "utf-8"
                            )
                        )
                        # id_ = str(
                        #     decoded["response"]["data"][i]["id"].encode(
                        #         "utf-8"
                        #     )
                        # )
                        i += 1
                        g.cursor.callproc(
                            "sp_InsertAllMaterials",
                            (id_m, nombre, uOM, org_Key),
                        )
            g.conn.commit()
            g.cursor.close()
            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# --------------------------- END Agregar Producto Nuevo -------------- #

# --- Template para crear bultos por cliente --- #
@app.route("/ShowAddNewPackageByClient")
def ShowAddNewPackageByClient():
    if session.get("user"):
        return render_template(
            "addPackage.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


# --- Template para crear bultos por cliente --- #
@app.route("/ShowAddNewTransferPackage")
def ShowAddNewTransferPackage():
    if session.get("user"):
        return render_template(
            "addtransferpackage.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


# --- Template para crear bultos por cliente --- #
@app.route("/ShowAddNewEmtyContainerPackage")
def ShowAddNewEmtyContainerPackage():
    if session.get("user"):
        return render_template(
            "addemtycontainer.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintTiketPackage", methods=["POST"])
def PrintTiketPackage():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IPM"), TCP_PORT))
        _org = int(session.get("org"))
        g.cursor.callproc("sp_getDatasOrg", (_org,))
        Org_Datas = g.cursor.fetchall()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        _ruta = request.form["ruta"]
        _cli = request.form["cli"]
        print (_ruta, _cli, Org_Datas)
        sendDatas = json.dumps(
            {
                "status": 1,
                "response": [
                    {
                        "orgkeyOB": global_org,
                        "ruta": _ruta,
                        "client": _cli,
                        "alm": global_alm,
                        "position": str(Org_Datas[0][7]),
                        "whkey": global_whkey,
                    }
                ],
            }
        )
        buf = cStringIO.StringIO()
        url = urlserver + "/fflask/NewLotNum"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, sendDatas)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()
        data = buf.getvalue()
        decoded = json.loads(data)
        if str(decoded["status"]) != "OK":
            return json.dumps({"status": str(decoded["status"])})
        else:
            buf.close()
        _tiketcode = str(decoded["response"])
        g.cursor.callproc("sp_AddRegistrerDataPackage", (_tiketcode, _cli, _ruta))
        Responce = g.cursor.fetchall()
        if not Responce:
            g.conn.commit()
        g.cursor.close()
        b = (
            b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
            + _tiketcode
            + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
            + _tiketcode
            + """|}
          {XS;I,0004,0002C6101|}"""
        )
        print (b)
        if connect_to_printers:
            s.send(b)
        s.close()
        return json.dumps({"status": "OK"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintTransferTiketPackage", methods=["POST"])
def PrintTransferTiketPackage():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IPM"), TCP_PORT))
        print (1)
        _org = int(session.get("org"))
        g.cursor.callproc("sp_getDatasOrg", (_org,))
        Org_Datas = g.cursor.fetchall()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        _ruta = request.form["ruta"]
        _cli = 999999999
        sendDatas = json.dumps(
            {
                "status": 1,
                "response": [
                    {
                        "orgkeyOB": global_org,
                        "num": _ruta,
                        "client": _cli,
                        "alm": global_alm,
                        "position": str(Org_Datas[0][7]),
                        "whkey": global_whkey,
                    }
                ],
            }
        )
        print (sendDatas)
        buf = cStringIO.StringIO()
        url = urlserver + "/fflask/NewTransferLotNum"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, sendDatas)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()
        data = buf.getvalue()
        decoded = json.loads(data)
        if str(decoded["status"]) != "OK":
            return json.dumps({"status": str(decoded["status"])})
        else:
            buf.close()
        _tiketcode = str(decoded["response"])
        g.cursor.callproc("sp_AddRegistrerDataPackage", (_tiketcode, _cli, _ruta))
        Responce = g.cursor.fetchall()
        if not Responce:
            g.conn.commit()
        g.cursor.close()
        b = (
            b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
            + _tiketcode
            + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
            + _tiketcode
            + """|}
          {XS;I,0004,0002C6101|}"""
        )
        print (b)
        if connect_to_printers:
            s.send(b)
        s.close()
        return json.dumps({"status": "OK"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# ----- Actializar Palet en template editpalet -------------#
@app.route("/CreateNewEmptyContainer", methods=["POST"])
def CreateNewEmptyContainer():
    try:
        if session.get("user"):
            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))
            _remision = request.form["ruta"]
            _org = session.get("org")

            g.cursor.callproc("sp_getDatasOrg", (_org,))
            # Org_Datas = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            buf = cStringIO.StringIO()
            url = (
                urlserver
                + "/fflask/CheckExistReceptionsRemitions?Alm="
                + global_alm
                + "$$"
                + _remision
            )
            c = pycurl.Curl()
            c.setopt(pycurl.URL, url)
            c.setopt(
                pycurl.HTTPHEADER,
                ["Accept: application/json", "Content-Type: application/json"],
            )
            c.setopt(c.WRITEFUNCTION, buf.write)
            c.perform()
            data = buf.getvalue()
            print (data)
            if str(data) != "OK":
                return json.dumps({"status": str(data)})
            else:
                buf.close()

            g.cursor.callproc("sp_addRemission2", ("das*R" + _remision, _org))
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNewRemission")
                data = g.cursor.fetchall()
                g.cursor.close()
                print (data)
                _container = str(data[0][2])
                print (_container)
                sendDatas = json.dumps(
                    {
                        "status": 1,
                        "response": [
                            {
                                "remision": _remision,
                                "alm": global_alm,
                                "whkey": global_whkey,
                                "org": global_org,
                                "lot": _container,
                            }
                        ],
                    }
                )
                print (sendDatas)
                buf = cStringIO.StringIO()
                url = urlserver + "/fflask/AddNewLotNumReception"
                c = pycurl.Curl()
                c.setopt(pycurl.URL, url)
                c.setopt(
                    pycurl.HTTPHEADER,
                    [
                        "Accept: application/json",
                        "Content-Type: application/json",
                    ],
                )
                c.setopt(pycurl.POST, 1)
                c.setopt(pycurl.POSTFIELDS, sendDatas)
                c.setopt(c.WRITEFUNCTION, buf.write)
                c.perform()
                data = buf.getvalue()
                print (data)
                if str(data) != "OK":
                    return json.dumps(str(data))
                else:
                    buf.close()
                    print (_container)
                    b = (
                        b"""{C|}
              {XB01;0205,0200,T,H,40,A,0,M2="""
                        + _container
                        + """|}
              {PV00;0270,1100,0060,0080,J,00,B="""
                        + _container
                        + """|}
              {XS;I,0004,0002C6101|}"""
                    )
                    if connect_to_printers:
                        s.send(b)
                    s.close()
                    return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# --- Template para crear nuevas etiquetas --- #
@app.route("/ShowPrintNewPalletByClient")
def ShowPrintNewPalletByClient():
    if session.get("user"):
        return render_template(
            "addNewTiket.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintNewTiketsByClient", methods=["POST"])
def PrintNewTiketsByClient():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IP"), TCP_PORT))
        _org = int(session.get("org"))
        g.cursor.callproc("sp_getDatasOrg", (_org,))
        Org_Datas = g.cursor.fetchall()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        _ruta = request.form["ruta"]
        _cli = request.form["cli"]

        sendDatas = json.dumps(
            {
                "status": 1,
                "response": [
                    {
                        "orgkeyOB": "DA2ABCEEBCC24A7C9D2B2BE337CADAE3",
                        "ruta": _ruta,
                        "client": _cli,
                        "alm": global_alm,
                        "position": str(Org_Datas[0][7]),
                    }
                ],
            }
        )
        buf = cStringIO.StringIO()
        url = urlserver + "/fflask/GetAllNewSerialNums"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, sendDatas)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        data = buf.getvalue()
        decoded = json.loads(data)
        if str(decoded["status"]) != "OK":
            return json.dumps({"status": str(decoded["status"])})
        else:
            buf.close()
        datos = decoded["response"]
        i = 0
        for material in datos:
            if i <= len(datos):
                print (len(datos))
                _Material = str(decoded["response"][i]["Material"])
                _Id = str(decoded["response"][i]["Id"])
                _qty = str(decoded["response"][i]["qty"])
                print (_Material, _Id, _qty)
                i += 1
                g.cursor.callproc(
                    "sp_CreateNewOutPalet",
                    (_Material, _qty, _Id, _ruta + ">>" + _cli),
                )
        g.conn.commit()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        i = 0
        for material in datos:
            if i <= len(datos):
                print (len(datos))
                _Material = str(decoded["response"][i]["Material"])
                _Id = str(decoded["response"][i]["Id"])
                _qty = str(decoded["response"][i]["qty"])
                print (_Material, _Id, _qty)
                i += 1
                g.cursor.callproc("sp_GetLastPaletOut", (_Material, _Id))
                DatasPrintin = g.cursor.fetchall()
                print (DatasPrintin)
                pallet = str(DatasPrintin[0][2])
                pallet = str(DatasPrintin[0][2])
                _material = elimina_tildes(DatasPrintin[0][3])
                _neto = str(DatasPrintin[0][4])
                materialkey = (_material).split(" ")[0]
                Descripcion = "Desc:" + _material.replace(materialkey, "")
                txt1 = Descripcion
                txt2 = ""
                if len(Descripcion) > 41:
                    txt1 = Descripcion[:40] + "-"
                    txt2 = Descripcion[40:]
                b = (
                    b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                    + pallet
                    + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                    + materialkey
                    + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                    + _neto
                    + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                    + txt1
                    + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                    + txt2
                    + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                    + pallet
                    + """*|}
                  {XS;I,0001,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)

                sendDatas = json.dumps(
                    {
                        "status": 1,
                        "response": [
                            {
                                "serialnum": pallet,
                                "id": _Id,
                                "materialkey": _Material,
                                "qty": int(_qty.split(".")[0]),
                            }
                        ],
                    }
                )
                buf = cStringIO.StringIO()
                url = urlserver + "/fflask/AddNewSerialNum"
                c = pycurl.Curl()
                c.setopt(pycurl.URL, url)
                c.setopt(
                    pycurl.HTTPHEADER,
                    [
                        "Accept: application/json",
                        "Content-Type: application/json",
                    ],
                )
                c.setopt(pycurl.POST, 1)
                c.setopt(pycurl.POSTFIELDS, sendDatas)
                c.setopt(c.WRITEFUNCTION, buf.write)
                c.perform()
                dtas = buf.getvalue()
                deco = json.loads(dtas)
                if str(deco["status"]) != "OK":
                    buf.close()
                    return json.dumps({"status": str(deco["status"])})
                buf.close()

        g.cursor.close()
        s.close()
        return json.dumps({"status": "OK"})
    except Exception as e:
        return json.dumps({"status": str(e)})


# --- Template para crear nuevas etiquetas --- #
@app.route("/ShowPrintNewLocalTiketPartition")
def ShowPrintNewLocalTiketPartition():
    if session.get("user"):
        return render_template(
            "addNewTiketpartition.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintNewTiketPartition", methods=["POST"])
def PrintNewTiketPartition():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IP"), TCP_PORT))
        _org = int(session.get("org"))
        g.cursor.callproc("sp_getDatasOrg", (_org,))
        # Org_Datas = g.cursor.fetchall()
        g.cursor.close()
        g.cursor = g.conn.cursor()
        _remision = request.form["ruta"]
        _almacen = global_alm

        sendDatas = json.dumps(
            {
                "status": 1,
                "response": [{"id_remision": _remision, "alm": _almacen}],
            }
        )
        buf = cStringIO.StringIO()
        url = urlserver + "/fflask/GetAllNewUPackingPartitionsByRemission"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, sendDatas)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        data = buf.getvalue()
        decoded = json.loads(data)
        if str(decoded["status"]) != "OK":
            return json.dumps({"status": str(decoded["status"])})
        else:
            buf.close()
        datos = decoded["response"]
        i = 0
        for material in datos:
            if i <= len(datos):
                print (len(datos))
                _Material = str(decoded["response"][i]["Material"])
                _Id = str(decoded["response"][i]["Id"])
                _qty = str(decoded["response"][i]["qty"])
                print (_Material, _Id, _qty)
                i += 1
                g.cursor.callproc(
                    "sp_CreateNewOutPalet",
                    (_Material, _qty, _Id, _remision + ">>Part"),
                )
        g.conn.commit()
        g.cursor.close()

        i = 0
        print ("OKOKOOKOK")
        for material in datos:
            if i <= len(datos):
                print (len(datos))
                _Material = str(decoded["response"][i]["Material"])
                _Id = str(decoded["response"][i]["Id"])
                _qty = str(decoded["response"][i]["qty"])
                print (_Material, _Id, _qty)
                i += 1
                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetLastPaletOut", (_Material, _Id))
                DatasPrintin = g.cursor.fetchall()
                g.cursor.close()
                print (DatasPrintin)
                pallet = str(DatasPrintin[0][2])
                pallet = str(DatasPrintin[0][2])
                _material = elimina_tildes(DatasPrintin[0][3])
                _neto = str(DatasPrintin[0][4])
                materialkey = (_material).split(" ")[0]
                Descripcion = "Desc:" + _material.replace(materialkey, "")
                txt1 = Descripcion
                txt2 = ""
                if len(Descripcion) > 41:
                    txt1 = Descripcion[:40] + "-"
                    txt2 = Descripcion[40:]
                b = (
                    b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                    + pallet
                    + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                    + materialkey
                    + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                    + _neto
                    + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                    + txt1
                    + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                    + txt2
                    + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                    + pallet
                    + """*|}
                  {XS;I,0001,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)
                print (b)
                sendDatas = json.dumps(
                    {
                        "status": 1,
                        "response": [{"serialnum": pallet, "id": _Id}],
                    }
                )
                buf = cStringIO.StringIO()
                url = urlserver + "/fflask/AddNewUPackingPartitionsByRemissio"
                c = pycurl.Curl()
                c.setopt(pycurl.URL, url)
                c.setopt(
                    pycurl.HTTPHEADER,
                    [
                        "Accept: application/json",
                        "Content-Type: application/json",
                    ],
                )
                c.setopt(pycurl.POST, 1)
                c.setopt(pycurl.POSTFIELDS, sendDatas)
                c.setopt(c.WRITEFUNCTION, buf.write)
                c.perform()
                dtas = buf.getvalue()
                deco = json.loads(dtas)
                print (str(deco["status"]))
                if str(deco["status"]) != "OK":
                    buf.close()
                    return json.dumps({"status": str(deco["status"])})
                buf.close()

        g.cursor.close()
        s.close()
        return json.dumps({"status": "OK"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# ----- Actializar Palet en template editpalet -------------#
@app.route("/PrintOldToketWithNewQty", methods=["POST"])
def PrintOldToketWithNewQty():
    try:
        s = socket.socket()
        if connect_to_printers:
            s.connect((session.get("TCP_IP"), TCP_PORT))

        _remision = request.form["ruta"]
        _almacen = global_alm

        sendDatas = json.dumps(
            {
                "status": 1,
                "response": [{"id_remision": _remision, "alm": _almacen}],
            }
        )
        buf = cStringIO.StringIO()
        url = urlserver + "/fflask/GetOldToketWithNewQty"
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(
            pycurl.HTTPHEADER,
            ["Accept: application/json", "Content-Type: application/json"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, sendDatas)
        c.setopt(c.WRITEFUNCTION, buf.write)
        c.perform()

        data = buf.getvalue()
        decoded = json.loads(data)
        if str(decoded["status"]) != "OK":
            return json.dumps({"status": str(decoded["status"])})
        else:
            buf.close()
        datos = decoded["response"]

        i = 0

        for material in datos:
            if i <= len(datos):
                print (len(datos))

                _material = decoded["response"][i]["Material"]
                _neto = str(decoded["response"][i]["qty"])
                pallet = str(decoded["response"][i]["pallet"])
                i += 1
                _material = elimina_tildes(_material)
                materialkey = (_material).split(" ")[0]
                Descripcion = "Desc:" + _material.replace(materialkey, "")
                txt1 = Descripcion
                txt2 = ""
                if len(Descripcion) > 41:
                    txt1 = Descripcion[:40] + "-"
                    txt2 = Descripcion[40:]

                b = (
                    b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                    + pallet
                    + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                    + materialkey
                    + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                    + _neto
                    + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                    + txt1
                    + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                    + txt2
                    + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                    + pallet
                    + """*|}
                  {XS;I,0001,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)

        s.close()
        return json.dumps({"status": "OK"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


# --- obtener todas las remisiones no Finalizadas --- #
@app.route("/getAllNumbersRoutes", methods=["POST"])
def getAllNumbersRoutes():
    try:
        if session.get("user"):
            _limit = 15
            _offset = request.form["offset"]
            _org = session.get("org")

            g.cursor.execute(
                "call sp_GetAllRoutes(%s,%s,%s,@p_total)",
                (_limit, _offset, _org),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            response = []
            materials_dict = [{"Id": "Ruta ID", "Date": "Fecha", "Alm": "Almacen"}]
            for material in materials:
                material_dict = {
                    "Id": material[0],
                    "Date": str(material[1]),
                    "Alm": str(material[2]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})
            print (response)
            return json.dumps(response)
        else:
            return json.dumps("Unauthorized Access")
    except Exception as e:
        print (e)
        return json.dumps(str(e))


# ---- obtener Palets de una remision Finalizada ---- #
@app.route("/getNewPalletsByRoute", methods=["POST"])
def getNewPalletsByRoute():
    try:
        if session.get("user"):
            # _user = session.get("user")
            _numFR = request.form["id"]
            print (_numFR)
            g.cursor.execute("call sp_GetPaletsByRouteId(%s,@p_total)", (_numFR,))
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()

            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Id": int(material[0]),
                    "Code": str(material[1]),
                    "Material": str(material[2]),
                    "client": str(material[3]),
                    "Date": str(material[4]),
                    "Neto": str(material[5]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})

            return json.dumps(response)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


# --- Template para crear nuevas etiquetas --- #
@app.route("/ShowPrintNewTiketProduct")
def ShowPrintNewTiketProduct():
    if session.get("user"):
        return render_template(
            "printtiketp.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/showRemissionWithContainer")
def showRemissionWithContainer():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar en produccion: 2020-12-07
    """
    return render_template("newremissioncontainer.html")


@app.route("/NewRemissionContainer", methods=["POST"])
def NewRemissionContainer():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar en produccion: 2020-12-07
    """
    try:
        if session.get("user"):
            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))
            _remission = str(request.form["remision"])
            _container = str(request.form["contenedor"])
            _org = session.get("org")
            _user = session.get("user")

            g.cursor.callproc(
                "sp_addRemissionContainerExist",
                (_remission, _container, _org, _user),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNewRemission")
                data = g.cursor.fetchall()
                g.cursor.close()

                b = (
                    b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
                    + _container
                    + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
                    + _container
                    + """|}
          {XS;I,0004,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)
                s.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print (e)
        return json.dumps({"status": str(e)})


@app.route("/getRemissionAndContainerByEdit", methods=["POST"])
def getRemissionAndContainerByEdit():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar en produccion: 2020-12-07
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            # _user = session.get("user")

            g.cursor.callproc("sp_GetNumRemissionByEditOrg", (_id,))
            result = g.cursor.fetchall()

            material = []
            material.append(
                {
                    "Id": _id,
                    "Remission": str(result[0][0]),
                    "Organization": str(result[0][2]),
                    "Container": str(result[0][3]),
                }
            )
            return json.dumps(material)
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/updateRemissionAndComtainer", methods=["POST", "GET"])
def updateRemissionAndComtainer():
    """
    Dudo  Fecha fuera de funcion: 2020-08-07
    Fecha para Retirar en produccion: 2020-12-07
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _num = request.form["number"]
            _container = request.form["container"]
            _org = session.get("orgname")

            g.cursor.callproc(
                "sp_EditRemissionAndContainer", (_id, _num, _container, _org)
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "ERROR"})
    except Exception:
        return json.dumps({"status": "Unauthorized Access"})
    return json.dumps({"status": "ERROR"})


@app.route("/ShowPrintTicketRack")
def ShowPrintTicketRack():
    """
    Nueva funcion para mostrar la pantalla para impresion de etiquetas.
    Parametros:
        No requiere parametros
    Return:
        return render_template("etiquetasRack.html")
        Redirige al archivo etiquetasRack.html
    """
    if session.get("user"):
        return render_template("etiquetasRack.html")
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/PrintTicketRack", methods=["POST"])
def PrintTicketRack():
    """
    Nueva funcion para imprimir etiquetas para rack
    Parametros:
        _ticket = str(request.form['desc'])
        Es el nombre del rack que se va a imprimir en la etiqueta
    Return:
        return json.dumps({'status': 'OK'})
        Devuelve el status en formato json
    """
    try:
        if session.get("user"):
            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))
            _ticket = str(request.form["desc"])

            b = (
                b"""{C|}
                {XB01;0200,1100,T,H,40,A,3,M2="""
                + _ticket
                + """|}
                {XS;I,0001,0002C6101|}"""
            )
            if connect_to_printers:
                s.send(b)
            s.close()

            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))

            b = (
                b"""{C|}
                {PV00;0800,1500,0500,0700,J,33,B="""
                + _ticket
                + """|}
                {XS;I,0001,0002C6101|}"""
            )
            if connect_to_printers:
                s.send(b)
            s.close()

            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        print e
        return json.dumps({"status": str(e)})


# New function to add pallets into remission #
@app.route("/addPalletToRemission", methods=["POST", "GET"])  # noqa
def addPalletToRemission():
    """
    Nueva funcion para agregar pallets a una remision.
    Parametros:
        _numRemision = Es el nombre de la remision
        _printer = la impresora a la que se manda la informacion
        _material = el material a agregar
        _peso = el peso del material
        _id = el id de la remision
        _unidad = la cantidad de material que se agrega en el pallet
        _lote = es el pallet a agregar
        _etiquetas = la cantidad de etiquetas a imprimir
    Return
        return json.dumps({'status':'OK'})
        Devuelve el status en formato json
    """
    try:
        s = socket.socket()
        if session.get("user"):
            _user = session.get("user")
            _org = session.get("org")
            _numRemision = request.form["remision"]  # Nombre de la remision
            _printer = session.get("TCP_IP")
            _material = request.form["material"]
            _peso = request.form["peso"]
            _id = request.form["idr"]  # Id de la remision
            _unidad = request.form["unidad"]
            _lote = request.form["lote"]
            _etiquetas = int(request.form["etiquetas"])
            if (
                _numRemision != "0"
                or _numRemision != 0
                or _numRemision is not None
                or _id != "0"
                or _id != 0
                or _id is not None
            ):
                g.cursor.callproc(
                    "sp_addProductsByRemission", (_material, _peso, _org, _id)
                )
                data = g.cursor.fetchall()
                if not data:
                    g.conn.commit()

                s.connect((_printer, TCP_PORT))

                g.cursor.callproc("sp_GetLocation", (_material,))
                locat = g.cursor.fetchall()
                locat1 = ""
                if len(locat) == 1:
                    locat1 = locat[0][0]
                elif len(locat) > 1:
                    for i in locat:
                        locat1 = locat1 + " " + i[0]
                materialkey = (_material).split(" ")[0]
                Descripcion = "Desc:" + str(
                    re.sub(
                        r"[^a-zA-Z0-9]+",
                        " ",
                        _material.replace(materialkey, ""),
                    )
                )
                txt1 = Descripcion
                txt2 = ""
                if len(Descripcion) > 41:
                    txt1 = Descripcion[:40] + "-"
                    txt2 = Descripcion[40:]
                    txt1 = elimina_tildes(txt1)
                    txt2 = elimina_tildes(txt2)
                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNumRemission", (_id, _user))
                result = g.cursor.fetchall()
                if not result or str(result[0][0]) == "None":
                    return json.dumps({"status": "Acceso no autorizado en la remisión"})
                remisionNum = result[0][0]
                g.cursor.close()
                if _numRemision != remisionNum:
                    return json.dumps({"status": "ERRORNUM2"})
                for _tiket in range(_etiquetas):
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc("sp_CreateNewPalet", (materialkey, _unidad, _id))
                    data = g.cursor.fetchall()

                    if not data:
                        g.conn.commit()

                    g.cursor.close()
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc("sp_GetLastPaletByEdit", (_numRemision,))
                    datap = g.cursor.fetchall()
                    pallet = str(datap[0][2])
                    g.cursor.close()

                    _bruto = 0
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc(
                        "sp_UpdateLastPalet",
                        (_numRemision, _material, _unidad, _bruto, _lote),
                    )
                    datasr = g.cursor.fetchall()
                    if not datasr and locat1 == "":
                        g.conn.commit()
                        b = (
                            b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                            + pallet
                            + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                            + materialkey
                            + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                            + _unidad
                            + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                            + txt1
                            + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                            + txt2
                            + """|}
                  {PV02;0004,0493,0025,0025,J,00,B=Ubicacion: """
                            + locat1
                            + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                            + pallet
                            + """_"""
                            + str(_user)
                            + """|}
                  {XS;I,0001,0002C6101|}"""
                        )
                        s.send(b)
                        g.cursor.close()
                    elif not datasr and locat1 != "":
                        g.conn.commit()
                        b = (
                            b"""{C|}
                  {XB01;0635,0070,T,H,18,A,0,M2="""
                            + pallet
                            + """|}
                  {PV01;0004,0138,0060,0100,J,00,B=SIEMENS Gamesa|}
                  {PV02;0004,0258,0030,0050,J,00,B=Ref:"""
                            + materialkey
                            + """|}
                  {PV02;0004,0323,0030,0050,J,00,B=Cant.Packing: """
                            + _unidad
                            + """|}
                  {PV02;0004,0383,0025,0045,J,00,B="""
                            + txt1
                            + """|}
                  {PV02;0004,0443,0025,0045,J,00,B="""
                            + txt2
                            + """|}
                  {PV02;0004,0493,0025,0025,J,00,B=Ubicacion: """
                            + locat1
                            + """|}
                  {PV02;0640,0450,0025,0045,J,00,B="""
                            + pallet
                            + """_"""
                            + str(_user)
                            + """|}
                  {XS;I,0001,0002C6101|}"""
                        )
                        s.send(b)
                        g.cursor.close()
                s.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "ERRORNUM1"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps(
            {"status": "Error reiniciar o conectar la impresora porfavor <br>" + str(e)}
        )


@app.route("/deletePalletToRemission", methods=["POST"])
def deletePalletToRemission():
    """
    Nueva funcion para eliminar pallets de una remision
    Parametros:
        _id = id de la remision
    Return:
        return json.dumps({"status": "OK"})
        Devuelve el status en formato json
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _user = session.get("user")
            g.cursor.callproc("sp_deleProductsByRemission", (_id, _user))
            result = g.cursor.fetchall()
            if not result:
                g.conn.commit()
            g.cursor.callproc("sp_deletNewPallet", (_id,))
            result = g.cursor.fetchall()
            if not result:
                g.conn.commit()
            return json.dumps({"status": "OK"})
        else:
            return json.dumps({"status": "An Error occured"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


@app.route("/ShowAddPackingListInfo")
def ShowAddPackingListInfo():
    """
    Template donde podemos agregar, editar o eliminar al sistema informacion primaria
    de un packinglist de entrada (Numero Doc. Cantidad de Bultos).
    Parametros:
    Return:
        Renderiza addPackingListInfo.html con
        variables nombre de usuario y organizacion.
    """
    if session.get("user"):
        return render_template(
            "addPackingListInfo.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/AddPackingListInfo", methods=["POST", "GET"])
def AddPackingListInfo():
    """
    Agrega un nuevo registro de Num. Doc PackingList
    de entrada a la tbl_info_packinglist.
    Parametros:
        _transporte: Numero de Documento o Numero de
            transporte el cual es el indentificador de un PackingList.
        _fecha: Fecha del documento PackingList.
        _peso: Peso Bruto total en KG PackingList.
        _volumen: Volumen total en M3 PackingList.
        _unidades: Cantidad de Bultos del PackingList.
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _transporte = request.form["Transporte"]
            _fecha = request.form["Fecha"]
            _peso = request.form["Peso"]
            _volumen = request.form["Volumen"]
            _unidades = request.form["Unidades"]
            _user = session.get("user")

            g.cursor.callproc(
                "sp_AddPackingListInfo",
                (
                    _transporte,
                    _fecha,
                    _peso,
                    _volumen,
                    _unidades,
                    _user,
                ),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": (data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/GetAllsPackingListInfo", methods=["POST"])
def GetAllsPackingListInfo():
    """
    Obtiene la lista de PackingsList de entrada filtrados por limite y paginacion.
    Parametros:
        _limit: Limete de registros a obtener.
        _offset: Numero de paginacion.
    Retorno: Objeto Json con la lista de registros PackingList encontrados en la BD
    & el total numero total de registros de PackingList.
    """
    try:
        if session.get("user"):
            _limit = request.form["limit"]
            _offset = request.form["offset"]

            g.cursor.execute(
                "call sp_GetAllsPackingListInfo(%s,%s,@p_total)",
                (_limit, _offset),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Transporte": "Doc. Transporte",
                    "Fecha": "Fecha",
                    "Peso": "Peso",
                    "Volumen": "Volumen",
                    "Unidades": "Bultos Documentados",
                    "UnidadesExtra": "Bultos No Documentados",
                    "Creado": "Fecha De Registro",
                }
            ]
            for material in materials:
                material_dict = {
                    "Id": (material[0]),
                    "Transporte": (material[1]),
                    "Fecha": str(material[2]),
                    "Peso": str(material[3]) + " KG",
                    "Volumen": str(material[4]) + " M3",
                    "Unidades": str(material[5]),
                    "CreadoPor": (material[6]),
                    "Creado": str(material[7]),
                    "ActualizadoPor": (material[8]),
                    "Actualizado": str(material[9]),
                    "EtiquetadoIniciado": int(material[10]),
                    "UnidadesExtra": str(material[11]),
                    "CreadoTitle": str(material[12]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})
            return json.dumps(response)
        else:
            return json.dumps({"error": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@app.route("/UpdatePackingListInfo", methods=["POST", "GET"])
def UpdatePackingListInfo():
    """
    Actualiza un registro de un PackingList de entrada.
    Parametros:
        _id: Id PackingList.
        _fecha: Fecha PackingList a actualizar.
        _peso: Peso Bruto total en KG PackingList a actualizar.
        _volumen: Volumen total en M3 PackingList a actualizar.
        _unidades: Cantidad de Bultos del PackingList a actualizar.
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["Id"]
            _fecha = request.form["Fecha"]
            _peso = request.form["Peso"]
            _volumen = request.form["Volumen"]
            _unidades = request.form["Unidades"]
            _user = session.get("user")

            g.cursor.callproc(
                "sp_UpdatePackingListInfo",
                (
                    _id,
                    _fecha,
                    _peso,
                    _volumen,
                    _unidades,
                    _user,
                ),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/DeletedPackingListInfo", methods=["POST", "GET"])
def DeletedPackingListInfo():
    """
    Actualiza el status de un registro de un PackingList de entrada a Eliminado.
    Parametros:
        _id: Id PackingList.
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["Id"]
            _user = session.get("user")

            g.cursor.callproc(
                "sp_DeletedPackingListInfo",
                (
                    _id,
                    _user,
                ),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ShowAddPackageInformation/<Id>")
def ShowAddPackageInformation(Id):
    """
    Muestra el Template donde podemos agregar los numeros de bulto
    de un PackingList de entrada & a cada bulto agregarle las Referencias
    (Materiales) que contienen segun el PackingList.
    Parametros:
    Retorno: Renderiza addPackageInfo.html con
        session_user_name: Nombre de usuario.
        orgname: Nombre Organizacion.
        Id: Id PackingList.
        Transport: Numero de Documento - Transporte.
        Bults: Numero de Bultos.
        PackagingDatas: Tipos de embalaje.
        DatasPackages: Datos existentes de Bultos
            (Numeros bulto con su tipo embalaje y APILABLE/REMONTABLE ).
        LenDatasPackages: Cantidad de Registros de Bultos
            existentes en la DB que pertenecen al PackingList.
        DatasSR: ["Apilable", "Remontable"],
        StatusForm= estado del formulario primario donde
            se agregan los datos principales de un bulto.
    """
    try:
        if session.get("user"):

            g.cursor.callproc(
                "sp_GetPackingListInfoById",
                (Id,),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            g.cursor = g.conn.cursor()
            g.cursor.callproc("sp_GetPackagingDatas")
            data2 = g.cursor.fetchall()
            g.cursor.close()

            PackagingDatas = []
            for packaging in data2:
                PackagingDatas.append([int(packaging[0]), packaging[1]])

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetPackagesInfoByPackingId",
                (Id,),
            )
            data3 = g.cursor.fetchall()
            g.cursor.close()
            DatasPackages = []
            # Enviar el len de DatasPackages para validar if
            if len(data) > 0:
                i = 0
                for package in data3:
                    if i < int(data[0][5]):
                        DatasPackages.append(
                            [
                                int(package[0]),
                                int(package[1]),
                                str(package[2]),
                                int(package[3]),
                                (package[4]),
                                str(package[5]),
                            ]
                        )
                    i += 1
                _statusForm = "incomplete"
                if int(data[0][5]) == len(DatasPackages) and int(data[0][5]) > 0:
                    _statusForm = "completed"
                return render_template(
                    "addPackageInfo.html",
                    session_user_name=session["username"],
                    orgname=session["orgname"],
                    Id=Id,
                    Transport=str(data[0][1]),
                    Bults=int(data[0][5]),
                    PackagingDatas=PackagingDatas,
                    DatasPackages=DatasPackages,
                    LenDatasPackages=len(DatasPackages),
                    DatasSR=["Apilable", "Remontable"],
                    StatusForm=_statusForm,
                    StartTagged=int(data[0][6]),
                    Finished=int(data[0][7]),
                )
            else:
                flash("La accion no fue permitida intente nuevamente")
                return redirect("/ShowAddPackingListInfo")
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        flash("danger:: " + str(e))
        return redirect("/")


@app.route("/AddPackageInformation", methods=["POST", "GET"])  #
def AddPackageInformation():
    """
    Agrega la informacion primaria de los bultos de un PackingList de entrada.
    Parametros:
        _Id: Id PackingList.
        _BultsDatas: Numeros de bulto delimitados por una coma,
        _DatasPackagingType: Tipos de envalaje por bulto.
        _DatasStackableRemovable: tipo apilable o remontable por cada bulto.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["_Id"]
            _BultsDatas = request.form["DatasBults"]
            _DatasPackagingType = request.form["DatasPackagingType"]
            _DatasStackableRemovable = request.form["DatasStackableRemovable"]
            _user = session.get("user")

            g.cursor.callproc(
                "sp_DeletedPackageByIdPacking",
                (
                    _id,
                    _user,
                ),
            )
            g.conn.commit()
            g.cursor.close()

            i = 0
            for NumBult in _BultsDatas.split(","):
                bult = NumBult.replace('"', "")
                a = str(_DatasPackagingType.split(",")[i]).replace('"', "")
                b = str(_DatasStackableRemovable.split(",")[i]).replace('"', "")
                i += 1

                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_AddPackageInfo",
                    (
                        _id,
                        bult,
                        a,
                        b,
                        _user,
                    ),
                )
                data = g.cursor.fetchall()
                if len(data) > 0:
                    return json.dumps({"status": str(data[0][0])})
                g.conn.commit()
                g.cursor.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ValidateProductExistence", methods=["POST", "GET"])
def ValidateProductExistence():
    """
    Validar la existencia de un producto en la tabla tbl_materials.
    Parametros:
        _referencia: Indentificador de referencia del material ejemplo: GP019441.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        _referencia = request.form["Referencia"]
        g.cursor.callproc(
            "sp_ValidateProductExistence",
            (_referencia,),
        )
        data = g.cursor.fetchall()
        g.cursor.close()
        return json.dumps({"status": str(data[0][0])})

    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/AddReferenceByPackage", methods=["POST", "GET"])
def AddReferenceByPackage():
    """
    Agregar Referencias (Materiales) con cantidad y tipo de Unidad de Medida
    por bulto de un PackingList.
    Parametros:
        _id: Id PackingList.
        _references: Datos con (
            Indentificador Material "Referencia"
            +Num. Bulto
            +Cantidad
            +Unidad de Medida).
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    Dudo 2020-09-16 si no se utiliza esta funcion
    dar de baja el dia 2021-03-16.
    """
    try:
        if session.get("user"):
            _id = request.form["PackingListId"]
            _references = request.form["References"]
            _user = session.get("user")

            g.cursor.callproc(
                "sp_DeletedReferenceByPackage",
                (
                    _id,
                    _user,
                ),
            )
            g.conn.commit()
            g.cursor.close()

            for reference in _references.split(","):
                _reference = reference.replace('"', "")
                if _reference == "":
                    return json.dumps({"status": "OK"})
                idreference = _reference.split("->>")[0]
                if str(idreference) == "GP052022":
                    print "OK"
                numbult = _reference.split("->>")[1]
                qty = _reference.split("->>")[2]
                uoM = _reference.split("->>")[3]
                try:
                    g.cursor = g.conn.cursor()
                    g.cursor.callproc(
                        "sp_AddReferenceByPackage",
                        (
                            idreference,
                            numbult,
                            _id,
                            qty,
                            uoM,
                            _user,
                            "",
                            0,
                        ),
                    )
                    g.conn.commit()
                    g.cursor.close()
                except Exception as e:
                    e

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/AddOneReferenceByPackage", methods=["POST", "GET"])
def AddOneReferenceByPackage():
    """
    Agregar una referencia a un numero de bulto de un packinglist.
    Parametros:
        _id: Id PackingList.
        _references: Indentificador Material "Referencia"
        _numbult: Num. Bulto
        _qty: Cantidad
        _uoM: Unidad de Medida
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["PackingListId"]
            _reference = request.form["Reference"]
            _numbult = request.form["NumBult"]
            _qty = request.form["Qty"]
            _uoM = request.form["UoM"]
            _user = session.get("user")

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_AddReferenceByPackage",
                (
                    _reference,
                    _numbult,
                    _id,
                    _qty,
                    _uoM,
                    _user,
                    "",
                    0,
                ),
            )
            g.conn.commit()
            g.cursor.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/DeleteOneReferenceByPackage", methods=["POST", "GET"])
def DeleteOneReferenceByPackage():
    """
    Eliminar una referencia a un numero de bulto de un packinglist.
    Parametros:
        _id: Id PackingList.
        _references: Indentificador Material "Referencia"
        _numbult: Num. Bulto
        _qty: Cantidad
        _uoM: Unidad de Medida
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["PackingListId"]
            _reference = request.form["Reference"]
            _numbult = request.form["NumBult"]
            _qty = request.form["Qty"]
            _uoM = request.form["UoM"]
            _user = session.get("user")

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_DeletedOneReferenceByPackage",
                (
                    _reference,
                    _numbult,
                    _id,
                    _qty,
                    _uoM,
                    _user,
                ),
            )
            g.conn.commit()
            g.cursor.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/GetReferenceByPackage", methods=["POST"])
def GetReferenceByPackage():
    """
    Obtiene las referencias (Materiales) por numero
    de bulto de un PackingList de entrada.
    Parametros:
        _package: Numero de bulto.
        _packing: Id de PackingList de entrada.
    Retorno: Objeto Json con la lista de registros de referencias encontrados en la BD.
    """
    try:
        if session.get("user"):
            _package = request.form["Package"]
            _packing = request.form["PackingListId"]

            g.cursor.execute(
                "call sp_GetReferenceByPackage(%s,%s)",
                (_package, _packing),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = []
            for material in materials:
                material_dict = {
                    "Material": (material[0]),
                    "Qty": str(material[1]),
                    "UoM": (material[2]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            return json.dumps(response)
        else:
            return json.dumps({"error": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@app.route("/ShowCreateUnDocumentedPackage/<Id>")
def ShowCreateUnDocumentedPackage(Id):
    """
    Vista donde podemos crear bultos no documentados de un packinglist.
    Parametros:
    Retorno: Renderiza createUnDocumentedPackage.html
    """
    try:
        if session.get("user"):

            g.cursor.callproc(
                "sp_GetPackingListInfoById",
                (Id,),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetUnDocumentedPackagesByPackingId",
                (Id,),
            )
            data3 = g.cursor.fetchall()
            g.cursor.close()
            DatasPackages = []
            # Enviar el len de DatasPackages para validar if
            if len(data) > 0:
                for package in data3:
                    DatasPackages.append(
                        [
                            int(package[0]),
                            int(package[1]),
                            str(package[2]),
                            int(package[3]),
                            (package[4]),
                            str(package[5]),
                        ]
                    )
                _statusForm = "incomplete"
                if len(DatasPackages) > 0 and int(data[0][5]) > 0:
                    _statusForm = "completed"

                return render_template(
                    "createUnDocumentedPackage.html",
                    session_user_name=session["username"],
                    orgname=session["orgname"],
                    Id=Id,
                    Transport=str(data[0][1]),
                    Bults=len(DatasPackages),
                    StatusForm=_statusForm,
                    Finished=int(data[0][7]),
                    DatasPackages=DatasPackages,
                    LenDatasPackages=len(DatasPackages),
                )
            else:
                flash("La accion no fue permitida intente nuevamente")
                return redirect("/ShowAddPackingListInfo")
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        flash("danger:: " + str(e))
        return redirect("/")


@app.route("/CreateUnDocumentedPackage", methods=["POST", "GET"])
def CreateUnDocumentedPackage():
    """
    Crea un numero de bulto no documentado de un packinglist de entrada.
    Parametros:
        _Id: Id PackingList.
        _BultsDatas: Numeros de bulto delimitados por una coma,
        _DatasPackagingType: Tipos de envalaje por bulto.
        _DatasStackableRemovable: tipo apilable o remontable por cada bulto.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["_Id"]
            _BultsDatas = request.form["DatasBults"]
            _user = session.get("user")
            g.cursor.callproc(
                "sp_DeletedUnDocumentedPackageByIdPacking",
                (
                    _id,
                    _user,
                ),
            )
            g.conn.commit()
            g.cursor.close()
            if str(_BultsDatas) == '""':
                return json.dumps({"status": "OK"})
            for NumBult in _BultsDatas.split(","):
                bult = NumBult.replace('"', "")

                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_AddUnDocumentedPackage",
                    (
                        _id,
                        bult,
                        1,
                        "",
                        _user,
                    ),
                )
                data = g.cursor.fetchall()
                if len(data) > 0:
                    return json.dumps({"status": str(data[0][0])})
                g.conn.commit()
                g.cursor.close()

            return json.dumps({"status": "OK"})

        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ShowLabelMaterial/<Id>")
def ShowLabelMaterial(Id):
    """
    Vista donde podemos ver los bultos de un packinglist
    y seleccionar uno para agregarle etiqetas.
    Parametros:
        _user: Id usuario.
    Retorno: Renderiza el template addContainersByPacking.html
    """
    try:
        if session.get("user"):
            # _user = session.get("user")
            g.cursor.callproc(
                "sp_GetPackingListInfoById",
                (Id,),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            return render_template(
                "labelMaterialByPackage.html",
                session_user_name=session["username"],
                orgname=session["orgname"],
                Id=Id,
                Transport=str(data[0][1]),
                Finished=int(data[0][7]),
            )
        else:
            flash("warning:: Acceso no autorizado")
            return redirect("/")
    except Exception as e:
        flash("danger:: " + str(e))
        return redirect("/")


@app.route("/getAllPackageByPackingList", methods=["POST"])
def getAllPackageByPackingList():
    """
    Obtiene la lista de todos los bultos de un packinglist.
    Parametros:
        _packing: Id PackingList.
    Retorno:
        Objeto Json con la lista de bultos y sus atributos.
    """
    try:
        if session.get("user"):
            _packing = request.form["packing"]

            g.cursor.execute(
                "call sp_GetAllPackagesByPackingId(%s)",
                (_packing,),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Package": "No. Bulto",
                    "DocumentStatus": "Bulto Documentado",
                    "Container": "Contenedor",
                    "Diff": "Diferencias Etiquetado vs Documentado",
                }
            ]
            for material in materials:
                DiffStatus = 0
                if int(material[4]) != 0:
                    callfuntion = GetDiffPackageInfoVsLabelled(
                        _packing,
                        str(material[2]),
                        str(material[6]),
                    )
                    if callfuntion[0] == "OK":
                        for Error in callfuntion[1]:
                            if not str(Error["differencesQty"]) in ("0", "Diferencias"):
                                DiffStatus = 1
                material_dict = {
                    "Id": material[0],
                    "PackingId": str(material[1]),
                    "Package": str(material[2]),
                    "DocumentStatus": str(material[3]),
                    "StatusContainer": int(material[4]),
                    "Container": str(material[5]),
                    "IdContainer": str(material[6]),
                    "StatusLabelledContainer": int(material[7]),
                    "StatusFinishContainer": int(material[8]),
                    "Diff": DiffStatus,
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            return json.dumps(response)
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/addContainerToPackageOfPackingList", methods=["POST"])
def addContainerToPackageOfPackingList():
    """
    Agrega un nuevo contenedor a tbl_remission y la liga a un PackingList
    por medion de packing_id, e imprime la etiqueta del contendor creado.
    Parametros:
        _remision: Num. Doc. Transporte del PackingList.
        _packing: Id PackingList.
        _org: Id Organizacion.
        _user: Id Usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            s = socket.socket()
            if connect_to_printers:
                s.connect((session.get("TCP_IPM"), TCP_PORT))
            _packing = request.form["packing"]
            _package = request.form["packange"]
            _packageId = request.form["Id"]
            _org = session.get("org")
            _user = session.get("user")

            g.cursor.callproc(
                "sp_AddContainerToPackageOfPackingList",
                (
                    _org,
                    _user,
                    _packing,
                    _package,
                    _packageId,
                ),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc("sp_GetNewRemission")
                data = g.cursor.fetchall()
                g.cursor.close()
                _container = str(data[0][2])

                b = (
                    b"""{C|}
            {XB01;0205,0200,T,H,40,A,0,M2="""
                    + _container
                    + """|}
            {PV00;0270,1100,0060,0080,J,00,B="""
                    + _container
                    + """|}
          {XS;I,0004,0002C6101|}"""
                )
                if connect_to_printers:
                    s.send(b)
                s.close()
                return json.dumps({"status": "OK", "Id": int(data[0][0])})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps(
            {"status": "Error reiniciar o conectar la impresora porfavor <br>" + str(e)}
        )


@app.route("/ShowAddPackagingUnitsPerPackaging/<_id>", methods=["POST", "GET"])
def ShowAddPackagingUnitsPerPackaging(_id):
    """
    Vista donde muestra el formulario para agregar unidades de empaque a un contenedor
    y la lista de unidades de empaques que pertenecen aun contenedor.
    Parametros: _id: Id contenedor (tbl_remission > remission_id).
    Retorno: rederiza al template addPackagingUnitsPerPackaging.html
    """
    try:
        if session.get("user"):

            g.cursor.callproc("sp_GetNumRemissionByEditOrg", (_id,))
            data = g.cursor.fetchall()
            g.cursor.close()

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetPackingListInfoById",
                (int(data[0][4]),),
            )
            data2 = g.cursor.fetchall()
            g.cursor.close()
            return render_template(
                "addPackagingUnitsPerPackaging.html",
                session_user_name=session["username"],
                orgname=session["orgname"],
                Remision=str(data[0][0]),
                ContainerId=_id,
                container=str(data[0][3]),
                PackingId=str(data[0][4]),
                Transport=str(data2[0][1]),
                StatusFinishLabeling=int(data[0][5]),
                StatusSendingDatas=int(data[0][6]),
                PrinterName=session["NamePrinterPacking"],
                Finished=int(data2[0][7]),
            )
        else:
            return render_template("error.html", error="Unauthorized Access")
    except Exception as e:
        return render_template("error.html", error=str(e))


@app.route("/ValidatePackingMaterialForPrintLabels", methods=["POST"])
def ValidatePackingMaterialForPrintLabels():
    """
    Permite evaluar un contenedor con tbl_remission > packing_id != 0,
    los siguientes situaciones.
    Si el material que se agrega al contendor no es localizado en
    los materiales del packingList al cual esta ligado. Si no esta ligado,
    envia una advertencia donde el usuario decide si agrega o declina el
    material a agregar en el contenedor.
    Si el contenedor esta marcado como etiquetado finalizado esto en
    tbl_remission > prepared_remission = 1, si es uno no permite agregar
    mas etiquetas.
    Si los datos del contendor ya fueron enviados a DASLabel si ya fureron
    no permite mas modificaciones en el contenedor.
    Parametros:
        _material: Id Material o Id referencia.
        _packing: Id PackingList.
        _remission: Id contenedor (tbl_remission > remission_id)
        _qty: Cantidad * unidades a crear etiquetas.
        _bulto: Numero de bulto.
        _IdContainer: Id contenedor.
    Retorno: Objeto Json donde
        "status":
            "OK" => No hay ninguna advertencia.
            "Block" => Etiquetado Bloqueado.
            "Finish" => Datos enviados a DASlabel.
            "False" => Material sin registro en packinglist.
            "Mayor1" => cantidad a etiquetar mayor a la del bulto
                y posiblemente mayor al total del packinglist.
            "Mayor2" => material no localizado en el bulto,
                pero si en el packinglist manda status de cantidades
                packinglist vs etiquetado + solicitado.
            "or Exceptions or application errors."
    """
    try:
        if session.get("user"):
            _material = request.form["material"]
            _packing = request.form["packingId"]
            _remission = request.form["remissionId"]
            _qty = request.form["qty"]
            _bulto = request.form["bultNum"]

            g.cursor.callproc(
                "sp_ValidatePackingMaterialForPrintLabels",
                (
                    _material,
                    _packing,
                    _remission,
                    _bulto,
                ),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            if str(data[0][0]) == "OK1":
                callfuntion1 = CheckReferenceOfPackage(
                    _material, _packing, _qty, _bulto, _remission
                )
                if callfuntion1[0] == "InBult":
                    callfuntion = CheckTheQtyToPrintedIsLess(_material, _packing, _qty)
                    if callfuntion[0] == "Mayor":
                        return json.dumps(
                            {
                                "status": "Mayor1",
                                "Qty": str(callfuntion[1]),
                                "QtyC": str(callfuntion[2]),
                                "QtyN": str(callfuntion[3]),
                                "QtyR": str(callfuntion[4]),
                                "BultQtyS": str(callfuntion1[1]),
                                "BultQty": str(callfuntion1[2]),
                                "BultQtyLabeling": str(callfuntion1[3]),
                                "BultQtyNew": str(callfuntion1[4]),
                            }
                        )
                else:
                    callfuntion = CheckTheQtyToPrintedIsLess(_material, _packing, _qty)
                    if callfuntion[0] == "Mayor":
                        if float(callfuntion[1]) == 0:
                            return json.dumps({"status": "OK"})
                        return json.dumps(
                            {
                                "status": "Mayor3",
                                "Qty": str(callfuntion[1]),
                                "QtyC": str(callfuntion[2]),
                                "QtyN": str(callfuntion[3]),
                                "QtyR": str(callfuntion[4]),
                            }
                        )
                    else:
                        return json.dumps({"status": str(callfuntion[0])})

            elif str(data[0][0]) == "OK2":
                callfuntion = CheckTheQtyToPrintedIsLess(_material, _packing, _qty)
                if callfuntion[0] == "Mayor":
                    return json.dumps(
                        {
                            "status": "Mayor2",
                            "Qty": str(callfuntion[1]),
                            "QtyC": str(callfuntion[2]),
                            "QtyN": str(callfuntion[3]),
                            "QtyR": str(callfuntion[4]),
                        }
                    )
                else:
                    return json.dumps({"status": str(callfuntion[0])})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


def CheckReferenceOfPackage(_material, _packing, _qty, _bulto, _IdContainer):
    """
    Verifica si la cantidad a etiquetar mas la cantidad total en el contenedor
    no se amayor a la cantidad registrada en un bulto.
    Parametros:
        _material: referencia + descripcion.
        _packing: Id PackingList.
        _qty: cantidad.
        _bulto: Numero de bulto.
        _IdContainer: Id contenedor.
    Retorno: si la cantidad a etiquetar mas la acomulada en el contenedor
        es menor o igual al total regisrado en el bulto manda ["OK"] else:
        retorna un areglo con las cantidades de diferencias, total bulto,
        total etiquetado en contenedor, nueva cantidad solicitada.
    """
    try:
        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetQtyReferenceByPackage",
            (
                _bulto,
                _packing,
                _material,
            ),
        )
        QtyReference = g.cursor.fetchall()
        g.cursor.close()

        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetQtyReferenceCumulativeByCotainer",
            (
                _IdContainer,
                _material,
            ),
        )
        CumulativeQty = g.cursor.fetchall()
        g.cursor.close()

        if float(QtyReference[0][0]) >= float(CumulativeQty[0][0]) + float(_qty):
            return ["OK"]
        else:
            cantidadDeMas = (
                float(CumulativeQty[0][0]) + float(_qty) - float(QtyReference[0][0])
            )
            return [
                "InBult",
                cantidadDeMas,
                float(QtyReference[0][0]),
                float(CumulativeQty[0][0]),
                float(_qty),
            ]
    except Exception as e:
        return str(e)


def CheckTheQtyToPrintedIsLess(_material, _packing, _qty):
    """
    Verifica si la cantidad a etiquetar de un packinglist
    mas la cantidad ya etiquetada es mayor a la cantidad
    indicada en el packinglist.
    Parametros:
        _material: Referencia + descripcion del material.
        _packing: Id packinglist.
        _qty: Cantidad nueva solicitada a etiquetar.
    Retorno: Arreglo [] donde el dato [0]="Mayor" indica que la suma de
    lo acomulado + lo solicitado es mayor a lo indicado.
    """
    try:
        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetPackagesInfoByPackingId",
            (_packing,),
        )
        dataPackages = g.cursor.fetchall()
        g.cursor.close()

        qtyLimit = 0
        for Package in dataPackages:
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetQtyReferenceByPackage",
                (
                    str(Package[2]),
                    _packing,
                    _material,
                ),
            )
            QtyReference = g.cursor.fetchall()
            g.cursor.close()
            qtyLimit += float(QtyReference[0][0])

        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetAllCotainersByPackingId",
            (_packing,),
        )
        dataContainers = g.cursor.fetchall()
        g.cursor.close()

        qtyCumulative = 0
        for Container in dataContainers:
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetQtyReferenceCumulativeByCotainer",
                (
                    str(Container[0]),
                    _material,
                ),
            )
            CumulativeQty = g.cursor.fetchall()
            g.cursor.close()
            qtyCumulative += float(CumulativeQty[0][0])

        qtyCumulative + float(_qty)
        qtyLimit
        if qtyCumulative + float(_qty) > qtyLimit:
            return [
                "Mayor",
                qtyCumulative + float(_qty) - qtyLimit,
                qtyCumulative,
                float(_qty),
                qtyLimit,
            ]
        if qtyCumulative + float(_qty) <= qtyLimit:
            return [
                "Mayor",
                0,
                qtyCumulative,
                float(_qty),
                qtyLimit,
            ]
    except Exception as e:
        return [e]


@app.route("/ShowFinishPackingList/<Id>", methods=["POST", "GET"])
def ShowFinishPackingList(Id):
    """
    Vista dode podemos finalizar un packinglist.
    Parametros:
        Id: Id packinglist que viene en url.
    Retorno: rederiza finishPackingList.html
    """
    try:
        if session.get("user"):
            g.cursor.callproc(
                "sp_GetPackingListInfoById",
                (Id,),
            )
            data = g.cursor.fetchall()
            g.cursor.close()

            return render_template(
                "finishPackingList.html",
                session_user_name=session["username"],
                orgname=session["orgname"],
                Id=Id,
                Transport=str(data[0][1]),
                Finished=int(data[0][7]),
            )
        else:
            flash("danger:: " + "Unauthorized Access")
            return redirect("/")
    except Exception as e:
        flash("danger:: " + str(e))
        return redirect("/")


@app.route("/FinishPackingList", methods=["POST"])
def FinishPackingList():
    """
    Finaliza un packingList para que ya no se pueda segir agregando
    datos como contenedores o unidades de empaque u otra informacion.
    Parametros:
        _id: Id PackingList.
        _nota: Texto para agregar cualquier informacion extra final.
        _user: Id usuario.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["PackingId"]
            _nota = request.form["nota"]
            _user = session.get("user")

            g.cursor.callproc("sp_FinishPackingList", (_id, _nota, _user))
            data = g.cursor.fetchall()

            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": "An error occurred!"})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/GetDifferencesInfoVsLabelledPackingBeforeEnding", methods=["POST"])
def GetDifferencesInfoVsLabelledPackingBeforeEnding():
    """
    Obtiene las diferencias informacion packinglist vs etiquetas de empaque
    al momento de solicitar finalizar packinglis de entrada, para que el ususario
    tenga presente que le hizo falta etiquetar y que etiqueto de mas.

    """
    try:
        if session.get("user"):
            _packing = request.form["PackingId"]
            _user = session.get("user")
            InsertPromised = InsertPromisedReferencesByPackage(_packing, _user)
            if InsertPromised == "OK":
                InsertLabelled = InsertLabelledReferencesByConatiner(_packing, _user)
                if InsertLabelled == "OK":
                    Differences = DifferencesInfoVsLabelledPacking(_packing, _user)
                    return Differences
                else:
                    return json.dumps({"status": InsertLabelled})
            else:
                return json.dumps({"status": InsertPromised})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


def InsertPromisedReferencesByPackage(_packing, _user):
    """
    Elimina todos los registros de tbl_allpromisedreferencesfrompackinglis
    donde packing_id sea igual al Id packinglist solicitado.
    Inserta en la tabla tbl_allpromisedreferencesfrompackinglist las cantidades
    totales por referencia - Bulto de la informacion de un packing list
    Parametros:
        _packing: Id packinglist.
        _user: Id usuario.
    Retorno: String donde "OK" es operacion correcta.
    """
    try:
        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_DeletedAllPromisedReferencesFromPackingList",
            (_packing,),
        )
        g.conn.commit()
        g.cursor.close()

        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetPackagesInfoByPackingId",
            (_packing,),
        )
        dataPackages = g.cursor.fetchall()
        g.cursor.close()

        for Package in dataPackages:
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_InsertPromisedReferencesByPackage",
                (
                    str(Package[2]),
                    _packing,
                    _user,
                ),
            )
            warning = g.cursor.fetchall()
            if not warning:
                g.conn.commit()
                g.cursor.close()
            else:
                g.cursor.close()
                return str(warning[0][0])
        return "OK"
    except Exception as e:
        return str(e)


def InsertLabelledReferencesByConatiner(_packing, _user):
    """
    Inserta en la tabla tbl_allpromisedreferencesfrompackinglist las cantidades
    totales por referencia - contenedor etiquetas que pertenecen a un packing list
    Parametros:
        _packing: Id packinglist.
        _user: Id usuario.
    Retorno: String donde "OK" es operacion correcta.
    """
    try:

        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetAllCotainersByPackingId",
            (_packing,),
        )
        dataContainers = g.cursor.fetchall()
        g.cursor.close()

        for Container in dataContainers:
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_InsertLabelledReferencesByPackage",
                (
                    int(Container[0]),
                    _packing,
                    _user,
                ),
            )
            warning = g.cursor.fetchall()
            if not warning:
                g.conn.commit()
                g.cursor.close()
            else:
                g.cursor.close()
                return str(warning[0][0])
        return "OK"
    except Exception as e:
        return str(e)


def DifferencesInfoVsLabelledPacking(_packing, _user):
    """
    Crea un objeto Json de las diferencias de cantidades
    de las referencias entre informacion packinglist de
    entrada vs unidades de empaque del packinglist.
    Por Id PackingList.
    Parametros:
        _packing: Id packinglist.
        _user: Id usuario.
    Retorno: Objeto Json con la lista de diferencias cantidad
    en packinglist vs cantidad etiquetada por referencia de un packinglist.
    """
    try:
        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetPackingPromisedReferences",
            (_packing,),
        )
        dataReferences = g.cursor.fetchall()
        g.cursor.close()

        FinalDatas = [
            {
                "referenceName": "Referencia",
                "PromisedQty": "Cantidad en PackingList",
                "LabelledQty": "Cantidad Etiquetada",
                "differencesQty": "Diferencias",
                "differencesQtyLabel": "",
            }
        ]
        for Reference in dataReferences:
            referenceName = Reference[0]
            PromisedQty = float(Reference[1])
            LabelledQty = float(Reference[3])

            differencesQtyLabel = ""
            differencesQty = 0
            if PromisedQty > LabelledQty:
                differencesQtyLabel = "Cantidad Faltante: "
                differencesQty = PromisedQty - LabelledQty

            elif PromisedQty < LabelledQty:
                differencesQtyLabel = "Cantidad Sobrante : "
                differencesQty = LabelledQty - PromisedQty

            if str(Reference[2].encode("utf-8")) != "":
                referenceName = Reference[2]

            final_dict = {
                "referenceName": referenceName,
                "PromisedQty": "{0:g}".format(PromisedQty),
                "LabelledQty": "{0:g}".format(LabelledQty),
                "differencesQty": "{0:g}".format(differencesQty),
                "differencesQtyLabel": differencesQtyLabel,
            }
            FinalDatas.append(final_dict)
        return json.dumps(FinalDatas)

    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ShowUserSettings")
def ShowUserSettings():
    """
    Vista donde podemos editar nuestro nombre de usuario o
    impresoras a usar en la aplicacion para impresion de etiquetas.
    Parametros:
    Retorno: renderiza el template userSettings.html.
    """
    try:
        if session.get("user"):

            g.cursor.callproc(
                "sp_GetPrintersByLabelSize",
                ("Contenedor",),
            )
            datasPrinterContainer = g.cursor.fetchall()
            g.cursor.close()

            ContainersPrinters = []
            for Printer in datasPrinterContainer:
                ContainersPrinters.append(
                    [
                        int(Printer[0]),
                        (Printer[1]),
                        (Printer[2]),
                        (Printer[3]),
                    ]
                )

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetPrintersByLabelSize",
                ("UnidadEmpaque",),
            )
            datasPrinterPackingUnit = g.cursor.fetchall()
            g.cursor.close()

            PackingUnitsPrinters = []
            for Printer in datasPrinterPackingUnit:
                PackingUnitsPrinters.append(
                    [
                        int(Printer[0]),
                        (Printer[1]),
                        (Printer[2]),
                        (Printer[3]),
                    ]
                )

            return render_template(
                "userSettings.html",
                session_user_name=session["username"],
                orgname=session["orgname"],
                email=session["mail"],
                PrintersContainer=ContainersPrinters,
                PrintersPackingUnits=PackingUnitsPrinters,
                MyPrinterContainerName=session["NamePrinterContainer"],
                MyPrinterPackingName=session["NamePrinterPacking"],
                MyPrinterContainerId=session["IdPrinterContainer"],
                MyPrinterPackingId=session["IdPrinterPacking"],
            )
        else:
            flash("danger:: " + "Unauthorized Access")
            return redirect("/")
    except Exception as e:
        flash("danger:: " + str(e))
        return redirect("/")


@app.route("/UpdateProfile", methods=["POST"])
def UpdateProfile():
    """
    Permite Actualizar nuestro datos de nuestro perfil:
        Nombre de usuario, Impresoras a utilizar para impresion de etiquetas.
    Parametros:
        _name: Nombre usuario.
        _email: Correo eletronico usuario.
        _printerContainer: Id impresora etiquetas contendor.
        _printerPackingUnit: Id impresora etiquetas unidad de empaque.
    Retorno: mensaje flash donde ("success::"+ "Datos Actualizados" )
    es operacion correcta.
    """
    try:
        _name = request.form["inputName"]
        _email = request.form["inputEmail"]
        _printerContainer = request.form["ContainerPrinter"]
        _printerPackingUnit = request.form["PackingUnitPrinter"]

        if _name and _email and _printerContainer and _printerPackingUnit:

            g.cursor.callproc(
                "sp_UpdateProfile",
                (
                    _name,
                    _email,
                ),
            )
            data = g.cursor.fetchall()

            if not data:
                g.conn.commit()
                g.cursor.close()
                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_AddUserPrinters",
                    (
                        _printerContainer,
                        _printerPackingUnit,
                        _email,
                    ),
                )
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_GetPrintersByUserLogin", (int(session.get("user")),)
                )
                datasPrinter = g.cursor.fetchall()
                g.cursor.close()
                session["username"] = _name
                session["TCP_IPM"] = os.environ.get(str(datasPrinter[0][0]))
                session["NamePrinterContainer"] = str(datasPrinter[0][2])
                session["IdPrinterContainer"] = int(datasPrinter[0][4])
                session["TCP_IP"] = os.environ.get(str(datasPrinter[0][1]))
                session["NamePrinterPacking"] = str(datasPrinter[0][3])
                session["IdPrinterPacking"] = int(datasPrinter[0][5])

                flash("success::" + "Datos Actualizados")
                return redirect("/ShowUserSettings")
            else:
                flash("warning::" + str(data[0][0]))
                return redirect("/ShowUserSettings")
        else:
            flash("warning:: Enter the required fields")
            return redirect("/ShowUserSettings")

    except Exception as e:
        flash("warning:: " + str(e))
        return redirect("/userHome")


@app.route("/ShowFinishedPackingListInfo")
def ShowFinishedPackingListInfo():
    """
    Vista packinglist finalizados de entrada.
    Parametros:
    Return:
        Renderiza finishedPackingListInfo.html con
        variables nombre de usuario y organizacion.
    """
    if session.get("user"):
        return render_template(
            "finishedPackingListInfo.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/GetAllsFinishedPackingListInfo", methods=["POST"])
def GetAllsFinishedPackingListInfo():
    """
    Obtiene la lista de PackingsList finalizados de
    entrada filtrados por limite y paginacion.
    Parametros:
        _limit: Limete de registros a obtener.
        _offset: Numero de paginacion.
        _user: Id usuario.
    Retorno: Objeto Json con la lista de registros
    PackingList finalizados encontrados en la BD
    con sus diferencias InfoVsLabelledPackingList
    & el total numero total de registros de PackingList.
    """
    try:
        if session.get("user"):
            _limit = request.form["limit"]
            _offset = request.form["offset"]
            _user = session.get("user")

            g.cursor.execute(
                "call sp_GetAllsFinishedPackingListInfo(%s,%s,@p_total)",
                (_limit, _offset),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()

            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Transporte": "Doc. Transporte",
                    "Fecha": "Fecha",
                    "Peso": "Peso Bruto (KG)",
                    "Volumen": "Volumen (M3)",
                    "Unidades": "Bultos Documentados",
                    "UnidadesExtra": "Bultos No Documentados",
                    "Faltantes": "Faltantes Totales:",
                    "Sobrantes": "Sobrantes Totales:",
                }
            ]
            for material in materials:
                Faltantes = 0
                Sobrantes = 0
                FaltanteCadena1 = ""
                FaltanteCadena2 = (
                    "<table class='table'><thead>"
                    + "<tr><th scope='col'>Referencia y Descripcion</th>"
                    + "<th scope='col'>Faltantes</th></tr>"
                    + "</thead><tbody>"
                )
                SobranteCadena1 = ""
                SobranteCadena2 = (
                    "<table class='table'><thead>"
                    + "<tr><th scope='col'>Referencia y Descripcion</th>"
                    + "<th scope='col'>Sobrantes</th></tr>"
                    + "</thead><tbody>"
                )
                InsertPromised = InsertPromisedReferencesByPackage(
                    int(material[0]), _user
                )
                if InsertPromised != "OK":
                    return json.dumps({"error": InsertPromised})
                InsertLabelled = InsertLabelledReferencesByConatiner(
                    int(material[0]), _user
                )
                if InsertLabelled != "OK":
                    return json.dumps({"error": InsertLabelled})

                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_GetPackingPromisedReferences",
                    (int(material[0]),),
                )
                dataReferences = g.cursor.fetchall()
                g.cursor.close()

                for Reference in dataReferences:
                    referenceName = Reference[0]
                    PromisedQty = float(Reference[1])
                    LabelledQty = float(Reference[3])

                    if str(Reference[2].encode("utf-8")) != "":
                        referenceName = Reference[2]

                    if PromisedQty > LabelledQty:
                        Faltantes += 1
                        faltanteQty = "{0:g}".format(PromisedQty - LabelledQty)
                        FaltanteCadena1 += (
                            str(referenceName.encode("utf-8"))
                            + " > Faltante:"
                            + str(faltanteQty)
                            + "\n\n"
                        )
                        FaltanteCadena2 += (
                            "<tr><td>"
                            + str(referenceName.encode("utf-8"))
                            + " </td><td> "
                            + str(faltanteQty)
                            + "</td></tr>"
                        )

                    elif PromisedQty < LabelledQty:
                        Sobrantes += 1
                        sobranteQty = "{0:g}".format(LabelledQty - PromisedQty)
                        SobranteCadena1 += (
                            str(referenceName.encode("utf-8"))
                            + " > Sobrante:"
                            + str(sobranteQty)
                            + "\n\n"
                        )
                        SobranteCadena2 += (
                            "<tr><td>"
                            + str(referenceName.encode("utf-8"))
                            + " </td><td> "
                            + str(sobranteQty)
                            + "</td></tr>"
                        )
                FaltanteCadena2 += "</tbody></table>"
                SobranteCadena2 += "</tbody></table>"

                material_dict = {
                    "Id": (material[0]),
                    "Transporte": (material[1]),
                    "Fecha": str(material[2]),
                    "Peso": str(material[3]),
                    "Volumen": str(material[4]),
                    "Unidades": str(material[5]),
                    "CreadoPor": (material[6]),
                    "Creado": str(material[7]),
                    "ActualizadoPor": (material[8]),
                    "Actualizado": str(material[9]),
                    "EtiquetadoIniciado": int(material[10]),
                    "UnidadesExtra": str(material[11]),
                }
                if Faltantes <= 1:
                    material_dict["Faltantes"] = Faltantes
                    material_dict["FaltantesshowItems"] = FaltanteCadena1
                else:
                    material_dict["Faltantes"] = Faltantes
                    material_dict["FaltantesModal"] = FaltanteCadena2
                    material_dict["FaltantesTitle"] = FaltanteCadena1
                    material_dict["FaltantesshowItems"] = "Varios"

                if Sobrantes <= 1:
                    material_dict["Sobrantes"] = Sobrantes
                    material_dict["SobrantesshowItems"] = SobranteCadena1
                else:
                    material_dict["Sobrantes"] = Sobrantes
                    material_dict["SobrantesModal"] = SobranteCadena2
                    material_dict["SobrantesTitle"] = SobranteCadena1
                    material_dict["SobrantesshowItems"] = "Varios"

                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor = g.conn.cursor()
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})
            return json.dumps(response)
        else:
            return json.dumps({"error": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@app.route("/deletePackingUnitById", methods=["POST"])
def deletePackingUnitById():
    """
    Elimina una unidad de empaque por medio del id y
    si el apckinglist aun no a sido finalizado.
    Parametros:
        _id: Id unidad de empaque.
        _packingId: Id PackingList.
        _idContainer: Id contenedor.
    Retorno: Objeto Json donde "status": "OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["id"]
            _packingId = request.form["packing"]
            _idContainer = request.form["IdContainer"]

            g.cursor.callproc("sp_GetPackingListInfoById", (_packingId,))
            IsFinish = g.cursor.fetchall()
            g.cursor.close()
            if int(IsFinish[0][7]) == 1:
                return json.dumps(
                    {
                        "status": (
                            "PackingList finalizado no puede "
                            + "eliminar, editar o agregar mas datos"
                        ),
                    }
                )

            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_deletNewPallet",
                (
                    _id,
                    _idContainer,
                ),
            )
            result = g.cursor.fetchall()

            if not result:
                g.conn.commit()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(result[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})
    finally:
        g.cursor.close()


@app.route("/AddPdf", methods=["POST"])
def AddPdf():
    """
    Carga archivo pdf al sistema de un packinglist de entrada.
    y llama a una funcion que inicializa la estraccion de la
    informacion del archivo para guardarla en la BD.
    Parametros:
        _user: id usuario.
        files : Archivo pdf.
    Retorno: Objeto json donde "status": "OK" es operacion correcta.
        y lleva con sigo cadenas htlm que forman tablas de la
        informacion primaria y secundaria del packinglist.
    """
    try:
        _user = session.get("user")
        files = request.files["file"]
        directory = pdf_directory_path
        for the_file in os.listdir(directory):
            pdfs = os.path.join(directory, the_file)
            try:
                if os.path.isfile(pdfs):
                    os.unlink(pdfs)
            except Exception as er:
                er
                return json.dumps(
                    {"status": "No se ha podido limpiar la carpeta de pdfs"}
                )
        if files:
            filename = "packinglist.pdf"
            files.save(os.path.join(directory, filename))
        call = Getfirstinfopackinglist(_user)
        if str(call[0]) != "OK":
            if str(call[0]) == "NotFoundMaterials":
                return json.dumps({"status": str(call[0]), "NumTest": call[1]})
            return json.dumps({"status": str(call[0])})
        else:
            return json.dumps(
                {"status": "OK", "principalInfo": call[2], "secondaryInfo": call[1]}
            )
    except Exception as e:
        return json.dumps({"status": str(e)})


def Getfirstinfopackinglist(_user):  # noqa
    """
    Obtiene la informacion principal del packinglist del archivo
    pdf cargado.
    Parametros: _user: id usuario.
    Retorno: areglo donde: ["OK" = operacion correcta,
        call[1] = cadena html donde escribe una tabla de bultos
            con referencias y cantidades,
        PrincipalTable = cadena html donde escribe una tabla
            con la informacion principal del packinglist]
    """
    try:
        pdf_document = pdf_directory_path + "/packinglist.pdf"
        doc = fitz.open(pdf_document)

        pages = doc.pageCount
        Datas = []
        docTransporte = 0
        date = ""
        qty = ""
        vol = ""
        qtyBults = 0
        PrincipalTable = "<table class='table'><thead>"

        g.cursor = g.conn.cursor()
        g.cursor.callproc("sp_CreateNonExistentReferencesNum")
        TestNumber = g.cursor.fetchone()
        g.cursor.close()

        for numpage in range(int(pages)):
            page1 = doc.loadPage(numpage)

            txt = page1.getText("text")

            CheckFirst = ""
            for text in txt.split("\n"):
                if CheckFirst == "Doc":
                    docTransporte = int(text.encode("utf-8"))
                    CheckFirst = ""
                elif CheckFirst == "Date":
                    date = str(text.encode("utf-8"))
                    date = (
                        date.split(".")[2]
                        + "-"
                        + date.split(".")[1]
                        + "-"
                        + date.split(".")[0]
                    )
                    CheckFirst = ""
                elif CheckFirst == "Qty":
                    qty = str(text.encode("utf-8")).replace(" KG", "")
                    qty = qty.replace(" LB", "")
                    qty = qty.replace(".", "")
                    qty = qty.replace(",", ".")
                    qty = float(qty)
                    CheckFirst = ""
                elif CheckFirst == "Vol":
                    vol = str(text.encode("utf-8")).replace(" M3", "")
                    vol = vol.replace(".", "")
                    vol = vol.replace(",", ".")
                    vol = float(vol)
                    CheckFirst = ""
                elif CheckFirst == "QtyBults":
                    qtyBults = str(text.encode("utf-8")).replace(" UN", "")
                    qtyBults = qtyBults.replace(" ST", "")
                    qtyBults = int(qtyBults)
                    CheckFirst = ""

                if str(text.encode("utf-8")).find("DOC. TRANSPORTE:") != -1:
                    docTransporte = int(
                        str(text.encode("utf-8")).replace("DOC. TRANSPORTE: ", "")
                    )

                if str(text.encode("utf-8")).find("SHIPMENT #:") != -1:
                    docTransporte = int(
                        str(text.encode("utf-8")).replace("SHIPMENT #: ", "")
                    )

                elif str(text.encode("utf-8")) in ("DOC. TRANSPORTE:", "SHIPMENT #:"):
                    CheckFirst = "Doc"
                elif str(text.encode("utf-8")) in ("FECHA:", "DATE:"):
                    CheckFirst = "Date"
                elif str(text.encode("utf-8")) in (
                    "PESO BRUTO TOTAL:",
                    "TOTAL GROSS WEIGHT:",
                ):
                    CheckFirst = "Qty"
                elif str(text.encode("utf-8")) in ("VOLUMEN:", "VOLUME:"):
                    CheckFirst = "Vol"
                elif str(text.encode("utf-8")) in (
                    "CANTIDAD DE BULTOS:",
                    "NUMBER OF PIECES:",
                ):
                    CheckFirst = "QtyBults"

        if docTransporte != 0:
            Datas.append(docTransporte)
            PrincipalTable = (
                PrincipalTable
                + "<tr><th scope='col'>DOC. TRANSPORTE:"
                + str(docTransporte)
                + "</th>"
            )
        else:
            return ["DOC. TRANSPORTE no localizado"]
        if date != "":
            Datas.append(date)
            PrincipalTable = (
                PrincipalTable + "<th scope='col'>FECHA:" + str(date) + "</th>"
            )
        else:
            return ["FECHA no localizado"]
        if qty != "":
            Datas.append(qty)
            PrincipalTable = (
                PrincipalTable
                + "<th scope='col'>PESO BRUTO TOTAL:"
                + str(qty)
                + "</th>"
            )
        else:
            return ["PESO BRUTO TOTAL no localizado"]
        if vol != "":
            Datas.append(vol)
            PrincipalTable = (
                PrincipalTable + "<th scope='col'>VOLUMEN:" + str(vol) + " M3</th>"
            )
        else:
            return ["VOLUMEN no localizado"]
        if qtyBults != 0:
            Datas.append(qtyBults)
            PrincipalTable = (
                PrincipalTable
                + "<th scope='col'>CANTIDAD DE BULTOS:"
                + str(qtyBults)
                + "</th></tr></thead></table>"
            )
        else:
            return ["CANTIDAD DE BULTOS no localizado"]

        call = GetSecondaryInfoPackingList(
            qtyBults,
            Datas,
            _user,
            int(TestNumber[0]),
        )
        if str(call[0]) != "OK":
            return [str(call), int(TestNumber[0])]
        return ["OK", call[1], PrincipalTable]

    except Exception as e:
        return [str(e)]


def GetSecondaryInfoPackingList(Bults, PrincipalInfo, _user, TestNumber):  # noqa
    """
    Obtiene los numeros de bulto de un packinglist del archivo pdf cargado y
    si la operacion final es correcta guarda los datos del packinglist a la DB.
    Parametros:
        Bults: Numero de bultos.
        PrincipalInfo: Areglo con la informacion principal de packinglist.
        _user: Id usuario.
    Retorno: arlego donde: ["OK" = operacion correcta,
        Table = cadena html donde escribe una tabla con la informacion de
            las referencias con cantidades por bulto. ]
    """
    try:
        pdf_document = pdf_directory_path + "/packinglist.pdf"
        doc = fitz.open(pdf_document)

        pages = doc.pageCount
        FinalDatas = []
        Datas = []
        i = 0
        j = 0
        firstbult = ""
        secondbult = ""
        Table = (
            "<table class='table'>"
            + "<thead>"
            + "<tr>"
            + "<th scope='col'>Referencia</th>"
            + "<th>"
            + "<p class='desc-pdf'>"
            + "Descripcion del PDF</p>"
            + "<p class='desc-ob'>"
            + "Descripcion en Open Bravo</p></th>"
            + "<th scope='col' class='colum-right'>Cantidad</th>"
            + "<th scope='col'>UM</th>"
            + "</tr>"
            + "</thead>"
            + "<tbody>"
        )
        StrNotFound = ""
        for numpage in range(int(pages)):
            page1 = doc.loadPage(numpage)

            txt = page1.getText("text")

            CheckFirst = ""
            for text in txt.split("\n"):
                if i == 7 and j < Bults:
                    i = 0
                elif CheckFirst == "OK":
                    try:
                        if i == 0:
                            Datas.append(int(text.encode("utf-8")))
                            j += 1
                            if j == 1:
                                firstbult = Datas[j - 1]
                            elif j == 2:
                                secondbult = Datas[j - 1]
                            else:
                                firstbult = secondbult
                                secondbult = Datas[j - 1]
                            if j > 1:
                                CallFuntion = GetNumbersPartByBult(
                                    firstbult,
                                    secondbult,
                                    TestNumber,
                                    _user,
                                    str(PrincipalInfo[0]),
                                )
                                if str(CallFuntion[0]) != "OK":
                                    return [str(CallFuntion[0])]
                                else:
                                    try:
                                        if str(CallFuntion[3]) != "":
                                            StrNotFound += str(CallFuntion[3])
                                    except Exception:
                                        pass
                                    FinalDatas.append(CallFuntion[1])
                                    Table = Table + CallFuntion[2]
                        i += 1
                    except Exception:
                        i = 0
                        pass

                if j > Bults:
                    CheckFirst = ""

                if str(text.encode("utf-8")) in ("REMONTABLE", "STACKABLE"):
                    CheckFirst = "OK"

        CallFuntion = GetNumbersPartByBult(
            Datas[Bults - 1], Datas[Bults - 1], TestNumber, _user, str(PrincipalInfo[0])
        )
        if str(CallFuntion[0]) != "OK":
            return [str(CallFuntion[0])]
        else:
            try:
                if str(CallFuntion[3]) != "":
                    StrNotFound += str(CallFuntion[3])
            except Exception:
                pass
            FinalDatas.append(CallFuntion[1])
            Table = Table + CallFuntion[2]

        Table = Table + "</tbody></table>"

        if StrNotFound != "":
            return "NotFoundMaterials"

        if len(FinalDatas) == int(Bults):
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_AddPackingListInfo",
                (
                    str(PrincipalInfo[0]),
                    str(PrincipalInfo[1]),
                    str(PrincipalInfo[2]),
                    str(PrincipalInfo[3]),
                    Bults,
                    _user,
                ),
            )
            AddPackingListInfo = g.cursor.fetchall()
            if not AddPackingListInfo:
                g.conn.commit()
                g.cursor.close()

                g.cursor = g.conn.cursor()
                g.cursor.callproc(
                    "sp_GetInfoPackinglistByTransportDocument",
                    (str(PrincipalInfo[0]),),
                )
                GetPackingListInfo = g.cursor.fetchall()
                g.cursor.close()
                if not GetPackingListInfo:
                    return ["El packinglist no se pudo agregar intente nueva mente"]

                Package = ""
                packegeupdate = ""
                for datasPackge in FinalDatas:
                    i = 0
                    Package = datasPackge[0][0]
                    if Package != "" and Package != packegeupdate:
                        packegeupdate = datasPackge[0][0]
                        g.cursor = g.conn.cursor()
                        g.cursor.callproc(
                            "sp_AddPackageInfo",
                            (
                                int(GetPackingListInfo[0][0]),
                                Package,
                                1,
                                "",
                                _user,
                            ),
                        )
                        data = g.cursor.fetchall()
                        if len(data) > 0:
                            g.cursor.close()
                            return [str(data[0][0])]
                        g.conn.commit()
                        g.cursor.close()

                    for ReferencesPackage in datasPackge:
                        i += 1
                        g.cursor = g.conn.cursor()
                        g.cursor.callproc(
                            "sp_AddReferenceByPackage",
                            (
                                str(ReferencesPackage[1]),
                                str(ReferencesPackage[0]),
                                int(GetPackingListInfo[0][0]),
                                str(ReferencesPackage[3]),
                                str(ReferencesPackage[4]),
                                _user,
                                str(ReferencesPackage[2]),
                                1,
                            ),
                        )
                        g.conn.commit()
                        g.cursor.close()

            else:
                return [str(AddPackingListInfo[0][0])]

        return ["OK", Table]

    except Exception as e:
        return [str(e)]


def GetNumbersPartByBult(  # noqa
    firstBultNum, SecondBultNum, TestNumber, _user, Packing
):  # noqa
    """
    Obtiene los numeros de parte (Referencia, Descripcion, Cantidad)
    diretamente del archivo pdf por numero de bulto de un packinglist.
    Parametros:
        firstBultNum: Numero del primer bulto a obtener datos:
        SecondBultNum: Numero del segundo bulto.
    Retorno: areglo con: [ "OK" = Operacion correcta,
        Datas = areglo de areglos donde cada areglo reresenta un
            numero de parte con descripcion y cantidad.
        linestable: cadena html representa lineas de una tabla
         con columnas donde van los datos de las referencias mas cantidades.
    Acerca de: Se utilza el primer bulto para buscar sus referencias y el
    segundo para saber hasta donde hay que buscar las referencias del primer bulto.
    Cuando los numeros de bulto son los mismo significa que es el ultimo bulto
    a buscar datos por lo tanto obtiene las referencias apartir de este bulto
    hasta terminar de recorrer todas.
    """
    try:
        pdf_document = pdf_directory_path + "/packinglist.pdf"
        doc = fitz.open(pdf_document)

        pages = doc.pageCount
        Datas = []
        i = 0
        j = 0
        linestable = "<tr><th scope=row'>Bulto No: " + str(firstBultNum) + "</th></tr>"
        newlinetable = ""
        CheckFirst = ""
        firstDatas = []
        Description = ""
        FirstFilterReference = ""
        FirstStrReference = ""
        ReferencesNotFound = ""
        DescriptionOB = ""
        for numpage in range(int(pages)):
            page1 = doc.loadPage(numpage)

            txt = page1.getText("text")

            for text in txt.split("\n"):
                _referencia = ""
                StrCheck = str(text.encode("utf-8")).replace(" ", "")
                if CheckFirst == "FirstFilter":
                    i += 1
                    if str(text.encode("utf-8")) != "Palet EUR" and j > 1:
                        if (
                            str(text.encode("utf-8")).find("DOC. TRANSPORTE:") == -1
                            and str(text.encode("utf-8")).find("SHIPMENT NUMBER:") == -1
                        ):

                            if i == 1:
                                _referencia = str(text.encode("utf-8"))
                                if _referencia != "":
                                    g.cursor = g.conn.cursor()
                                    g.cursor.callproc(
                                        "sp_ValidateReferenceExistence",
                                        (_referencia,),
                                    )
                                    dataCheck = g.cursor.fetchall()
                                    g.cursor.close()
                                    if (
                                        str(dataCheck[0][0]) != "OK"
                                        and FirstFilterReference != ""
                                    ):
                                        ReferencesNotFound += FirstStrReference

                                        g.cursor = g.conn.cursor()
                                        g.cursor.callproc(
                                            "sp_AddNonExistentReferences",
                                            (
                                                TestNumber,
                                                FirstStrReference,
                                                str(dataCheck[0][0]),
                                                _user,
                                                Packing,
                                            ),
                                        )
                                        g.conn.commit()
                                        g.cursor.close()

                                    elif (
                                        str(dataCheck[0][0]) != "OK"
                                        and FirstFilterReference == ""
                                    ):
                                        FirstFilterReference = "SecondFilterReference"
                                        FirstStrReference = _referencia
                                        i = 0
                                    else:
                                        firstDatas.append(firstBultNum)

                                        g.cursor = g.conn.cursor()
                                        g.cursor.callproc(
                                            "sp_GetMaterialsNameByReference",
                                            (str(text.encode("utf-8")),),
                                        )
                                        MaterialName = g.cursor.fetchone()
                                        g.cursor.close()

                                        DescriptionOB = str(
                                            MaterialName[0].encode("utf-8")
                                        ).replace(str(text.encode("utf-8")) + " ", "")

                                        firstDatas.append(str(text.encode("utf-8")))
                                        newlinetable = (
                                            newlinetable
                                            + "<tr><td>"
                                            + str(text.encode("utf-8"))
                                            + "</td>"
                                        )
                                        FirstStrReference = ""
                            if i == 2:
                                Description = str(text.encode("utf-8"))

                            try:
                                if str(text.encode("utf-8")).split(" ")[1] in (
                                    "KG",
                                    "L",
                                    "M",
                                    "M2",
                                    "ROL",
                                    "UN",
                                    "ST",
                                ):
                                    i = 3
                            except Exception:
                                pass

                            if i == 3:
                                qty = str(text.encode("utf-8")).replace(" KG", "")
                                qty = qty.replace(" L", "")
                                qty = qty.replace(" M", "")
                                qty = qty.replace(" M2", "")
                                qty = qty.replace(" ROL", "")
                                qty = qty.replace(" UN", "")
                                qty = qty.replace(" ST", "")
                                tipe = str(text.encode("utf-8")).replace(qty, "")
                                tipe = tipe.replace(" ", "")
                                qty = qty.replace(".", "")
                                qty = qty.replace(",", ".")

                                try:
                                    qty = float(qty)
                                    if DescriptionOB != Description:
                                        newlinetable = (
                                            newlinetable
                                            + "<td>"
                                            + Description
                                            + "<br>"
                                            + "<label class='description-ob'>"
                                            + DescriptionOB
                                            + "</label>"
                                            + "</td>"
                                        )
                                    else:
                                        newlinetable = (
                                            newlinetable
                                            + "<td>"
                                            + Description
                                            + "</td>"
                                        )
                                    firstDatas.append(Description)
                                    Description = ""
                                    firstDatas.append(qty)
                                    firstDatas.append(tipe)
                                    newlinetable = (
                                        newlinetable
                                        + "<td class='colum-right'>"
                                        + str(text.encode("utf-8").split(" ")[0])
                                        + "</td>"
                                        + "<td>"
                                        + str(text.encode("utf-8").split(" ")[1])
                                        + "</td></tr>"
                                    )
                                    DescriptionOB = ""
                                except Exception as e:
                                    Description = (
                                        Description + " " + str(text.encode("utf-8"))
                                    )
                                    i = 2

                            if i == 5:
                                Datas.append(firstDatas)
                                firstDatas = []
                                linestable = linestable + newlinetable
                                newlinetable = ""
                                FirstFilterReference = ""
                                i = 0

                        else:
                            i = 0
                            CheckFirst = ""
                            if numpage + 1 < pages:
                                CheckFirst = "SecondFilter"

                    else:
                        i = 0
                        CheckFirst = ""

                if CheckFirst == "SecondFilter":
                    if str(text.encode("utf-8")).find("PEDIDO CLIENTE") != -1:
                        CheckFirst = "FirstFilter"
                    elif str(text.encode("utf-8")).find("CUST. ORDER") != -1:
                        CheckFirst = "FirstFilter"

                if StrCheck == str(firstBultNum):
                    CheckFirst = "FirstFilter"
                    j += 1

                if firstBultNum != SecondBultNum:
                    if StrCheck == str(SecondBultNum) and j > 1:
                        return ["OK", Datas, linestable, ReferencesNotFound]

        return ["OK", Datas, linestable, ReferencesNotFound]

    except Exception as e:
        return [str(e)]


@app.route("/StartPackingLabeling", methods=["POST"])
def StartPackingLabeling():
    """
    Cambia el estado de un packinglist a etiquetado iniciado,
    con lo cual desabilita las funciones para editar la informacion
    primaria y secundaria o la eliminacion del packinglist.
    Parametros:
        _user: Id usuario.
        _id: Id del packinglist.
    Retorno: Objeto Json donde "status":"OK" es operacion correcta.
    """
    try:
        if session.get("user"):
            _user = session.get("user")
            _id = request.form["packingId"]
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_StartTaggedByPackingList",
                (
                    _id,
                    _user,
                ),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/SendDiffPackageInfoVsLabelled", methods=["POST"])
def SendDiffPackageInfoVsLabelled():
    """
    Envia las diferencias entre lo etiquetado vs lo documentado
    por numero de bulto - PackingList.
    Parametros:
        _packing: Id PackingList.
        _bulto: Numero de Bulto.
        _IdContainer: Id Contenedor o Id Remision.
    Retorno: Objeto Json con la lista de diferencias
    entre lo etiquetado vs lo documentado.
    """
    try:
        if session.get("user"):
            _packing = request.form["packingId"]
            _bulto = request.form["bultNum"]
            _IdContainer = request.form["IdContainer"]
            callfuntion = GetDiffPackageInfoVsLabelled(_packing, _bulto, _IdContainer)
            if callfuntion[0] == "OK":
                return json.dumps(callfuntion[1])
            return json.dumps({"status": callfuntion[0]})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


def GetDiffPackageInfoVsLabelled(_packing, _bulto, _IdContainer):
    """
    Crea Objeto Json de las diferencias entre lo etiquetado
    vs lo documentado por numero de bulto - PackingList.
    Parametros:
        _packing: Id PackingList.
        _bulto: Numero de Bulto.
        _IdContainer: Id Contenedor o Id Remision.
    Retorno: Objeto Json con la lista de diferencias
    entre lo etiquetado vs lo documentado.
    """
    try:
        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetSumQtyReferencesByPackage",
            (
                _bulto,
                _packing,
            ),
        )
        data = g.cursor.fetchall()
        g.cursor.close()
        InfoPackage = [
            {
                "referenceName": "Referencia",
                "PromisedQty": "Cantidad en Bulto",
                "LabelledQty": "Cantidad Etiquetada",
                "differencesQty": "Diferencias",
                "differencesQtyLabel": "",
            }
        ]
        ReferencesInInfoBult = []
        for referenceDatas in data:
            PromisedQty = float(referenceDatas[1])
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetQtyReferenceCumulativeByCotainer",
                (
                    _IdContainer,
                    str(referenceDatas[2]),
                ),
            )
            QtyInContainer = g.cursor.fetchone()
            g.cursor.close()
            LabelledQty = float(QtyInContainer[0])

            differencesQtyLabel = ""
            differencesQty = 0
            if PromisedQty > LabelledQty:
                differencesQtyLabel = "Cantidad Faltante: "
                differencesQty = PromisedQty - LabelledQty

            elif PromisedQty < LabelledQty:
                differencesQtyLabel = "Cantidad Sobrante : "
                differencesQty = LabelledQty - PromisedQty

            final_dict = {
                "referenceName": referenceDatas[0],
                "PromisedQty": "{0:g}".format(PromisedQty),
                "LabelledQty": "{0:g}".format(LabelledQty),
                "differencesQty": "{0:g}".format(differencesQty),
                "differencesQtyLabel": differencesQtyLabel,
            }
            InfoPackage.append(final_dict)
            ReferencesInInfoBult.append(str(referenceDatas[2]))

        g.cursor = g.conn.cursor()
        g.cursor.callproc(
            "sp_GetAllReferencesByCotainer",
            (_IdContainer,),
        )
        SpareReferences = g.cursor.fetchall()
        g.cursor.close()
        for SpareReference in SpareReferences:
            if str(SpareReference[1]) not in ReferencesInInfoBult:
                LabelledQty = float(SpareReference[0])
                final_dict = {
                    "referenceName": SpareReference[2],
                    "PromisedQty": 0,
                    "LabelledQty": "{0:g}".format(LabelledQty),
                    "differencesQty": "{0:g}".format(LabelledQty),
                    "differencesQtyLabel": "Cantidad Sobrante : ",
                }
                InfoPackage.append(final_dict)
        return ["OK", InfoPackage]

    except Exception as e:
        return [str(e)]


@app.route("/SendAllDiffPackageInfoVsLabelledByPackingId", methods=["POST"])
def SendAllDiffPackageInfoVsLabelledByPackingId():
    """
    Envia las diferencias entre lo etiquetado vs lo documentado
    de cada bulto de un PackingList.
    Parametros:
        _packing: Id PackingList.
    Retorno: Objeto Json con la lista de diferencias
    entre lo etiquetado vs lo documentado por bulto
    de un packinglist.
    """
    try:
        if session.get("user"):
            _packing = request.form["packingId"]
            AllsDatas = []
            g.cursor = g.conn.cursor()
            g.cursor.callproc(
                "sp_GetAllPackagesByPackingId",
                (_packing,),
            )
            PackagesDatas = g.cursor.fetchall()
            g.cursor.close()
            i = 0
            for PackageData in PackagesDatas:
                DiffStatus = 0
                callfuntion = GetDiffPackageInfoVsLabelled(
                    _packing, str(PackageData[2]), int(PackageData[6])
                )
                if callfuntion[0] != "OK":
                    return json.dumps({"status": callfuntion[0]})
                for Error in callfuntion[1]:
                    if not str(Error["differencesQty"]) in ("0", "Diferencias"):
                        DiffStatus = 1

                if DiffStatus == 0:
                    AllsDatas.append([str(PackageData[2]), callfuntion[1]])
                if DiffStatus == 1:
                    AllsDatas.insert(i, [str(PackageData[2]), callfuntion[1]])
                    i += 1

            return json.dumps(AllsDatas)
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ShowAlertMails")
def ShowAlertMails():
    """
    Vista donde podemos agregar mails para
    que nos envie algun tipo de alerta.
    Parametros:
    Retorno:
        Renderiza addAlertMails.html con
        variables nombre de usuario y organizacion.
    """
    if session.get("user"):

        g.cursor.callproc("sp_GetAllAlertReasons")
        data = g.cursor.fetchall()
        g.cursor.close()
        Reasons = []
        for reason in data:
            Reasons.append([reason[0], reason[1]])

        return render_template(
            "addAlertMails.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
            Reasons=Reasons,
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/AddAlertMails", methods=["POST", "GET"])
def AddAlertMails():
    """
    Crea un nuevo registro de un mail al cual
    podemos enviar una alerta especifica.
    Parametros:
        _name: Nombre de la persona destino.
        _email: Correo eletronico de la persona destino.
        _reason: Motivo, razón o tipo de alerta que se envía.
    Retorno: Objeto Json donde "status":"OK" es oprecion correcta.
    """
    try:
        _name = request.form["inputName"]
        _email = request.form["inputEmail"]
        _reason = request.form["Reason"]
        _user = session.get("user")

        g.cursor.callproc(
            "sp_AddAlertMails",
            (
                _name,
                _email,
                _reason,
                _user,
            ),
        )
        data = g.cursor.fetchall()
        if not data:
            g.conn.commit()
            g.cursor.close()
            return json.dumps({"status": "OK"})
        else:
            g.cursor.close()
            return json.dumps({"status": str(data[0][0])})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/GetAllsAlertMails", methods=["POST"])
def GetAllsAlertMails():
    """
    Obtiene la lista de los registros
    de mails para envio de alertas.
    Parametros: _limit: Limite de registros a obtener.
        _offset: apartir de que numero de registro se obtienen.
    Retorno: Objeto Json con la lista de registros encontrados.
    """
    try:
        if session.get("user"):
            _limit = request.form["limit"]
            _offset = request.form["offset"]

            g.cursor.execute(
                "call sp_GetAllsAlertMails(%s,%s,@p_total)",
                (_limit, _offset),
            )
            materials = g.cursor.fetchall()
            g.cursor.close()
            g.cursor = g.conn.cursor()
            response = []
            materials_dict = [
                {
                    "Id": 0,
                    "Mail": "Email",
                    "Reason": "Descripcion Alerta",
                    "Name": "Nombre o Alias",
                    "Date": "Fecha Registro",
                }
            ]
            for material in materials:
                material_dict = {
                    "Id": (material[0]),
                    "Mail": str(material[1]),
                    "Reason": str(material[2]),
                    "Name": str(material[5]),
                    "Date": str(material[3]),
                }
                materials_dict.append(material_dict)
            response.append(materials_dict)
            g.cursor.execute("SELECT @p_total")
            outParam = g.cursor.fetchone()
            response.append({"total": outParam[0]})
            return json.dumps(response)
        else:
            return json.dumps({"error": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@app.route("/DeletedAlertMails", methods=["POST", "GET"])
def DeletedAlertMails():
    """
    Elimina un mail por su id de la tbl_alert_mails
    Parametros: Id: Id del mail.
    Retorno: Objeto Json donde "status": "OK"
    es operacion correcta.
    """
    try:
        if session.get("user"):
            _id = request.form["Id"]

            g.cursor.callproc(
                "sp_DeletedAlertMails",
                (_id,),
            )
            data = g.cursor.fetchall()
            if not data:
                g.conn.commit()
                g.cursor.close()
                return json.dumps({"status": "OK"})
            else:
                return json.dumps({"status": str(data[0][0])})
        else:
            return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/ShowMaterialsNotFound/<Id>")
def ShowMaterialsNotFound(Id):
    """
    Muestra la lista de posibles referencias no
    localizados en un packinglist.
    Parametros:
    Retorno: Renderiza materialsNotFound.html
    Con la lista de posibles referencias no localizadas.
    """
    if session.get("user"):

        g.cursor.callproc("sp_GetNonExistentReferencesByTestNumber", (Id,))
        data = g.cursor.fetchall()
        g.cursor.close()
        References = []
        for reference in data:
            References.append(str(reference[2]) + " " + str(reference[3]))

        return render_template(
            "materialsNotFound.html",
            session_user_name=session["username"],
            orgname=session["orgname"],
            References=References,
            Packing=str(data[0][6]),
        )
    else:
        return render_template("error.html", error="Unauthorized Access")


@app.route("/AddXlsx", methods=["POST"])
def AddXlsx():
    try:
        if session.get("user"):
            files = request.files["file"]
            directory = xlsx_directory_path
            for the_file in os.listdir(directory):
                xlsx = os.path.join(directory, the_file)
                try:
                    if os.path.isfile(xlsx):
                        os.unlink(xlsx)
                except Exception:
                    return json.dumps(
                        {"status": "No se ha podido limpiar la carpeta de xlsx"}
                    )
            if files:
                filename = "list.xlsx"
                files.save(os.path.join(directory, filename))

            return json.dumps({"status": "OK"})
        else:
             return json.dumps({"status": "Unauthorized Access"})
    except Exception as e:
        return json.dumps({"status": str(e)})


@app.route("/AddReferencesToPackigViaXlsxFile", methods=["POST"])
def AddReferencesToPackigViaXlsxFile():
    try:
        _user = session.get("user")
        _id = request.form["Id"]
        _packing = request.form["Packing"]
        filename = "list.xlsx"
        doc = openpyxl.load_workbook(xlsx_directory_path + "/" + filename)
        sheet_name = doc.get_sheet_names()
        hoja = doc.get_sheet_by_name(str(sheet_name[0]))

        Material = ""  # Material
        Bult = ""  # Doc.mat.
        Quantity = ""  # Cantidad
        UoM = ""  # UME
        i = 0
        HeadsRow=0
        Datas = []
        NotFoundMaterials = ""
        
        g.cursor = g.conn.cursor()
        g.cursor.callproc("sp_CreateNonExistentReferencesNum")
        TestNumber = g.cursor.fetchone()
        g.cursor.close()

        for filas in hoja.rows:
            j = 0
            for row in filas:
                try:
                    if str((row.value).encode("utf-8")) == "Material":
                        Material = j
                    if str((row.value).encode("utf-8")) == "Doc.mat.":
                        Bult = j
                    if str((row.value).encode("utf-8")) == "Cantidad":
                        Quantity = j
                    if str((row.value).encode("utf-8")) == "UME":
                        UoM = j
                        HeadsRow = i
                except Exception as e:
                    e
                j += 1

            if (
                i > HeadsRow 
                and Material != "" 
                and Bult != "" 
                and Quantity != "" 
                and UoM != ""
            ):
                try:
                    material = str(filas[Material].value)
                    bult = str(filas[Bult].value)
                    quantity = str(filas[Quantity].value)
                    uom = str(filas[UoM].value)

                    if ( 
                        material != "None"
                        and bult != "None"
                        and quantity != "None"
                        and uom != "None"
                    ):
                        g.cursor = g.conn.cursor()
                        g.cursor.callproc(
                            "sp_ValidateReferenceExistence",
                            (material,),
                        )
                        dataCheck = g.cursor.fetchone()
                        g.cursor.close()

                        if (
                            str(dataCheck[0]) != "OK"
                        ):
                            g.cursor = g.conn.cursor()
                            g.cursor.callproc(
                                "sp_AddNonExistentReferences",
                                (
                                    int(TestNumber[0]),
                                    material,
                                    str(dataCheck[0]),
                                    _user,
                                    _packing,
                                ),
                            )
                            g.conn.commit()
                            g.cursor.close()

                            NotFoundMaterials = NotFoundMaterials + material

                        if quantity.find(",") != -1:
                            quantity = quantity.split(",")[0]
                            quantity = quantity+"."+str(filas[Quantity].value).split(",")[1]
                        Datas.append([
                            material,
                            bult,
                            float(quantity),
                            uom
                        ])
                except Exception as e:
                    e
            i+=1
        
        if NotFoundMaterials != "":
            
            return json.dumps({
                "status": "NotFoundMaterials",
                "NumTest": int(TestNumber[0])
            })

        if Material == "" or Bult == "" or Quantity == "" or UoM == "":
            return json.dumps({"status": (
                "Encabezados no localizado verifica que los Encabezados"
                + " contengan exactamente los siguientes titulos"
                + " 'Material' , 'Doc.mat.' , 'Cantidad' , 'UME'"
            )})
        Datas
        return json.dumps({"status":"OK"})

    except Exception as e:
        if str(e) == "File is not a zip file":
            return json.dumps({
                "status":
                "Archivo Excel no soportado este tiene que ser con extension xlsx"
            })
        if str(e) == "tuple index out of range":
            return json.dumps({
                "status":"Archivo o Formato Incorrecto."
            })
        return json.dumps({"status":str(e)})


if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
