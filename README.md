# GoingLLM
I want to make Assistant (the ChatGPT model) be able to do Google searches if it's required to solve a task.

## Preconditions:

• You need a Google Custom Search JSON API - API key (https://developers.google.com/custom-search/v1/overview?hl=en)  
• You also need an OpenAI account with subsequent API key (https://platform.openai.com/account/api-keys)  
• And you need a Heroku "Basic" Dynos account (https://dashboard.heroku.com/new-app) to create a new app  
• You can then create a Github repository with all the files, and connect your Heroku app with it (https://dashboard.heroku.com/apps/YOURAPPNAME/deploy/github)

-----
## How it works:

It shows you an input and output window, a send button and a progress bar at https://YOURAPPNAME.herokuapp.com/ once you've set up the API keys and the Config Vars and successfully deployed it.
The tool takes a regular chat command, and submits it to the official ChatGPT-API.  
It will prompt the ChatGPT API to decide whether or not Google searches will be required to create a response. (If you add 'Perform an internet search' to your prompt, it will most likely do it every time.)  
Then if a Google search is required, the tool will generate further prompts to the ChatGPT API to ask it to create appropriate keywords for the research.  
Then it will use the Google Custom Search API to perform these searches, download the files temporarily in plaintext, and ask the ChatGPT API to extract the most important data from the results.  
Finally, it will send the collected result data together with the original prompt or question back to the ChatGPT API and show you the resulting answer.  
The tool will now prompt the ChatGPT API to weight the Google results by showing it the URL, title and summary, before it downloads it. So that the bot can decide which results it thinks will be most useful to serve the initial request.  
You now have the option to check the "Always Google" checkbox/override, so the tool will skip the initial question to ChatGPT, whether it thinks that a google research will be useful to serve the initial request, and will do a Google search in any case.

-----
## Setup:

The python script is meant to be deployed at Heroku. I used a "Basic Dynos" account.
It is protected with Basic Auth and will be available at https://YOURAPPNAME.herokuapp.com/ when you deploy it at Heroku.  
➔ You MUST edit the Procfile and put in your own app's name in place of "goingllm" and rename the script "goingllm.py" accordingly: If your app is "Myapp", then replace goingllm with Myapp in Procfile, and also rename goingllm.py to Myapp.py.  
All the other files can remain unchanged. All other settings and API keys are configured in the Heroku Config Vars.

Note that the internal prompts to the ChatGPT API are written in German, but it shouldn't be hard to ask it to answer in English or any other language it understands, anyways.  
There is lots of debug output in the logs - you don't have to install Heroku CLI, just go to https://dashboard.heroku.com/apps/YOURAPPNAME/logs to view them. You can also deploy, start and stop the app on the Heroku Dashboard website.

### Config Vars

At the Heroku app's settings you will need to set all the following **Config Vars**, including the API keys and the ChatGPT API variables at https://dashboard.heroku.com/apps/YOURAPPNAME/settings with these exact names:

NUMBER_OF_KEYWORDS  
3  
[This number will be used to instruct the ChatGPT API how many keywords it should create.]


AUTH_PASS  
[Your Basic Auth password, for a quick-and-dirty authentication implementation.]

AUTH_UNAME  
[Your Basic Auth username.]

CUSTOMSEARCHKEY  
[Your Google Custom Search API key.]

cx  
[Your Google Custom Search API 'CX' key.]

BODY_MAX_LENGTH  
15000  
[Absolute max length of the input that the tool will allow.]

FINALRESULT_MAX_TOKEN_LENGTH  
2380  
[The token length for the final result for ChatGPT. Note that in total (prompt+answer) you may not exceed 4096 tokens or the request will fail, and the request will easily already consume over 1200 tokens, often more.]

MAX_FILE_CONTENT  
8200  
[How many bytes will be downloaded from the Google search results, this is AFTER stripping all html tags, duplicate linebreaks and headers.]

max_tokens_create_searchterms  
100  
[The ChatGPT token length for the creation of the search keywords.]

max_tokens_decision_to_google  
3  
[The ChatGPT token length for the decision whether or not a Google search should be performed.]

model  
gpt-3.5-turbo  
[The OpenAI model, here it's gpt-3.5-turbo.]

model_max_token  
4096  
[The max number of tokens that the selected model allows.]

NUMBER_GOOGLE_RESULTS  
3  
[The number of Google results for each keyword that will be temporarily downloaded.]

SECRETKEY  
[Your secret OpenAI key.]

SUMMARIZE_MAX_TOKEN_LENGTH  
300  
[The ChatGPT token length for summarizing the individual Google search results.]

SUMMARIZE_MIN_TOKEN_LENGTH  
100  
[The minimum ChatGPT token length for summarizing the individual Google search results. If this is too low, GPT will create unfinished sentences, leading to issues in the final result.]

SELECT_SEARCHES_MAX_TOKEN_LENGTH  
256  
[The ChatGPT token length for selecting the most promising search results with weighting]

temperature_select_searches  
0.4

temperature_create_searchterms  
0.36

temperature_decision_to_google  
0.2

temperature_final_result  
0.3

temperature_summarize_result  
0.2

[The temperature values for the various ChatGPT prompts. Lower means more factual, higher means more creative. Between 0 and 1. OpenAI recommends 0.2 or higher.]  
All token maximums determine how many tokens will be reserved for the response. The tool will truncate the input for each request to the OpenAI API, to make sure answer+response never exceed "model_max_token" tokens in sum (4096 for the ChatGPT API).  
The most relevant numbers here are NUMBER_GOOGLE_RESULTS, MAX_FILE_CONTENT and NUMBER_OF_KEYWORDS, because this will have impact on the execution time of the script.

Note that the API requests are not free. Use this at your own risk. If you sign up for a basic, free Google Custom Search API key, you can do 100 free searches/day at the time of writing.  
If you are using this for a public API, you might consider adding aufgabe = bleach.clean(body) and import bleach, or something similar, to sanitize input, at the top of the python script.

The token-calculation could be off in future models of gpt-3.5-turbo (calculate_tokens, truncate_string_to_tokens), I did not include the suggested limitation to the exact version of the model "gpt-3.5-turbo-0301" as suggested in https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb, because obviously "gpt-3.5-turbo" (the latest version) would not work then.

-----
## To Do:

Usability, Frontend, New Features:  
• Allow continuing conversations instead of single prompts only: summarize and process chat history.  
• Provide feedback to users, such as current search terms, URLs, and status.  
• Allow Shift+Enter.  
• Adjust the height for tablets.  
• Implement ChatML if necessary.  
• Avoid encoded unicode characters in the final output.  
• Sources!

Backend and enhancing the Backend for a More Intelligent Tool:  
• Improve error handling for edge-cases and balance all the variables in settings.  
• Strip unnecessary data/whitespace/formatting from the temporarily downloaded files.  
• Refine the search flow to make it more intelligent and responsive to user queries.  
• Allow GPT to determine if it needs more Google results and if it wants to adjust the keywords.  
• Explain to GPT what the tool is doing and how it works.  
• Provide source information, i.e. URLs in the final query.

Testing, Bugs and Error Handling:  
• Test the tool's handling of Powerpoint and plaintext files.  
• Implement client-side error handling if the .json file does not exist.  
• Avoid too short remaining max_token values for the summary-generation, because GPT tends to finish unfinished sentences in the prompt.


I have heavily used ChatGPT and Bing Chat to create this program in less than a day. What a time to be alive!