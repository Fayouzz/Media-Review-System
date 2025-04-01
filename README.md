# Multi-Threaded Media Review System

## Project Overview

This **Multi-Threaded Media Review System** is a Python-based CLI application that allows users to:

- **Add, search, and review media items** (Movies, Web Shows, Songs, Cartoons)
- **Favorite media items** for personalized recommendations
- **View top-rated media items** based on user reviews
- **Search media items** by title
- **Leverage Redis caching** for improved performance
- **Use multi-threading** to handle multiple reviews concurrently

---

## 🛠 Installation Steps

### **🔹 Prerequisites**

Ensure you have the following installed:

1. Python (>=3.8)
2. SQLite3 (Comes pre-installed with Python)
3. Redis (for caching)
4. Pytest
5. Tabulate

### **🔹 Start Redis Server** (Required for caching)

- **Linux/macOS:**
  ```sh
  redis-server --daemonize yes
  ```
- **Windows:** Use [Redis for Windows](https://github.com/microsoftarchive/redis/releases) and start `redis-server.exe`.

### **🔹 Initialize the Database**

Run the following command to set up the SQLite database:

```sh
python init.py
```

---

## How to Use

### **🔹 Add a User**

```sh
python media_review.py --add-user <username> <password>
```

Example:

```sh
python media_review.py --add-user alice mysecurepassword
```

### **🔹 Add a Media Item**

```sh
python media_review.py --add-media <title> <type>
```

Example:

```sh
python media_review.py --add-media "Inception" "Movie"
```

### **🔹 List All Media**

```sh
python media_review.py --list
```

### **🔹 Search for a Media**

```sh
python media_review.py --search "<title>"
```

Example:

```sh
python media_review.py --search "Breaking Bad"
```

### **🔹 Add a Review**

```sh
python media_review.py --review <user_id> <media_id> <rating> <comment>
```

Example:

```sh
python media_review.py --review 1 2 5 "Amazing movie!"
```

### **🔹 View Top-Rated Media**

```sh
python media_review.py --top-rated
```

### **🔹 Add to Favorites**

```sh
python media_review.py --favorite <user_id> <media_id>
```

Example:

```sh
python media_review.py --favorite 1 3
```

### **🔹 Get Recommendations**

```sh
python media_review.py --recommend <user_id>
```

Example:

```sh
python media_review.py --recommend 1
```

(If no recommendations are found, top-rated media will be returned.)

---

## Database Schema

### **Users Table**

| id  | username | password        |
| --- | -------- | --------------- |
| 1   | alice    | hashed_password |

### **Media Table**

| id  | title        | type    |
| --- | ------------ | ------- |
| 1   | Inception    | Movie   |
| 2   | Breaking Bad | WebShow |

### **Reviews Table**

| id  | user_id | media_id | rating | comment         | timestamp  |
| --- | ------- | -------- | ------ | --------------- | ---------- |
| 1   | 1       | 2        | 5      | Amazing series! | 2025-03-18 |

### **Favorites Table**

| id  | user_id | media_id | timestamp  |
| --- | ------- | -------- | ---------- |
| 1   | 1       | 3        | 2025-03-18 |

### **Recommendations Table**

| id  | user_id | media_id | generated_by_system |
| --- | ------- | -------- | ------------------- |
| 1   | 1       | 5        | TRUE                |

---

## Features & Tech Stack

- **Python (3.8+)** - Main programming language
- **SQLite3** - Lightweight database
- **Redis** - Caching system
- **Argparse** - CLI interface
- **Threading** - Multi-threaded review submission
- **Factory Pattern** - Dynamic media object creation

---
