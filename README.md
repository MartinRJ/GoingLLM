# GoingLLM
I want to make Assistant (the ChatGPT model) be able to do Google searches if it's required to solve a task.


Preconditions:
• You need a Google Custom Search JSON API - API key (https://developers.google.com/custom-search/v1/overview?hl=en)
• You also need an OpenAI account with subsequent API key (https://platform.openai.com/account/api-keys)
• And you need a Heroku "Basic" Dynos account (https://dashboard.heroku.com/new-app) to create a new app
• You can then create a Github repository with all the files, and connect your Heroku app with it (https://dashboard.heroku.com/apps/YOURAPPNAME/deploy/github)

-----
How it works:
It shows you an input and output window, a send button and a progress bar at https://YOURAPPNAME.herokuapp.com/ once you've set up the API keys and the Config Vars and successfully deployed it.
The tool takes a regular chat command, and submits it to the official ChatGPT-API.
It will prompt the ChatGPT API to decide whether or not Google searches will be required to create a response. (If you add 'Perform an internet search' to your prompt, it will most likely do it every time.)
Then if a Google search is required, the tool will generate further prompts to the ChatGPT API to ask it to create appropriate keywords for the research.
Then it will use the Google Custom Search API to perform these searches, download the files temporarily in plaintext, and ask the ChatGPT API to extract the most important data from the results.
Finally, it will send the collected result data together with the original prompt or question back to the ChatGPT API and show you the resulting answer.

-----
The python script is meant to be deployed at Heroku. I used a "Basic Dynos" account.
It is protected with Basic Auth and will be available at https://YOURAPPNAME.herokuapp.com/ when you deploy it at Heroku.

➔ You MUST edit the Procfile and put in your own app's name in place of "goingllm" and rename the script "goingllm.py" accordingly: If your app is "Myapp", then replace goingllm with Myapp in Procfile, and also rename goingllm.py to Myapp.py.

All the other files can remain unchanged. All other settings and API keys are configured in the Heroku Config Vars.


Note that the internal prompts to the ChatGPT API are written in German, but it shouldn't be hard to ask it to answer in English or any other language it understands, anyways.

There is lots of debug output in the logs - you don't have to install Heroku CLI, just go to https://dashboard.heroku.com/apps/YOURAPPNAME/logs to view them. You can also deploy, start and stop the app on the Heroku Dashboard website.

At the Heroku app's settings you will need to set all the following Config Vars, including the API keys and the ChatGPT API variables at https://dashboard.heroku.com/apps/YOURAPPNAME/settings with these exact names:

NUMBER_OF_KEYWORDS
4
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
20000
[Absolute max length of the input that the tool will allow.]

FINALRESULT_MAX_TOKEN_LENGTH
2150
[The token length for the final result for ChatGPT. Note that in total (prompt+answer) you may not exceed 4096 tokens or the request will fail, and the request will easily already consume over 1200 tokens, often more.]

MAX_FILE_CONTENT
12000
[How many bytes will be downloaded from the Google search results, this is AFTER stripping all html tags and duplicate linebreaks and headers.]

max_tokens_create_searchterms
300
[The ChatGPT token length for the creation of the search keywords.]

max_tokens_decision_to_google
16
[The ChatGPT token length for the decision whether or not a Google search should be performed.]

model
gpt-3.5-turbo
[The OpenAI model, here it's gpt-3.5-turbo.]

model_max_token
4096
[The max number of tokens that the selected model allows.]

NUMBER_GOOGLE_RESULTS
2
[The number of Google results for each keyword that will be temporarily downloaded.]

SECRETKEY
[Your secret OpenAI key.]

SUMMARIZE_MAX_TOKEN_LENGTH
300
[The ChatGPT token length for summarizing the individual Google search results.]

temperature_create_searchterms
0.36

temperature_decision_to_google
0.2

temperature_final_result
0.3

temperature_summarize_result
0.2
[The temperature values for the various ChatGPT prompts. Lower means more factual, higher means more creative. Between 0 and 1. OpenAI recommends 0.2 or higher.]

All token maximums determine how many tokens will be reserved for the response. The tool will truncate the input for each request to the OpenAI API, to make sure answer+response never exceed "model_max_token" tokens in sum (4096 for the ChatGPT API). The most relevant numbers here are NUMBER_GOOGLE_RESULTS, MAX_FILE_CONTENT and NUMBER_OF_KEYWORDS, because this will have impact on the execution time of the script.

Note that the API requests are not free. Use this at your own risk. If you sign up for a basic, free Google Custom Search API key, you can do 100 free searches/day at the time of writing.

If you are using this for a public API, you might consider adding aufgabe = bleach.clean(body) and import bleach, or something similar, to sanitize input, at the top of the python script.

-----
To Do:
More and thorougher error handling, taking more edge-cases into account.
Better balancing of all the variables in settings.
Possibly more stripping of unnecessary data/whitespace/formatting from the temporarily downloaded files.
Implementing formatting (ChatML), but so far I haven't seen any attempts of the model to create ChatML. It could be as easy as adding "markdown.markdown(responsemessage)" before writing out the response.
The option to continue a conversation, as right now these are always only single prompts.
Also needed is a check of the token length before the actual requests to the ChatGPT API, in order to avoid errors if the maximum (4096) gets exceeded.



I have heavily used ChatGPT and Bing Chat to create this program in less than a day. What a time to be alive!