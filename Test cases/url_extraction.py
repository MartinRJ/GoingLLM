from urlextract import URLExtract
import re
import string
from uuid import uuid4

def remove_punctuation(urls):
    cleaned_urls = []
    for url in urls:
        cleaned_url = url.rstrip(string.punctuation)
        cleaned_urls.append(cleaned_url)
    return cleaned_urls

def normalize_urls_protocol(urls):
    normalized_urls = []
    for url in urls:
        # Replace improper protocols and "http://" with "https://"
        url = re.sub(r'^(?:htp://|http:/*|http://|https?://)', 'https://', url, flags=re.IGNORECASE)
       
        # Add "https://" protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        normalized_urls.append(url)
    return normalized_urls

def find_additional_urls(text):
    tlds = [".com", ".tk", ".cn", ".de", ".net", ".uk", ".org", ".nl", ".ru", ".br", ".au",
    ".fr", ".eu", ".it", ".pl", ".in", ".info", ".es", ".ca", ".io", ".gov", ".gov.uk", ".gouv.fr",
    ".gc.ca", ".gov.au", ".gov.in", ".gov.za", ".gov.cn", ".gov.br", ".gov.sg", ".gov.de",
    ".gov.it", ".gov.nl", ".gov.my", ".gov.ru", ".gov.ua", ".gov.ie", ".gov.nz", ".gov.il",
    ".gov.pl", ".edu", ".ac", ".sci", ".research", ".scholar", ".ir", ".ch", ".at", ".be", ".dk",
    ".fi", ".gr", ".hu", ".no", ".pt", ".se", ".co", ".biz", ".co.uk", ".ac.uk", ".edu.au",
    ".edu.sg", ".edu.de", ".coop", ".museum", ".pro", ".name", ".govt.nz"]
    additional_urls = []

    # Find URLs with https:// or http:// and special characters at the end
    pattern = re.compile(r'https?://[^\s!\"\'\[\]\(\)]+')
    matches = pattern.finditer(text)
    for match in matches:
        additional_urls.append(match.group())

    # Find URLs without https:// or http://
    url_chars = r"[A-Za-z0-9\-\._~:/\?#\[\]@!\$&'\(\)\*\+,;=äöüÄÖÜß]+"
    
    for tld in tlds:
        pattern = re.compile(fr"{url_chars}{re.escape(tld)}")
        matches = pattern.finditer(text)
        for match in matches:
            if not match.group().startswith(("http://", "https://")):
                additional_urls.append(match.group())
    return additional_urls

def remove_extracted_urls_from_text(text, extracted_urls):
    cleaned_text = text
    for url in extracted_urls:
        index = text.find(url)
        if index > 0 and text[index - 1] == ".":
            cleaned_text = cleaned_text.replace("." + url, "", 1)
        else:
            cleaned_text = cleaned_text.replace(url, "", 1)
    return cleaned_text

def extract_document_urls_using_urlextract(text):
    if not text:
        return []
    #Extracts all URLs from text
    tlds = [".com", ".tk", ".cn", ".de", ".net", ".uk", ".org", ".nl", ".ru", ".br", ".au",
    ".fr", ".eu", ".it", ".pl", ".in", ".info", ".es", ".ca", ".io", ".gov", ".gov.uk", ".gouv.fr",
    ".gc.ca", ".gov.au", ".gov.in", ".gov.za", ".gov.cn", ".gov.br", ".gov.sg", ".gov.de",
    ".gov.it", ".gov.nl", ".gov.my", ".gov.ru", ".gov.ua", ".gov.ie", ".gov.nz", ".gov.il",
    ".gov.pl", ".edu", ".ac", ".sci", ".research", ".scholar", ".ir", ".ch", ".at", ".be", ".dk",
    ".fi", ".gr", ".hu", ".no", ".pt", ".se", ".co", ".biz", ".co.uk", ".ac.uk", ".edu.au",
    ".edu.sg", ".edu.de", ".coop", ".museum", ".pro", ".name", ".govt.nz"]
    file_exts = [
        ".txt", ".csv", ".md", ".log", ".conf", ".config", ".ini", ".yml", ".yaml",
        ".xml", ".json", ".html", ".php", ".js", ".py", ".java", ".c", ".cpp",
        ".cs", ".rb", ".sh", ".r", ".m", ".sql"
    ]

    replacements = []
    uuids = []

    pattern = re.compile(r'/(?P<filename>[\w\-]+)(?P<file_ext>\.[A-Za-z0-9]+)(?P<next_char>[\s\.,:;\?!])')
    #Make sure that TLDs don't override file extensions
    for tld in tlds:
        for file_ext in file_exts:
            if file_ext.startswith(tld):
                matches = pattern.finditer(text)
                for match in matches:
                    if match.group('file_ext') == file_ext:
                        tempuuid = uuid4()
                        temp_tld = f"{tempuuid}.com"
                        original_filename = match.group('filename')
                        replacements.append((original_filename, file_ext, temp_tld))
                        uuids.append(tempuuid)
                        original_str = f"/{match.group('filename')}{file_ext}{match.group('next_char')}"
                        replaced_str = f"/{tempuuid}.com{match.group('next_char')}"
                        text = text.replace(original_str, replaced_str)

    extractor = URLExtract()
    all_urls = extractor.find_urls(text)
    
    # Filter out the URLs that are just TLDs
    cleaned_urls = []
    for url in all_urls:
        index = text.find(url)
        if index == 0 or text[index - 1] != ".":
            cleaned_urls.append(url)

    # Remove the extracted URLs from the text
    cleaned_text = remove_extracted_urls_from_text(text, all_urls)
    
    # Find additional URLs with special characters at the end
    additional_urls = find_additional_urls(cleaned_text)

    cleaned_urls.extend(additional_urls)
    
    cleaned_urls = normalize_urls_protocol(cleaned_urls)
    cleaned_urls = remove_punctuation(cleaned_urls)

    # Replace temporary TLDs and filenames back to original values
    for original_filename, file_ext, temp_tld in replacements:
        cleaned_urls = [url.replace(temp_tld, f"{original_filename}{file_ext}") for url in cleaned_urls]

    # Remove URLs containing any of the stored UUIDs
    cleaned_urls = [url for url in cleaned_urls if not any(str(tempuuid) in url for tempuuid in uuids)]
    # Remove duplicates
    cleaned_urls = list(set(cleaned_urls))
    return cleaned_urls

#------------------------

# Unit tests:
def test_extract_urls(input_text, expected_urls):
    extracted_urls = extract_document_urls_using_urlextract(input_text)
    print("Testing")
    correct = True
    
    missing_urls = set(expected_urls) - set(extracted_urls)
    excess_urls = set(extracted_urls) - set(expected_urls)
    
    if missing_urls:
        print(f"Missing URLs: {missing_urls}")
        correct = False
    
    if excess_urls:
        print(f"Excess URLs: {excess_urls}")
        correct = False
    return correct

# Test case 1
input_text1 = "Visit openai.com/blog for more information. You can also check out hTtps://www.example.org/news and Https://twitter.com/openai/status/123456789."

expected_urls1 = [
    "https://openai.com/blog",
    "https://www.example.org/news",
    "https://twitter.com/openai/status/123456789"
]

# Test case 2
input_text2 = "Some interesting websites include: www.github.com, www.google.com, and openai.com. Don't forget to visit hTtps://arxiv.org/abs/2103.00027v1!"

expected_urls2 = [
    "https://www.github.com",
    "https://www.google.com",
    "https://openai.com",
    "https://arxiv.org/abs/2103.00027v1"
]

# Test case 3
input_text3 = "Here's a list of resources: http://blog.openai.com, Https://www.example.com/post?id=42, and https://www.example.com/post?id=43. Also, check the paper at https://arxiv.org/pdf/2103.00027v1.pdf."

expected_urls3 = [
    "https://blog.openai.com",
    "https://www.example.com/post?id=42",
    "https://www.example.com/post?id=43",
    "https://arxiv.org/pdf/2103.00027v1.pdf"
]

# Test case 4
input_text4 = "https://hallo.com. Please analyze the information in the website goingllm.com and compare it with the information from github.com/martinrj/goingllm and extract the most relevant info. Put the information from google-scholar.gov.nl/covid-news/researchpapers/paper3-4.22.nll.pdf into a table. Can you summarize the info from https://someurl.gov.nz/test.xlsx and tell me the most notable findings in the data? Is the .edu.de TLD more common than .name in Germany? I want to compare a list of websites (fuerholz.org, fürholz.de, https://fuerholz.net), and don't forget Http://google.de and https://google.com! And print them in a CSV-list. >>>> Https://google.au, https://google.gov? https://google.cc] https://google.org[ google.ch( http://googleimg.eu( <<<< Also check http:/fuerholz.de"

expected_urls4 = [
    "https://hallo.com",
    "https://goingllm.com",
    "https://github.com/martinrj/goingllm",
    "https://google-scholar.gov.nl/covid-news/researchpapers/paper3-4.22.nll.pdf",
    "https://someurl.gov.nz/test.xlsx",
    "https://fuerholz.org",
    "https://fürholz.de",
    "https://fuerholz.net",
    "https://google.de",
    "https://google.com",
    "https://google.au",
    "https://google.gov",
    "https://google.cc",
    "https://google.org",
    "https://google.ch",
    "https://googleimg.eu",
    "https://fuerholz.de"
]

# Test case 5: Empty text
input_text5 = ""

expected_urls5 = []

# Test case 6: Text with no URLs
input_text6 = "This is a text without any URLs. It just contains some random words and punctuation marks, such as: commas, periods, and exclamation marks!"

expected_urls6 = []

# Test case 7: Text with only one URL
input_text7 = "Https://www.example.com"

expected_urls7 = [
    "https://www.example.com"
]

# Test case 8
input_text8 = """
Visit https://openai.com/blog for more information.
Some interesting resources include:
  - openai.com
  - www.github.com
  - www.google.com
Also, check the following:
https://www.example.org/news
And don't forget to read htTps://arxiv.org/abs/2103.00027v1!
"""

expected_urls8 = [
    "https://openai.com/blog",
    "https://openai.com",
    "https://www.github.com",
    "https://www.google.com",
    "https://www.example.org/news",
    "https://arxiv.org/abs/2103.00027v1"
]

# Test case 9
input_text9 = """
Visit these URLs with different file extensions:
tst.com/file.txt,
tst.com/data.csv,
tst.com/readme.md,
tst.com/app.log,
Http:/tst.com/server.conf,
tst.com/app.config,
HtTps://tst.com/settings.ini,
tst.com/config.yml,
tst.com/data.yaml,
tst.com/sample.xml,
http://tst.com/data.json,
tst.com/index.html,
tst.com/script.php,
tst.com/app.js,
tst.com/main.py,
tst.com/test.java,
tst.com/code.c,
tst.com/program.cpp,
tst.com/app.cs,
tst.com/script.rb,
tst.com/command.sh,
tst.com/analysis.r,
tst.com/algorithm.m,
tst.com/query.sql
"""

expected_urls9 = [
    "https://tst.com/file.txt",
    "https://tst.com/data.csv",
    "https://tst.com/readme.md",
    "https://tst.com/app.log",
    "https://tst.com/server.conf",
    "https://tst.com/app.config",
    "https://tst.com/settings.ini",
    "https://tst.com/config.yml",
    "https://tst.com/data.yaml",
    "https://tst.com/sample.xml",
    "https://tst.com/data.json",
    "https://tst.com/index.html",
    "https://tst.com/script.php",
    "https://tst.com/app.js",
    "https://tst.com/main.py",
    "https://tst.com/test.java",
    "https://tst.com/code.c",
    "https://tst.com/program.cpp",
    "https://tst.com/app.cs",
    "https://tst.com/script.rb",
    "https://tst.com/command.sh",
    "https://tst.com/analysis.r",
    "https://tst.com/algorithm.m",
    "https://tst.com/query.sql"
]

# Running the tests
print("Test case 1:", test_extract_urls(input_text1, expected_urls1))  # Should print True
print("Test case 2:", test_extract_urls(input_text2, expected_urls2))  # Should print True
print("Test case 3:", test_extract_urls(input_text3, expected_urls3))  # Should print True
print("Test case 4:", test_extract_urls(input_text4, expected_urls4))  # Should print True
print("Test case 5:", test_extract_urls(input_text5, expected_urls5))  # Should print True
print("Test case 6:", test_extract_urls(input_text6, expected_urls6))  # Should print True
print("Test case 7:", test_extract_urls(input_text7, expected_urls7))  # Should print True
print("Test case 8:", test_extract_urls(input_text8, expected_urls8))  # Should print True
print("Test case 9:", test_extract_urls(input_text9, expected_urls9))  # Should print True