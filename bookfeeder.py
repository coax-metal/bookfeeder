import csv
import enum
import feedparser
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
        
        This ensures that the 'books' table accurately reflects the books you currently have.
        """
        library_books = session.query(Library).all()
        for lib_book in library_books:
            book = session.query(Book).filter_by(authors=lib_book.authors, title=lib_book.title).first()
            if book:
                # Book already exists in the books table: ensure it's active
                book.mark_as_active()
            else:
                # Book is in the library but not in the books table: add it as active
                new_book = Book(authors=lib_book.authors, title=lib_book.title, status=BookStatus.ACTIVE)
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
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                authors = entry.get('author')
                title = entry.get('title')
                if not authors or not title:
                    continue

                book_in_library = session.query(Library).filter_by(authors=authors, title=title).first()
                if not book_in_library:
                    # Avoid duplicates in the missing_books list
                    if not any(book for book in missing_books if book['authors'] == authors and book['title'] == title):
                        missing_books.append({"authors": authors, "title": title})

        return missing_books


def import_books_from_csv(csv_file_path, session):
    """
    Import books from a CSV file into the Library table. The CSV must have 'authors' and 'title' columns.
    These represent the books you currently have in your local collection.
    """
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            authors = row.get('authors')
            title = row.get('title')
            if authors and title:
                book = Library(authors=authors, title=title)
                session.add(book)
        session.commit()


if __name__ == "__main__":
    # Goodreads RSS feed URLs for your shelves
    goodreads_rss_urls = [
        'https://www.goodreads.com/review/list_rss/184080032?key=2ed0F7Y3ez7Cr2Z5MiN1xvvMOkjf2fQSyg5675be4pHqyWib&shelf=to-read',
        'https://www.goodreads.com/review/list_rss/184161213?shelf=requests'
    ]  # Replace with actual RSS feed URLs

    # Connect to the database (e.g., SQLite)
    DATABASE_URL = 'sqlite:///books.db'
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    # Create a database session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Import your current local library of books
    csv_file_path = '/mnt/user/data/media/books/calibre/Current Books.csv'  
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

