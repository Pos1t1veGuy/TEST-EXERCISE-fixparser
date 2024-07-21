import scrapy
import time
import json
import sys


class FixpriceSpider(scrapy.Spider):
    name = "FixPrice"
    allowed_domains = ['fix-price.com']
    catalog = 'https://fix-price.com/catalog/kosmetika-i-gigiena/ukhod-za-polostyu-rta'
    result_filename = 'result.json'
    max_page = 70 # if 0 it will scan all pages

    results = []
    end = False


    def start_requests(self):
        cookies = {
            'localy': '{"city":"Екатеринбург","cityId":55,"longitude":60.597474,"latitude":56.838011,"prefix":"г"}'
        }

        index = 0
        while not self.end and (index < self.max_page or self.max_page == 0):
            index += 1
            yield scrapy.Request(url=f'{self.catalog}?page={index}', cookies=cookies, callback=self.parse_page, cb_kwargs={'page': index})


    def parse_page(self, response, page: int = 1):
        product_links = response.xpath("//div[@class='description']/a[@class='title']/@href").getall()

        if response.status == 404:
            print(f'Page {page} not found. Stopping parsing.')
            self.end = True
            return

        print(f"Parsing {page} page")

        for link in product_links:
            yield response.follow(link, self.parse_product)


    def parse_product(self, response):
        marketing_tags = [
            tag.strip() for tag in response.xpath("//div[contains(@class, 'sticker')]/text()").getall() if tag.strip()
        ]
        title = response.xpath("//h1[@class='title']/text()").get()
        sections = [
            crumb.strip() for crumb in response.xpath("//div[@itemscope='itemscope']//span[@itemprop='name']/text()").getall() if crumb.strip()
        ]
        sprice = response.xpath("//div[@class='special-price']/text()").get()
        rprice = response.xpath("//div[@class='regular-price']/text()").get()
        imgs = response.xpath("//div[@class='product-images']//img/@src").getall()
        description = response.xpath("//div[@class='description' and text()!='Выберите способ получения']/text()").get()

        tags_keys = response.xpath("//p[@class='property' and span[@class='title']]/span[@class='title']/text()").getall()
        tags_values = (
            [response.xpath(
                "//p[@class='property' and span[@class='title']]/span[@class='value']/a[@class='link']/text()"
            ).get()] + 
            response.xpath(
                "//p[@class='property' and span[@class='title']]/span[@class='value']/text()"
            ).getall()
        )

        res = {
            'timestamp': int(time.time()),
            'RPC': None,
            'url': response.url,
            'title': title,
            "marketing_tags": marketing_tags,
            "brand": None,
            "section": sections,
            "price_data": {
                "current": float(sprice.split(' ')[0]) if sprice else rprice,
                "original": float(rprice) if rprice else None,
                "sale_tag": f'{100 - sprice*100//rprice}%' if sprice and rprice else None,
            },
            "stock": {
                "in_stock": None,
                "count": None,
            },
            "assets": {
                "main_image": imgs[0] if imgs else None,
                "set_images": imgs[1:] if imgs else [],
                "view360": None,
                "video": None,
            },
            "metadata": {
                "__description": description,
            }
        }
        for key, value in zip(tags_keys, tags_values):
            if key == 'Код товара':
                res['RPC'] = value
            elif key == 'Бренд':
                res['brand'] = value
            else:
                res['metadata'][key] = value

        self.results.append(res)

    def closed(self, reason):
        with open(self.result_filename, 'w') as f:
            json.dump(self.results, f, indent=4)

        print(f'Saved results to {self.result_filename}')