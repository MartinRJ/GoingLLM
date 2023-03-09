from bs4 import BeautifulSoup
from flask import Flask, request, make_response, send_from_directory
from googleapiclient.discovery import build
from io import BytesIO
import json
import markdown
import mimetypes
import openai
import os
import pandas as pd
from pptx import Presentation
from PyPDF2 import PdfReader
import requests
from text_to_num import text2num
import threading
import time
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
ANZAHL_EINTRAEGE_AUSGESCHRIEBEN = os.getenv('ANZAHL_EINTRAEGE')
TEMPERATURE_FINAL_RESULT = float(os.getenv('temperature_final_result'))
MAX_TOKENS_FINAL_RESULT = int(os.getenv('FINALRESULT_MAX_TOKEN_LENGTH'))

#BASIC AUTHENTICATION
AUTH_UNAME = os.getenv('AUTH_UNAME')
AUTH_PASS = os.getenv('AUTH_PASS')
MODEL = os.getenv('model')
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
        aufgabe = body
    except Exception as e:
        print("There was an error with the input.", flush=True)
        return f'Error extracting body: {e}', 400

    dogoogleoverride = False
    always_google = request.headers.get('X-Always-Google')
    if always_google and always_google.lower() == 'true':
        dogoogleoverride = True

    #create new JSON output file with status 'started' and send a 200 response, and start the actual tasks.
    task_id = str(uuid.uuid4())
    threading.Thread(target=response_task, args=(body, task_id, dogoogleoverride)).start()
    writefile("{\"task_id\":\"" + task_id + "\",\"progress\":0}", task_id)
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

def writefile(json_object, task_id):
    # create a 'searches' directory if it does not exist
    if not os.path.exists('searches'):
        os.makedirs('searches')
    # set the file path
    file_path = f'searches/{task_id}.json'
    # open file in write mode
    print("Writing to /" + file_path, flush=True)
    with open(file_path, 'w') as f:
        # write JSON data to file
        json.dump(json_object, f)

def response_task(aufgabe, task_id, dogoogleoverride):
    if "<<" in aufgabe or ">>" in aufgabe:
        aufgabe = aufgabe.replace("<<", "»").replace(">>", "«")

    aufgabe = json.dumps(aufgabe)
    #The user can omit the part, where this tool asks Assistant whether it requires a google search for the task
    dogooglesearch = False
    if not dogoogleoverride:
        response = openai.ChatCompletion.create(
        model=MODEL,
        temperature=TEMPERATURE_DECISION_TO_GOOGLE,
        max_tokens=MAX_TOKENS_DECISION_TO_GOOGLE,
        messages=[
                {"role": "system", "content": "Ich bin dein persönlicher Assistent für die Internetrecherche und antworte nur mit 'Ja.' oder 'Nein.'"},
                {"role": "user", "content": "Es wurde folgende Anfrage gestellt: >>" + aufgabe + "<<. Benötigst du weitere Informationen aus einer Google-Suche, um diese Anfrage zu erfüllen? Bitte antworte mit 'Ja.' oder 'Nein.'."}
            ]
        )
        responsemessage = response['choices'][0]['message']['content']
        dogooglesearch = yes_or_no(responsemessage)
    else:
        dogooglesearch = True

    has_result = False
    if dogooglesearch:
        response = openai.ChatCompletion.create(
        model=MODEL,
        temperature=TEMPERATURE_CREATE_SEARCHTERMS,
        max_tokens=MAX_TOKENS_CREATE_SEARCHTERMS,
        messages=[
                {"role": "system", "content": "Ich bin dein persönlicher Assistent für die Internetrecherche"},
                {"role": "user", "content": "Bitte gib das JSON-Objekt als Antwort zurück, das "+ ANZAHL_EINTRAEGE_AUSGESCHRIEBEN + " Einträge mit dem Schlüssel 'keywords' enthält, mit den am besten geeigneten Suchbegriffen oder -phrasen, um relevante Informationen zu folgendem Thema mittels einer Google-Suche zu finden: >>" + aufgabe + "<<. Berücksichtige dabei Synonyme und verwandte Begriffe und ordne die Suchbegriffe in einer Reihenfolge an, die am wahrscheinlichsten zu erfolgreichen Suchergebnissen führt. Berücksichtige, dass die Ergebnisse der fünf Suchen in Kombination verwendet werden sollen, also kannst du bei Bedarf nach einzelnen Informationen suchen."}
            ]
        )
        keywords = [False]

        #Attempt to extract the JSON object from the response
        jsonobject = extract_json(response['choices'][0]['message']['content'])

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
        anzahl_eintraege = text2num(ANZAHL_EINTRAEGE_AUSGESCHRIEBEN,"de")
        if not ergebnis == False:
            for keyword in keywords:
                result = search_google(keyword)
                # Check if the result is None
                if result is None:
                    # The function has returned an error
                    print("There was an error in the search.", flush=True)
                else:
                    # The function has returned a list of URLs
                    for URL in result:
                        percent = str(((zaehler / (NUMBER_GOOGLE_RESULTS * anzahl_eintraege)) * 100));
                        writefile("{\"task_id\":\"" + task_id + "\",\"progress\":" + percent + "}", task_id)
                        zaehler = zaehler + 1
                        print("Here are the URLs: " + URL, flush=True)
                        dlfile = extract_content(URL)
                        if not dlfile == False:
                            responsemessage = dlfile

                            response = openai.ChatCompletion.create(
                            model=MODEL,
                            temperature=TEMPERATURE_SUMMARIZE_RESULT,
                            max_tokens=MAX_TOKENS_SUMMARIZE_RESULT,
                            messages=[
                                    {"role": "system", "content": "Ich bin dein persönlicher Assistent für die Internetrecherche"},
                                    {"role": "user", "content": "Es wurde folgende Anfrage gestellt: >>" + aufgabe + "<<. Im Folgenden findest du den Inhalt einer Seite aus den Google-Suchergebnissen zu dieser Anfrage, bitte fasse das Wesentliche zusammen um mit dem Resultat die Anfrage bestmöglich beantworten zu können:\n\n" + json.dumps(responsemessage)}
                                ]
                            )
                            result_summary = response['choices'][0]['message']['content']
                            searchresults.append(result_summary)
                            has_result = True
                        else:
                            responsemessage = "Error"
                            print("Error summarizing URL content: " + URL, flush=True)
        else:
            #no search terms
            has_result = False
            print("No search terms.", flush=True)

        finalquery = "Zu der folgenden Anfrage: >>" + aufgabe + "<< wurde eine Google-Recherche durchgeführt, die Ergebnisse findest du im Anschluss. Bitte nutze die Ergebnisse und die Informationen aus einer tiefen Recherche in deinen Datenbanken, um die Anfrage zu lösen.\n\nHier sind die Ergebnisse der Google-Recherche:\n"
        has_text = False
        for text in searchresults:
            if len(text) > 0:
                has_text = True
                finalquery += json.dumps(text)

        if has_text:
            print("Final result found, making final query.", flush=True)
            response = openai.ChatCompletion.create(
            model=MODEL,
            temperature=TEMPERATURE_FINAL_RESULT,
            max_tokens=MAX_TOKENS_FINAL_RESULT,
            messages=[
                    {"role": "system", "content": "Ich bin dein persönlicher Assistent für die Internetrecherche"},
                    {"role": "user", "content": finalquery}
                ]
            )
            final_result = response['choices'][0]['message']['content']
            final_result = escape_result(final_result)
            print("Final query completed.", flush=True)
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
        response = openai.ChatCompletion.create(
        model=MODEL,
        temperature=TEMPERATURE_FINAL_RESULT,
        max_tokens=MAX_TOKENS_FINAL_RESULT,
        messages=[
                {"role": "system", "content": "Ich bin dein persönlicher Assistent für die Internetrecherche"},
                {"role": "user", "content": aufgabe}
            ]
        )
        final_result = response['choices'][0]['message']['content']
        final_result = escape_result(final_result)

    #html = markdown.markdown(responsemessage)
    writefile("{\"task_id\":\"" + task_id + "\",\"progress\":100,\"answer\":\"" + final_result + "\"}", task_id)
    #return markdown.markdown(htmlstart + final_result)

def escape_result(final_result):
    print("Final result (unescaped): " + final_result, flush=True)
    final_result = final_result.replace('"', '＂')
    return final_result

def extract_json(stringwithjson):
    #find the JSON object
    start = stringwithjson.find('{')
    end = stringwithjson.find('}') + 1
    if start == -1 or end == 0:
        print("Error: JSON object not found", flush=True)
        return False

    json_string = stringwithjson[start:end]

    #parse the JSON object
    try:
        data = json.loads(json_string)
    except ValueError as e:
        print("Error: Malformed JSON object", flush=True)
        return False

    keywords = []
    #access the "keywords" array
    if "keywords" in data:
        keywords = data["keywords"]
    else:
        print("Error: JSON object doesn't contain 'keywords' array", flush=True)
        return False

    #return the result
    return keywords

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

    # Make a search request to the API
    response = cse.list(q=query, cx=CX).execute()

    # Check if there are search results
    if 'items' in response:
        # Extract the first three URLs from Google search results or less if there are not enough
        urls = [item['link'] for item in response['items'][:min(NUMBER_GOOGLE_RESULTS, len(response['items']))]]
        return urls
    else:
        # There were no search results for this query
        print("No search results for this query.", flush=True)
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
                    Process #CSV content
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