import sqlite3
import redis
import threading
import argparse
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from tabulate import tabulate

# Database Connection


class DatabaseConnection:
    def __enter__(self):
        self.conn = sqlite3.connect(
            "media_reviews.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()


# Redis Caching Setup
cache = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Check Redis Connection
try:
    if cache.ping():
        print("Redis is connected and working!")
    else:
        print("Redis connection failed.")
except redis.exceptions.ConnectionError as e:
    print(f"Redis connection error: {e}")

# Implementing LRU Cache with Redis
CACHE_SIZE = 5

# Initialize Database Schema
with DatabaseConnection() as cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        media_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        alert TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)


# Media Factory Pattern
@dataclass
class Media(ABC):
    title: str
    type: str

    @abstractmethod
    def get_details(self):
        pass


@dataclass
class Movie(Media):
    def get_details(self):
        return f"Movie: {self.title}"


@dataclass
class WebShow(Media):
    def get_details(self):
        return f"WebShow: {self.title}"


@dataclass
class Cartoon(Media):
    def get_details(self):
        return f"Cartoon: {self.title}"


@dataclass
class Song(Media):
    def get_details(self):
        return f"Song: {self.title}"


class MediaFactory:
    @staticmethod
    def create_media(title: str, media_type: str):
        media_classes = {"Movie": Movie, "WebShow": WebShow, "Song": Song}
        if media_type in media_classes:
            return media_classes[media_type](title, media_type)
        else:
            logging.warning(
                f"Unknown media type '{media_type}' for title '{title}'. Defaulting to generic media.")
            # Return a generic Media object instead of raising an error
            return Media(title, media_type)

# Function to Add a Media Item


def add_media(title, media_type):
    """Inserts a new media item into the database if it does not already exist."""
    try:
        with DatabaseConnection() as cursor:
            # Restrict media types
            valid_types = ["Movie", "WebShow", "Song", "Cartoon"]
            if media_type not in valid_types:
                print(
                    f"Invalid media type '{media_type}'. Choose from {valid_types}.")
                return

            cursor.execute("SELECT * FROM media WHERE title = ?", (title,))
            if cursor.fetchone():
                print(f"Media item '{title}' already exists in the database.")
                return

            cursor.execute(
                "INSERT INTO media (title, type) VALUES (?, ?)", (title, media_type))
            print(
                f"Media item '{title}' added successfully as a '{media_type}'!")
    except sqlite3.Error as e:
        print(f"Database Error: {e}")


# Function to Remove a Media Item
def remove_media(media_id):
    """Removes a media item from the database by ID."""
    with sqlite3.connect("media_reviews.db") as conn:
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM media WHERE id = ?", (media_id,))
            if cursor.rowcount == 0:
                print(f"No media item found with ID {media_id}.")
            else:
                print(f"Media item with ID {media_id} removed successfully.")

            conn.commit()
        except sqlite3.Error as e:
            print(f"Error: {e}")

# Function to Add Favorite Media


def add_favorite(user_id, media_id):
    with DatabaseConnection() as cursor:
        cursor.execute(
            "INSERT INTO favorites (user_id, media_id) VALUES (?, ?)", (user_id, media_id))
    print(f"Media ID {media_id} added to favorites for User ID {user_id}!")

# Function to List Media


def list_media(limit):
    cached_media = cache.get("media_list")

    if cached_media and limit == "all":
        print("Fetching from cache...")
        print(cached_media)
        return

    print("Fetching from database...")
    with DatabaseConnection() as cursor:
        query = """
            SELECT m.id, m.title, m.type, IFNULL(AVG(r.rating), 'No Ratings') AS avg_rating 
            FROM media m 
            LEFT JOIN reviews r ON m.id = r.media_id 
            GROUP BY m.id
        """
        if limit != "all":
            query += " LIMIT ?"
            cursor.execute(query, (int(limit),))
        else:
            cursor.execute(query)

        results = cursor.fetchall()

    if not results:
        print("No media found. Please add media first!")
    else:
        table_data = [
            [row[0], MediaFactory.create_media(row[1], row[2]).get_details(), row[3]] for row in results
        ]

        headers = ["ID", "Media Details", "Avg Rating"]
        table_output = tabulate(table_data, headers=headers, tablefmt="grid")

        print(table_output)
        cache.set("media_list", table_output, ex=60)


def add_review(user_id, reviews):
    """Function to add media reviews and generate alerts for favorited media."""
    with DatabaseConnection() as cursor:
        cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            print("Invalid user ID. Review submission failed.")
            return

    def review_task(media_id, rating, comment):
        with DatabaseConnection() as cursor:
            # Insert the review
            cursor.execute("INSERT INTO reviews (user_id, media_id, rating, comment) VALUES (?, ?, ?, ?)",
                           (user_id, media_id, rating, comment))

            # Find users who favorited this media
            cursor.execute(
                "SELECT user_id FROM favorites WHERE media_id = ?", (media_id,))
            favorite_users = [row[0] for row in cursor.fetchall()]

            # Insert alerts for those users
            alert_message = f"User {user_id} added a review for media ID {media_id}."
            for fav_user_id in favorite_users:
                if fav_user_id != user_id:  # Avoid alerting the same user
                    cursor.execute(
                        "INSERT INTO alerts (user_id, alert) VALUES (?, ?)", (fav_user_id, alert_message))

        print(f"Review submitted for Media ID {media_id}!")

    # Create threads for each review
    threads = []
    for media_id, rating, comment in reviews:
        thread = threading.Thread(
            target=review_task, args=(media_id, rating, comment))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def get_alerts(user_id):
    """Fetch and display alerts for a specific user."""
    with DatabaseConnection() as cursor:
        cursor.execute(
            "SELECT alert FROM alerts WHERE user_id = ?", (user_id,))
        alerts = cursor.fetchall()

    if alerts:
        print("Your Alerts:")
        for alert in alerts:
            print(f"- {alert[0]}")
    else:
        print("No new alerts.")


# Function to Search Media
def search_media(title):
    with DatabaseConnection() as cursor:
        cursor.execute("SELECT * FROM media WHERE title LIKE ?",
                       (f"%{title}%",))
        results = cursor.fetchall()

    if results:
        for row in results:
            print(f"ID: {row[0]}, Title: {row[1]}, Type: {row[2]}")
    else:
        print("No matching media found in the database")


def recommend_media(user_id):
    with DatabaseConnection() as cursor:
        # Get user's favorite media
        cursor.execute("""
            SELECT DISTINCT media_id FROM favorites WHERE user_id = ?
        """, (user_id,))
        favorite_media = [row[0] for row in cursor.fetchall()]

        if favorite_media:
            # Recommend one media item per type from user's favorites
            cursor.execute("""
                SELECT m.id, m.title, m.type 
                FROM media m 
                WHERE m.id IN ({}) 
                GROUP BY m.type 
                ORDER BY RANDOM()
            """.format(",".join("?" * len(favorite_media))), favorite_media)

            recommendations = cursor.fetchall()
        else:
            # No favorites found, recommend top-rated media instead
            cursor.execute("""
                SELECT m.id, m.title, m.type 
                FROM media m
                JOIN reviews r ON m.id = r.media_id
                GROUP BY m.id
                ORDER BY AVG(r.rating) DESC
                LIMIT 5
            """)
            recommendations = cursor.fetchall()

    if recommendations:
        print("Recommended Media:")
        for media in recommendations:
            print(f"{media[1]} ({media[2]}) - ID: {media[0]}")
    else:
        print("No recommendations available!")

# Function to Get Top Rated Media


def get_top_rated():
    with DatabaseConnection() as cursor:
        cursor.execute("""
            SELECT m.id, m.title, ROUND(AVG(r.rating), 2) AS avg_rating
            FROM media m 
            JOIN reviews r ON m.id = r.media_id  -- Ensures only rated media are selected
            GROUP BY m.id 
            ORDER BY avg_rating DESC 
            LIMIT 5
        """)
        results = cursor.fetchall()

    if not results:
        print("No rated media available yet!")
    else:
        table_data = [[row[0], row[1], row[2]] for row in results]
        headers = ["Media ID", "Title", "Average Rating"]
        table_output = tabulate(table_data, headers=headers, tablefmt="grid")

        print(table_output)

# Function to Add User


def add_user(username, password):
    with DatabaseConnection() as cursor:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    print("User added successfully!")

# Function to List All Users


def list_users():
    """Fetch and display all users from the database."""
    with sqlite3.connect("media_reviews.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users")
        users = cursor.fetchall()

    if users:
        print("User IDs and Usernames:")
        for user in users:
            print(f"ID: {user[0]}, Username: {user[1]}")
    else:
        print("No users found in the database.")

# Function to Remove a User


def remove_user(user_id):
    """Removes a user from the database by user ID."""
    with sqlite3.connect("media_reviews.db") as conn:
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if cursor.rowcount == 0:
                print(f"No user found with ID {user_id}.")
            else:
                print(f"User with ID {user_id} removed successfully.")
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Media Review System")
    parser.add_argument("--add-media", nargs=2,
                        metavar=("title", "type"), help="Add a new media item")
    parser.add_argument("--remove-media", type=int,
                        metavar="media_id", help="Remove a media item by ID")
    parser.add_argument("--list", action="store_true",
                        help="View all media items")
    parser.add_argument("--top-rated", action="store_true",
                        help="View top-rated media")
    parser.add_argument("--search", type=str, help="Search for media by title")
    parser.add_argument("--add-user", nargs=2,
                        metavar=("username", "password"), help="Add a new user")
    parser.add_argument("--recommend", type=int, metavar="user_id",
                        help="Get recommendations for a user")
    parser.add_argument("--review", nargs=3, metavar=("user_id", "media_id", "rating"),
                        help="Provide user ID, media ID, and rating (e.g., --review 8 11 5)")
    parser.add_argument("--comment", type=str, nargs="*", metavar="comment",
                        help="Optional comment on the review")
    parser.add_argument("--favorite", nargs=2, metavar=("user_id",
                        "media_id"), type=int, help="Add media to favorites")
    parser.add_argument("--list-users", action="store_true",
                        help="List all users in the database")
    parser.add_argument("--remove-user", type=int,
                        metavar="user_id", help="Remove a user by ID")
    parser.add_argument("--alerts", type=int, metavar="user_id",
                        help="View alerts for a specific user")

    args = parser.parse_args()

    if args.review:
        try:
            user_id, media_id, rating = map(
                int, args.review)  # Convert to integers
            comment = " ".join(
                args.comment) if args.comment else "No comment provided"

            print(
                f"Parsed: user_id={user_id}, media_id={media_id}, rating={rating}, comment={comment}")

            parsed_review = [(media_id, rating, comment)]
            add_review(user_id, parsed_review)
        except ValueError as e:
            print(
                f"Error: user_id, media_id, and rating must be integers. {e}")

    if args.list:
        list_media("all")

    elif args.add_media:
        title, media_type = args.add_media
        add_media(title, media_type)

    elif args.remove_media:
        remove_media(args.remove_media)

    elif args.top_rated:
        get_top_rated()

    elif args.search:
        search_media(args.search)

    elif args.add_user:
        username, password = args.add_user
        add_user(username, password)

    elif args.recommend:
        user_id = args.recommend
        recommend_media(user_id)

    elif args.favorite:
        user_id, media_id = args.favorite
        add_favorite(user_id, media_id)

    elif args.list_users:
        list_users()

    elif args.remove_user:
        remove_user(args.remove_user)

    elif args.alerts:
        get_alerts(args.alerts)
