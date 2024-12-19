import csv
import enum
import feedparser
import requests
from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the database base model
Base = declarative_base()

class BookStatus(enum.Enum):
    ACTIVE = "active"
    MISSING = "missing"


class Book(Base):
    """
    Represents a book in the Book table. Tracks authors, title, and status.
    """
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True, autoincrement=True)
    authors = Column(String, nullable=False)
    title = Column(String, nullable=False)
    status = Column(Enum(BookStatus), default=BookStatus.ACTIVE, nullable=False)

    def mark_as_missing(self):
        """Mark this book as missing."""
        self.status = BookStatus.MISSING

    def mark_as_active(self):
        """Mark this book as active."""
        self.status = BookStatus.ACTIVE


class Library(Base):
    """
    Represents a book record from the local library database (the Library table).
    The Library table reflects books you currently have in your local collection.
    """
    __tablename__ = 'library'
    id = Column(Integer, primary_key=True, autoincrement=True)
    authors = Column(String, nullable=False)
    title = Column(String, nullable=False)

    @staticmethod
    def scan_and_update_books(session):
        """
        Syncs the 'books' table with the current library state:
        - If a book is in the library and in the books table, mark it as active.
        - If a book is in the library but not in the books table, add it as active.
        """
        library_books = session.query(Library).all()
        print(f"[DEBUG] Found {len(library_books)} books in the library.")

        for lib_book in library_books:
            authors = lib_book.authors.strip()
            title = lib_book.title.strip()

            book = session.query(Book).filter_by(authors=authors, title=title).first()
            if book:
                # Book already exists in the books table: ensure it's active
                print(f"[DEBUG] Marking '{title}' by '{authors}' as active in books table.")
                book.mark_as_active()
            else:
                # Book is in the library but not in the books table: add it as active
                print(f"[DEBUG] Adding '{title}' by '{authors}' to the books table.")
                new_book = Book(authors=authors, title=title, status=BookStatus.ACTIVE)
                session.add(new_book)
        session.commit()

    @staticmethod
    def check_goodreads_rss(feed_urls, session):
        """
        Given a list of Goodreads RSS feed URLs, returns a list of books that are in the Goodreads RSS
        but NOT in the library. These represent books that are missing from your actual collection.
        """
        missing_books = []

        for feed_url in feed_urls:
            print(f"[DEBUG] Parsing feed: {feed_url}")
            feed = feedparser.parse(feed_url)

            # If there's a parsing error, skip this feed
            if feed.bozo:
                print(f"[ERROR] Problem parsing feed: {feed_url}")
                continue

            # Iterate over each entry
            for entry in feed.entries:
                # Use 'author_name' from the feed instead of 'author'
                authors = entry.get('author_name')
                title = entry.get('title')

                # Check if both authors and title are present
                if not authors or not title:
                    print(f"[WARNING] Feed entry missing required fields. Authors: {authors}, Title: {title}")
                    continue

                # Trim whitespace just in case
                authors = authors.strip()
                title = title.strip()

                # Check if this book is in the library
                book_in_library = session.query(Library).filter_by(authors=authors, title=title).first()

                # If not in library, consider it missing and avoid duplicates
                if not book_in_library:
                    if not any(book for book in missing_books if book['authors'] == authors and book['title'] == title):
                        missing_books.append({"authors": authors, "title": title})

        return missing_books


def import_books_from_csv(csv_file_path, session):
    """
    Import books from a CSV file into the Library table. The CSV must have 'authors' and 'title' columns.
    These represent the books you currently have in your local collection.
    """
    with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)

        print("Detected CSV Headers:", reader.fieldnames)

        # Validate that the required columns are present
        if 'authors' not in reader.fieldnames or 'title' not in reader.fieldnames:
            raise ValueError("CSV file must contain 'authors' and 'title' columns.")

        count = 0
        for row in reader:
            authors = row.get('authors')
            title = row.get('title')

            if authors and title:
                # Trim whitespace
                authors = authors.strip()
                title = title.strip()

                if authors and title:
                    # Check if this entry already exists in the library to avoid duplicates
                    existing_book = session.query(Library).filter_by(authors=authors, title=title).first()
                    if not existing_book:
                        session.add(Library(authors=authors, title=title))
                        count += 1
            # If the row is missing authors/title, we just skip it silently.

        session.commit()
    print(f"Imported {count} new books from CSV.")


if __name__ == "__main__":
    # Goodreads RSS feed URLs for your shelves
    goodreads_rss_urls = [
        'https://www.goodreads.com/review/list_rss/example',
        'https://www.goodreads.com/review/list/example'
    ]  # Replace with actual RSS feed URLs

    # Connect to the database (e.g., SQLite)
    DATABASE_URL = 'sqlite:///books.db'
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)

    # Create a database session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Import your current local library of books
    csv_file_path = 'path/to/your/calibre/library.csv'
    import_books_from_csv(csv_file_path, session)

    # Sync the books table with your current library state
    Library.scan_and_update_books(session)

    # Check which books appear in Goodreads RSS but are not in your library
    missing_books = Library.check_goodreads_rss(goodreads_rss_urls, session)
    if missing_books:
        print("Missing books:")
        for book in missing_books:
            print(f"Authors: {book['authors']}, Title: {book['title']}")
    else:
        print("No missing books found.")

# Configuration
MAM_BASE_URL = "https://www.myanonamouse.net"  # Base site URL
MAM_SEARCH_ENDPOINT = f"{MAM_BASE_URL}/tor/js/loadSearchJSONbasic.php"

# You need a valid cookie to access MyAnonamouse
MAM_COOKIE = {"mam_id": "session_cookie_here"}

# qBittorrent configuration
QB_HOST = "192.XXX.XXX.XXX"
QB_PORT = 8080
QB_USERNAME = "admin"
QB_PASSWORD = "password"
QB_CATEGORY = "myanonamouse"

# Create a qBittorrent session
qb_session = requests.Session()
login_data = {
    'username': QB_USERNAME,
    'password': QB_PASSWORD
}
login_resp = qb_session.post(f"http://{QB_HOST}:{QB_PORT}/api/v2/auth/login", data=login_data)
login_resp.raise_for_status()
if "Ok." not in login_resp.text:
    raise Exception("Failed to authenticate with qBittorrent")


def search_on_myanonamouse(book_title, book_author):
    """
    Search MyAnonamouse for a given book title and author.
    Adjust parameters as needed to refine categories, etc.
    """
    # Combine title and author for search text
    search_text = f"{book_title} {book_author}"

    payload = {
        "tor": {
            "text": search_text,
            "searchType": "all",
            "searchIn": "torrents",
            "cat": ["0"],  # '0' might mean all categories, adjust as needed
            "sortType": "default",
            "startNumber": "0",
            "srchIn": {
                "title": "true",
                "author": "true"
            }
        },
        "thumbnail": "true"
    }

    # POST request with session cookie
    resp = requests.post(MAM_SEARCH_ENDPOINT, json=payload, cookies=MAM_COOKIE)
    resp.raise_for_status()

    results = resp.json().get('data', [])
    if not results:
        return None

    # Filter results to find the best match
    # For now, just return the first result. You may need more logic here.
    for r in results:
        # r['title'] from MAM might be in 'name' or 'title', verify by printing/inspecting
        torrent_title = r.get('name')
        # Simple check: does torrent title contain the book title's words?
        if torrent_title and all(word.lower() in torrent_title.lower() for word in book_title.split()):
            # Construct download link
            # According to the documentation, you can prepend:
            # https://www.myanonamouse.net/tor/download.php/
            # or use https://www.myanonamouse.net/tor/download.php?tid=ID
            # The `dl` field gives a hash, so use the first approach if recommended.
            
            dl_hash = r.get('dl')
            torrent_id = r.get('id')
            if dl_hash:
                # Using the hash for dlLink might be complex, consider the ?tid= approach:
                download_url = f"{MAM_BASE_URL}/tor/download.php?tid={torrent_id}"
                return download_url

    return None


def add_torrent_to_qbittorrent(torrent_url):
    add_data = {
        'urls': torrent_url,
        'category': QB_CATEGORY
    }
    add_resp = qb_session.post(f"http://{QB_HOST}:{QB_PORT}/api/v2/torrents/add", data=add_data)
    add_resp.raise_for_status()
    if add_resp.text:
        print("qBittorrent response:", add_resp.text)
    print("Torrent added to qBittorrent!")


# Example: After you get `missing_books` from your code:
missing_books = [
    # Example missing books; you'd get this from Library.check_goodreads_rss
    {"authors": "George Saunders", "title": "Lincoln in the Bardo"},
    # Add more as needed
]

for book in missing_books:
    authors = book['authors']
    title = book['title']

    print(f"Searching for '{title}' by '{authors}' on MyAnonamouse...")
    torrent_url = search_on_myanonamouse(title, authors)
    if torrent_url:
        print(f"Found torrent for '{title}' by '{authors}': {torrent_url}")
        add_torrent_to_qbittorrent(torrent_url)
    else:
        print(f"No torrent found for '{title}' by '{authors}' on MyAnonamouse")