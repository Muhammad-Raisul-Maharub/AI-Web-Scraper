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
imageUpload.addEventListener('change', function (event) {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      // Create new slide and append it to the container
      const newSlide = document.createElement('div');
      newSlide.classList.add('slide', 'fade');
      newSlide.style.backgroundImage = `url(${e.target.result})`;

      // Append new slide to the container
      slidesContainer.appendChild(newSlide);

      // Update the slides collection and restart the slideshow
      setTimeout(() => {
        showSlides();
      }, 100); // Short delay to ensure new slide is included
    };
    reader.readAsDataURL(file);
  }
});
