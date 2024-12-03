# Install required libraries first:
# pip install telethon EbookLib Pillow

from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from ebooklib import epub
import datetime
import os
from PIL import Image, UnidentifiedImageError

# API
api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")

# Parameters
channel_list = ["@kashinguru", "@whalesgohigh"]
start_date = datetime.datetime(2024, 10, 1, tzinfo=datetime.timezone.utc)
end_date = datetime.datetime(2024, 10, 11, tzinfo=datetime.timezone.utc)
number_of_posts = None  # Set to None if using date range, otherwise specify number of last posts to download
enforce_new_page = True
extract_images = True
gray_scale_images = True

client = TelegramClient('session_name', api_id, api_hash)

# Create images directory if it doesn't exist
os.makedirs('images', exist_ok=True)

# Function to get posts from a given channel in a specified date range or by number of posts
def get_posts(channel_username, start_date=None, end_date=None, number_of_posts=None):
    print(f"Getting posts from channel: {channel_username}")
    channel = client.get_entity(channel_username)  # Get channel entity using channel username
    messages = []

    if number_of_posts:
        # Get the specified number of last posts
        for message in client.iter_messages(channel, limit=number_of_posts):
            print(f"Evaluating message from {message.date}")
            messages.append(message)
            print(f"Retrieved message from {message.date}")
    else:
        # Get posts in the specified date range
        for message in client.iter_messages(channel, offset_date=end_date, reverse=True):
            message_date = message.date.replace(tzinfo=datetime.timezone.utc)
            print(f"Evaluating message from {message_date}")
            if message_date < start_date:  # Stop if message is before start_date
                print(f"Stopping, as message date {message_date} is before start_date {start_date}")
                break
            if start_date <= message_date <= end_date:  # Collect messages within date range
                messages.append(message)
                print(f"Retrieved message from {message_date}")

    print(f"Total messages retrieved from {channel_username}: {len(messages)}")
    return messages

# Function to process and add an image to the EPUB
def process_and_add_image(media, message, book, image_count):
    image_name = f'image_{message.id}_{image_count}_{message.date.strftime("%Y%m%d%H%M%S")}.jpg'
    image_path = os.path.join('images', image_name)
    print(f"Downloading media to {image_path}")
    client.download_media(media, file=image_path)  # Download media to specified path

    # Convert image to grayscale if enabled
    if gray_scale_images:
        print(f"Converting image {image_path} to grayscale")
        try:
            with Image.open(image_path) as img:
                gray_image = img.convert('L')
                gray_image.save(image_path)  # Save the grayscale image
        except UnidentifiedImageError:
            print(f"Error: cannot identify image file '{image_path}'. Skipping this image.")
            return ""

    # Add image to EPUB
    try:
        with open(image_path, 'rb') as img_file:
            image_item = epub.EpubItem(uid=image_name, file_name=image_name, media_type='image/jpeg', content=img_file.read())
        book.add_item(image_item)  # Add the image to the EPUB
        print(f"Image {image_name} added to EPUB")
    except FileNotFoundError:
        print(f"Error: file '{image_path}' not found. Skipping this image.")
        return ""

    # Return content with page break
    return f"<div style='page-break-after: always;'><img src='{image_name}' alt='Image {image_count}' /></div>"

# Function to create an EPUB book from messages
def create_epub(messages):
    print("Creating EPUB book")
    book = epub.EpubBook()

    # Set metadata for the EPUB book
    book.set_identifier('id123456')
    book.set_title('Posts from Multiple Channels')
    book.set_language('en')

    # Add content to the EPUB
    content = ""
    image_count = 0

    for message in messages:
        page_break = "page-break-after: always;" if enforce_new_page else ""
        content += f"<p style='{page_break}'><b>{message.date} - {message.chat.title}</b>: {message.message}</p>"
        print(f"Adding message from {message.date} to EPUB content")

        # Extract images if enabled
        if extract_images and message.media:
            if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                # Handle single photo or document
                image_count += 1
                content += process_and_add_image(message.media, message, book, image_count)
            elif hasattr(message.media, 'webpage') and hasattr(message.media.webpage, 'photos'):
                # Handle multiple photos in a post (e.g., albums)
                for media in message.media.webpage.photos:
                    if isinstance(media, MessageMediaPhoto):
                        image_count += 1
                        content += process_and_add_image(media, message, book, image_count)

    # Create a chapter for the EPUB with all the collected content
    chapter = epub.EpubHtml(title='Posts', file_name='chap_01.xhtml', lang='en')
    chapter.content = content
    book.add_item(chapter)

    # Define the Table of Contents
    book.toc = [epub.Link('chap_01.xhtml', 'Posts', 'chap_01')]

    # Add default NCX and Nav files for EPUB navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define CSS style for the EPUB
    style = 'BODY {color: black;} IMG {display: block; margin: 0 auto;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # Create spine for EPUB content flow
    book.spine = ['nav', chapter]

    # Write the EPUB file to disk
    epub_file_name = 'combined_posts.epub'
    print(f"Writing EPUB to {epub_file_name}")
    epub.write_epub(epub_file_name, book)
    print("EPUB creation complete")

# Main function to get posts from multiple channels and create an EPUB book
def run():
    all_messages = []

    for channel in channel_list:
        messages = get_posts(channel, start_date=start_date, end_date=end_date, number_of_posts=number_of_posts)  # Get messages from each channel
        all_messages.extend(messages)

    # Sort all messages by date
    all_messages.sort(key=lambda msg: msg.date)
    print(f"Total messages to be added to EPUB: {len(all_messages)}")

    if all_messages:
        create_epub(all_messages)  # Create the EPUB with the collected messages
    else:
        print("No messages found in the specified date range or with the specified number of posts. EPUB creation skipped.")

# Run the client and execute the main function
with client:
    run()