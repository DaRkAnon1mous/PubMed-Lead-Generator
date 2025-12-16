## 1. 🔍 DETAILED BACKEND EXPLANATION

---

### **A. Understanding PubMed's API Structure**

PubMed doesn't require traditional "scraping" (like BeautifulSoup parsing HTML). Instead, it provides a **free REST API** called **E-utilities** that returns structured data.

**Two-Step Process:**

1. **E-Search** - Search for articles, get IDs
2. **E-Fetch** - Fetch full details using those IDs

---

### **B. STEP 1: Searching PubMed (`search_pubmed` function)**

```python
def search_pubmed(keywords: List[str], years_back: int, max_results: int) -> List[str]:
```

**What happens here:**

1. **Build the query string:**
   ```python
   query_parts = []
   for keyword in keywords:
       query_parts.append(f'"{keyword}"[Title/Abstract]')
   query = " OR ".join(query_parts)
   ```
   
   **Example:** If user enters `["liver toxicity", "hepatotoxicity"]`
   - Becomes: `"liver toxicity"[Title/Abstract] OR "hepatotoxicity"[Title/Abstract]`
   - `[Title/Abstract]` tells PubMed to search in title and abstract only

2. **Add date filter:**
   ```python
   current_year = datetime.now().year  # 2025
   start_year = current_year - years_back  # 2025 - 2 = 2023
   query += f" AND {start_year}:{current_year}[PDAT]"
   ```
   - `[PDAT]` = Publication Date field
   - Final query: `"liver toxicity"[Title/Abstract] OR "hepatotoxicity"[Title/Abstract] AND 2023:2025[PDAT]`

3. **Make HTTP GET request:**
   ```python
   params = {
       "db": "pubmed",           # Database to search
       "term": query,            # Our search query
       "retmax": max_results,    # Max 100 results
       "retmode": "xml",         # Return format (XML)
       "sort": "pub_date"        # Sort by newest first
   }
   response = requests.get(PUBMED_SEARCH_URL, params=params)
   ```

4. **Parse XML response:**
   ```xml
   <eSearchResult>
       <IdList>
           <Id>38234567</Id>
           <Id>38234568</Id>
           <Id>38234569</Id>
       </IdList>
   </eSearchResult>
   ```
   
   ```python
   root = ET.fromstring(response.content)
   pmids = [id_elem.text for id_elem in root.findall(".//Id")]
   # Returns: ['38234567', '38234568', '38234569']
   ```

**Result:** List of PubMed IDs (PMIDs) - just numbers, no author info yet!

---

### **C. STEP 2: Fetching Article Details (`fetch_article_details` function)**

```python
def fetch_article_details(pmids: List[str]) -> List[dict]:
```

**What happens here:**

1. **Request full article data:**
   ```python
   params = {
       "db": "pubmed",
       "id": ",".join(pmids),  # "38234567,38234568,38234569"
       "retmode": "xml"
   }
   response = requests.get(PUBMED_FETCH_URL, params=params)
   ```

2. **Parse complex XML structure:**
   
   PubMed returns XML like this:
   ```xml
   <PubmedArticle>
       <PMID>38234567</PMID>
       <Article>
           <ArticleTitle>Drug-Induced Liver Injury in 3D Models</ArticleTitle>
           <AuthorList>
               <Author>
                   <LastName>Smith</LastName>
                   <ForeName>John</ForeName>
                   <AffiliationInfo>
                       <Affiliation>Department of Toxicology, Harvard Medical School, Boston, MA. john.smith@harvard.edu</Affiliation>
                   </AffiliationInfo>
               </Author>
               <Author>
                   <LastName>Doe</LastName>
                   <ForeName>Jane</ForeName>
               </Author>
           </AuthorList>
           <PubDate>
               <Year>2024</Year>
               <Month>Nov</Month>
           </PubDate>
       </Article>
   </PubmedArticle>
   ```

3. **Extract each piece of data:**

   **A. Get PMID:**
   ```python
   pmid = article.find(".//PMID").text
   # Result: "38234567"
   ```

   **B. Get Title:**
   ```python
   title_elem = article.find(".//ArticleTitle")
   title = "".join(title_elem.itertext())
   # Result: "Drug-Induced Liver Injury in 3D Models"
   ```

   **C. Get Publication Date:**
   ```python
   pub_date = article.find(".//PubDate")
   year = pub_date.find("Year").text  # "2024"
   month = pub_date.find("Month").text  # "Nov"
   pub_date_str = f"{year}-{month}"  # "2024-Nov"
   ```

   **D. Get Authors (Most Important Part):**
   ```python
   authors = article.findall(".//Author")
   
   for idx, author in enumerate(authors):
       lastname = author.find("LastName").text  # "Smith"
       forename = author.find("ForeName").text  # "John"
       name = f"{forename} {lastname}"  # "John Smith"
       
       # Get affiliation (contains email!)
       affiliation_elem = author.find(".//Affiliation")
       affiliation = affiliation_elem.text
       # "Department of Toxicology, Harvard Medical School, Boston, MA. john.smith@harvard.edu"
       
       # Extract email using regex
       email = extract_email(affiliation)
   ```

4. **Email Extraction Logic:**
   ```python
   def extract_email(text: str) -> Optional[str]:
       email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
       matches = re.findall(email_pattern, text)
       return matches[0] if matches else None
   ```
   
   **How regex works:**
   - `[A-Za-z0-9._%+-]+` - Username part (john.smith)
   - `@` - Literal @ symbol
   - `[A-Za-z0-9.-]+` - Domain (harvard)
   - `\.` - Literal dot
   - `[A-Z|a-z]{2,}` - Extension (edu, com)
   
   **From:** "Department of Toxicology, Harvard Medical School, Boston, MA. john.smith@harvard.edu"  
   **Extracts:** "john.smith@harvard.edu"

5. **Prioritize Corresponding Author:**
   ```python
   # First author without email
   first_author = {"name": "John Smith", "email": None}
   
   # Loop through all authors
   for author in authors:
       if author has email:
           corresponding_author = {"name": "John Smith", "email": "john.smith@harvard.edu"}
           break  # Stop, we found someone with email!
   
   # Use corresponding author if found, else use first author
   author_data = corresponding_author if corresponding_author else first_author
   ```

**Result:** List of dictionaries with all extracted data!

---

### **D. STEP 3: Scoring Algorithm (`calculate_score` function)**

```python
def calculate_score(article: dict, keywords: List[str]) -> int:
    score = 0
```

**Scoring breakdown:**

1. **Base score:** Everyone gets 20 points for being found

2. **Recency scoring:**
   ```python
   year = 2024
   current_year = 2025
   years_old = 2025 - 2024 = 1
   
   if years_old == 0: score += 40  # Published this year (2025)
   elif years_old == 1: score += 30  # Last year (2024)
   else: score += 20  # 2 years ago (2023)
   ```

3. **Keyword matching in title:**
   ```python
   title = "Drug-Induced Liver Injury in 3D Models"
   keywords = ["liver toxicity", "3D cell culture"]
   
   # Count how many keywords appear in title
   keyword_matches = 0
   if "liver toxicity" in title.lower(): keyword_matches += 1
   if "3D cell culture" in title.lower(): keyword_matches += 1
   
   score += min(keyword_matches * 10, 30)  # Max 30 points
   ```

4. **Email bonus:**
   ```python
   if article["email"]:
       score += 10  # Having contact info is valuable!
   ```

5. **Cap at 100:**
   ```python
   return min(score, 100)
   ```

**Example calculation:**
- Base: 20
- Published in 2024: +30
- 1 keyword match: +10
- Has email: +10
- **Total: 70/100**

---

### **E. STEP 4: Ranking and Sorting**

```python
leads.sort(key=lambda x: x.score, reverse=True)

for idx, lead in enumerate(leads):
    lead.rank = idx + 1
```

**What happens:**
1. Sort all leads by score (highest first)
2. Assign rank numbers (1st, 2nd, 3rd...)

**Example:**

Before sorting:
- John Smith (score: 60)
- Jane Doe (score: 85)
- Bob Wilson (score: 72)

After sorting:
- Rank 1: Jane Doe (score: 85)
- Rank 2: Bob Wilson (score: 72)
- Rank 3: John Smith (score: 60)


---

### **F. CSV Export (Frontend JavaScript)**


function exportToCSV() {
    // 1. Define headers
    const headers = ['Rank', 'Score', 'Name', 'Affiliation', ...];
    
    // 2. Convert each lead to array
    const rows = allLeads.map(lead => [
        lead.rank,      // 1
        lead.score,     // 85
        lead.name,      // "Jane Doe"
        lead.affiliation, // "Harvard Medical School"
        lead.email || '', // "jane@harvard.edu"
        ...
    ]);
    
    // 3. Build CSV string
    let csv = 'Rank,Score,Name,Affiliation,Email\n';
    csv += '1,85,"Jane Doe","Harvard Medical School","jane@harvard.edu"\n';
    csv += '2,72,"Bob Wilson","MIT","bob@mit.edu"\n';
    
    // 4. Create downloadable file
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    
    // 5. Trigger download
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pubmed_leads_2025-12-16.csv';
    a.click();
}


**Why it's easy:**
- No server processing needed
- JavaScript creates file in browser
- User downloads immediately

---

### **G. Why This Works So Well**

1. **No scraping needed** - PubMed provides clean XML API
2. **No authentication** - Completely free, no API key
3. **Structured data** - XML is easy to parse with ElementTree
4. **Rich metadata** - PubMed includes emails in affiliations
5. **Fast** - One request gets 100 articles at once

---

### **H. Complete Data Flow Summary**


User Input: ["liver toxicity", "3D models"]
    ↓
1. E-Search API: Get PMIDs
   Query: "liver toxicity"[Title/Abstract] OR "3D models"[Title/Abstract] AND 2023:2025[PDAT]
   Response: [38234567, 38234568, 38234569, ...]
    ↓
2. E-Fetch API: Get full XML for each PMID
   Request: id=38234567,38234568,38234569
   Response: Giant XML with all article details
    ↓
3. XML Parsing: Extract data using ElementTree
   - Find <PMID> tags → get IDs
   - Find <ArticleTitle> tags → get titles
   - Find <Author> tags → get names
   - Find <Affiliation> tags → extract emails with regex
   - Find <PubDate> tags → get publication dates
    ↓
4. Scoring: Calculate propensity score
   - Base (20) + Recency (40) + Keywords (10) + Email (10) = 80/100
    ↓
5. Ranking: Sort by score, assign rank numbers
    ↓
6. API Response: Return JSON to frontend
   {
     "leads": [
       {"rank": 1, "score": 80, "name": "John Smith", ...},
       {"rank": 2, "score": 75, "name": "Jane Doe", ...}
     ],
     "total": 50
   }
    ↓
7. Frontend: Display in table, enable filtering
    ↓
8. Export: Convert JSON to CSV, download file
