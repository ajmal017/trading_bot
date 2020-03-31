import requests
import pandas as pd

from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

urls = []
date_time = []
titles = []
content = []
start_page = 1
end_page = 2
analyser = SentimentIntensityAnalyzer()

for i in range(start_page, end_page):
    url = 'https://oilprice.com/Energy/Crude-Oil/Page-{}.html'.format(i)
    request = requests.get(url)
    soup = BeautifulSoup(request.text, "html.parser")
    for article_link in soup.find_all('div', class_='categoryArticle'):
        for content in article_link.find_all('a'):
            link = content.get('href')
            if link not in urls:
                urls.append(link)

 
for article in urls:
    titles.append(article.split("/")[-1].replace('-',' ').replace('.html', ''))
    request = requests.get(article)
    soup = BeautifulSoup(request.text, "html.parser")
    
    for dates in soup.find_all('span', {'class': 'article_byline'}):
        date_time.append(dates.text.split('-')[-1])
    
    temp = []
    for news in soup.find_all('p'):
        temp.append(news.text)
    
    for article_end in reversed(temp):
        if article_end.split(" ")[0]=="By":
            break

    article_text = ' '.join(temp[temp.index("More Info") + 1 : temp.index(article_end)])
    content.append(article_text)

df = pd.DataFrame(
    {
        'Date' : date_time,
        'Title': titles,
        'Content': content,
    })
    
df["Polarity"] = df["Content"].apply(lambda x : analyser.polarity_scores(x)["compound"])

show_data = df.drop(["Content"], axis = 1)
print(show_data.to_string())