from flask import Flask, jsonify
import praw
from pymongo import MongoClient
import asyncio
import sys

app = Flask(__name__)

@app.route('/scrap', methods=['POST'])
def scrap():
    data = request.get_json(force=True, silent=True)
    subreddit_name = data.get('subreddit', 'movies')
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
    for submission in subreddit.hot(limit=5):
        post_data = get_post(sort_type="hot", submission=submission, get_comments=get_comments)
        submissions_list.append(post_data)
    for submission in subreddit.top(limit=5):
        post_data = get_post(sort_type="top", submission=submission, get_comments=get_comments)
        submissions_list.append(post_data)
    hot_sub_posts.extend(submissions_list)
    
    
    # combine all posts
    all_posts_data = hot_sub_posts
    print(f"Total French posts scraped: {len(all_posts_data)}")
    
    
    
    sys.stdout.reconfigure(encoding='utf-8')
    return jsonify(all_posts_data)
