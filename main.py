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
