from discord import Webhook, RequestsWebhookAdapter
from bs4 import BeautifulSoup
import collections
import requests
import discord
import time

article_url = "https://www.br.de/nachrichten/deutschland-welt/russland-ukraine-krieg-news-ticker-kw12"
hook_url = 'https://discord.com/api/webhooks/945623544585416715/anbgNXHkA4gmqKXCUS4gEVJ33n0P2xKflR0Swh2j8tyxCcynsgNvC5I4chFVOALOPyrQ'
webhook = Webhook.from_url(hook_url, adapter=RequestsWebhookAdapter())
session = requests.Session()

latest_titles = collections.deque(maxlen=50)
latest_contents = collections.deque(maxlen=50)

while True:
    try:
        response = session.get(article_url)
    except requests.ConnectionError:
        print("Session Reset")
        session = requests.Session()
        time.sleep(60)
        continue

    soup = BeautifulSoup(response.text, 'html5lib')
    parent = soup.find(id='articlebody')

    if not parent:
        print("No Parent")
        time.sleep(60)
        continue

    all_sections = parent.find_all('section')
    latest_section = all_sections[1]
    titles = latest_section.find_all('h2')

    if not titles:
        urls = latest_section.find_all('a')

        if not urls:
            print("No Title")
            time.sleep(60)
            continue

        latest_section = all_sections[2]
        titles = latest_section.find_all('h2')

    if len(titles) > 1:
        paragraphs = []
        title_element = None

        father = latest_section.find_all('div')[0]
        for child in father.children:

            if child.name == "h2":
                if not child.text:
                    continue

                if not title_element:
                    title_element = child
                else:
                    break

            elif child.name == "p":
                paragraphs.append(child)

    else:
        title_element = titles[0]
        paragraphs = latest_section.find_all('p')

    title = title_element.text
    content = "\n\n".join([p.text.replace("\n", "") for p in paragraphs])

    if not title or not content:
        pass

    elif title not in latest_titles and content not in latest_contents:
        latest_titles.append(title)
        latest_contents.append(content)

        embed = discord.Embed(title=title[:256], url=article_url)
        embed.description = content
        webhook.send(embed=embed)

    time.sleep(60)



