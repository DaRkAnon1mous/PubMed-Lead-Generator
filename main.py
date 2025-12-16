from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import xml.etree.ElementTree as ET
from typing import List, Optional
import re
from datetime import datetime
import uvicorn

app = FastAPI(title="PubMed Lead Generator")

# Models
class SearchRequest(BaseModel):
    keywords: List[str]
    years_back: int = 2
    max_results: int = 100

class Lead(BaseModel):
    rank: int
    name: str
    affiliation: str
    email: Optional[str]
    paper_title: str
    publication_date: str
    score: int
    pubmed_id: str

# PubMed API Configuration
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def search_pubmed(keywords: List[str], years_back: int, max_results: int) -> List[str]:
    """Search PubMed and return list of PMIDs"""
    # Build search query
    query_parts = []
    for keyword in keywords:
        query_parts.append(f'"{keyword}"[Title/Abstract]')
    
    query = " OR ".join(query_parts)
    
    # Add date filter
    current_year = datetime.now().year
    start_year = current_year - years_back
    query += f" AND {start_year}:{current_year}[PDAT]"
    
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "xml",
        "sort": "pub_date"
    }
    
    response = requests.get(PUBMED_SEARCH_URL, params=params)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="PubMed search failed")
    
    # Parse XML response
    root = ET.fromstring(response.content)
    pmids = [id_elem.text for id_elem in root.findall(".//Id")]
    
    return pmids

def fetch_article_details(pmids: List[str]) -> List[dict]:
    """Fetch detailed information for given PMIDs"""
    if not pmids:
        return []
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }
    
    response = requests.get(PUBMED_FETCH_URL, params=params)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="PubMed fetch failed")
    
    # Parse XML
    root = ET.fromstring(response.content)
    articles = []
    
    for article in root.findall(".//PubmedArticle"):
        try:
            # Extract PMID
            pmid = article.find(".//PMID").text
            
            # Extract title
            title_elem = article.find(".//ArticleTitle")
            title = "".join(title_elem.itertext()) if title_elem is not None else "No title"
            
            # Extract publication date
            pub_date = article.find(".//PubDate")
            year = pub_date.find("Year").text if pub_date is not None and pub_date.find("Year") is not None else "N/A"
            month = pub_date.find("Month").text if pub_date is not None and pub_date.find("Month") is not None else "01"
            pub_date_str = f"{year}-{month}" if year != "N/A" else "N/A"
            
            # Extract authors (focus on corresponding author or first author)
            authors = article.findall(".//Author")
            corresponding_author = None
            first_author = None
            
            for idx, author in enumerate(authors):
                lastname = author.find("LastName")
                forename = author.find("ForeName")
                
                if lastname is not None and forename is not None:
                    name = f"{forename.text} {lastname.text}"
                    
                    # Get affiliation
                    affiliation_elem = author.find(".//Affiliation")
                    affiliation = affiliation_elem.text if affiliation_elem is not None else "No affiliation"
                    
                    # Extract email from affiliation
                    email = extract_email(affiliation)
                    
                    if idx == 0:
                        first_author = {
                            "name": name,
                            "affiliation": affiliation,
                            "email": email
                        }
                    
                    # Check if corresponding author (usually has email)
                    if email:
                        corresponding_author = {
                            "name": name,
                            "affiliation": affiliation,
                            "email": email
                        }
                        break
            
            # Prefer corresponding author, fallback to first author
            author_data = corresponding_author if corresponding_author else first_author
            
            if author_data:
                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "pub_date": pub_date_str,
                    "author": author_data["name"],
                    "affiliation": author_data["affiliation"],
                    "email": author_data["email"]
                })
        
        except Exception as e:
            print(f"Error parsing article: {e}")
            continue
    
    return articles

def extract_email(text: str) -> Optional[str]:
    """Extract email from text"""
    if not text:
        return None
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, text)
    
    return matches[0] if matches else None

def calculate_score(article: dict, keywords: List[str]) -> int:
    """Calculate propensity score for a lead"""
    score = 0
    
    # Base score for being found
    score += 20
    
    # Score based on publication recency
    try:
        year = int(article["pub_date"].split("-")[0])
        current_year = datetime.now().year
        years_old = current_year - year
        
        if years_old == 0:
            score += 40  # Published this year
        elif years_old == 1:
            score += 30  # Published last year
        else:
            score += 20  # Published 2 years ago
    except:
        score += 10
    
    # Score based on keyword matches in title
    title_lower = article["title"].lower()
    keyword_matches = sum(1 for kw in keywords if kw.lower() in title_lower)
    score += min(keyword_matches * 10, 30)  # Max 30 points for keywords
    
    # Bonus for having email
    if article["email"]:
        score += 10
    
    return min(score, 100)  # Cap at 100

@app.post("/api/search")
async def search_leads(request: SearchRequest):
    """Search PubMed and return scored leads"""
    try:
        # Step 1: Search PubMed
        pmids = search_pubmed(request.keywords, request.years_back, request.max_results)
        
        if not pmids:
            return {"leads": [], "total": 0}
        
        # Step 2: Fetch article details
        articles = fetch_article_details(pmids)
        
        # Step 3: Calculate scores and create leads
        leads = []
        for article in articles:
            score = calculate_score(article, request.keywords)
            
            lead = Lead(
                rank=0,  # Will be set after sorting
                name=article["author"],
                affiliation=article["affiliation"][:200],  # Truncate long affiliations
                email=article["email"],
                paper_title=article["title"][:200],  # Truncate long titles
                publication_date=article["pub_date"],
                score=score,
                pubmed_id=article["pmid"]
            )
            leads.append(lead)
        
        # Step 4: Sort by score and assign ranks
        leads.sort(key=lambda x: x.score, reverse=True)
        for idx, lead in enumerate(leads):
            lead.rank = idx + 1
        
        return {
            "leads": [lead.dict() for lead in leads],
            "total": len(leads)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PubMed Lead Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .search-section {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        
        .search-form {
            display: grid;
            gap: 20px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        label {
            font-weight: 600;
            color: #495057;
            font-size: 0.95em;
        }
        
        input[type="text"],
        input[type="number"],
        select {
            padding: 12px;
            border: 2px solid #dee2e6;
            border-radius: 6px;
            font-size: 1em;
            transition: all 0.3s;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .keywords-input {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .keyword-tag {
            background: #667eea;
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .keyword-tag button {
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 1.2em;
            line-height: 1;
        }
        
        .preset-keywords {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        
        .preset-btn {
            background: white;
            border: 2px solid #667eea;
            color: #667eea;
            padding: 6px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.3s;
        }
        
        .preset-btn:hover {
            background: #667eea;
            color: white;
        }
        
        .search-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .search-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .search-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .results-section {
            padding: 30px;
        }
        
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .results-count {
            font-size: 1.2em;
            color: #495057;
            font-weight: 600;
        }
        
        .filter-input {
            padding: 10px 15px;
            border: 2px solid #dee2e6;
            border-radius: 6px;
            font-size: 1em;
            width: 300px;
        }
        
        .export-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .export-btn:hover {
            background: #218838;
        }
        
        .table-container {
            overflow-x: auto;
            border: 1px solid #dee2e6;
            border-radius: 8px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        
        thead {
            background: #f8f9fa;
            position: sticky;
            top: 0;
        }
        
        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #495057;
            border-bottom: 2px solid #dee2e6;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
            font-size: 0.95em;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .score-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }
        
        .score-high {
            background: #d4edda;
            color: #155724;
        }
        
        .score-medium {
            background: #fff3cd;
            color: #856404;
        }
        
        .score-low {
            background: #f8d7da;
            color: #721c24;
        }
        
        .rank-badge {
            background: #667eea;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.85em;
        }
        
        .email-link {
            color: #667eea;
            text-decoration: none;
        }
        
        .email-link:hover {
            text-decoration: underline;
        }
        
        .pubmed-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        
        .pubmed-link:hover {
            text-decoration: underline;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
            color: #667eea;
        }
        
        .no-results {
            text-align: center;
            padding: 50px;
            color: #6c757d;
        }
        
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 PubMed Lead Generator</h1>
            <p>Find and rank potential leads based on recent scientific publications</p>
        </div>
        
        <div class="search-section">
            <form class="search-form" id="searchForm">
                <div class="form-group">
                    <label>Search Keywords</label>
                    <input type="text" id="keywordInput" placeholder="Enter keyword and press Enter">
                    <div class="keywords-input" id="keywordTags"></div>
                    <div class="preset-keywords">
                        <span style="font-size: 0.85em; color: #6c757d;">Quick add:</span>
                        <button type="button" class="preset-btn" onclick="addKeyword('drug-induced liver injury')">Drug-Induced Liver Injury</button>
                        <button type="button" class="preset-btn" onclick="addKeyword('3D cell culture')">3D Cell Culture</button>
                        <button type="button" class="preset-btn" onclick="addKeyword('hepatotoxicity')">Hepatotoxicity</button>
                        <button type="button" class="preset-btn" onclick="addKeyword('organoid')">Organoid</button>
                        <button type="button" class="preset-btn" onclick="addKeyword('in vitro')">In Vitro</button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Years Back</label>
                    <input type="number" id="yearsBack" value="2" min="1" max="10">
                </div>
                
                <div class="form-group">
                    <label>Max Results</label>
                    <input type="number" id="maxResults" value="50" min="10" max="200">
                </div>
                
                <button type="submit" class="search-btn" id="searchBtn">
                    🔍 Search PubMed
                </button>
            </form>
        </div>
        
        <div class="results-section" id="resultsSection" style="display: none;">
            <div class="results-header">
                <div class="results-count" id="resultsCount">0 leads found</div>
                <input type="text" class="filter-input" id="filterInput" placeholder="Filter by name, affiliation, or keyword...">
                <button class="export-btn" onclick="exportToCSV()">📥 Export to CSV</button>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Score</th>
                            <th>Name</th>
                            <th>Affiliation</th>
                            <th>Email</th>
                            <th>Paper Title</th>
                            <th>Date</th>
                            <th>PubMed</th>
                        </tr>
                    </thead>
                    <tbody id="resultsBody">
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="loading" id="loadingDiv" style="display: none;">
            Searching PubMed... ⏳
        </div>
    </div>

    <script>
        let keywords = [];
        let allLeads = [];
        
        // Keyword management
        document.getElementById('keywordInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const keyword = this.value.trim();
                if (keyword) {
                    addKeyword(keyword);
                    this.value = '';
                }
            }
        });
        
        function addKeyword(keyword) {
            if (!keywords.includes(keyword)) {
                keywords.push(keyword);
                updateKeywordTags();
            }
        }
        
        function removeKeyword(keyword) {
            keywords = keywords.filter(k => k !== keyword);
            updateKeywordTags();
        }
        
        function updateKeywordTags() {
            const container = document.getElementById('keywordTags');
            container.innerHTML = keywords.map(kw => `
                <div class="keyword-tag">
                    ${kw}
                    <button onclick="removeKeyword('${kw}')">×</button>
                </div>
            `).join('');
        }
        
        // Search form submission
        document.getElementById('searchForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (keywords.length === 0) {
                alert('Please add at least one keyword');
                return;
            }
            
            const yearsBack = parseInt(document.getElementById('yearsBack').value);
            const maxResults = parseInt(document.getElementById('maxResults').value);
            
            // Show loading
            document.getElementById('loadingDiv').style.display = 'block';
            document.getElementById('resultsSection').style.display = 'none';
            document.getElementById('searchBtn').disabled = true;
            
            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        keywords: keywords,
                        years_back: yearsBack,
                        max_results: maxResults
                    })
                });
                
                const data = await response.json();
                allLeads = data.leads;
                displayResults(allLeads);
                
            } catch (error) {
                alert('Error searching PubMed: ' + error.message);
            } finally {
                document.getElementById('loadingDiv').style.display = 'none';
                document.getElementById('searchBtn').disabled = false;
            }
        });
        
        // Display results
        function displayResults(leads) {
            document.getElementById('resultsSection').style.display = 'block';
            document.getElementById('resultsCount').textContent = `${leads.length} leads found`;
            
            const tbody = document.getElementById('resultsBody');
            tbody.innerHTML = leads.map(lead => {
                const scoreClass = lead.score >= 70 ? 'score-high' : lead.score >= 50 ? 'score-medium' : 'score-low';
                const emailDisplay = lead.email ? `<a href="mailto:${lead.email}" class="email-link">${lead.email}</a>` : 'N/A';
                
                return `
                    <tr>
                        <td><span class="rank-badge">#${lead.rank}</span></td>
                        <td><span class="score-badge ${scoreClass}">${lead.score}</span></td>
                        <td><strong>${lead.name}</strong></td>
                        <td>${lead.affiliation}</td>
                        <td>${emailDisplay}</td>
                        <td>${lead.paper_title}</td>
                        <td>${lead.publication_date}</td>
                        <td><a href="https://pubmed.ncbi.nlm.nih.gov/${lead.pubmed_id}" target="_blank" class="pubmed-link">View</a></td>
                    </tr>
                `;
            }).join('');
        }
        
        // Filter results
        document.getElementById('filterInput').addEventListener('input', function(e) {
            const filterText = e.target.value.toLowerCase();
            const filteredLeads = allLeads.filter(lead => 
                lead.name.toLowerCase().includes(filterText) ||
                lead.affiliation.toLowerCase().includes(filterText) ||
                lead.paper_title.toLowerCase().includes(filterText)
            );
            displayResults(filteredLeads);
        });
        
        // Export to CSV
        function exportToCSV() {
            const headers = ['Rank', 'Score', 'Name', 'Affiliation', 'Email', 'Paper Title', 'Publication Date', 'PubMed ID'];
            const rows = allLeads.map(lead => [
                lead.rank,
                lead.score,
                lead.name,
                lead.affiliation,
                lead.email || '',
                lead.paper_title,
                lead.publication_date,
                lead.pubmed_id
            ]);
            
            let csv = headers.join(',') + '\\n';
            rows.forEach(row => {
                csv += row.map(field => `"${field}"`).join(',') + '\\n';
            });
            
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `pubmed_leads_${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)