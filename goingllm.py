from bs4 import BeautifulSoup
from flask import Flask, request, make_response, send_from_directory
from googleapiclient.discovery import build
from io import BytesIO
import json
import markdown
import mimetypes
from num2words import num2words
import openai
import os
import pandas as pd
from pptx import Presentation
from PyPDF2 import PdfReader
import re
import requests
import threading
import tiktoken
import time
from urlextract import URLExtract
import uuid
app = Flask(__name__)

SECRET_KEY = os.getenv('SECRETKEY')
CUSTOMSEARCH_KEY = os.getenv('CUSTOMSEARCHKEY')
CX = os.getenv('cx')
TEMPERATURE_DECISION_TO_GOOGLE = float(os.getenv('temperature_decision_to_google'))
MAX_TOKENS_DECISION_TO_GOOGLE = int(os.getenv('max_tokens_decision_to_google'))
TEMPERATURE_CREATE_SEARCHTERMS = float(os.getenv('temperature_create_searchterms'))
MAX_TOKENS_CREATE_SEARCHTERMS = int(os.getenv('max_tokens_create_searchterms'))
TEMPERATURE_SUMMARIZE_RESULT = float(os.getenv('temperature_summarize_result'))
MAX_TOKENS_SUMMARIZE_RESULT = int(os.getenv('SUMMARIZE_MAX_TOKEN_LENGTH'))
MAX_FILE_CONTENT = int(os.getenv('MAX_FILE_CONTENT'))
NUMBER_GOOGLE_RESULTS = int(os.getenv('NUMBER_GOOGLE_RESULTS'))
NUMBER_OF_KEYWORDS = int(os.getenv('NUMBER_OF_KEYWORDS'))
TEMPERATURE_FINAL_RESULT = float(os.getenv('temperature_final_result'))
MAX_TOKENS_FINAL_RESULT = int(os.getenv('FINALRESULT_MAX_TOKEN_LENGTH'))
TEMPERATURE_SELECT_SEARCHES = float(os.getenv('temperature_select_searches'))
MAX_TOKENS_SELECT_SEARCHES_LENGTH = int(os.getenv('SELECT_SEARCHES_MAX_TOKEN_LENGTH'))
BODY_MAX_LENGTH = int(os.getenv('BODY_MAX_LENGTH'))

#BASIC AUTHENTICATION
AUTH_UNAME = os.getenv('AUTH_UNAME')
AUTH_PASS = os.getenv('AUTH_PASS')

MODEL = os.getenv('model')
MODEL_MAX_TOKEN = int(os.getenv('model_max_token'))

openai.api_key = SECRET_KEY

@app.route("/", methods=['POST'])
def startup():
    auth = request.authorization #Basic authentication
    if not auth or not (auth.username == AUTH_UNAME and auth.password == AUTH_PASS):
        response = make_response('Could not verify your login!', 401)
        response.headers['WWW-Authenticate'] = 'Basic realm="Login Required"'
        return response
    try:
        body = request.get_data(as_text=True)
        if not body:
            raise ValueError('Empty body')
    except Exception as e:
        print("There was an error with the input.", flush=True)
        return f'Error extracting body: {e}', 400

    if len(body) > BODY_MAX_LENGTH:
        task_id = str(uuid.uuid4())
        errormessage = "Input is too long."
        print(errormessage, flush=True)
        writefile(100, errormessage, task_id)
        response = make_response('', 200)
        response.headers['task_id'] = task_id
        return response
    else:
        usertask = body
        dogoogleoverride = False
        always_google = request.headers.get('X-Always-Google')
        if always_google and always_google.lower() == 'true':
            dogoogleoverride = True

        #create new JSON output file with status 'started' and send a 200 response, and start the actual tasks.
        task_id = str(uuid.uuid4())
        threading.Thread(target=response_task, args=(body, task_id, dogoogleoverride)).start()
        writefile(0, False, task_id)
        response = make_response('', 200)
        response.headers['task_id'] = task_id
        return response

@app.route('/searches/<filename>')
def download_file(filename):
    return send_from_directory('searches', filename)

@app.route('/')
def index():
    return app.send_static_file('assistant.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(os.path.join(app.root_path, 'static'), path)

def writefile(progress, json_data, task_id):
    data = {}
    if not json_data:
        data = {
            "task_id": task_id,
            "progress": progress
        }
    else:
        data = {
            "task_id": task_id,
            "progress": progress,
            "answer": json_data
        }
    try:
        # create a 'searches' directory if it does not exist
        if not os.path.exists('searches'):
            os.makedirs('searches')
        # set the file path
        file_path = f'searches/{task_id}.json'
        # open file in write mode
        print("Writing to /" + file_path, flush=True)
        with open(file_path, 'w') as f:
            # write JSON data to file
            f.write(json.dumps(data))
    except Exception as e:
        print("Could not write file", flush=True)


def response_task(usertask, task_id, dogoogleoverride):
    if "<<" in usertask or ">>" in usertask:
        usertask = usertask.replace("<<", "»").replace(">>", "«")

    ALLURLS = []

    #The user can omit the part, where this tool asks Assistant whether it requires a google search for the task
    dogooglesearch = False
    if not dogoogleoverride:
        if calculate_available_tokens(MAX_TOKENS_DECISION_TO_GOOGLE) < 1:
            print("Error, need at least 1 token for a query.", flush=True)
            final_result = "Error - need at least 1 token for a query."
        else:
            prompt = "Es wurde folgende Anfrage gestellt: >>" + usertask + "<<. Benötigst du weitere Informationen aus einer Google-Suche, um diese Anfrage zu erfüllen? Bitte antworte mit 'Ja.' oder 'Nein.'."
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche und antworte nur mit 'Ja.' oder 'Nein.'"
            prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_DECISION_TO_GOOGLE, system_prompt)
            response = openai.ChatCompletion.create(
            model=MODEL,
            temperature=TEMPERATURE_DECISION_TO_GOOGLE,
            max_tokens=MAX_TOKENS_DECISION_TO_GOOGLE,
            messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            responsemessage = response['choices'][0]['message']['content']
            dogooglesearch = yes_or_no(responsemessage)
    else:
        dogooglesearch = True

    has_result = False
    if dogooglesearch:
        number_keywords = num2words(NUMBER_OF_KEYWORDS, lang='de')
        if NUMBER_OF_KEYWORDS == 1:
            number_entries = "einen Eintrag"
            number_searches = "eine Suche"
        else:
            number_entries = number_keywords + " Einträge"
            number_searches = number_keywords + "Suchen"

        if calculate_available_tokens(MAX_TOKENS_CREATE_SEARCHTERMS) < 1:
            print("Error, need at least 1 token for a query.", flush=True)
            has_result = False
        else:
            prompt = "Bitte gib das JSON-Objekt als Antwort zurück, das "+ number_entries + " mit dem Schlüssel 'keywords' enthält, mit den am besten geeigneten Suchbegriffen oder -phrasen, um relevante Informationen zu folgendem Thema mittels einer Google-Suche zu finden: >>" + usertask + "<<. Berücksichtige dabei Synonyme und verwandte Begriffe und ordne die Suchbegriffe in einer Reihenfolge an, die am wahrscheinlichsten zu erfolgreichen Suchergebnissen führt. Berücksichtige, dass die Ergebnisse der "+ number_searches + " in Kombination verwendet werden sollen, also kannst du bei Bedarf nach einzelnen Informationen suchen. Nutze für die Keywords diejenige Sprache die am besten geeignet ist um relevante Suchergebnisse zu erhalten."
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
            prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_CREATE_SEARCHTERMS, system_prompt)
            response = openai.ChatCompletion.create(
            model=MODEL,
            temperature=TEMPERATURE_CREATE_SEARCHTERMS,
            max_tokens=MAX_TOKENS_CREATE_SEARCHTERMS,
            messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            keywords = [False]

            #Attempt to extract the JSON object from the response
            jsonobject = extract_json(response['choices'][0]['message']['content'], "keywords")

            if jsonobject:
                # the function returned a list
                keywords = jsonobject
            else:
                # the function returned False
                keywords = [False]

            ergebnis = False
            if not keywords:
                ergebnis = False
            elif all(isinstance(item, str) for item in keywords):
                ergebnis = True
            else:
                ergebnis = False
                print("Not all entries in the keyword-array are strings. Cannot use the results.", flush=True)
            searchresults = []
            zaehler = 0
            if not ergebnis == False:
                for keyword in keywords:
                    search_google_result = search_google(keyword)
                    print("Search Google result contains the following data: " + json.dumps(search_google_result), flush=True)
                    google_result = None
                    for search_result in search_google_result['searchresults']:
                        for key in search_result:
                            if not google_result is None:
                                google_result.append(search_result[key]['url'])
                            else:
                                google_result = [search_result[key]['url']]
                    # Let ChatGPT pick the most promising

                    if calculate_available_tokens(MAX_TOKENS_SELECT_SEARCHES_LENGTH) < 1:
                        print("Error, need at least 1 token for a query.", flush=True)
                        has_result = False
                    else:
                        prompt = "Bitte wählen Sie die Reihenfolge der vielverprechendsten Google-Suchen aus der folgenden Liste aus die für Sie zur Beantwortung der Aufgabe >>" + usertask + "<< am nützlichsten sein könnten und geben Sie sie als JSON-Objekt mit dem Objekt \"weighting\", das index, und einen \"weight\" Wert enthält zurück, der die geschätzte Gewichtung der Relevanz angibt, in Summe soll das den Wert 1 ergeben. Ergebnisse die für die Aufgabe keine Relevanz versprechen, können Sie aus dem resultierenden JSON-Objekt entfernen: \n\n" + json.dumps(search_google_result) + " Beispiel-Antwort: {\"weighting\": {3:0.6,0:0.2,1:0.1,2:0.1}}. Schreibe keine Begründung, sondern antworte nur mit dem JSON-Objekt."
                        system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche und antworte mit JSON-Objekten"
                        #debug_output("Page content - untruncated", prompt, system_prompt, 'w') #----Debug Output
                        prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_SELECT_SEARCHES_LENGTH, system_prompt)
                        #debug_output("Page content", prompt, system_prompt, 'a') #----Debug Output
                        response = openai.ChatCompletion.create(
                        model=MODEL,
                        temperature=TEMPERATURE_SELECT_SEARCHES,
                        max_tokens=MAX_TOKENS_SELECT_SEARCHES_LENGTH,
                        messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        weighting = extract_json(response['choices'][0]['message']['content'], "weighting")

                        if weighting:
                            # the function returned a list, re-sort
                            sorted_weighting = sorted(weighting.items(), key=lambda x: x[1], reverse=True)
                            gpturls = {}
                            for index, _ in sorted_weighting:
                                gpturls[index] = search_google_result['searchresults'][index]['url']
                            results = gpturls
                        else:
                            # the function returned False, resume unaltered
                            print("No results of initial sort.", flush=True)


                    # Check for links in the original task
                    extractor = URLExtract()
                    urls = extractor.find_urls(usertask)
                    if len(urls) > 0:
                        # use a list comprehension to add https:// to each url if needed
                        urls = ["https://" + url if not url.startswith("https://") else url for url in urls]
                        if google_result is None:
                            google_result = urls
                        else:
                            google_result[:0] = urls

                    # Check if the result is None
                    if google_result is None:
                        # The function has returned an error
                        print("There was an error in the search.", flush=True)
                    else:
                        # The function has returned a list of URLs
                        for URL in google_result:
                            percent = str(zaehler / ((NUMBER_GOOGLE_RESULTS * NUMBER_OF_KEYWORDS)+len(urls)) * 100)
                            writefile(percent, False, task_id)
                            zaehler = zaehler + 1
                            if URL in ALLURLS:
                                continue
                            ALLURLS.append(URL)
                            print("Here are the URLs: " + URL, flush=True)
                            dlfile = extract_content(URL)
                            if not dlfile == False:
                                responsemessage = dlfile

                                if calculate_available_tokens(MAX_TOKENS_SUMMARIZE_RESULT) < 1:
                                    print("Error, need at least 1 token for a query.", flush=True)
                                    has_result = False
                                else:
                                    prompt = "Es wurde folgende Anfrage gestellt: >>" + usertask + "<<. Im Folgenden findest du den Inhalt einer Seite aus den Google-Suchergebnissen zu dieser Anfrage, bitte fasse das Wesentliche zusammen um mit dem Resultat die Anfrage bestmöglich beantworten zu können, stelle sicher, dass du sämtliche relevanten Spezifika, die in deinen internen Datenbanken sonst nicht vorhanden sind, in der Zusammefassung erwähnst:\n\n" + responsemessage
                                    system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
                                    #debug_output("Page content - untruncated", prompt, system_prompt, 'w') #----Debug Output
                                    prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_SUMMARIZE_RESULT, system_prompt)
                                    #debug_output("Page content", prompt, system_prompt, 'a') #----Debug Output
                                    response = openai.ChatCompletion.create(
                                    model=MODEL,
                                    temperature=TEMPERATURE_SUMMARIZE_RESULT,
                                    max_tokens=MAX_TOKENS_SUMMARIZE_RESULT,
                                    messages=[
                                            {"role": "system", "content": system_prompt},
                                            {"role": "user", "content": prompt}
                                        ]
                                    )
                                    result_summary = response['choices'][0]['message']['content']
                                    #debug_output("Page content - result", result_summary, system_prompt, 'a')
                                    searchresults.append(result_summary)
                                    has_result = True
                            else:
                                responsemessage = "Error"
                                print("Error summarizing URL content: " + URL, flush=True)
            else:
                #no search terms
                has_result = False
                print("No search terms.", flush=True)

            finalquery = "Zu der folgenden Anfrage: >>" + usertask + "<< wurde eine Google-Recherche durchgeführt, die Ergebnisse findest du im Anschluss. Bitte nutze die Ergebnisse und die Informationen aus einer tiefen Recherche in deinen Datenbanken, um die Anfrage zu lösen.\n\nHier sind die Ergebnisse der Google-Recherche:\n"
            has_text = False
            for text in searchresults:
                if len(text) > 0:
                    has_text = True
                    finalquery += text

            if has_text:
                print("Final result found, making final query.", flush=True)
                if calculate_available_tokens(MAX_TOKENS_FINAL_RESULT) < 1:
                    print("Error, need at least 1 token for a query.", flush=True)
                    has_result = False
                else:
                    system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
                    #debug_output("final query - untruncated", finalquery, system_prompt, 'w') #----Debug Output
                    finalquery = truncate_string_to_tokens(finalquery, MAX_TOKENS_FINAL_RESULT, system_prompt)
                    response = openai.ChatCompletion.create(
                    model=MODEL,
                    temperature=TEMPERATURE_FINAL_RESULT,
                    max_tokens=MAX_TOKENS_FINAL_RESULT,
                    messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": finalquery}
                        ]
                    )
                    final_result = response['choices'][0]['message']['content']
                    #final_result = escape_result(final_result)
                    print("Final query completed. Usage = prompt_tokens: " + str(response['usage']['prompt_tokens']) + ", completion_tokens: " + str(response['usage']['completion_tokens']) + ", total_tokens: " + str(response['usage']['total_tokens']), flush=True)
                    #debug_output("final query", finalquery, system_prompt, 'a') #----Debug Output
                    has_result = True
            else:
                has_result = False
                print("No search results.", flush=True)
    else:
        has_result = False
        print("GPT thinks, no search is required: " + responsemessage, flush=True)

    if not has_result:
        print("Nothing found, making a regular query.", flush=True)
        #Make a regular query
        if calculate_available_tokens(MAX_TOKENS_FINAL_RESULT) < 1:
            print("Error, need at least 1 token for a query.", flush=True)
            final_result = "Error - need at least 1 token for a query."
        else:
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
            usertask = truncate_string_to_tokens(usertask, MAX_TOKENS_FINAL_RESULT, system_prompt)
            response = openai.ChatCompletion.create(
            model=MODEL,
            temperature=TEMPERATURE_FINAL_RESULT,
            max_tokens=MAX_TOKENS_FINAL_RESULT,
            messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": usertask}
                ]
            )
            final_result = response['choices'][0]['message']['content']
            #final_result = escape_result(final_result)

    #html = markdown.markdown(responsemessage)
    writefile(100, final_result, task_id)

def debug_output(note, string, system_prompt, mode):
    messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": string}
    ]
    try:
        # create a 'searches' directory if it does not exist
        if not os.path.exists('searches'):
            os.makedirs('searches')
        # set the file path
        file_path = f'searches/temp.json'
        # open file in write mode
        print("Writing debug output to /" + file_path, flush=True)
        with open(file_path, mode) as f:
            # write JSON data to file
            f.write(note + "\n")
            json.dump(messages, f)
    except Exception as e:
        print("Could not write file", flush=True)

def extract_json(stringwithjson, objectname):
    # Find the start and end indices of the outermost JSON object
    start = -1
    end = -1
    brace_count = 0
    for i, char in enumerate(stringwithjson):
        if char == '{':
            if start == -1:
                start = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    #find the JSON object
    if start == -1 or end == 0:
        print("Error: JSON object not found", flush=True)
        return False

    json_string = stringwithjson[start:end]

    #parse the JSON object
    try:
        # Convert integer keys to strings
        json_string = re.sub(r'\"(\d+)\":', lambda match: '"' + str(match.group(1)) + '":', json_string)
        data = json.loads(json_string)
    except ValueError as e:
        print("Error: Malformed JSON object: " + stringwithjson, flush=True)
        return False

    items = []
    #access the array
    if objectname in data:
        items = data[objectname]
    else:
        print("Error: JSON object doesn't contain '" + objectname + "' array: " + stringwithjson, flush=True)
        return False

    #return the result
    return items

def calculate_available_tokens(token_reserved_for_response):
    #Calculates the available tokens for a request, taking into account the Tokens reserved for the response
    if token_reserved_for_response > MODEL_MAX_TOKEN:
        return 0
    else:
        return MODEL_MAX_TOKEN - token_reserved_for_response

def truncate_string_to_tokens(string, max_tokens, system_prompt):
    # Truncate string to specified number of tokens, if required.
    # max_tokens is what is reserved for the completion (max), string is the user message content, and system_prompt is the system message content.
    base_tokens = 1 #Base value
    try:
        enc = tiktoken.encoding_for_model(MODEL)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
        print("Error using \"" + MODEL + "\" as encoding model in truncation, falling back to cl100k_base.", flush=True)

    messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": string}
    ]
    num_tokens = 0
    base_tokens += 4
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        base_tokens += 4
        for key, value in message.items():
            num_tokens += len(enc.encode(value))
            base_tokens += 2
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
                base_tokens += -1
    num_tokens += 2  # every reply is primed with <im_start>assistant
    base_tokens += 4

    tokens_system = enc.encode(system_prompt)
    possible_tokens = MODEL_MAX_TOKEN - max_tokens - base_tokens
    if (num_tokens > possible_tokens):
        print("Length: " + str(num_tokens) + " tokens. Too long, truncating to " + str(possible_tokens), flush=True)
        tokens = enc.encode(string)
        truncated_tokens = tokens[:possible_tokens] # truncate the tokens if they exceed the maximum
        truncated_string = enc.decode(truncated_tokens) # decode the truncated tokens
        return truncated_string
    else:
        print("Length: " + str(num_tokens) + " tokens. Resuming.", flush=True)
        return string

def yes_or_no(string):
  # Define a boolean variable as return value
  ausgabe = True

  # Try to check the beginning of the string
  try:
    if string.startswith("Nein"):
      ausgabe = False
    else:
      # Assume "Yes" by default
      ausgabe = True
  # Catch an error if the string is not a valid parameter
  except AttributeError:
    # Do nothing and return True
    pass

  # Return the output
  return ausgabe

def search_google(query):
    # Initialise the API with your key and search engine
    service = build("customsearch", "v1", developerKey=CUSTOMSEARCH_KEY)
    cse = service.cse()
    try:
        # Make a search request to the API
        response = cse.list(q=query, cx=CX).execute()

        # Check if there are search results
        if "items" in response:
            # Extract the first three URLs from Google search results or less if there are not enough
            results = {"searchresults":[]}
            count = 0
            for item in response["items"][:min(NUMBER_GOOGLE_RESULTS, len(response["items"]))]:
                result = {
                    count: {"title":item["title"],
                    "url": item["link"],
                    "description": item["snippet"]}
                }
                results["searchresults"].append(result)
            return results
        else:
            # There were no search results for this query
            print("No search results for this query.", flush=True)
            return None
    except Exception as e:
        print(f"Error in Google API query: {e}", Flush=True)
        return None

def load_url_text(url):
    try:
        response = requests.get(url, timeout=(3, 8))
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Request timed out", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", Flush=True)
        return False
    else:
        # process response
        response = requests.get(url)
        status_code = response.status_code
        if status_code == 200:
            text = response.text
            if len(text) > 0:
                return text
            else:
                return False
        else:
            return False

def load_url_content(url):
    try:
        response = requests.get(url, timeout=(3, 8))
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Request timed out", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", Flush=True)
        return False
    else:
        # process response
        status_code = response.status_code
        if status_code == 200:
            content = response.content
            if len(content) > 0:
                return content
            else:
                return False
        else:
            return False

def replace_newlines(text):
    # loop until there are no more occurrences of four newlines
    while "\n\n\n\n" in text:
        text = text.replace("\n\n\n\n", "\n")
    return text

# Define a function that takes a URL as a parameter and extracts the content
def extract_content(url):
    # Try to send a request to the URL and catch possible exceptions
    mimetype, encoding = mimetypes.guess_type(url)
    try:
        response = requests.head(url, timeout=(3, 8))
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Request timed out", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", flush=True)
        return False
    else:
        # process response
        status_code = response.status_code

        try:
            # Check the status code of the response
            if mimetype is None:
                print("Could not determine mimetype for URL:" + url, flush=True)
                mimetype = response.headers.get("content-type")

            if status_code == 200:
                # Check the content type of the response and handle it accordingly
                if "application/pdf" in mimetype:
                    # Process PDF content
                    filecontent = load_url_content(url)
                    if filecontent: 
                        pdf = PdfReader(BytesIO(filecontent))
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text()
                            if len(text) > MAX_FILE_CONTENT:
                                break
                        text = replace_newlines(text)
                        return text[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif "text/html" in mimetype:
                    filecontent = load_url_text(url)
                    if bool(filecontent): 
                        # Process HTML content
                        # Create a BeautifulSoup object from the HTML string
                        soup = BeautifulSoup(filecontent, "html.parser")
                        # Find the body element in the HTML document
                        body = soup.body
                        # Extract the text from the body element
                        html = body.get_text()
                        html = replace_newlines(html)
                        return html[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif "text/plain" in mimetype:
                    filecontent = load_url_text(url)
                    if bool(filecontent):
                        # Process plain text content
                        filecontent = replace_newlines(filecontent)
                        return filecontent[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif any(substring in mimetype for substring in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel.sheet.macroEnabled.12"]):
                    # Process Excel content
                    filecontent = load_url_content(url)
                    if filecontent:
                        df = pd.read_csv(BytesIO(filecontent))
                        text = df.to_string()
                        text = replace_newlines(text)
                        return text[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif "text/csv" in mimetype:
                    # Process CSV content
                    filecontent = load_url_content(url)
                    if filecontent:
                        df = pd.read_csv(BytesIO(filecontent))
                        text = df.to_string()
                        text = replace_newlines(text)
                        return text[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif any(substring in mimetype for substring in ["application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.ms-powerpoint.presentation.macroEnabled.12"]):
                    # Process PowerPoint content
                    filecontent = load_url_content(url)
                    if filecontent:
                        pr = Presentation(BytesIO(filecontent))
                        text = ""
                        for slide in pr.slides:
                            for shape in slide.shapes:
                                if hasattr(shape, "text"):
                                    text += shape.text + "\n"
                                    if len(text) > MAX_FILE_CONTENT:
                                        break
                        text = replace_newlines(text)
                        return text[:MAX_FILE_CONTENT]
                    else:
                        return False
                else:
                    # The content type is not supported
                    print(f"Content type '{mimetype}' not supported", flush=True)
                    return False
            else:
                # The URL could not be found or there was another error
                print(f"Error retrieving URL: {status_code}", flush=True)
                return False
        except Exception as e:
            # There was another error
            print(f"Error retrieving URL: {e}", flush=True)
            return False

if __name__ == "__main__":
    app.run()