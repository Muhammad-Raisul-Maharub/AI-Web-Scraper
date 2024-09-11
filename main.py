#main.py

import streamlit as st
import streamlit.components.v1 as components
from scrape import (
    scrape_website,
    extract_body_content,
    clean_body_content,
    split_dom_content,
    dive_deep,
    keyword_based_extraction
)
from parse import parse_with_ollama
# HTML content with embedded CSS and JavaScript
html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Web Scraper</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Arial', sans-serif; color: #fff; text-align: center; background: #333; overflow: hidden; height: 100vh; }
    .container { position: relative; z-index: 10; padding: 20px; max-width: 100%; height: 100vh; margin: 0 auto; background: rgba(0, 0, 0, 0.5); border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .header h1 { font-size: 2.5rem; margin-bottom: 20px; }
    .content { width: 100%; }
    form { margin-bottom: 20px; }
    #url-input { width: 80%; padding: 10px; margin: 10px 0; border: 2px solid #fff; border-radius: 5px; }
    #scrape-btn, #stop-btn { padding: 10px 20px; background-color: #28a745; border: none; border-radius: 5px; cursor: pointer; color: #fff; margin-top: 10px; }
    #scrape-btn:hover, #stop-btn:hover { background-color: #218838; }
    #scraped-content { width: 100%; padding: 10px; border-radius: 5px; margin-top: 20px; }
    .controls { margin-top: 20px; }
    label { display: block; margin-bottom: 10px; }
    input[type="file"] { display: inline-block; }
    .background-slider { position: absolute; top: 0; left: 0; width: 100%; height: 100vh; z-index: -1; overflow: hidden; }
    .slide { display: none; background-size: cover; background-position: center; width: 100%; height: 100vh; position: absolute; top: 0; left: 0; }
    .fade { animation: fadeEffect 1.5s; }
    @keyframes fadeEffect { from { opacity: 0.4; } to { opacity: 1; } }
    body.dark-mode { background: #121212; color: #e0e0e0; }
    body.dark-mode .container { background: rgba(0, 0, 0, 0.8); }
    body.dark-mode #scrape-btn, body.dark-mode #stop-btn { background-color: #1e1e1e; }
    body.dark-mode #scrape-btn:hover, body.dark-mode #stop-btn:hover { background-color: #333; }
    #toggle-btn { position: absolute; top: 10px; right: 10px; padding: 5px 10px; background-color: #444; border: none; border-radius: 5px; cursor: pointer; color: #fff; }
    #toggle-btn:hover { background-color: #555; }
    #image-upload { position: absolute; bottom: 10px; left: 10px; }
  </style>
</head>
<body>
  <div class="background-slider">
    <div class="slide fade" style="background-image: url('data:image/jpeg;base64,INSERT_BASE64_IMAGE1');"></div>
    <div class="slide fade" style="background-image: url('data:image/jpeg;base64,INSERT_BASE64_IMAGE2');"></div>
    <div class="slide fade" style="background-image: url('data:image/jpeg;base64,INSERT_BASE64_IMAGE3');"></div>
  </div>
  <div class="container">
    <div class="header"><h1>AI Web Scraper</h1></div>
    <div class="content">
      <form id="scrape-form">
        <label for="url-input">Enter Website URL:</label>
        <input type="text" id="url-input" placeholder="https://example.com" required>
        <button type="submit" id="scrape-btn">Scrape Website</button>
      </form>
      <div class="result">
        <textarea id="scraped-content" rows="10" placeholder="Scraped content will appear here..." readonly></textarea>
      </div>
      <div class="controls">
        <button id="stop-btn">Stop Parsing</button>
        <label for="image-upload">Upload Background Image:</label>
        <input type="file" id="image-upload" accept="image/*">
      </div>
    </div>
    <button id="toggle-btn">Toggle Light/Dark Mode</button>
  </div>
  <script>
    let slideIndex = 0;
    const slidesContainer = document.querySelector('.background-slider');
    const slides = document.getElementsByClassName("slide");

    function showSlides() {
      for (let i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
      }
      slideIndex++;
      if (slideIndex > slides.length) {
        slideIndex = 1;
      }
      slides[slideIndex - 1].style.display = "block";
      setTimeout(showSlides, 5000); // Change image every 5 seconds
    }

    showSlides();

    // Handle image upload
    const imageUpload = document.getElementById('image-upload');
    imageUpload.addEventListener('change', function(event) {
      const file = event.target.files[0];
      const reader = new FileReader();
      reader.onload = function(e) {
        const newSlide = document.createElement('div');
        newSlide.className = 'slide fade';
        newSlide.style.backgroundImage = url(${e.target.result});
        slidesContainer.appendChild(newSlide);
        showSlides();
      };
      reader.readAsDataURL(file);
    });

    // Toggle light/dark mode
    const toggleBtn = document.getElementById('toggle-btn');
    toggleBtn.addEventListener('click', function() {
      document.body.classList.toggle('dark-mode');
    });
  </script>
</body>
</html>
"""

# Streamlit UI
st.title("AI Web Scraper")

# Display the HTML content
components.html(html_code, height=800)

# Streamlit components for scraping and parsing
url = st.text_input("Enter Website URL")
if st.button("Scrape Website"):
    if url:
        st.write("Scraping the website...")

        # Scrape the website
        dom_content = scrape_website(url)
        if dom_content:
            body_content = extract_body_content(dom_content)
            cleaned_content = clean_body_content(body_content)

            # Store the DOM content in Streamlit session state
            st.session_state.dom_content = cleaned_content

            # Display the DOM content in an expandable text box
            with st.expander("View DOM Content"):
                st.text_area("DOM Content", cleaned_content, height=300)

# Ask Questions About the DOM Content
if "dom_content" in st.session_state:
    parse_description = st.text_area("Describe what you want to parse")

    # Define a flag for stopping the parsing
    if "stop_parsing" not in st.session_state:
        st.session_state.stop_parsing = False

    # Parse Content button
    if st.button("Parse Content"):
        if parse_description:
            st.write("Parsing the content...")
            st.session_state.stop_parsing = False

            # Parse the content with Ollama
            dom_chunks = split_dom_content(st.session_state.dom_content)
            parsed_result = parse_with_ollama(dom_chunks, parse_description)

            if not st.session_state.stop_parsing:
                st.write(parsed_result)

    # Stop Parsing button
    if st.button("Stop Parsing"):
        st.session_state.stop_parsing = True
        st.write("Parsing has been stopped.")

# Scrape Website with Deep Dive
if st.button("Scrape Website with Deep Dive"):
    if url:
        st.write("Scraping the website with deep dive...")

        # Scrape the website and linked pages
        deep_content = dive_deep(url, max_depth=2)
        combined_content = "\n".join(deep_content)
        cleaned_content = clean_body_content(combined_content)

        # Store the deep-dived DOM content in session state
        st.session_state.dom_content = cleaned_content

        # Display the deep-dived DOM content
        with st.expander("View Deep-Dived DOM Content"):
            st.text_area("DOM Content", cleaned_content, height=300)

# Keyword-Based Extraction
keywords_input = st.text_area("Enter Keywords (comma-separated)", placeholder="Enter keywords like: product, price, review")

if st.button("Extract Information Using Keywords"):
    if "dom_content" in st.session_state:
        keywords = [keyword.strip() for keyword in keywords_input.split(',')]
        if keywords:
            st.write("Extracting information based on keywords...")
            extracted_info = keyword_based_extraction(st.session_state.dom_content, keywords)
            st.write(extracted_info)