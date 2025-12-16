# 🔬 PubMed Lead Generator

A web-based lead generation tool that identifies, enriches, and ranks potential biotech/pharma customers based on their scientific publications in PubMed.

## 🎯 Overview

This application helps business developers find qualified leads by analyzing recent scientific publications. It searches PubMed for researchers working on specific topics (e.g., drug-induced liver injury, 3D cell culture, hepatotoxicity) and ranks them based on their propensity to purchase related products or services.

## ✨ Features

- **🔍 Smart Search**: Search PubMed using custom keywords and date ranges
- **📊 Propensity Scoring**: Automatically ranks leads 0-100 based on:
  - Publication recency (more recent = higher score)
  - Keyword relevance (title matches = higher score)
  - Contact availability (email present = higher score)
- **📧 Contact Extraction**: Automatically extracts emails from author affiliations
- **🎨 Interactive Dashboard**: Filter and sort results in real-time
- **💾 CSV Export**: One-click export to Excel-compatible format
- **🚀 Fast & Free**: No API keys required, uses PubMed's free E-utilities API

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **API**: PubMed E-utilities (free, no authentication)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Data Format**: XML parsing with Python's ElementTree

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## 🚀 Installation

1. **Clone or download the repository**
   ```bash
   git clone <your-repo-url>
   cd pubmed-lead-generator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python main.py
   ```
   
   Or with uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

4. **Open your browser**
   ```
   http://localhost:8000
   ```

## 📖 Usage

### Basic Search

1. **Add Keywords**: 
   - Type keywords like "liver toxicity" and press Enter
   - Or use preset buttons for common terms
   - Add multiple keywords for broader search

2. **Set Parameters**:
   - **Years Back**: How far to search (default: 2 years)
   - **Max Results**: Number of papers to analyze (default: 50)

3. **Click Search**: Wait for results to load (typically 5-10 seconds)

### Working with Results

- **Filter**: Use the search box to filter by name, affiliation, or keywords
- **Sort**: Results are automatically sorted by score (highest first)
- **Export**: Click "Export to CSV" to download results
- **View Papers**: Click "View" links to see full papers on PubMed

### Scoring System

Each lead receives a score out of 100:

| Factor | Points | Description |
|--------|--------|-------------|
| Base Score | 20 | All found leads |
| Published this year | +40 | Very recent research |
| Published last year | +30 | Recent research |
| Published 2 years ago | +20 | Somewhat recent |
| Keyword match | +10 each | Match in paper title (max 30) |
| Email available | +10 | Contact info present |

**Example Scores:**
- 90-100: Hot lead (recent, relevant, contactable)
- 70-89: Warm lead (good fit, some missing factors)
- 50-69: Moderate lead (older or less relevant)
- Below 50: Cold lead (limited relevance)

## 🔍 Sample Searches

Try these keyword combinations:

**For 3D Cell Culture Companies:**
- "3D cell culture"
- "organoid"
- "spheroid"
- "organ-on-chip"

**For Toxicology Services:**
- "drug-induced liver injury"
- "hepatotoxicity"
- "DILI"
- "liver toxicity"

**For In Vitro Research:**
- "in vitro models"
- "cell-based assays"
- "primary hepatocytes"

## 📁 Project Structure

```
pubmed-lead-generator/
├── main.py              # FastAPI backend + frontend HTML
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🔧 API Endpoints

### `POST /api/search`

Search PubMed and return ranked leads.

**Request Body:**
```json
{
  "keywords": ["liver toxicity", "3D models"],
  "years_back": 2,
  "max_results": 50
}
```

**Response:**
```json
{
  "leads": [
    {
      "rank": 1,
      "name": "John Smith",
      "affiliation": "Harvard Medical School",
      "email": "john.smith@harvard.edu",
      "paper_title": "3D Liver Models for Toxicity Testing",
      "publication_date": "2024-11",
      "score": 85,
      "pubmed_id": "38234567"
    }
  ],
  "total": 50
}
```

### `GET /`

Serves the main HTML dashboard.

## 🌐 Deployment

### Local Development
```bash
python main.py
```

### Hugging Face Spaces
1. Create a new Space with Python SDK
2. Upload `main.py` and `requirements.txt`
3. Set SDK to "Gradio" or "Streamlit" (or create custom Space)
4. Your app will be available at: `https://huggingface.co/spaces/[username]/[space-name]`

### Other Platforms
- **Heroku**: Add `Procfile` with `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Railway**: Auto-detects FastAPI apps
- **Render**: Supports Python web services out of the box

## ⚙️ Configuration

You can modify these parameters in the code:

```python
# In main.py

# API rate limiting (PubMed recommends max 3 requests/second)
time.sleep(0.35)  # Add between requests if needed

# Default search parameters
years_back: int = 2  # Search last 2 years
max_results: int = 100  # Max papers to fetch

# Scoring weights
RECENCY_SCORE = 40  # Points for recent publications
KEYWORD_SCORE = 10  # Points per keyword match
EMAIL_BONUS = 10    # Points for having email
```

## 🐛 Troubleshooting

### "No results found"
- Try broader keywords
- Increase years back (search further in past)
- Check that keywords are spelled correctly

### "PubMed search failed"
- Check internet connection
- PubMed may be down (rare)
- Try reducing max_results to avoid timeouts

### CSV export not working
- Check browser allows downloads
- Try different browser
- Disable popup blockers

## 📊 Sample Output

```
Rank  Score  Name              Affiliation                 Email
1     95     Dr. Jane Smith    Harvard Medical School      jane@harvard.edu
2     88     Dr. John Doe      MIT                         john@mit.edu
3     75     Dr. Bob Wilson    Stanford University         bob@stanford.edu
```

## 🚧 Limitations

- Only searches PubMed (biomedical literature)
- Email extraction depends on authors including emails in affiliations
- Does not access LinkedIn or conference data
- Scoring is rule-based (not ML-powered)

## 🔮 Future Enhancements

- [ ] Integration with LinkedIn Sales Navigator API
- [ ] Conference attendee list processing
- [ ] Company funding data (Crunchbase API)
- [ ] Location-based scoring (biotech hubs)
- [ ] Grant database integration (NIH RePORTER)
- [ ] Duplicate detection across sources
- [ ] CRM integration (Salesforce, HubSpot)

## 📄 License

This project is provided as-is for demonstration purposes.

## 🤝 Contributing

This is a demo project for an assignment. For production use, consider:
- Adding rate limiting
- Implementing caching
- Using asynchronous requests
- Adding user authentication
- Storing results in database

## 📞 Contact

For questions or feedback about this implementation, please contact [Your Email].

## 🙏 Acknowledgments

- PubMed E-utilities API for free access to biomedical literature
- FastAPI for the excellent Python web framework
- National Library of Medicine for maintaining PubMed
