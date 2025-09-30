from newspaper import Article

url = 'https://36kr.com/p/3482899443506050'
article = Article(url)

article.download()
article.parse()

print('Title:', article.title)
print('Author:', article.authors)

article.nlp()
print('Keywords:', article.keywords)
print('Summary:', article.summary)