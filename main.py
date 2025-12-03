# utf-8
# -*- coding: utf-8 -*-
import sys
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from openai import OpenAI



sys.stderr = sys.stdout

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

CORS(app)

BASE_URL = "https://www.agent-ia-supportpresta.omega-connect.com"
API_KEY = "4BC8AHKVG3RB5K3AH2DK82SL5SQMJB9H"

# openai.api_key = "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"
client_openai = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key="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",
)



# prompt 
instructions_systemes_search = """
Tu es un expert PrestaShop, MySQL et analyse sémantique.
Ta mission : convertir toute demande utilisateur en requêtes SQL correctes, sécurisées et exploitables avec PDO, au format JSON strict.

🔥 RÈGLES STRICTES :

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

Paramètres PDO

Toutes les valeurs utilisateur passent par :param.

Pour les noms de clients ou produits, utiliser firstname, lastname ou product_name.

Toutes les recherches par nom doivent utiliser LOWER() pour insensibilité à la casse.

Détection dynamique et jointures intelligentes

Clients : id → customer.id_customer, email → customer.email, firstname/lastname → customer.firstname/lastname.

Produits : id → product.id_product, nom → product_lang.name (avec id_lang = 1).

Commandes : id_order, reference, id_customer, current_state, total_paid, date_add → orders.

États de commande : order_state_lang.name (avec id_lang = 1).

Joindre automatiquement order_state_lang si la demande mentionne “état” ou “status”.

Joindre customer pour toutes les requêtes sur commandes.

Joindre product_lang pour toutes les requêtes sur produits nommés.

Règles sémantiques

“dernière commande” → ORDER BY o.date_add DESC LIMIT 1.

“état de …” → joindre order_state_lang.

“id de ce produit” → sélectionner depuis product ou product_lang.

“liste de commandes d’un client” → inclure autant de colonnes utiles que possible : id_order, reference, current_state, total_paid, date_add.

Toujours adapter les colonnes et jointures en fonction du sens exact de la demande.

Sécurité

Pas de valeurs directes dans la requête → toujours :param.

Pas de SQL dangereux.

Collecte maximale de données pertinentes

Pour chaque entité (client, commande, produit), récupérer toutes les colonnes pertinentes existantes dans PrestaShop sans causer d’erreur.

Ne jamais sélectionner une colonne qui n’existe pas.

Objectif final

Générer un JSON directement exploitable par un script PHP PDO.

La requête doit être sécurisée, correcte et cohérente avec la demande utilisateur.

Toujours vérifier que la requête fonctionne même si les colonnes supplémentaires n’existent pas.
"""




instructions_reponses = """
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


def generate_sql(client, instructions, user_question):
    search_prompt = """
    - Voici la liste des tables de la base de donnée Prestashop:
        mwafd_access
        mwafd_accessory
        mwafd_address
        mwafd_address_format
        mwafd_admin_filter
        mwafd_advice
        mwafd_advice_lang
        mwafd_alias
        mwafd_api_client
        mwafd_attachment
        mwafd_attachment_lang
        mwafd_attribute
        mwafd_attribute_group
        mwafd_attribute_group_lang
        mwafd_attribute_group_shop
        mwafd_attribute_lang
        mwafd_attribute_shop
        mwafd_authorization_role
        mwafd_blockwishlist_statistics
        mwafd_carrier
        mwafd_carrier_group
        mwafd_carrier_lang
        mwafd_carrier_shop
        mwafd_carrier_tax_rules_group_shop
        mwafd_carrier_zone
        mwafd_cart
        mwafd_cart_cart_rule
        mwafd_cart_product
        mwafd_cart_rule
        mwafd_cart_rule_carrier
        mwafd_cart_rule_combination
        mwafd_cart_rule_country
        mwafd_cart_rule_group
        mwafd_cart_rule_lang
        mwafd_cart_rule_product_rule
        mwafd_cart_rule_product_rule_group
        mwafd_cart_rule_product_rule_value
        mwafd_cart_rule_shop
        mwafd_category
        mwafd_category_group
        mwafd_category_lang
        mwafd_category_product
        mwafd_category_shop
        mwafd_cms
        mwafd_cms_category
        mwafd_cms_category_lang
        mwafd_cms_category_shop
        mwafd_cms_lang
        mwafd_cms_role
        mwafd_cms_role_lang
        mwafd_cms_shop
        mwafd_condition
        mwafd_condition_advice
        mwafd_configuration
        mwafd_configuration_kpi
        mwafd_configuration_kpi_lang
        mwafd_configuration_lang
        mwafd_connections
        mwafd_connections_page
        mwafd_connections_source
        mwafd_contact
        mwafd_contact_lang
        mwafd_contact_shop
        mwafd_country
        mwafd_country_lang
        mwafd_country_shop
        mwafd_currency
        mwafd_currency_lang
        mwafd_currency_shop
        mwafd_customer
        mwafd_customer_group
        mwafd_customer_message
        mwafd_customer_message_sync_imap
        mwafd_customer_session
        mwafd_customer_thread
        mwafd_customization
        mwafd_customization_field
        mwafd_customization_field_lang
        mwafd_customized_data
        mwafd_date_range
        mwafd_delivery
        mwafd_emailsubscription
        mwafd_employee
        mwafd_employee_account
        mwafd_employee_session
        mwafd_employee_shop
        mwafd_eventbus_incremental_sync
        mwafd_eventbus_job
        mwafd_eventbus_live_sync
        mwafd_eventbus_type_sync
        mwafd_feature
        mwafd_feature_flag
        mwafd_feature_lang
        mwafd_feature_product
        mwafd_feature_shop
        mwafd_feature_value
        mwafd_feature_value_lang
        mwafd_ganalytics
        mwafd_ganalytics_data
        mwafd_gender
        mwafd_gender_lang
        mwafd_group
        mwafd_group_lang
        mwafd_group_reduction
        mwafd_group_shop
        mwafd_gsitemap_sitemap
        mwafd_guest
        mwafd_homeslider
        mwafd_homeslider_slides
        mwafd_homeslider_slides_lang
        mwafd_hook
        mwafd_hook_alias
        mwafd_hook_module
        mwafd_hook_module_exceptions
        mwafd_image
        mwafd_image_lang
        mwafd_image_shop
        mwafd_image_type
        mwafd_import_match
        mwafd_info
        mwafd_info_lang
        mwafd_info_shop
        mwafd_lang
        mwafd_lang_shop
        mwafd_layered_category
        mwafd_layered_filter
        mwafd_layered_filter_block
        mwafd_layered_filter_shop
        mwafd_layered_indexable_attribute_group
        mwafd_layered_indexable_attribute_group_lang_value
        mwafd_layered_indexable_attribute_lang_value
        mwafd_layered_indexable_feature
        mwafd_layered_indexable_feature_lang_value
        mwafd_layered_indexable_feature_value_lang_value
        mwafd_layered_price_index
        mwafd_layered_product_attribute
        mwafd_linksmenutop
        mwafd_linksmenutop_lang
        mwafd_link_block
        mwafd_link_block_lang
        mwafd_link_block_shop
        mwafd_log
        mwafd_mail
        mwafd_mailalert_customer_oos
        mwafd_manufacturer
        mwafd_manufacturer_lang
        mwafd_manufacturer_shop
        mwafd_mbo_api_config
        mwafd_memcached_servers
        mwafd_message
        mwafd_message_readed
        mwafd_meta
        mwafd_meta_lang
        mwafd_migrationpro_configuration
        mwafd_migrationpro_data
        mwafd_migrationpro_error_logs
        mwafd_migrationpro_mapping
        mwafd_migrationpro_migrated_data
        mwafd_migrationpro_pass
        mwafd_migrationpro_process
        mwafd_migrationpro_save_mapping
        mwafd_migrationpro_warning_logs
        mwafd_module
        mwafd_module_access
        mwafd_module_carrier
        mwafd_module_country
        mwafd_module_currency
        mwafd_module_group
        mwafd_module_history
        mwafd_module_preference
        mwafd_module_shop
        mwafd_mutation
        mwafd_operating_system
        mwafd_orders
        mwafd_order_carrier
        mwafd_order_cart_rule
        mwafd_order_detail
        mwafd_order_detail_tax
        mwafd_order_history
        mwafd_order_invoice
        mwafd_order_invoice_payment
        mwafd_order_invoice_tax
        mwafd_order_message
        mwafd_order_message_lang
        mwafd_order_payment
        mwafd_order_return
        mwafd_order_return_detail
        mwafd_order_return_state
        mwafd_order_return_state_lang
        mwafd_order_slip
        mwafd_order_slip_detail
        mwafd_order_state
        mwafd_order_state_lang
        mwafd_pack
        mwafd_page
        mwafd_pagenotfound
        mwafd_page_type
        mwafd_page_viewed
        mwafd_product
        mwafd_product_attachment
        mwafd_product_attribute
        mwafd_product_attribute_combination
        mwafd_product_attribute_image
        mwafd_product_attribute_lang
        mwafd_product_attribute_shop
        mwafd_product_carrier
        mwafd_product_comment
        mwafd_product_comment_criterion
        mwafd_product_comment_criterion_category
        mwafd_product_comment_criterion_lang
        mwafd_product_comment_criterion_product
        mwafd_product_comment_grade
        mwafd_product_comment_report
        mwafd_product_comment_usefulness
        mwafd_product_country_tax


    - Analyse bien la demande utilisateur et choisis bien les tables pour récupérer les données en fonction de la reqûete utilisateur.
    - Voici la demande utilisateur:
    """
    
    prompt = search_prompt + user_question
    print("\n\nprompt:", user_question, "\n\n")

    try:

        response = client.chat.completions.create(
            model="moonshotai/Kimi-K2-Instruct-0905",
            messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
            ]
        )

        content = response.choices[0].message.content.strip()

        # Nettoyage des ```json ... ```
        if content.startswith("```"):
            content = content.replace("```json", "")
            content = content.replace("```", "").strip()

        print("Réponse détection rubriques GPT :", content)

        json_data = json.loads(content)

        if "requests" not in json_data:
            return {"requests": []}

        return json_data

    except Exception as e:
        print("Erreur detection rubriques :", e)
        return {"requests": []}



def fetch_data(BASE_URL, item):
    url = f"{BASE_URL}/ps_api/data_shop/Retrieve.php"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }

    payload = {"requests": [item]}

    response = requests.post(url, json=payload, headers=headers)

    print("Status code:", response.status_code)

    try:
        return response.json()
    except Exception:
        return {"success": False, "error": f"JSON decode failed: {response.text}"}


def fetch_all_data(BASE_URL, requests_list):
    results = []
    for item in requests_list:
        results.append(fetch_data(BASE_URL, item))
    return results


def generate_final_answer(client, question, data, instructions):
    prompt = f"Voici les données PrestaShop : {data}\nQuestion : {question}\nRéponds clairement."
    
    try:
        response = client.chat.completions.create(
            model="moonshotai/Kimi-K2-Instruct-0905",
            messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
            ]
        )

        return response.choices[0].message.content
    except Exception as e:
        print("❌ Erreur génération réponse LLM :", e)
        return "Erreur lors de la génération de la réponse."


@app.route("/chatbot", methods=["POST"])
def chatbot():
    request_user = request.get_json()
    user_input = request_user.get("input", "")

    request_data = generate_sql(client_openai, instructions_systemes_search, user_input)
    print("Requêtes générées :", request_data)

    results = fetch_all_data(BASE_URL, request_data.get("requests"))

    OpenaiResponse = generate_final_answer(client_openai, user_input, results, instructions_reponses)

    return jsonify({"reponses": OpenaiResponse})


if __name__ == "__main__":
    app.run(debug=True)
