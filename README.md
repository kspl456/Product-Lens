# ProductLens — Explainable Multi-Criteria Decision System for E-Commerce Product Comparison

A real-time web application that compares Amazon products intelligently using sentiment analysis, aspect-level feature scoring, review authenticity detection, and a transparent Weighted Trust Score.

## Features

- Compares 2 to 5 Amazon products side by side
- Aspect-based sentiment analysis using spaCy and VADER
- Review Authenticity Risk Index (RARI) to detect fake or suspicious reviews
- Weighted Trust Score with two modes — Budget Priority ON and OFF
- MongoDB caching to reduce redundant API calls
- Supports short Amazon URLs from the share button

## Review Authenticity Risk Index (RARI)

RARI is a rule-based scoring system that analyses review patterns to detect suspicious or manipulated activity. It evaluates five signals — exact duplicate reviews, moderately repeated content, same-day review bursts, generic one-liner reviews, and dominance of very short reviews. Based on the total risk score, products are classified as Low, Medium, or High risk. When risk is Medium or High, the system automatically filters to verified purchase reviews only before performing sentiment analysis, ensuring that fake or promotional reviews do not influence the final Trust Score.

## Tech Stack

- Python, Flask
- spaCy, VADER
- MongoDB Atlas
- SerpAPI
- HTML, CSS, JavaScript

## Usage

- Paste 2 to 5 Amazon product URLs of the same category
- Toggle Budget Priority ON if price is a key factor for you
- Click Analyse and wait for the results
- The system displays a Best Pick with full score breakdown for each product

## Project Structure

```
project/
├── app.py
├── config.py
├── requirements.txt
├── data_ingestion/
│   └── serp_fetcher.py
├── processing/
│   ├── cleaner.py
│   ├── aspect_extraction.py
│   └── sentiment.py
├── authenticity/
│   └── rari.py
├── scoring/
│   └── scorer.py
├── database/
│   └── mongo.py
├── templates/
│   └── index.html
└── static/
    └── style.css
```

## Note

This system works exclusively with Amazon India (amazon.in) product listings. Products must have existing reviews and ratings to be analysed.
