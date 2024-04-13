import re

from loguru import logger

CHAT_DATA = "ai_group_chat"


def load_text_file(file_path):
    try:
        with open(file_path) as file:
            text = file.read()
        return text
    except FileNotFoundError:
        logger.info(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        logger.info(f"Error: An unexpected error occurred: {e}")
        return None


full_chat = load_text_file(f"./data/{CHAT_DATA}.txt")


split_regex = r"(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}\s*[AP]M\s*-)"
splits = re.split(split_regex, full_chat)
splits = [s for s in splits if len(s.strip()) > 0]
logger.info(len(splits))

structured_data = []
name_dictionary = {}
names_used_index = 0
for i in range(0, len(splits), 2):
    message = splits[i + 1]
    if ":" not in message:
        continue
    date_time = splits[i].split(" -")[0].split(", ")
    date = date_time[0]
    time = date_time[1]
    person = message.split(": ")[0]
    message = ": ".join(message.split(": ")[1:]).strip().replace("\n", " ")
    structured_data.append(
        {
            "date": date,
            "time": time,
            "person": person,
            "message": message,
        }
    )
logger.info(len(structured_data))
logger.info(structured_data[:5])

# group structured_data by date
grouped_data = {}
for data in structured_data:
    if grouped_data.get(data["date"], None) is None:
        grouped_data[data["date"]] = []
    grouped_data[data["date"]].append(data)
logger.info(len(grouped_data))

chat_daywise = []
for date, data in grouped_data.items():
    chat_for_date = []
    for chat in data:
        # remove any new lines from the message
        chat_for_date.append(f"{chat['message']}")
    chat_daywise.append(
        {
            "date": date,
            "chat": "\n".join(chat_for_date),
            "person": chat["person"],
        }
    )
logger.info(len(chat_daywise))

import requests

CHAT_URL = "http://localhost:8080/api/chat"
headers = {"Content-Type": "application/json"}
summary_prompt = """Write the minutes of the chat below.
Structure the output in the following way:

Questions Asked:
- question 1
- question 2
- ...

Decisions Made:
- decision 1
- decision 2
- ...

Action Items:
- action item 1
- action item 2
- ...

Important URLs:
- url 1
- url 2
- ...

Summary:
- summary of the chat
"""

links_prompt = """Extract only the URLs of the chat below.
Structure the output in the following way:

Important URLs:
- url 1
- url 2
- ...

Summary:
- summary of the chat
"""

body = {
    "model": "mistral:instruct",
    "messages": [
        {
            "role": "user",
            "content": "<<chat>>",
        },
    ],
    "stream": False,
}

for chat in chat_daywise:
    try:
        # if file already existst, skip
        if load_text_file(f"./results/{CHAT_DATA}/summary_{chat['date'].replace('/', '_')}.txt") is not None:
            logger.info(f"Skipping chat for date {chat['date']}.")
            continue
        body["messages"][0]["content"] = f"{summary_prompt}\n\nHere is the chat:\n{chat['chat']}"
        response = requests.post(CHAT_URL, json=body, headers=headers, timeout=60)
        if response.status_code != 200:
            logger.info(f"Error: Failed to summarize chat for date {chat['date']}.")
            continue
        summary = response.json()
        body["messages"][0]["content"] = f"{links_prompt}\n\nHere is the chat:\n{chat['chat']}"
        response = requests.post(CHAT_URL, json=body, headers=headers, timeout=60)
        if response.status_code != 200:
            logger.info(f"Error: Failed to summarize chat for date {chat['date']}.")
            continue
        links = response.json()
        result_chat = {
            "date": chat["date"],
            "summary": summary["message"]["content"],
            "links": links["message"]["content"],
            "chat": f"{summary['message']['content'].strip()}\n\n{links['message']['content'].strip()}\n",
        }
        # save the chat summary to a file
        with open(f"./results/{CHAT_DATA}/summary_{chat['date'].replace('/', '_')}.txt", "w") as file:
            file.write(result_chat["chat"])
        logger.info(f"Done with chat for date {chat['date']}.")
        # append actual chat at the end of file
        with open(f"./results/{CHAT_DATA}/summary_{chat['date'].replace('/', '_')}.txt", "a") as file:
            file.write(
                f"\n\n\n\n##################################### CHAT #####################################\n\n{chat['person']}: {chat['chat']}"
            )
        # break
    except Exception as e:
        logger.info(f"Error: An unexpected error occurred: {e}")
        continue

logger.info("Done with all chats.")
