from flask import Flask, jsonify, request
import praw
from pymongo import MongoClient
import asyncio
import sys
import pandas as pd
import requests
import json
import string
import re
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import openai

app = Flask(__name__)

@app.route('/scrap', methods=['POST'])
def scrap():
    data = request.get_json()
    subreddit_name = data.get('subreddit')
    def get_comments(submission):
        comments = []
        try:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments:
                replies = []
                if len(comment.replies) > 0:
                    comment.replies.replace_more(limit=0)
                    for reply in comment.replies:
                        replies.append({
                            "id": reply.id,
                            "author": str(reply.author), # Convert Redditor object to string
                            "created_utc": reply.created_utc,
                            "score": reply.score,
                            "body": reply.body
                        })
    
                    replies = sorted(replies, key=lambda x: x["score"], reverse=True)[:5]
                    comments.append({
                        "id": comment.id,
                        "author": str(comment.author), # Convert Redditor object to string
                        "created_utc": comment.created_utc,
                        "score": comment.score,
                        "body": comment.body,
                        "replies": replies
                    })
    
            comments = sorted(comments, key=lambda x: x["score"], reverse=True)[: (20 if len(comments)>20 else len(comments))]
            return comments
    
        except:
            return []

    def get_post(sort_type, submission, get_comments):
        return {
            "id": submission.id,
            "title": submission.title,
            "text": submission.selftext,
            "author": str(submission.author), # Convert Redditor object to string
            "score": submission.score,
            "created_utc": submission.created_utc,
            "num_comments": submission.num_comments,
            "subreddit": str(submission.subreddit), # Convert Subreddit object to string
            "sort_type": sort_type,
            "comments": get_comments(submission)
        }
    
    # authentication reddit
    client_id = "RiaZSGXrAfcvd-nBZR0fiQ"
    client_secret = "Ma5FAfGIpS4dr56crDKB-s14pClZVg"
    user_agent = "python:scrap:v1.0 (by /u/No-Flan6855)"
    username = "No-Flan6855"
    password = "roddytanjakaReddit#"
    
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    except Exception as e:
        print(f"error: {e}")

    
    subreddit = reddit.subreddit(str(subreddit_name))
    
    # get hot reddit posts
    
    hot_sub_posts = []
    hot_subreddits = set()
    submissions_list = []
    for submission in subreddit.hot(limit=10):
        post_data = get_post(sort_type="hot", submission=submission, get_comments=get_comments)
        submissions_list.append(post_data)
    hot_sub_posts.extend(submissions_list)
    
    
    # combine all posts
    all_posts_data = hot_sub_posts
    print(f"Total French posts scraped: {len(all_posts_data)}")
    
    
    
    # sys.stdout.reconfigure(encoding='utf-8')
    return jsonify(all_posts_data)




@app.route('/cluster', methods=['POST'])
def cluster():
  # cleaning text data post
  def clean_text(text):
    text = str(text).lower()
    emoji_pattern = re.compile(
      r'['
      r'\U0001F600-\U0001F64F' 
      r'\U0001F300-\U0001F5FF'  
      r'\U0001F680-\U0001F6FF'  
      r'\U0001F1E0-\U0001F1FF'  
      r'\U00002702-\U000027B0'
      r'\U000024C2-\U0001F251'
      r'\U0001F900-\U0001F9FF'  
      r'\U0001FA00-\U0001FA6F'  
      r'\U00002600-\U000026FF'  
      r'\U00002B00-\U00002BFF' 
      r'\U00002500-\U000025FF'  
      r']+',
      flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text
  def clean_comments_list(comments_list):
    if not isinstance(comments_list, list):
      return comments_list
    cleaned_comments = []
    for comment_dict in comments_list:
      if isinstance(comment_dict, dict):
        if 'body' in comment_dict:
            comment_dict['body'] = clean_text(comment_dict['body'])
        if 'replies' in comment_dict and isinstance(comment_dict['replies'], list):
            comment_dict['replies'] = clean_comments_list(comment_dict['replies'])
      # append each (possibly cleaned) comment to the result list
      cleaned_comments.append(comment_dict)
    return cleaned_comments

  # prepare before sending to LLM
  def format_data(df):
    id_list = list(df['id'])
    title = list(df['title'])
    text = list(df['text'])
    comments = list(df['comments'])
    COMMENT_REPLY_SEPARATOR = " / "
    data_post = {}
    for i in range(len(id_list)):
      current_id = id_list[i]
      # guard against NaN or None values in title/text
      t = "" if pd.isna(title[i]) else str(title[i])
      b = "" if pd.isna(text[i]) else str(text[i])
      data_text = (t + " " + b).strip()
      processed_comments_parts = []
      if comments[i]:
        for comment in comments[i]:
          if isinstance(comment, dict) and comment.get('body'):
            processed_comments_parts.append(str(comment['body']))
            if 'replies' in comment and isinstance(comment['replies'], list):
              for reply in comment['replies']:
                if isinstance(reply, dict) and reply.get('body'):
                  processed_comments_parts.append(str(reply['body']))

      # join parts with a clean separator (no trailing separator problem)
      final_comments_string = COMMENT_REPLY_SEPARATOR.join(processed_comments_parts)

      # store as strings to avoid type issues downstream
      data_post[str(current_id)] = {
        'id': str(current_id),
        'text': data_text,
        'comments': final_comments_string
      }
    return data_post

  async def get_summary(data=None, results=None, model="mistralai/mistral-7b-instruct", api_key="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"):
    prompt ="""
      remove all unecessary words and resume this reddit post in one clear text by analyzing the data I'll give you.
      Don't say anything else but translate the resume in french and just give me the result of the resume in format: {"id":"...", "resume":"..."};
      The data:
    """
    data = data or {}
    results = results or []
    for key, value in data.items():
      try:
        response = requests.post(
          url="https://api.openrouter.ai/v1/chat/completions",
          headers={
            "Authorization": "Bearer " + api_key,
            "content-type": "application/json"
          },
          data=json.dumps({
            "model": model,
            "messages": [
              {
                "role": "user",
                "content": prompt + " id: " + str(data[key]['id']) + ";text:" + str(data[key]['text']) + ";comments:" + str(data[key]['comments'])
              }
            ]
          })
        )

        response.raise_for_status()
        response_json = response.json()

        if "choices" in response_json and len(response_json["choices"]) > 0:
          try:
            result = json.loads(response_json["choices"][0]["message"]["content"])
          except Exception:
            # If the model returned plain text or malformed JSON, keep raw content
            result = response_json["choices"][0]["message"].get("content")
          results.append(result)
        else:
          print(f"Warning: No choices found in API response for ID {key} from model {model}. Response: {response_json}")
          results.append("ERROR_NO_CHOICES")
      except requests.exceptions.RequestException as e:
        print(f"HTTP error when calling OpenRouter for ID {key}: {e}")
        results.append({"id": data[key].get('id') if isinstance(data.get(key, {}), dict) else key, "error": str(e)})


  async def get_cluster(data, results=None, model="mistralai/mistral-7b-instruct", api_key="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"):
    prompt ="""
    Tu es un expert en data science spécialisé en clustering sémantique de textes courts.

    Je vais te donner une liste de résumés de posts Reddit.
    Ta tâche est de :
    1. Lire tous les résumés.
    2. Identifier les thèmes majeurs présents dans l’ensemble.
    3. Créer des clusters cohérents basés uniquement sur le sens des résumés.
    4. Pour chaque cluster, fournir :
      - un titre court et clair (3–6 mots)
      - une description du thème
      - la liste des ID ou indices des résumés appartenant à ce cluster
      - 2–3 mots-clés représentatifs

    Règles :
    - Le nombre de clusters doit être choisi automatiquement en fonction des données (ni trop faible, ni trop élevé).
    - Aucun résumé ne doit apparaître dans plusieurs clusters.
    - Si certains résumés sont trop uniques, place-les dans un cluster “Divers”.
    - Ne pas inventer de contenu : utilise seulement le texte fourni.

    Donne la réponse tout en français au format JSON strict et pour cluster_id n'ajoute rien à part le numéro:

    {
      "clusters": [
        {
          "cluster_id": "string",
          "title": "string",
          "description": "string",
          "keywords": ["string"],
          "items": [ID, ID, ...]
        }
      ]
    }

    Voici la liste des résumés, sous la forme :

    """
    results = results or []
    response = requests.post(
      url="https://api.openrouter.ai/v1/chat/completions",
      headers={
        "Authorization": "Bearer " + api_key,
        "content-type": "application/json"
      },
      data=json.dumps({
        "model": model,
        "messages": [
          {
            "role": "user",
            "content": prompt + " id: " + ", ".join(map(str, data.get('id', []))) + "/resume:" + "; ".join(map(str, data.get('resume', [])))
          }
        ]
      })
    )
    try:
      response.raise_for_status()
      response_json = response.json()

      if "choices" in response_json and len(response_json["choices"]) > 0:
        try:
          result = json.loads(response_json["choices"][0]["message"]["content"])
        except Exception:
          result = response_json["choices"][0]["message"].get("content")
        results.append(result)
      else:
        print(f"Warning: No choices found in clustering API response. Response: {response_json}")
        results.append("ERROR_NO_CHOICES")
    except requests.exceptions.RequestException as e:
      print(f"HTTP error when calling OpenRouter clustering endpoint: {e}")
      results.append({"error": str(e)})

  # add resume in dataframe
  def add_resume(df, summary):
    resume = []
    if summary:
      for i in range(len(df)):
        resume.append(summary[i]['resume'])
      df['summary'] = resume

  # add cluster results in dataframe
  def add_results_cluster(df, cluster_results):
    # cluster_results is expected to be a list where index 0 contains the API result
    if not cluster_results or not isinstance(cluster_results[0], dict) or 'clusters' not in cluster_results[0]:
      print("add_results_cluster: no valid cluster results to add")
      return
    for cluster in cluster_results[0]['clusters']:
      cluster_id = cluster['cluster_id']
      cluster_title = cluster['title']
      description = cluster['description']
      keywords = ", ".join(cluster['keywords'])
      for item_id in cluster['items']:
        df.loc[df['id'] == item_id, 'cluster_id'] = cluster_id
        df.loc[df['id'] == item_id, 'cluster_title'] = cluster_title
        df.loc[df['id'] == item_id, 'description'] = description
        df.loc[df['id'] == item_id, 'keywords'] = keywords

  # preparing data to insert into mongodb
  def prepare_insert(cluster_results):
    # cluster_results is expected to be a list where index 0 contains the API result
    if not cluster_results or not isinstance(cluster_results[0], dict) or 'clusters' not in cluster_results[0]:
      print("prepare_insert: no cluster results to prepare")
      return []
    clusters = cluster_results[0]['clusters']
    rows = []
    for cluster in clusters:
      cluster_id = cluster['cluster_id']
      title = cluster['title']
      description = cluster['description']
      keywords = ", ".join(cluster['keywords'])
      # ensure items are strings when joining
      items = ", ".join(map(str, cluster.get('items', [])))
      for item in cluster['items']:
          rows.append({
            'id': item,
            'title': title,
            'description': description,
            'keywords': keywords,
          })

    return rows
  
  # prepare data for clustering
  def prepare_data(df):
    data_resume = {
      "id":list(df['id']),
      "resume":list(df['summary'])
    }
    return data_resume


  data = request.get_json()
  df = pd.DataFrame(list(data))

  # extracting hot and top data in separate dataframe
  hot_data = df[df['sort_type'] == 'hot']
  top_data = df[df['sort_type'] == 'top']

  #resume data by LLM
  hot_post = format_data(hot_data)
  top_post = format_data(top_data)
  hot_summary = []
  top_summary = []
  async def main():
    await asyncio.gather(
      get_summary(data=hot_post, results=hot_summary, model="openai/gpt-oss-20b:free", api_key="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"),
      get_summary(data=top_post, results=top_summary, model="openai/gpt-oss-20b:free", api_key="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")
    )
  asyncio.run(main())
  add_resume(hot_data, hot_summary)
  add_resume(top_data, top_summary)

  # clustering data
  hot_pre_cluster = prepare_data(hot_data)
  top_pre_cluster = prepare_data(top_data)
  hot_cluster_results = []
  top_cluster_results = []
  async def main_cluster():
    # await both clustering tasks
    await asyncio.gather(
      get_cluster(data=hot_pre_cluster, results=hot_cluster_results, model="openai/gpt-oss-20b:free", api_key="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"),
      get_cluster(data=top_pre_cluster, results=top_cluster_results, model="openai/gpt-oss-20b:free", api_key="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")
    )
  asyncio.run(main_cluster())

  add_results_cluster(hot_data, hot_cluster_results)
  add_results_cluster(top_data, top_cluster_results)

  cluster_hot_data = pd.DataFrame(prepare_insert(hot_cluster_results))
  cluster_hot_data = cluster_hot_data.merge(hot_data[['id', 'summary', 'created_utc', 'sort_type']], on='id', how='left')
  cluster_top_data = pd.DataFrame(prepare_insert(top_cluster_results))
  cluster_top_data = cluster_top_data.merge(top_data[['id', 'summary', 'created_utc', 'sort_type']], on='id', how='left')

  # convert DataFrames to JSON-serializable records before returning
  try:
    hot_records = cluster_hot_data.to_dict(orient='records') if not cluster_hot_data.empty else []
  except Exception:
    hot_records = []

  try:
    top_records = cluster_top_data.to_dict(orient='records') if not cluster_top_data.empty else []
  except Exception:
    top_records = []

  return jsonify({"hot": hot_records, "top": top_records})




#raise RuntimeError("TEST ERREUR FLASK MOD_WSGI")


# Rediriger les erreurs vers stdout pour les logs Apache
sys.stderr = sys.stdout

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

CORS(app)

BASE_URL = "https://www.agent-ia-supportpresta.omega-connect.com"
API_KEY = "4BC8AHKVG3RB5K3AH2DK82SL5SQMJB9H"

openai.api_key = os.getenv("OPENAI_API_KEY")

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
            model="gpt-4.1-mini",
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
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt}
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

    request_data = generate_sql(openai, instructions_systemes_search, user_input)
    print("Requêtes générées :", request_data)

    results = fetch_all_data(BASE_URL, request_data.get("requests"))

    OpenaiResponse = generate_final_answer(openai, user_input, results, instructions_reponses)

    return jsonify({"reponses": OpenaiResponse})



if __name__ == "__main__":
    app.run(debug=True)
