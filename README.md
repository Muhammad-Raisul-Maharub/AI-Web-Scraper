# AI-Web-Scraper
# AI Web Scraper with Streamlit and Ollama Model Integration

This project is a powerful web scraper that scrapes website content, cleans and parses the DOM, and extracts meaningful information using keyword-based extraction. The scraper uses **Selenium** for dynamic web content scraping, **BeautifulSoup** for DOM parsing, and is integrated with the **Ollama model** for AI-based content analysis. The project is built with **Streamlit** to provide an interactive UI for the web scraping process.

## Features

- **Website Scraping**: Scrapes websites and extracts DOM content.
- **Deep Dive Scraping**: Recursively scrapes linked pages up to a configurable depth.
- **Content Parsing**: Cleans and extracts meaningful content from the scraped DOM.
- **Keyword-Based Extraction**: Extracts content relevant to specific keywords entered by the user.
- **Background Image Slideshow**: Upload images for a background slideshow via the UI.
- **Ollama Model Integration**: Parses scraped content using the Ollama language model.

## Technology Stack

- **Streamlit**: Web app framework for creating the interactive user interface.
- **Selenium**: Used to scrape dynamic web pages.
- **BeautifulSoup**: For parsing and cleaning DOM content.
- **Ollama Model**: AI-based content parsing (simulated integration in this project).
- **JavaScript**: For background image upload and slideshow functionality.

## Prerequisites

- Python 3.7 or higher
- WebDriver for Selenium (Chrome or Firefox)
- Basic knowledge of using a proxy server (if required for scraping certain sites)

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Muhammad-Raisul-Maharub/ai-web-scraper.git
   cd ai-web-scraper

2. **Create a virtual environment (optional but recommended):**
     ```python
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

3.**Install required dependencies:**
pip install -r requirements.txt

4.**Set up the WebDriver for Selenium:**
Download the WebDriver for your preferred browser (e.g., Chrome or Firefox) and ensure it's in your PATH or specify its location in scrape.py.

5.**Run the Streamlit app:**
streamlit run main.py

<h2>Author-Muhammad Raisul Maharub</h2>


