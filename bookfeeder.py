import csv
import enum
import feedparser
import requests
import json
import logging
from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all levels of logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),  # Logs will be written to debug.log
        logging.StreamHandler()            # Logs will also be output to the console
    ]
)


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
                print(f"[DEBUG] Marking '{title}' by '{authors}' as active in books table.")
                book.mark_as_active()
            else:
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
                authors = entry.get('author_name')
                title = entry.get('title')

                if not authors or not title:
                    print(f"[WARNING] Feed entry missing required fields. Authors: {authors}, Title: {title}")
                    continue

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

        if 'authors' not in reader.fieldnames or 'title' not in reader.fieldnames:
            raise ValueError("CSV file must contain 'authors' and 'title' columns.")

        count = 0
        for row in reader:
            authors = row.get('authors')
            title = row.get('title')

            if authors and title:
                authors = authors.strip()
                title = title.strip()

                if authors and title:
                    existing_book = session.query(Library).filter_by(authors=authors, title=title).first()
                    if not existing_book:
                        session.add(Library(authors=authors, title=title))
                        count += 1

        session.commit()
    print(f"Imported {count} new books from CSV.")


# qBittorrent and MyAnonamouse Configuration
MAM_BASE_URL = "https://www.myanonamouse.net"
MAM_SEARCH_ENDPOINT = f"{MAM_BASE_URL}/tor/js/loadSearchJSONbasic.php"
MAM_COOKIE = {"mam_id": "key_here"}

QB_HOST = "192.168.XXX.XXX"
QB_PORT = 8080
QB_USERNAME = "admin"
QB_PASSWORD = ""
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


def normalize_string(s):
    """Normalize string by removing extra whitespace."""
    return ' '.join(s.split())


def author_matches(book_author, author_info_str):
    """
    Check if the given book_author matches any of the authors in author_info.
    author_info is a JSON string like {"8234": "Author Name"}.
    """
    if not author_info_str:
        return False

    try:
        author_data = json.loads(author_info_str)
    except json.JSONDecodeError:
        return False

    norm_requested_author = normalize_string(book_author)
    for a_id, a_name in author_data.items():
        if normalize_string(a_name) == norm_requested_author:
            return True

    return False


def title_matches(book_title, torrent_title):
    """
    Check if all words of the book_title appear in the torrent_title.
    """
    if not torrent_title:
        return False
    norm_title = normalize_string(torrent_title)
    norm_book_title = normalize_string(book_title)
    return all(word.lower() in norm_title.lower() for word in norm_book_title.split())


def search_on_myanonamouse(book_title, book_author):
    """
    Search MyAnonamouse for a given book title and author.
    """
    # Enclose title and author in quotes
    search_text = f'"{book_title}" "{book_author}"'

    payload = {
        "tor": {
            "text": search_text,
            "srchIn": {
                "title": "true",
                "author": "true",
            },
            "searchType": "all",
            "searchIn": "torrents",
            "cat": ["0"],
            "browseFlagsHideVsShow": "0",
            "startDate": "",
            "endDate": "",
            "hash": "",
            "sortType": "default",
            "startNumber": "0"
        },
        "thumbnail": "true"
    }

    # Log the JSON payload being sent
    logging.debug("JSON Payload Sent to MyAnonamouse:")
    logging.debug(json.dumps(payload, indent=4, ensure_ascii=False))
    logging.debug("-" * 50)  # Separator for readability

    resp = requests.post(MAM_SEARCH_ENDPOINT, json=payload, cookies=MAM_COOKIE)
    resp.raise_for_status()

    results = resp.json().get('data', [])
    if not results:
        return None

    for r in results:
        torrent_title = r.get('name')
        if torrent_title and all(word.lower() in torrent_title.lower() for word in book_title.split()):
            dl_hash = r.get('dl')
            torrent_id = r.get('id')
            if dl_hash:
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


if __name__ == "__main__":
    # Goodreads RSS feed URLs for your shelves
    goodreads_rss_urls = [
        'https://www.goodreads.com/review/list_rss/184080032?example',
        'https://www.goodreads.com/review/list/184161213?example'
    ]

    DATABASE_URL = 'sqlite:///books.db'
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    csv_file_path = '/path/to/your/calibre/library.csv'
    import_books_from_csv(csv_file_path, session)

    Library.scan_and_update_books(session)

    missing_books = Library.check_goodreads_rss(goodreads_rss_urls, session)
    if missing_books:
        print("Missing books:")
        print(json.dumps(missing_books, indent=4, ensure_ascii=False))
        for book in missing_books:
            print(f"Authors: {book['authors']}, Title: {book['title']}")
    else:
        print("No missing books found.")

    # Only search MyAnonamouse and add to qBittorrent if we have missing books
    if missing_books:
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
