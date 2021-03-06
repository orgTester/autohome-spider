# -*- coding: utf-8 -*-

from autohomeSpider.items import Article
from requests.exceptions import RequestException
from urllib2 import urlopen
from urllib2 import quote
import json
import scrapy
import re

class ArticlesSpider(scrapy.Spider):
    name = "articles"

    custom_settings = {
        'ITEM_PIPELINES': {
            'autohomeSpider.pipelines.ArticleMongoPipeline': 300
        }
    }

    def start_requests(self):
        if not self.words:
            raise ValueError("No search keyword given.")
        keywords = self.words.split(',')
        for keyword in keywords:
            keyword = quote(keyword.encode('gb2312'))
            url = 'https://sou.autohome.com.cn/wenzhang?q=%s' % keyword
            yield scrapy.Request(url=url, callback=self.parse_search_page)

    def parse_search_page(self, response):
        # crawl all the articles in current page
        for link in response.xpath("//dl[@class='list-dl']/dt/a/@href").extract():
            self.logger.info("Crawling: %s" % link)
            yield scrapy.Request(url=link, callback=self.parse_article_page)
        # go to next page
        next_page = response.xpath("//a[@class='page-item-next']/@href").extract_first()
        self.logger.info("Next page: %s" % next_page)
        if next_page is not None:
            yield response.follow(url=next_page, callback=self.parse_search_page)

    def parse_article_page(self, response):
        article = Article()
        article['id'] = re.compile(r'.*/(\d+).html$').findall(response.url)[0]
        article['title'] = response.xpath("//div[@id='articlewrap']/h1/text()").extract_first().strip()
        article['date'] = response.xpath("//div[@class='article-info']/span/text()")[0].extract().strip()

        # extract text from each <p> tag and combine all them as a single string
        origin_content = response.xpath("//div[@id='articleContent']/p[not(contains(@class, 'center')) and not(contains(@align, 'center'))]").extract()
        content = ""
        regexp = re.compile(r'(<[^>]*>)|(\xa0)')
        for p in origin_content:
            content += regexp.sub('', p).strip()
        article['content'] = content

        # get tags
        article['tags'] = response.xpath("//span[contains(@class, 'tags')]/a/text()").extract()

        # get all comments from the api and store in the article item
        comments = []
        try:
            comment_api = 'https://reply.autohome.com.cn/api/comments/show.json?id=%s&appid=1&count=0' % article['id']
            request = json.load(urlopen(comment_api))
            for c in request['commentlist']:
                comments.append(c['RContent'])
        except Exception:
            self.logger.error("Get comments failed for article #" + article['id'])
        finally:
            article['comments'] = comments
            yield article
