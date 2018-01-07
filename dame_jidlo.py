#!/usr/bin/env python

import logging
from lxml import etree
import re
import weblib
import pandas as pd
import os
from grab import Grab
import googlemaps
import urllib.parse
import json
import configparser

logging.basicConfig(level=logging.DEBUG)
dame_jidlo = 'https://www.damejidlo.cz'
g = Grab()
g.go(dame_jidlo)

def get_the_restaurant_refs():
    """Gets all the links for restaurants from the damejidlo catalog.
    
    Returns:
        all restaurant references in catalogue
    """
    
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

def get_rating():
    """Gets ratings for restaurant.
    
    Returns:
        0-100 rating
        -1    no ratings
        None  restaurant doesn't offer anything at the moment/wrong structure 
    """

    try:
        rat = g.doc.select("(//div[@class='restaurant-rating__text-top'])[1]")
        rat_nodes = rat.node().getchildren()
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        return None

    if len(rat_nodes) == 0:
        # no ratings 
        return -1
    else:
        try: 
            # rating is in the strong element - first child
            rating = int(rat.node().getchildren()[0].text.strip('%'))

        except Exception as e:
            # formatting went wrong 
            rating = None
            print(type(e))
            print(e)

    return rating

def get_number_of_ratings():
    """Gets number of ratings for restaurant.
    
    Returns:
        0-x   number of ratings
        None  restaurant doesn't offer anything at the moment/wrong structure
    """

    try:
        nor = g.doc.select("(//div[@class='restaurant-rating__text-bottom'])[1]")
        nor_nodes = nor.node().getchildren()
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        return None

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
            number_of_ratings = None
            print(type(e))
            print(e)
            
    return number_of_ratings

def get_delivery_fee():
    """Gets deliver fee for restaurant.

    Delivery fee price depends on the address and sometimes varies based on the price of the order.
    Thus it's string for now.

    Returns:
        string  including delivery fee prices
        None    restaurant doesn't offer anything at the moment/wrong structure
    """

    try:
        fee_selection = g.doc.select("(//div[@class='delivery-info__price delivery-info__item'])[1]")
        fee = fee_selection.text()
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        return None
    return fee

def fill_lat_long_and_return_geocoding_response(addresses, lats, lngs):
    """Gets address and geocodes the address to lat long with gmaps API.
    
    lat - saved into lats list
    lng - saved into lngs list
    
    When incapable of getting lat, lng values, filling None because:
    -restaurant doesn't offer anything at the moment/wrong structure
    -the API didnt't handle the format of the address    

    Returns:
        dict of geocoding response from API
        None
    """
    try:
        gmaps_link = g.doc.select("(//div[@class='moreinfo__address-image'])[1]/a/@href").text()
        url_encoded_address = gmaps_link.split('=')[1]

        # URL address decoded to string in utf-8
        address = urllib.parse.unquote(url_encoded_address).replace('+',' ')
        addresses.append(address)
         
    except weblib.error.DataNotFound as e:
        print(type(e))
        print(e)
        addresses.append(None)
        lats.append(None)
        lngs.append(None)
        return None

    try:    
        config = configparser.ConfigParser()
        config.read('auth.cfg')
        gmaps = googlemaps.Client(key=config['gmaps-geocoding']['api_key'])
        geocode_result = gmaps.geocode(address)
        
        location = geocode_result[0]['geometry']['location']
        lats.append(location['lat'])
        lngs.append(location['lng'])
    except:
        print(type(e))
        print(e)
        lats.append(None)
        lngs.append(None)
        return None

    return geocode_result[0]

def get_municipal_district(address):
    """Gets the district from the address. 
    
    Worth to mention:
    -it's not always in the address and sometimes it's not correct
    -scans through address looking for the first location of Praha 'number'

    Returns:
        number of municipal district
        None - it's not always in the address
    """
    if address is not None:
        municipal_district = re.search('Praha\s(\d+)', address) 
        return municipal_district.group(1) if municipal_district is not None else None
    return None

def create_dataset(names, urls, ratings, number_of_ratings, addresses, lats, lngs, municipal_districts, delivery_fees):
    final_dict = {}
    final_dict['restaurant_name'] = names
    final_dict['url'] = urls
    final_dict['rating'] = ratings
    final_dict['number_of_ratings'] = number_of_ratings
    final_dict['full_address'] = addresses
    final_dict['lat'] = lats
    final_dict['lng'] = lngs
    final_dict['prague_municipal_district'] = municipal_districts
    final_dict['delivery_fee'] = delivery_fees
    df = pd.DataFrame(data=final_dict)
    return df

def export_dataset(dataframe):
    """Exports dataframe to csv and json file."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    csv_file = dataframe.to_csv(os.path.join(dir_path, 'dame_jidlo_prague.csv'), encoding='utf-8')
    out = dataframe.to_json(orient='records')
    with open(os.path.join(dir_path, 'dame_jidlo_prague.json'), 'w') as json_file:
        json_file.write(out)

def save_geocoding_responses(names, geocoding_dicts):
    """Saves dicts from Google Maps Geocoding API to json files for future use."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    for i in range(len(names)):
        with open(os.path.join(dir_path, 'geocoding_jsons/%s.json' % (names[i])), 'w') as geocoding_file:
            json.dump(geocoding_dicts[i], geocoding_file, ensure_ascii=False, indent=2)

def main():    
    refs = get_the_restaurant_refs()
    lats, lngs, addresses = [], [], []
    ratings, number_of_ratings, delivery_fees = [], [], []
    geocoding_dicts = []

    for ref in refs:
        g.go(ref)
        geocoding_dicts.append(fill_lat_long_and_return_geocoding_response(addresses, lats, lngs))
        ratings.append(get_rating())
        number_of_ratings.append(get_number_of_ratings())
        delivery_fees.append(get_delivery_fee())

    urls = ['https://www.damejidlo.cz' + ref for ref in refs]
    names = [ref.strip('/') for ref in refs]
    prague_municipal_districts = [get_municipal_district(address) for address in addresses]

    dataframe = create_dataset(names, urls, ratings, number_of_ratings, addresses, lats, lngs, prague_municipal_districts, delivery_fees)
    dataframe.index.name = 'id'
    dataframe = dataframe[['restaurant_name', 'rating', 'number_of_ratings', 'delivery_fee', 'full_address', 'lat', 'lng', 'prague_municipal_district', 'url']]

    export_dataset(dataframe)
    save_geocoding_responses(names, geocoding_dicts)


if __name__ == "__main__":
    main()