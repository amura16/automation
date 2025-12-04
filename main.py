# utf-8
# -*- coding: utf-8 -*-
import sys
import faulthandler
faulthandler.enable()

import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from google import genai
import re
from dotenv import load_dotenv
import os

sys.stderr = sys.stdout

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

CORS(app)

BASE_URL = "https://www.agent-ia-supportpresta.omega-connect.com"
API_KEY = "4BC8AHKVG3RB5K3AH2DK82SL5SQMJB9H"

load_dotenv()  # lit le fichier .env
key = os.getenv("API_KEY")

# client = genai.Client(api_key="AIzaSyDSgNUQke1A6QRkaahNSrpqVvJNo2RV5cA") 
client = genai.Client(api_key=key) 

# prompt

instructions_system = """
T'es un expert prestashop et MySQL.
Ta mission est de trouver quelles tables doivent être consulter pour répondre au demande de l'utilsateur 

1. REGLES DE REPONSES:
    - lister les tables possibles de jointures en SQL pour donner plus d'informations possibles.
    - ta réponse doit être directement un format JSON stricte:
        {"reponses":{
            "nom_groupe_table":['table', 'table'],
            "nom_groupe_table":['table', 'table']
            }
        }
    - ta réponse ne doit pas avoir de texte autour du JSON, tu dois donner directement donner le format JSON sans dire autres choses.

2. Objectif: Lister les tables en fonction de la demande utilisateur en donnant les tables nécessaires pour donner plus d'information satisfaisant à l'utilisateur.

3. Voici des groupes de tables que tu vas travailler:
    1️⃣ Clients et groupes:
        mwafd_customer, mwafd_customer_group, mwafd_customer_message, mwafd_customer_message_sync_imap, mwafd_customer_session, mwafd_customer_thread, mwafd_address, mwafd_address_format, mwafd_emailsubscription, mwafd_guest, mwafd_group, mwafd_group_lang, mwafd_group_reduction, mwafd_group_shop

    2️⃣ Produits, catégories et attributs:

        mwafd_product, mwafd_product_attachment, mwafd_product_attribute, mwafd_product_attribute_combination, mwafd_product_attribute_image, mwafd_product_attribute_lang, mwafd_product_attribute_shop, mwafd_product_carrier, mwafd_product_comment, mwafd_product_comment_criterion, mwafd_product_comment_criterion_category, mwafd_product_comment_criterion_lang, mwafd_product_comment_criterion_product, mwafd_product_comment_grade, mwafd_product_comment_report, mwafd_product_comment_usefulness, mwafd_product_country_tax, mwafd_product_download, mwafd_category, mwafd_category_group, mwafd_category_lang, mwafd_category_product, mwafd_category_shop, mwafd_attribute, mwafd_attribute_group, mwafd_attribute_group_lang, mwafd_attribute_group_shop, mwafd_attribute_lang, mwafd_attribute_shop, mwafd_feature, mwafd_feature_flag, mwafd_feature_lang, mwafd_feature_product, mwafd_feature_shop, mwafd_feature_value, mwafd_feature_value_lang

    3️⃣ Commandes et règles panier

        mwafd_orders, mwafd_order_carrier, mwafd_order_cart_rule, mwafd_order_detail, mwafd_order_detail_tax, mwafd_order_history, mwafd_order_invoice, mwafd_order_invoice_payment, mwafd_order_invoice_tax, mwafd_order_message, mwafd_order_message_lang, mwafd_order_payment, mwafd_order_return, mwafd_order_return_detail, mwafd_order_return_state, mwafd_order_return_state_lang, mwafd_order_slip, mwafd_order_slip_detail, mwafd_order_state, mwafd_order_state_lang, mwafd_cart, mwafd_cart_cart_rule, mwafd_cart_product, mwafd_cart_rule, mwafd_cart_rule_carrier, mwafd_cart_rule_combination, mwafd_cart_rule_country, mwafd_cart_rule_group, mwafd_cart_rule_lang, mwafd_cart_rule_product_rule, mwafd_cart_rule_product_rule_group, mwafd_cart_rule_product_rule_value, mwafd_cart_rule_shop

    4️⃣ Transporteurs et livraison:

        mwafd_carrier, mwafd_carrier_group, mwafd_carrier_lang, mwafd_carrier_shop, mwafd_carrier_tax_rules_group_shop, mwafd_carrier_zone, mwafd_delivery, mwafd_product_carrier

    5️⃣ CMS, pages et liens:

        mwafd_cms, mwafd_cms_category, mwafd_cms_category_lang, mwafd_cms_category_shop, mwafd_cms_lang, mwafd_cms_role, mwafd_cms_role_lang, mwafd_cms_shop, mwafd_page, mwafd_pagenotfound, mwafd_page_type, mwafd_page_viewed, mwafd_linksmenutop, mwafd_linksmenutop_lang, mwafd_link_block, mwafd_link_block_lang, mwafd_link_block_shop, mwafd_meta, mwafd_meta_lang

    6️⃣ Images:

        mwafd_image, mwafd_image_lang, mwafd_image_shop, mwafd_image_type, mwafd_product_attribute_image, mwafd_product_attachment

    7️⃣ Autres (configuration, modules, logs…):

        mwafd_access, mwafd_admin_filter, mwafd_alias, mwafd_api_client, mwafd_authorization_role, mwafd_blockwishlist_statistics, mwafd_configuration, mwafd_configuration_kpi, mwafd_configuration_kpi_lang, mwafd_configuration_lang, mwafd_connections, mwafd_connections_page, mwafd_connections_source, mwafd_employee, mwafd_employee_account, mwafd_employee_session, mwafd_employee_shop, mwafd_eventbus_incremental_sync, mwafd_eventbus_job, mwafd_eventbus_live_sync, mwafd_eventbus_type_sync, mwafd_hook, mwafd_hook_alias, mwafd_hook_module, mwafd_hook_module_exceptions, mwafd_lang, mwafd_lang_shop, mwafd_log, mwafd_mail, mwafd_mailalert_customer_oos, mwafd_manufacturer, mwafd_manufacturer_lang, mwafd_manufacturer_shop, mwafd_mbo_api_config, mwafd_memcached_servers, mwafd_migrationpro_configuration, mwafd_migrationpro_data, mwafd_migrationpro_error_logs, mwafd_migrationpro_mapping, mwafd_migrationpro_migrated_data, mwafd_migrationpro_pass, mwafd_migrationpro_process, mwafd_migrationpro_save_mapping, mwafd_migrationpro_warning_logs, mwafd_module, mwafd_module_access, mwafd_module_carrier, mwafd_module_country, mwafd_module_currency, mwafd_module_group, mwafd_module_history, mwafd_module_preference, mwafd_module_shop, mwafd_mutation, mwafd_operating_system, mwafd_date_range, mwafd_condition, mwafd_condition_advice, mwafd_info, mwafd_info_lang, mwafd_info_shop, mwafd_ganalytics, mwafd_ganalytics_data, mwafd_gender, mwafd_gender_lang, mwafd_homeslider, mwafd_homeslider_slides, mwafd_homeslider_slides_lang, mwafd_layered_category, mwafd_layered_filter, mwafd_layered_filter_block, mwafd_layered_filter_shop, mwafd_layered_indexable_attribute_group, mwafd_layered_indexable_attribute_group_lang_value, mwafd_layered_indexable_attribute_lang_value, mwafd_layered_indexable_feature, mwafd_layered_indexable_feature_lang_value, mwafd_layered_indexable_feature_value_lang_value, mwafd_layered_price_index, mwafd_layered_product_attribute, mwafd_import_match, mwafd_pack

Obligation stricte: n'inventes pas de table qui n'est pas sur la liste.
"""

instructions_system_sql = """
Tu es un expert PrestaShop, MySQL et analyse sémantique.
Ta mission : convertir toute demande utilisateur en requêtes SQL correctes, sécurisées et exploitables avec PDO, au format JSON strict.

1. RÈGLES STRICTES :

Format JSON STRICT

{
  "requests": [
    {
      "sql": "REQUETE SQL AVEC :param",
      "params": {
        "clé": "valeur"
      }
    }
  ]
}

Aucun texte avant ou après le JSON.

Jamais de commentaires ni d’explications.

Respect des tables et préfixes

Utiliser uniquement les tables existantes et les noms exacts (ex. mwafd_customer, mwafd_orders, mwafd_product, etc.).

Respecter le préfixe tel quel (ex. mwafd_).

Ne jamais inventer de table ou colonne.

2. Paramètres PDO:

    Toutes les valeurs utilisateur passent par :param.

    Les clés dans params doit toujours correspondre aux colonnes de la base.
 
    Toutes les recherches par nom doivent utiliser LOWER() pour insensibilité à la casse.

    Détection dynamique et jointures intelligentes

    La requête SQL ne doit pas être limité juste à la demande de l'utilisateur, il faut que tu fasses le plus de jointure possible et prendre plus de donnée pour satisfaire l'utilisateur
    (exemple: si l'utilisateur demande l'état de sa commande, tu dois donner la date, le nom du produit, l'id client, l'id commande, etc)
    Il faut que l'utilisateur aie des réponses détaillés et précis.

3. Sécurité:

    Pas de valeurs directes dans la requête → toujours :param.

    Pas de SQL dangereux.

    Collecte maximale de données pertinentes

    la requête doit toujours être SELECT

    interdiction de UPDATE, DELETE, INSERT

4.Objectif final

    Générer un JSON directement exploitable par un script PHP PDO.

    La requête doit être sécurisée, correcte et cohérente avec la demande utilisateur.

    Toujours vérifier que la requête fonctionne même si les colonnes supplémentaires n’existent pas.
"""


instructions_system_reponse = """
    Tu es un assistant expert en PrestaShop. Ta tâche est de répondre aux questions des utilisateurs
    en utilisant uniquement les données fournies dans les rubriques PrestaShop : "customers", "orders", "order_states". 
    Ne jamais inventer de données. Ne jamais répondre à partir de connaissances externes.

    Lorsque l'utilisateur pose une question sur un client ou une commande, tu dois :

    1. Identifier le client concerné à partir des informations fournies (nom, prénom, email).  
    2. Identifier les commandes pertinentes du client, et pour chaque commande, fournir :
    - l'identifiant de la commande,
    - la date de la commande,
    - le montant total payé,
    - la liste des produits achetés (nom, quantité, prix),
    - l'état actuel de la commande (state_name).
    3. Fournir la réponse sous forme de texte naturel détaillé, clair et concis, en français.
    4. Si la question concerne "la dernière commande", ne répondre qu'à celle-ci.
    5. Toujours détailler chaque produit avec nom, quantité et prix, ainsi que l'état de la commande.
"""



def clean_json_string(raw_text):
    """
    Nettoie un texte contenant un JSON entre ``` ou avec des retours à la ligne,
    et renvoie un dictionnaire Python exploitable.
    """
    if not isinstance(raw_text, str):
        raise ValueError("raw_text doit être une chaîne de caractères")

    # 1️⃣ Supprimer les backticks et éventuel 'json'
    cleaned = re.sub(r"```(?:json)?\n?", "", raw_text)
    cleaned = cleaned.replace("```", "")  # Supprime les backticks de fin

    # 2️⃣ Supprimer les retours à la ligne superflus
    cleaned = cleaned.strip()

    # 3️⃣ Charger le JSON
    try:
        data = json.loads(cleaned)
        return data
    except json.JSONDecodeError as e:
        print("Erreur JSON :", e)
        return None


def tables_finder(client, instructions, user_question):

    search_prompt = """
    - Analyse bien la demande utilisateur et choisis bien les tables pour récupérer les données en fonction de la reqûete utilisateur.
    - Voici la demande utilisateur:
    """
    
    prompt = search_prompt + user_question

    print("\n\nPrompt envoyé au LLM :", prompt, "\n\n")

    try:
        # 1️⃣ APPEL LLM
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"System:{instructions}\nUtilisateur: {prompt}"
        )

        print(response.text)

        content = response.text.strip()
        content = clean_json_string(content)
        print("Réponse LLM :", content)

        # 2️⃣ PARSE DU JSON
        try:
            json_data = json.loads(content)
        except:
            return {"error": "invalid_json", "raw": content}

        if "reponses" not in json_data:
            return {"error": "missing_reponses", "raw": json_data}

        # 3️⃣ ENVOI D'UN SEUL BLOC À PHP !
        url = f"{BASE_URL}/ps_api/col_finder.php"
        payload = {"reponses": json_data["reponses"]}

        try:
            r = requests.post(url, json=payload)
            result = r.json()
        except Exception as e:
            result = {"success": False, "error": str(e)}

        return result

    except Exception as e:
        return {"error": str(e)}




def generate_sql(client, instructions, data_field, user_input):
    prompt = f"géneres des requetes sql en fonction de la demanade utilisateur:{user_input} et voici les tables que tu vas consulter: {data_field}"
    try:
        # 1️⃣ APPEL LLM
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"System:{instructions}\nUtilisateur: {prompt}"
        )

        print(response.text)

        content = response.text.strip()
        content = clean_json_string(content)
        print("sql generé: ", content)
        return content
    except:
        print("error lors de la generation sql")

    

def fetch_data(BASE_URL, data):
    url = f"{BASE_URL}/ps_api/data_shop/Retrieve.php"

    # Si la donnée est une chaîne JSON (comme dans ton exemple), on la parse
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception as e:
            print("Erreur parsing JSON:", e)
            return {"success": False, "error": f"Invalid JSON: {e}"}

    # Vérifie que c'est bien au format attendu
    if "requests" not in data or not isinstance(data["requests"], list):
        return {"success": False, "error": "JSON must contain 'requests' list"}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PythonClient/1.0"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}



def generate_final_answer(client, question, data, instructions):
    prompt = f"Voici les données PrestaShop : {data}\nQuestion : {question}\nRéponds clairement."
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"System:{instructions}\nUtilisateur: {prompt}"
        )

        print(response.text)

        return response.text
    
    except Exception as e:
        print("❌ Erreur génération réponse LLM :", e)
        return "Erreur lors de la génération de la réponse."


@app.route("/chatbot", methods=["POST"])
def chatbot():
    request_user = request.get_json()
    user_input = request_user.get("input", "")

    table_fields = tables_finder(client, instructions_system, user_input)

    requetes = generate_sql(client, instructions_system_sql, table_fields, user_input)

    php_response = fetch_data(BASE_URL, requetes)
    
    reponseFinale = generate_final_answer(client, user_input, php_response, instructions_system_reponse)

    return jsonify({"reponses": reponseFinale})


@app.errorhandler(500)
def internal_error(error):
    return "<pre>" + traceback.format_exc() + "</pre>", 500


if __name__ == "__main__":
    app.run(debug=True)
