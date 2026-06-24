import os
import pandas as pd
import numpy
from collections import Counter
from ckip_transformers.nlp import CkipWordSegmenter, CkipPosTagger, CkipNerChunker

# 取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

input_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'csv_tmp', 'dcard_data1_tmp.csv')
output_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'csv_tmp', 'dcard_data2_preprocessed_tmp.csv')

df = pd.read_csv(input_path, sep='|')

df = df.dropna(subset=["content"])
df["content"] = df["content"].astype(str)


# ckiplab word segment (中研院斷詞)
# Initialize drivers
# It takes time to download ckiplab models

# default參數是model="bert-base"
# ws = CkipWordSegmenter() 
# pos = CkipPosTagger()
# ner = CkipNerChunker()

# model="albert-tiny" 模型小，斷詞速度比較快，犧牲一些精確度
ws = CkipWordSegmenter(model="albert-tiny") 
pos = CkipPosTagger(model="albert-tiny")
ner = CkipNerChunker(model="albert-tiny")



## Word Segmentation
# tokens = ws(df.content)
tokens = ws(df["content"].tolist())

## POS
tokens_pos = pos(tokens)

## word pos pair 詞性關鍵字
word_pos_pair = [list(zip(w, p)) for w, p in zip(tokens, tokens_pos)]

## NER命名實體辨識
entity_list = ner(df["content"].tolist())

# Remove stop words and filter using POS tag (tokens_v2)
#with open('stops_chinese_traditional.txt', 'r', encoding='utf8') as f:
#    stops = f.read().split('\n')

# 過濾條件:兩個字以上 特定的詞性
# allowPOS 過濾條件: 特定的詞性
allowPOS = ['Na', 'Nb', 'Nc', 'VC']

tokens_v2 = []
for wp in word_pos_pair:
    tokens_v2.append([w for w, p in wp if (len(w) >= 2) and p in allowPOS])

# Insert tokens into dataframe (新增斷詞資料欄位)
df['tokens'] = tokens
df['tokens_v2'] = tokens_v2
df['entities'] = entity_list
df['token_pos'] = word_pos_pair

# Calculate word count (frequency) 計算字頻(次數)


def word_frequency(wp_pair):
    filtered_words = []
    for word, pos in wp_pair:
        if (pos in allowPOS) & (len(word) >= 2):
            filtered_words.append(word)
        #print('%s %s' % (word, pos))
    counter = Counter(filtered_words)
    return counter.most_common(200)


keyfreqs = []
for wp in word_pos_pair:
    topwords = word_frequency(wp)
    keyfreqs.append(topwords)

df['top_key_freq'] = keyfreqs

# Abstract (summary) and sentimental score(摘要與情緒分數)
summary = []
sentiment = []
for text in df["content"]:
    summary.append("暫無")
    sentiment.append("暫無")

df['summary'] = summary
df['sentiment'] = sentiment

# Rearrange the colmun order for readability
df = df[[
    'category', 'article_dates', 'article_id', 'title', 'content', 'summary', 'sentiment', 'tokens', 'tokens_v2', 'entities', 'token_pos', 'top_key_freq', 'links',
]]

# Save data to disk
# df.to_csv(os.path.join('csv_file', 'dcard_data2_preprocessed.csv'), sep='|', index=False)

df.to_csv(
    output_path,
    sep='|',
    index=False,
    encoding='utf-8-sig'
)

## Read it out 讀出看看
#df = pd.read_csv('cna_dataset_preprocessed.csv', sep='|')
#df.head(1)

print("Tokenize OK!")
