from bs4 import BeautifulSoup
import chardet
from datetime import datetime
from flask import Flask, request, make_response, send_from_directory
from googleapiclient.discovery import build
from io import BytesIO
import json
import markdown
import mimetypes
from num2words import num2words
import openai
import openpyxl
import os
import pandas as pd
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from pptx import Presentation
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
    PROMPT_FINAL_QUERY = "Zu der folgenden Anfrage: >>" + usertask + "<< wurde eine Google-Recherche durchgeführt, die Ergebnisse findest du im Anschluss. Bitte nutze die Ergebnisse und die Informationen aus einer tiefen Recherche in deinen Datenbanken, um die Anfrage zu lösen.\n\nHier sind die Ergebnisse der Google-Recherche:\n"
    SYSTEM_PROMPT_FINAL_QUERY = "Ich bin dein persönlicher Assistent für die Internetrecherche. Ich bekomme als Input eine Zusammenfassung einer aktuellen internen Google-Recherche. Du als Nutzer kennst und sieht diese Recherche-Informationen aus den Anfragen an mich nicht, die Recherche passiert intern, du wirst immer nur meine Antwort und deine ursprüngliche Anfrage (in spitzen Klammern, Beispiel: >>Wie spät ist es?<<) sehen können. Ich kann die Informationen aus der Google-Recherche nutzen um meine Antwort auf deine Anfrage potentiell zu verbessern. Ich antworte deiner Anfrage entsprechend potentiell ausführlich."

    ALLURLS = []

    #The user can omit the part, where this tool asks Assistant whether it requires a google search for the task
    dogooglesearch = False
    if not dogoogleoverride:
        if calculate_available_tokens(MAX_TOKENS_DECISION_TO_GOOGLE) < 1:
            print("Error, need at least 1 token for a query.", flush=True)
            final_result = "Error - need at least 1 token for a query."
        else:
            # Get current UTC time
            now = datetime.utcnow()
            # Round to the nearest minute
            now = now.replace(second=0, microsecond=0)
            # Format as a string
            now_str = now.strftime("%Y-%m-%d %H:%M")

            prompt = "Es wurde soeben folgende Anfrage gestellt: >>" + usertask + "<<. Benötigst du weitere Informationen aus einer Google-Suche, um diese Anfrage im Anschluss zu erfüllen? Bitte antworte mit \"Ja\" oder \"Nein\". Falls du keinen Zugriff auf Informationen hast die notwendig sind um die Anfrage zu beantworten (zum Beispiel falls du nach Dingen wie der aktuellen Uhrzeit oder nach aktuellen Ereignissen gefragt wirst), oder deine internen Informationen in Bezug auf die Anfrage nicht mehr aktuell sind zum aktuellen Zeitpunkt (" + now_str + " UTC), so antworte mit \"Ja\". Bei Anfragen oder Fragen die du mit dem Wissen aus deinen Datenbanken alleine ausreichend beantworten kannst (zum Beispiel bei der Frage nach der Lösung einfacher Berechnungen wie \"Wieviel ist 2*2?\", die keine zusätzlichen Daten benötigen), antworte mit \"Nein\". Würdest du weitere Recherche-Ergebnisse aus einer Google-Suche benötigen, um diese Anfrage zufriedenstellend zu beantworten, Ja oder Nein?"
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche und antworte ausschließlich nur mit \"Ja\" oder \"Nein\" um initial zu entscheiden ob eine zusätzliche Internetsuche nötig sein wird um in Folge eine bestimmte Anfrage zu beantworten. Mir ist bewusst, dass ich zur Lösung der Aufgabe/Anfrage im Verlauf des Chats bei Bedarf mit neuen relevanten Google-Suchresultaten gespeist werde. Für den Fall, dass ich keinen Zugriff auf benötigte Informationen habe die notwendig sind um die Anfrage zu beantworten (zum Beispiel falls nach Dingen wie der aktuellen Uhrzeit oder nach aktuellen Ereignissen gefragt wird), oder meine internen Informationen in Bezug auf eine Anfrage nicht mehr aktuell sind zum aktuellen Zeitpunkt (" + now_str + " UTC), so antworte ich immer mit \"Ja\", in dem Wissen, dass mir diese Informationen im Verlauf des Chats noch zur Verfügung gestellt werden. Bei Anfragen oder Fragen die ich mit dem Wissen aus meinen Datenbanken alleine ausreichend beantworten kann (zum Beispiel bei der Frage nach der Lösung einfacher Berechnungen wie \"Wieviel ist 2*2?\", die keine zusätzlichen Daten benötigen), antworte ich immer mit \"Nein\"."
            prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_DECISION_TO_GOOGLE, system_prompt)
            responsemessage = chatcompletion(system_prompt, prompt, TEMPERATURE_DECISION_TO_GOOGLE, MAX_TOKENS_DECISION_TO_GOOGLE)
            print("Does ChatGPT require a Google-Search: " + responsemessage, flush=True)
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
            prompt = "Bitte gib das JSON-Objekt als Antwort zurück, das "+ number_entries + " mit dem Schlüssel 'keywords' enthält, mit den am besten geeigneten Suchbegriffen oder -phrasen, um relevante Informationen zu folgender Anfrage mittels einer Google-Suche zu finden: >>" + usertask + "<<. Wenn die Anfrage dich auffordert nach einer bestimmten Information zu suchen, dann erstelle Suchbegriffe oder -phrasen, welche möglichst genau der Aufforderung in der Anfrage entsprechen. Berücksichtige dabei Synonyme und verwandte Begriffe und ordne die Suchbegriffe in einer Reihenfolge an, die am wahrscheinlichsten zu erfolgreichen Suchergebnissen führt. Berücksichtige, dass die Ergebnisse der "+ number_searches + " in Kombination verwendet werden sollen, also kannst du bei Bedarf nach einzelnen Informationen suchen. Nutze für die Keywords diejenige Sprache die am besten geeignet ist um relevante Suchergebnisse zu erhalten. Für spezifische Suchen verwende Google-Filter wie \"site:\", besonders wenn z.B. nach Inhalten von speziellen Seiten gesucht wird, wie Twitter, in dem Fall suche beispielsweise nach: \"<suchbegriff> site:twitter.com\". Nutze gegebenenfalls auch andere Suchfilter wo immer das helfen kann, zum Beispiel: \"<suchbegriff> filetype:xlsx\", wenn eine Suche nach speziellen Formaten hilfreich ist (hier: Excel-Dateien). Oder wo nötig nutze auch den \"site:\"-Filter um Ergebnisse aus einem bestimmten Land zu finden, zum Beispiel: \"<suchbegriff> site:.de\" um nur Inhalte von Deutschen Seiten zu finden."
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche, und das Format meiner Antworten ist immer ein JSON-Objekt mit dem Schlüssel 'keywords', das zur Anfrage passende Google-Suchbegriffe oder -phrasen enthält. Ich unterstütze Google-Suchfilter wie site:, filetype:, allintext:, inurl:, link:, related: und cache: sowie Suchoperatoren wie Anführungszeichen, und die Filter after: / before: um Suchergebnisse aus bestimmten Zeiträumen zu finden. Ich berücksichtige besonders spezifische Benutzer-Eingaben in Anfragen. Besonders wenn nach spezifischen Daten oder Formaten verlangt wird, dann passe ich meine auszugebenden Suchbegriffe im JSON-Objekt der Anfrage möglichst genau an. Beispiel-Anwort zu einer Beispiel-Anfrage \"Wie spät ist es?\": {\"keywords\": [\"aktuelle Uhrzeit\",\"Uhrzeit jetzt\",\"Atomuhr genau\"]}."
            prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_CREATE_SEARCHTERMS, system_prompt)
            responsemessage = chatcompletion(system_prompt, prompt, TEMPERATURE_CREATE_SEARCHTERMS, MAX_TOKENS_CREATE_SEARCHTERMS)

            keywords = [False]

            #Attempt to extract the JSON object from the response
            jsonobject = extract_json(responsemessage, "keywords")

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
                print("Not all entries in the keyword-array are strings. Cannot use the results: " + json.dumps(keywords), flush=True)
            searchresults = []
            zaehler = 0
            if ergebnis:
                for keyword in keywords:
                    search_google_result = search_google(keyword)
                    #print("Search Google result contains the following data: " + json.dumps(search_google_result), flush=True) #debug
                    google_result = None
                    if search_google_result is None: #Skip if nothing was found or there was an error in search
                        continue
                    for search_result in search_google_result['searchresults']:
                        for key in search_result:
                            if not google_result is None:
                                google_result.append(search_result[key]['url'])
                            else:
                                google_result = [search_result[key]['url']]
                    # Let ChatGPT pick the most promising
                    gpturls = False
                    if calculate_available_tokens(MAX_TOKENS_SELECT_SEARCHES_LENGTH) < 1:
                        print("Error, need at least 1 token for a query.", flush=True)
                        has_result = False
                    else:
                        prompt = "Bitte wähle die Reihenfolge der vielverprechendsten Google-Suchen aus der folgenden Liste aus die für dich zur Beantwortung der Aufgabe >>" + usertask + "<< am nützlichsten sein könnten, und gebe sie als JSON-Objekt mit dem Objekt \"weighting\", das index, und einen \"weight\" Wert enthält zurück, der die geschätzte Gewichtung der Relevanz angibt; In Summe soll das den Wert 1 ergeben. Ergebnisse die für die Aufgabe keine Relevanz versprechen, kannst du aus dem resultierenden JSON-Objekt entfernen: \n\n" + json.dumps(search_google_result) + "\n\nBeispiel-Antwort: {\"weighting\": {\"3\":0.6,\"0\":0.2,\"1\":0.1,\"2\":0.1}}. Schreibe keine Begründung, sondern antworte nur mit dem JSON-Objekt."
                        system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche und antworte immer mit JSON-Objekten mit dem Key \"weighting\". Beispiel: {\"weighting\": {\"2\":0.6,\"0\":0.3,\"1\":0.1}}"
                        #debug_output("Page content - untruncated", prompt, system_prompt, 'w') #----Debug Output
                        prompt = truncate_string_to_tokens(prompt, MAX_TOKENS_SELECT_SEARCHES_LENGTH, system_prompt)
                        #debug_output("Page content", prompt, system_prompt, 'a') #----Debug Output
                        responsemessage = chatcompletion(system_prompt, prompt, TEMPERATURE_SELECT_SEARCHES, MAX_TOKENS_SELECT_SEARCHES_LENGTH)
                        weighting = extract_json(responsemessage, "weighting")

                        print("weighting content: " + json.dumps(weighting), flush=True)
                        print("search_google_result content: " + json.dumps(search_google_result), flush=True)
                        if weighting:
                            # the function returned a dictionary, re-sort
                            sorted_weighting = sorted(weighting.items(), key=lambda x: x[1], reverse=True)
                            gpturls = {}
                            for index, _ in sorted_weighting:
                                if int(index) > len(search_google_result['searchresults'])-1:
                                    break
                                gpturls[index] = search_google_result['searchresults'][int(index)][index]['url']
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
                            if dlfile:
                                responsemessage = dlfile

                                if calculate_available_tokens(MAX_TOKENS_SUMMARIZE_RESULT) < 1:
                                    print("Error, need at least 1 token for a query.", flush=True)
                                    has_result = False
                                else:
                                    prompt = "Es wurde folgende Anfrage gestellt: >>" + usertask + "<<. Im Folgenden findest du den Inhalt einer Seite aus den Ergebnissen einer Google-Suche zu dieser Anfrage, bitte fasse das Wesentliche zusammen um mit dem Resultat die Anfrage später bestmöglich beantworten zu können, stelle sicher, dass du sämtliche relevanten Spezifika, die in deinen internen Datenbanken sonst nicht vorhanden sind in der Zusammenfassung erwähnst. Erwähne auch die URL oder Webseite wenn sie relevant ist.\n\nVon URL: " +  URL + "\nInhalt:\n" + responsemessage
                                    system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
                                    #debug_output("Page content - untruncated", prompt, system_prompt, 'w') #----Debug Output

                                    weighting_value = False
                                    if gpturls:
                                        if URL in gpturls.values():
                                            # Find the corresponding key in the gpturls dictionary
                                            key = list(gpturls.keys())[list(gpturls.values()).index(URL)]
                                            # Get the weighting value for the key
                                            weighting_value = float(weighting[key])

                                    max_tokens_completion_summarize = MAX_TOKENS_SUMMARIZE_RESULT

                                    #Check if there's a weighting value for this URL
                                    if weighting_value and weighting_value > 0 and len(gpturls) > 0:
                                        max_tokens_completion_summarize = int(MAX_TOKENS_SUMMARIZE_RESULT * len(gpturls) * weighting_value)
                                        print("Weighting applied: " + str(weighting_value) + " weight => " + str(max_tokens_completion_summarize) + " tokens", flush=True)
                                        if max_tokens_completion_summarize < 1:
                                            max_tokens_completion_summarize = 1 # max_tokens may not be 0

                                    #Calculate if there are enough tokens left for the current max_tokens_completion_summarize value, otherwise use less:
                                    text_summary = "\nZusammenfassung der Ergebnisse von \"{}\": "
                                    formatted_text_summary = text_summary.format(URL)

                                    #How many tokens are already used up, take into account the "text_summary" that will be submitted as opening to the summary:
                                    test_finalquery = PROMPT_FINAL_QUERY
                                    for text in searchresults:
                                        if len(text) > 0:
                                            test_finalquery += text
                                    sum_results = calculate_tokens(test_finalquery+formatted_text_summary, SYSTEM_PROMPT_FINAL_QUERY)
                                    if MODEL_MAX_TOKEN < sum_results + max_tokens_completion_summarize:
                                        print("Decreasing tokens for summary for: " + URL + ", not enough tokens left: " + str(MODEL_MAX_TOKEN - sum_results + ", requested were " + str(max_tokens_completion_summarize)), flush=True)
                                        max_tokens_completion_summarize = MODEL_MAX_TOKEN - sum_results #not enough tokens left for the original number of tokens in max_tokens_completion_summarize, use less
                                    if max_tokens_completion_summarize < 1:
                                        print("Error - no tokens left for summary of URL content: " + URL, flush=True)
                                    else:
                                        prompt = truncate_string_to_tokens(prompt, max_tokens_completion_summarize, system_prompt)

                                        result_summary = chatcompletion(system_prompt, prompt, TEMPERATURE_SUMMARIZE_RESULT, max_tokens_completion_summarize)
                                        #debug_output("Page content", prompt, system_prompt, 'a') #----Debug Output
                                        #debug_output("Page content - result", result_summary, system_prompt, 'a')
                                        searchresults.append(formatted_text_summary + result_summary)
                                        has_result = True
                            else:
                                responsemessage = "Error"
                                print("Error summarizing URL content: " + URL, flush=True)
            else:
                #no search terms
                has_result = False
                print("No search terms.", flush=True)

            finalquery = PROMPT_FINAL_QUERY
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
                    #debug_output("final query - untruncated", finalquery, system_prompt, 'w') #----Debug Output
                    finalquery = truncate_string_to_tokens(finalquery, MAX_TOKENS_FINAL_RESULT, SYSTEM_PROMPT_FINAL_QUERY)
                    final_result = chatcompletion(SYSTEM_PROMPT_FINAL_QUERY, finalquery, TEMPERATURE_FINAL_RESULT, MAX_TOKENS_FINAL_RESULT)
                    #final_result = escape_result(final_result)
                    #debug_output("final query", finalquery, system_prompt, 'a') #----Debug Output
                    has_result = True
            else:
                has_result = False
                print("No search results.", flush=True)
    else:
        has_result = False
        print("GPT thinks, no search is required. Response to 'Is search required?' was: " + responsemessage, flush=True)

    if not has_result:
        print("Nothing found, making a regular query.", flush=True)
        #Make a regular query
        if calculate_available_tokens(MAX_TOKENS_FINAL_RESULT) < 1:
            print("Error, need at least 1 token for a query.", flush=True)
            final_result = "Error - need at least 1 token for a query."
        else:
            system_prompt = "Ich bin dein persönlicher Assistent für die Internetrecherche"
            usertask = truncate_string_to_tokens(usertask, MAX_TOKENS_FINAL_RESULT, system_prompt)
            final_result = chatcompletion(system_prompt, usertask, TEMPERATURE_FINAL_RESULT, MAX_TOKENS_FINAL_RESULT)
            #final_result = escape_result(final_result)

    #html = markdown.markdown(responsemessage)
    writefile(100, final_result, task_id)

def chatcompletion(system_prompt, prompt, completiontemperature, completionmaxtokens):
    response = openai.ChatCompletion.create(
    model=MODEL,
    temperature=completiontemperature,
    max_tokens=completionmaxtokens,
    messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    )
    print("Query completed. Usage = prompt_tokens: " + str(response['usage']['prompt_tokens']) + ", completion_tokens: " + str(response['usage']['completion_tokens']) + ", total_tokens: " + str(response['usage']['total_tokens']) + "\n\nPrompt:\n" + prompt, flush=True)
    return response['choices'][0]['message']['content']

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


def calculate_tokens(string, system_prompt):
    # Calculate tokens. Set system_prompt to False to only count a single string, otherwise the entire message will be counted.
    try:
        enc = tiktoken.encoding_for_model(MODEL)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
        print("Error using \"" + MODEL + "\" as encoding model in truncation, falling back to cl100k_base.", flush=True)

    if system_prompt:
        messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": string}
        ]
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += len(enc.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        return len(enc.encode(string))

def truncate_string_to_tokens(string, max_tokens, system_prompt):
    # Truncate string to specified number of tokens, if required.
    # max_tokens is what is reserved for the completion (max), string is the user message content, and system_prompt is the system message content.
    base_tokens = 10 #Base value, I noticed that the max of 4096 is off by 1 in the gpt-3.5 API
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
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(enc.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant

    system_tokens = len(enc.encode(system_prompt))
    possible_tokens = MODEL_MAX_TOKEN - max_tokens - system_tokens - base_tokens
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
                    str(count): {"title": item["title"],
                    "url": item["link"],
                    "description": item["snippet"]}
                }
                results["searchresults"].append(result)
                count += 1 # increment count for each result
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
        with requests.get(url, timeout=(3, 8), allow_redirects=True) as response:
            response.raise_for_status()
            # process response
            status_code = response.status_code
            if status_code == 200:
                text = response.text
                if len(text) > 0:
                    return text
                else:
                    return False
            else:
                return False
    except requests.exceptions.Timeout:
        print("Request timed out", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", flush=True)
        return False

def load_url_content(url):
    try:
        with requests.get(url, timeout=(3, 8), allow_redirects=True) as response:
            response.raise_for_status()
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
    except requests.exceptions.Timeout:
        print("Request timed out", flush=True)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", flush=True)
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
        with requests.head(url, timeout=(3, 8), allow_redirects=True) as response:
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
                    with requests.get(url, stream=True, allow_redirects=True) as response:
                        response.raise_for_status()
                        with BytesIO() as filecontent:
                            for chunk in response.iter_content(chunk_size=8192):
                                filecontent.write(chunk)
                            filecontent.seek(0)
                            with BytesIO() as outfp:
                                extract_text_to_fp(filecontent, outfp, laparams=LAParams())
                                text = outfp.getvalue().decode('utf-8')
                                text = replace_newlines(text)
                                print("downloaded pdf file: " + text[:300], flush=True) #debug
                                return text[:MAX_FILE_CONTENT]
                elif "text/html" in mimetype:
                    filecontent = load_url_text(url)
                    if filecontent: 
                        # Process HTML content
                        # Create a BeautifulSoup object from the HTML string
                        soup = BeautifulSoup(filecontent, "html.parser")
                        html = process_html_content(soup)
                        print("downloaded html file: " + html[:300], flush=True) #debug
                        return html
                    else:
                        return False
                elif "text/plain" in mimetype:
                    filecontent = load_url_text(url)
                    if filecontent:
                        # Process plain text content
                        filecontent = replace_newlines(filecontent)
                        print("downloaded plaintext file: " + filecontent[:300], flush=True) #debug
                        return filecontent[:MAX_FILE_CONTENT]
                    else:
                        return False
                elif any(substring in mimetype for substring in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel.sheet.macroEnabled.12"]):
                    # Process Excel content
                    filecontent = load_url_content(url)
                    if filecontent:
                        text = process_excel_content(filecontent)
                        if text:
                            print("downloaded excel file: " + text[:300], flush=True) #debug
                            return text
                        else:
                            return False
                    else:
                        return False
                elif "text/csv" in mimetype:
                    # Process CSV content
                    filecontent = load_url_content(url)
                    if filecontent:
                        text = process_csv_content(filecontent)
                        if text:
                            print("downloaded csv file: " + text[:300], flush=True) #debug
                            return text
                        else:
                            return False
                    else:
                        return False
                elif any(substring in mimetype for substring in ["application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.ms-powerpoint.presentation.macroEnabled.12"]):
                    # Process PowerPoint content
                    filecontent = load_url_content(url)
                    if filecontent:
                        text = process_ppt_content(filecontent)
                        if text:
                            print("downloaded powerpoint file: " + text[:300], flush=True) #debug
                            return text
                        else:
                            return False
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

def process_excel_content(filecontent):
    try:
        # Detect the encoding of the file content using chardet
        with BytesIO(filecontent) as f:
            df = pd.read_excel(f)
            text = df.to_string()
            text = replace_newlines(text)
            return text[:MAX_FILE_CONTENT]
    except Exception as e:
        print(f"Error processing Excel content: {e}", flush=True)
        return False

def process_csv_content(filecontent):
    try:
        # Detect the encoding of the file content using chardet
        detected_encoding = chardet.detect(filecontent)['encoding']

        with BytesIO(filecontent) as f:
            df = pd.read_csv(f, encoding=detected_encoding)
            text = df.to_string()
            text = replace_newlines(text)
            return text[:MAX_FILE_CONTENT]
    except Exception as e:
        print(f"Error processing CSV content: {e}", flush=True)
        return False

def process_ppt_content(filecontent):
    try:
        with BytesIO(filecontent) as f:
            pr = Presentation(f)
            text = ""
            for slide in pr.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
                        if len(text) > MAX_FILE_CONTENT:
                            break
            text = replace_newlines(text)
            return text[:MAX_FILE_CONTENT]
    except Exception as e:
        print(f"Error processing PowerPoint content: {e}", flush=True)
        return False

def process_html_content(soup):
    # Find the body element in the HTML document
    body = soup.body
    # Extract the text from the body element
    html = body.get_text()
    html = replace_newlines(html)
    return html[:MAX_FILE_CONTENT]

if __name__ == "__main__":
    app.run()