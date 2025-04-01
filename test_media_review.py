import pytest
from media_review import DatabaseConnection, add_favorite, list_media, add_review

# Test database connection


@pytest.fixture
def db_connection():
    with DatabaseConnection() as cursor:
        yield cursor  # Provide the cursor for tests

# Test adding a favorite media entry


def test_add_favorite(db_connection):
    user_id, media_id = 1, 1  # Assuming user and media exist
    try:
        add_favorite(user_id, media_id)
        assert True  # If no exception, test passes
    except Exception as e:
        pytest.fail(f"add_favorite failed: {e}")

# Test listing media (should not fail)


def test_list_media():
    try:
        list_media("all")  # Just checking if it runs without error
        assert True
    except Exception as e:
        pytest.fail(f"list_media failed: {e}")

# Test adding a review with threading


def test_add_review():
    user_id = 1  # Assuming this user exists
    reviews = [(1, 5, "Great movie!")]  # (media_id, rating, comment)
    try:
        add_review(user_id, reviews)
        assert True
    except Exception as e:
        pytest.fail(f"add_review failed: {e}")
