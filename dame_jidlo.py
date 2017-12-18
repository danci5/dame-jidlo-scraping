#!/usr/bin/env python

import logging
from lxml import etree
import re
import weblib
import pandas as pd
import os
from grab import Grab

logging.basicConfig(level=logging.DEBUG)
dame_jidlo = 'https://www.damejidlo.cz'
g = Grab()
g.go(dame_jidlo)

def get_the_restaurant_refs():
    """ Retrieves all the links for restaurants from the damejidlo catalog. """
    
    # grabbing the catalog
    g.go('/katalog/')

    # selecting prague list
    catalog = g.doc.select("//ul[@class='catalogue__list']")
    prague = catalog[0]

    # creating my own etree
    html_prague = prague.html().replace('\t','').replace('\n','')
    root = etree.fromstring(html_prague)
    tree = etree.ElementTree(root)

    # xpath for all links of restaurants from ul of prague
    refs = tree.xpath("//@href")

    return refs 

def get_rating(url):
    """ Retrieves ratings for restaurant.
    
    0-100 ratings
    -1    no ratings
    -2    restaurant doesn't offer anything at the moment/wrong structure 
    """

    g.go(url)
    try:
        rat = g.doc.select("(//div[@class='restaurant-rating__text-top'])[1]")
        rat_nodes = rat.node().getchildren()
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        return -2

    if len(rat_nodes) == 0:
        # no ratings 
        return -1
    else:
        try: 
            # rating is in the strong element - first child
            rating = int(rat.node().getchildren()[0].text.strip('%'))

        except Exception as e:
            # formatting went wrong 
            rating = -2
            print(type(e))
            print(e)

    return rating

def get_number_of_ratings(url):
    """ Retrieves number of ratings for restaurant.
    
    0-x number of ratings
    -2  restaurant doesn't offer anything at the moment/wrong structure
    """

    g.go(url)
    try:
        nor = g.doc.select("(//div[@class='restaurant-rating__text-bottom'])[1]")
        nor_nodes = nor.node().getchildren()
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        return -2

    if nor_nodes[0].tag == 'span' or len(nor_nodes) == 0:
        # no ratings or no children for upper element selection
        return 0

    else:
        try: 
            if nor_nodes[0].attrib['class'] == 'modal-activator--rating':
                # number of ratings - get the first number which occurs in the child node
                number_of_ratings = re.search(r'\d+', nor_nodes[0].text).group()

        except KeyError as e:
            # formatting went wrong
            number_of_ratings = -2
            print(type(e))
            print(e)
            
    return number_of_ratings

def create_dataset(names, urls, ratings, number_of_ratings):
    final_dict = {}
    final_dict['restaurant_names'] = names
    final_dict['urls'] = urls
    final_dict['ratings'] = ratings
    final_dict['number_of_ratings'] = number_of_ratings
    df = pd.DataFrame(data=final_dict)
    return df

def main():    
    refs = get_the_restaurant_refs()
    names = [ref.strip('/') for ref in refs]
    urls = ['https://www.damejidlo.cz' + ref for ref in refs]
    ratings = [get_rating(ref) for ref in refs]
    number_of_ratings = [get_number_of_ratings(ref) for ref in refs]
    # delivery_fees 

    dataframe = create_dataset(names, urls, ratings, number_of_ratings)
    dataframe.index.name = 'id'
    
    dir_path = os.path.dirname(os.path.realpath(__file__))

    csv_file = dataframe.to_csv(os.path.join(dir_path, 'dame_jidlo_prague.csv'), encoding='utf-8')
    out = dataframe.to_json(orient='records')
    with open(os.path.join(dir_path, 'dame_jidlo_prague.json'), 'w') as json_file:
        json_file.write(out)


if __name__ == "__main__":
    main()