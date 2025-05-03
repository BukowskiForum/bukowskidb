import pymysql
import logging
import sys
import os
from sshtunnel import SSHTunnelForwarder
from sshtunnel import BaseSSHTunnelForwarderError
import re
import json
import argparse

# Configuration
SSH_HOST = os.environ.get('BUKOWSKIFORUM_HOST')
SSH_PORT = 22
SSH_USER = os.environ.get('BUKOWSKIFORUM_USER')

# Database Configuration
DB_HOST_TUNNELED = 'localhost'
DB_PORT_TUNNELED = 3306
DB_USER = os.environ.get('BUKOWSKIFORUM_USER')
DB_PASSWORD = os.environ.get('BUKOWSKIFORUM_DB_PASS')
DB_NAME = os.environ.get('BUKOWSKIFORUM_DB_NAME')

# XenForo Table/Column Names
DB_POST_TABLE = 'xf_post'
DB_POSTID_COLUMN = 'post_id'
DB_THREADID_COLUMN_IN_POST = 'thread_id'
DB_CONTENT_COLUMN = 'message'

DB_THREAD_TABLE = 'xf_thread'
DB_THREADID_COLUMN = 'thread_id'
DB_THREAD_TITLE_COLUMN = 'title'
DB_THREAD_NODEID_COLUMN = 'node_id' # what forum the thread is in
DB_THREAD_STATE_COLUMN = 'discussion_state' # thread visibility

# Target URL Pattern Configuration
# This is the base URL structure we are looking for in posts
TARGET_BASE_URL = 'https://bukowskiforum.com/database/'
# Base URL for constructing links back to forum threads
FORUM_THREAD_BASE_URL = 'https://bukowskiforum.com/threads/'

# Filtering Configuration
EXCLUDED_NODE_ID = 24 # Exclude the moderator forum
VISIBLE_DISCUSSION_STATE = 'visible' # not deleted

# Output
OUTPUT_DIR = 'data'
OUTPUT_JSON_FILE = os.path.join(OUTPUT_DIR, 'thread_links.json')

# Simple logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def generate_map():
    """Connects to the DB, scans posts, and generates the discussion map."""
    print("Starting discussion map generation...")

    # Validate required environment variables
    required_env_vars = {
        'BUKOWSKIFORUM_HOST': SSH_HOST,
        'BUKOWSKIFORUM_USER': SSH_USER,
        'BUKOWSKIFORUM_DB_PASS': DB_PASSWORD,
        'BUKOWSKIFORUM_DB_NAME': DB_NAME
    }
    missing_vars = [k for k, v in required_env_vars.items() if not v]
    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Regex pattern for matching database URLs
    url_pattern = re.compile(
        r'(?:https?://)?'                        
        r'bukowskiforum\.com/database/'          
        r'([^/]+)/'                              # type directory (works, books, etc)
        r'[^/\s]+?-'                             
        r'(\d+)'                                 # numeric ID
        r'(?:/|(?=$)|(?=[\s<\[\]"\')]))',        
        re.IGNORECASE
    )

    discussion_map = {} # Structure: { "type/id": {"threads": [list_of_thread_dicts], "seen_threads": set()} }
    thread_info_cache = {} # Cache thread titles to reduce DB queries: {thread_id: title}

    try:
        print(f"Establishing SSH tunnel...")
        
        with SSHTunnelForwarder(
            (SSH_HOST, SSH_PORT),
            ssh_username=SSH_USER,
            remote_bind_address=(DB_HOST_TUNNELED, DB_PORT_TUNNELED)
        ) as tunnel:
            local_bind_port = tunnel.local_bind_port
            print(f"Connecting to database...")

            connection = None
            try:
                connection = pymysql.connect(
                    host='127.0.0.1',
                    port=local_bind_port,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    charset='utf8mb4',
                    connect_timeout=30,
                    cursorclass=pymysql.cursors.DictCursor
                )

                with connection.cursor() as post_cursor:
                    with connection.cursor() as thread_cursor:
                        print("Querying posts...")
                        post_query = f"""
                            SELECT `{DB_POSTID_COLUMN}`, `{DB_THREADID_COLUMN_IN_POST}`, `{DB_CONTENT_COLUMN}`
                            FROM `{DB_POST_TABLE}`
                            WHERE `{DB_CONTENT_COLUMN}` LIKE %s
                        """
                        like_pattern = f"%{TARGET_BASE_URL}%"
                        post_cursor.execute(post_query, (like_pattern,))

                        all_posts = post_cursor.fetchall()
                        total_posts_found = len(all_posts)
                        print(f"Found {total_posts_found} posts to scan")

                        processed_count = 0
                        links_found_count = 0
                        for post in all_posts:
                            processed_count += 1
                            post_id = post[DB_POSTID_COLUMN]
                            thread_id = post[DB_THREADID_COLUMN_IN_POST]
                            content = post[DB_CONTENT_COLUMN]

                            if not content or not thread_id:
                                continue # Skip posts with no content or no associated thread

                            if processed_count % 5000 == 0:
                                 print(f"Processed {processed_count}/{total_posts_found} posts...")

                            matches = url_pattern.finditer(content)
                            for match in matches:
                                links_found_count += 1
                                type_dir = match.group(1).lower() # e.g., "works"
                                item_id = match.group(2) # e.g., "1234"
                                map_key = f"{type_dir}/{item_id}"

                                # Get thread title (use cache if available)
                                if thread_id not in thread_info_cache:
                                    thread_query = f"""
                                        SELECT `{DB_THREAD_TITLE_COLUMN}`, `{DB_THREAD_NODEID_COLUMN}`, `{DB_THREAD_STATE_COLUMN}`
                                        FROM `{DB_THREAD_TABLE}`
                                        WHERE `{DB_THREADID_COLUMN}` = %s
                                    """
                                    thread_cursor.execute(thread_query, (thread_id,))
                                    thread_result = thread_cursor.fetchone()
                                    if thread_result:
                                        thread_info_cache[thread_id] = thread_result
                                    else:
                                        thread_info_cache[thread_id] = None
                                        continue

                                thread_info = thread_info_cache[thread_id]
                                if thread_info is None: # Check cache for previous miss
                                     continue

                                thread_title = thread_info[DB_THREAD_TITLE_COLUMN]
                                node_id = thread_info[DB_THREAD_NODEID_COLUMN]
                                discussion_state = thread_info[DB_THREAD_STATE_COLUMN]

                                if node_id == EXCLUDED_NODE_ID or discussion_state != VISIBLE_DISCUSSION_STATE:
                                    continue

                                # Initialize entry in map if first time seeing this type/id
                                if map_key not in discussion_map:
                                    discussion_map[map_key] = {"threads": [], "seen_threads": set()}

                                # Add thread info if not already added for this specific map_key
                                if thread_id not in discussion_map[map_key]["seen_threads"]:
                                    thread_url = f"{FORUM_THREAD_BASE_URL.rstrip('/')}/{thread_id}/post-{post_id}"
                                    thread_data = {
                                        "thread_title": thread_title,
                                        "thread_url": thread_url
                                    }
                                    discussion_map[map_key]["threads"].append(thread_data)
                                    discussion_map[map_key]["seen_threads"].add(thread_id)

                print(f"Found {links_found_count} links across {len(discussion_map)} unique MkDocs pages")

                # Clean up the map by removing the temporary 'seen_threads' sets
                final_map = {key: value["threads"] for key, value in discussion_map.items()}

                # Save the map to JSON
                print(f"Saving discussion map...")
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(final_map, f, indent=4, ensure_ascii=False)
                print("Done!")

            except pymysql.MySQLError as err:
                print(f"Database error: {err}")
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error: {e}")
                sys.exit(1)
            finally:
                if connection:
                    connection.close()

    except BaseSSHTunnelForwarderError as tunnel_err:
        print(f"SSH Tunnel Error: {tunnel_err}")
        sys.exit(1)
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a map of forum discussions linking to MkDocs pages.')
    args = parser.parse_args()
    generate_map()
    sys.exit(0)
