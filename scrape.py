#scrape.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup 
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# Set up the proxy with credentials directly in the code
SBR_WEBDRIVER = "https://brd-customer-hl_eea3f70e-zone-ai_web_scrapper:40qlebz3h871@brd.superproxy.io:9515"

def scrape_website(website):
    print("Connecting to Scraping Browser...")

    # Configure Chrome options
    chrome_options = ChromeOptions()
    
    # Add Proxy settings
    chrome_options.add_argument('--proxy-server=http://brd.superproxy.io:9515')

    # Set up Selenium Remote WebDriver connection using the proxy
    driver = webdriver.Remote(
        command_executor=SBR_WEBDRIVER,
        options=chrome_options
    )

    try:
        # Open the website
        driver.get(website)
        print("Waiting for CAPTCHA to solve...")

        # Check for CAPTCHA or wait for manual solve (optional)
        if "captcha" in driver.page_source.lower():
            print("CAPTCHA detected! Please solve it manually.")
            return None
        
        print("Successfully navigated! Scraping page content...")
        html = driver.page_source
    finally:
        # Ensure the browser is closed after scraping
        driver.quit()
    
    return html

def extract_body_content(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    body_content = soup.body
    return str(body_content) if body_content else ""

def clean_body_content(body_content):
    soup = BeautifulSoup(body_content, "html.parser")
    for tag in soup(["script", "style", "iframe", "noscript"]):
        tag.extract()
    cleaned_content = soup.get_text(separator="\n")
    return "\n".join(line.strip() for line in cleaned_content.splitlines() if line.strip())

def split_dom_content(dom_content, max_length=6000):
    return [dom_content[i:i + max_length] for i in range(0, len(dom_content), max_length)]

def dive_deep(website, max_depth=2, current_depth=0):
    """
    Function to dive deep into a website by following links up to a certain depth.

    Parameters:
    website (str): The URL of the website to scrape.
    max_depth (int): Maximum depth to follow links (default: 2).
    current_depth (int): Current depth level (default: 0).

    Returns:
    list: A list of HTML content from the main page and linked pages.
    """
    if current_depth > max_depth:
        return []

    html_content = scrape_website(website)
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    full_links = [link for link in links if link.startswith('http')]

    all_content = [html_content]

    # Follow links recursively up to max_depth
    for link in full_links:
        all_content += dive_deep(link, max_depth=max_depth, current_depth=current_depth + 1)

    return all_content

def keyword_based_extraction(content, keywords):
    """
    Extracts information based on specific keywords.

    Parameters:
    content (str): The scraped content to search through.
    keywords (list): A list of keywords to search for.

    Returns:
    str: Extracted content containing the keywords.
    """
    lines = content.split("\n")
    extracted_lines = [line for line in lines if any(keyword.lower() in line.lower() for keyword in keywords)]
    
    return "\n".join(extracted_lines)