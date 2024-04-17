
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import os
import json
import glob
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from webdriver_manager.chrome import ChromeDriverManager

add_zero = lambda x: '0' + str(x) if len(str(x)) < 2 else str(x)
number_ticket = 1

options = Options()
options.headless = True  # hide GUI
options.add_argument("--window-size=1920,1080")  # set window size to native GUI size
options.add_argument("start-maximized")  # ensure window is full-screen
# configure chrome browser to not load images and javascript
# chrome_options = webdriver.ChromeOptions()
# chrome_options.add_experimental_option(
#                     "prefs", {"profile.managed_default_content_settings.images": 2}
#                         )
service = Service()

def parse_page(page):
    soup = BeautifulSoup(page, features='html.parser')

    # prices = soup.find_all('div', attrs={'class':'ticket-desktop__side-container'})
    prices = soup.find_all('div', attrs={'data-test-id':'ticket-preview'})

    price_ticket = list(map(lambda x: x.find('span', attrs={'data-test-id':'price'}), prices))
    price_ticket = list(map(lambda x: x.text.replace('\u202f','').replace('\u2009₽',''), price_ticket))

    price_luggage = list(map(lambda x: x.find('div', text='Багаж'), prices))
    price_luggage = list(map(lambda x: x.find_next('span').get_text(strip=True) if x else '0',  price_luggage))
    del_words = ['+\u2009','\u202f', '\u2009₽', '₽']
    for word in del_words:
        price_luggage = list(map(lambda x: x.replace(word,'') if x else '0', price_luggage))

    wo_luggage = list(map(lambda x: 1 if x.find('div', text='Без багажа') else 0, prices))

    #duration = soup.find_all('div', attrs={'class':'segment-route__duration'})
    # duration = soup.find_all('div', attrs={'span':'data-test-id'})
    # duration = list(map(lambda x: x.text.replace('В пути:  ',''), duration))

    duration = list(map(lambda x: x.find('div', attrs={'data-test-id':'ticket-segment-route'}), prices))
    duration = list(map(lambda x: x.find_all('span', attrs={'data-test-id':'text'})[1], duration))
    duration = list(map(lambda x: x.text.replace('В пути: ',''), duration))
    duration = list(map(lambda x: x.replace('\u200a',' '), duration))


    # transfer = soup.find_all('div', attrs={'class':'segment-route__path'})
    # transfer = list(map(lambda x: x.find_all('div', attrs={'class':'segment-route__stop'}), transfer))
    # transfer = list(map(lambda x: list(map(lambda y: y['data-iatas'], x)), transfer))

    transfer =  list(map(lambda x: x.find('div', attrs={'data-test-id':'ticket-segment-route'}), prices))
    transfer = list(map(lambda x: x.find_all('div', attrs={'data-test-id':'text'}), transfer))

    # time_start = soup.find_all('div', attrs={'class':'segment-route__endpoint origin'})
    # time_start = list(map(lambda x: x.find_all('div', attrs={'class':'segment-route__time'})[0].text, time_start))

    time_start = list(map(lambda x: x.find('div', attrs={'data-test-id':'origin-endpoint'}), prices))
    time_start = list(map(lambda x: x.find_all('span', attrs={'data-test-id':'text'})[0].text, time_start))

    # time_stop = soup.find_all('div', attrs={'class':'segment-route__endpoint destination'})
    # time_stop = list(map(lambda x: x.find_all('div', attrs={'class':'segment-route__time'})[0].text, time_stop))

    time_stop = list(map(lambda x: x.find('div', attrs={'data-test-id':'destination-endpoint'}), prices))
    time_stop = list(map(lambda x: x.find_all('span', attrs={'data-test-id':'text'})[0].text, time_stop))

    #transfer = list(map(lambda x: ', '.join(x), transfer))
    # transfer = list(map(lambda x: x.replace('\n',"->"), transfer))

    number_transfer = list(map(lambda x: len(x), transfer))
    transfer = list(map(lambda x: list(map(lambda y: y.text, x)), transfer))
    transfer = list(map(lambda x: '->'.join(x), transfer))


    not_ticket = soup.find_all('div', attrs={'class':'error-informer__container'})
    keys = ['price', 'luggage', 'without_luggage', 'duration', 'time_start', 'time_stop', 'transfer', 'number_transfer']

    if not_ticket and 'Билеты не найдены' in not_ticket[0].text:
        zipped = [[None] * 8]
    else:
        zipped = zip(price_ticket, price_luggage, wo_luggage, duration, transfer, number_transfer)

    data = [dict(zip(keys, values)) for values in zipped]
    return data


def list_dates(datetime_start, datetime_end):
    delta = timedelta(days = 1)
    range_dates = []
    date = datetime_start
    while date <= datetime_end:
        range_dates.append(date)
        date = date + delta
    return range_dates


def get_ticket(origin, destination, date, update_base = False, time_sleep = 20, screenshot = False):

    root = 'tickets'
    month, day = add_zero(date.month), add_zero(date.day)
    date = date.strftime('%Y-%m-%d')

    dir_json = os.path.join('.', root, 'json')
    json_pattern = os.path.join(dir_json,'*.json')
    file_list = glob.glob(json_pattern)
    ticket_list = list(map(lambda x: x.split('.')[-2].split('\\')[-1], file_list))
    name_ticket = origin + '_' + destination + '_' + date

    now = datetime.now()
    path_ticket = os.path.join(dir_json, name_ticket + '.json')

    #проверяем нужно ли качать билет
    #1е условие - запрос от пользователя
    #2е условие - есть ли такой файл
    #3е условие если он старше 2 часов
    #4е условие пустой ли файл
    not_update_base = (not update_base and
                    name_ticket in ticket_list and
                    os.path.getmtime(path_ticket) + 30 * 3600 > now.timestamp() and
                    os.path.getsize(path_ticket) > 2)

    # скрипаем если не нужно обновлять
    if not_update_base: return

    driver = webdriver.Chrome(options=options, chrome_options=options, service = service)
    url = 'https://www.aviasales.ru/search/' + origin + day + month + destination + str(number_ticket)
    driver.get(url)
    time.sleep(time_sleep)
    try:
        element = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@id='ui-datepicker-div']//a[@class='ui-state-default']")))
    except TimeoutException:
        pass
    page = driver.page_source
    tickets = parse_page(page)
    tickets = [dict(item, **{'date':date, 'origin':origin, 'destination':destination}) for item in tickets]
    if not os.path.isdir(root):
        os.makedirs(os.path.join(root))
        os.makedirs(os.path.join(root, 'json'))
        os.makedirs(os.path.join(root, 'screenshots'))

    with open(os.path.join(root, 'json', origin + '_' + destination + '_' + date + '.json'), 'w', encoding='utf-8') as f:
        json.dump(tickets, f)

    driver.set_window_size(1920, 1080)
    time.sleep(2)
    if screenshot:
        driver.save_screenshot(os.path.join(root, 'screenshots', origin + '_' + destination + '_' + date + '.png'))
    driver.close()

# чтобы обработать все json
def conver_all_json():
    root = '.\\tickets\\json'
    json_pattern = os.path.join(root,'*.json')
    file_list = glob.glob(json_pattern)

    data = [] # an empty list to store the data frames
    for file in file_list:
        with open(file) as f:
            ticket = json.load(f)
            data += ticket

    df = pd.DataFrame(data)
    df.to_csv('tickets.txt', sep = ';', index = False, encoding='utf-8-sig')