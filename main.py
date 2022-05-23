import asyncio
import json
import multiprocessing

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from fake_useragent import UserAgent
from seleniumwire import webdriver as sdriver

from datetime import datetime
from os import popen
from time import sleep
from random import choice

from config import Config
from db_connection import db_connection
import check_html
import bots

task_urls = []


geckodriver_path = '/usr/bin/geckodriver'


# proxies = []
# with open('proxy.txt', 'rt') as file:
#     for line in file:
#         proxies.append(line)


def get_html(url, time_out=4):
    options = Options()
    options.add_argument(f'user-agent={UserAgent().random}')
    # options.add_argument('--headless')
    driver = webdriver.Firefox(executable_path=geckodriver_path, options=options)
    try:
        driver.get(url=url)
        sleep(time_out)
        result = driver.page_source
    except Exception as e:
        result = ''
        print('Cant driver.get()')
        print(e)
    finally:
        driver.close()
        driver.quit()
#    soup = BeautifulSoup(result, 'lxml')
#    if not check_html.check_title(soup.find('title')):
#        options = sdriver.ChromeOptions()
#        options.add_argument('user-agent={}'.format(UserAgent().random))
#        options.add_argument('--headless')
#        proxy_options={'proxy':{'http': f'http://wiwgczwb:807hs8833d2u@{choice(proxies)}'}}
#        try:
#            driver = sdriver.Chrome(executable_path='chromedriver', seleniumwire_options=proxy_options)
#            driver.get(url)
#            result = driver.page_source
#        except:
#            print('proxy doesnt work')
#        finally:
#            driver.close()
#            driver.quit()
    with open('html.html', 'wt') as file:
        file.write(result)
    return result


def save_advanced_project_data_to_db(data):
    with db_connection() as connection:
        with connection.cursor() as cursor:
            if data['client']['location'] != None:
                sql_query = f"SELECT EXISTS(SELECT id FROM country WHERE slug=\'{data['client']['location'].lower().replace(' ', '_')}\')"
                cursor.execute(sql_query)
                if cursor.fetchone()[0] == 0:
                    sql_query = f"INSERT INTO country(name, slug) VALUES(\'{data['client']['location']}\', \'{data['client']['location'].lower().replace(' ', '_')}\')"
                    cursor.execute(sql_query)
                sql_query = f"SELECT id FROM country WHERE slug=\'{data['client']['location'].lower().replace(' ', '_')}\'"
                cursor.execute(sql_query)
                sql_query = f"INSERT INTO meta_job(id_job, meta_key, meta_value) VALUES({data['id']}, 'country', \'{cursor.fetchone()[0]}\')"
                cursor.execute(sql_query)
        connection.commit()


def save_project_first_data_to_db(datas):
    with db_connection() as connection:
        with connection.cursor() as cursor:
            count_getted_elements = len(datas)
            count_added_elements = 0
            for data in datas:
                time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open('project.json', 'w') as file:
                    json.dump(data, file, indent=2)
                # is job exists in db
                sql_query = f"SELECT EXISTS(SELECT id FROM job WHERE link=\'{data['url']}\')"
                cursor.execute(sql_query)
                if cursor.fetchone()[0] == 1:
                    continue

                # new record to table job
                sql_query = f"""INSERT INTO job(name, description, link) VALUES(\'{data['title'].replace("'", '')}\', \'{data['description'].replace("'", '')}\', \'{data['url']}\')"""
                cursor.execute(sql_query)

                # get job id
                sql_query = f"SELECT id FROM job WHERE link=\'{data['url']}\'"
                cursor.execute(sql_query)
                data['id'] = cursor.fetchone()[0]

                # append job to advanced scrapping
                task_urls.append({'title': data['title'], 'url': data['url']})
                count_added_elements += 1

                tags_id = []
                if data['tags'] != 0:
                    for tag in data['tags']:
                        slug = tag['title'].lower().replace(' ', '_')
                        sql_query = f"SELECT EXISTS(SELECT id FROM skill WHERE slug='{slug}')"
                        cursor.execute(sql_query)
                        if cursor.fetchone()[0] == 0:
                            sql_query = f"INSERT INTO skill(name, slug) VALUES(\'{tag['title']}\', \'{slug}\')"
                            cursor.execute(sql_query)
                        sql_query = f"SELECT id FROM skill WHERE slug=\'{slug}\'"
                        cursor.execute(sql_query)
                        tags_id.append(cursor.fetchone()[0])

                # add tags to meta_job
                sql_query = f"INSERT INTO meta_job(id_job, meta_key, meta_value) VALUES({data['id']}, 'skill', \'{str(tags_id)}\')"
                cursor.execute(sql_query)

                # add price to meta_job
                sql_query = f"""INSERT INTO meta_job(id_job, meta_key, meta_value) VALUES({data['id']}, 'price', \'{{isFixed: {data['price']['is_fixed']}, cost: {str(data['price']['value']).replace("'",'')}}}\')"""
                cursor.execute(sql_query)

                # add experience to meta_job
                if data['experience'] != 'Without experience':
                    sql_query = f"INSERT INTO meta_job(id_job, meta_key, meta_value) VALUES({data['id']}, 'experience', '{data['experience'].lower()}')"
                    cursor.execute(sql_query)
        connection.commit()
        print('{} of {} was added'.format(count_added_elements, count_getted_elements))


def scrap():
    print('scrap started')

    async def scrap_search_page():
        while True:
            url = 'https://www.upwork.com/nx/jobs/search/?sort=recency&per_page=50'
            print('Search page in progress')

            html = get_html(url=url, time_out=8)
            soup = BeautifulSoup(html, 'lxml')
            try:
                if not check_html.check_title(title=soup.find('title').text.strip()):
                    write_to_logfile('Bad Search Page')
                    await asyncio.sleep(90)
                    continue
            except:
                await asyncio.sleep(90)
                continue


            result = []

            sections = soup.find_all('section', class_='up-card-section up-card-list-section up-card-hover')
            if sections == []:
                continue

            domain = 'https://www.upwork.com/freelance-jobs/apply/'
            for section in sections:
                data = {}

                # uid
                data['uid'] = section.find('h4', class_='my-0 p-sm-right job-tile-title').find('a')['href'].split('~')[1][:-1]

                # title
                data['title'] = section.find('h4', class_='my-0 p-sm-right job-tile-title').text.replace('\'', '').strip()
                if 'Do not apply' in data['title']:
                    print('do not apply')
                    continue

                # description
                data['description'] = section.find('span', attrs={'data-test': 'job-description-text'}).text.replace('\'', '').strip()

                # price
                data['price'] = {}
                if 'Fixed-price' == section.find('strong', attrs={'data-test': 'job-type'}).text:
                    data['price']['is_fixed'] = True
                    try:
                        data['price']['value'] = float(section.find('span', attrs={'data-test': 'budget'}).text.strip()[1:].replace(',', ''))
                    except:
                        data['price']['value'] = 0
                else:
                    data['price']['is_fixed'] = False

                    budget = section.find('strong', attrs={'data-test': 'job-type'}).text.strip().split('$')
                    if len(budget) == 1:
                        data['price']['is_fixed'] = True
                        data['price']['value'] = 0
                    elif len(budget) == 2:
                        data['price']['value'] = {'min': float(budget[1].replace('-', '')), 'max': float(budget[1])}
                    else:
                        data['price']['value'] = {'min': float(budget[1].replace('-', '')), 'max': float(budget[2])}


                # experience
                try:
                    data['experience'] = section.find('span', attrs={'data-test': 'contractor-tier'}).text
                except:
                    data['experience'] = 'Without experience'

                # duration
                try:
                    data['duration'] = section.find('span', attrs={'data-test': 'duration'}).text
                except:
                    data['duration'] = 'Without duration'

                try:
                    data['tags'] = [{'title': tag.text.replace('\'', ''), 'uid': tag['href'].split('=')[-1]} for tag in section.find('div', class_='up-skill-container').find('div', class_='up-skill-wrapper').find_all('a')]
                except:
                    data['tags'] = 0
                data['url'] = domain + section.find('div', class_='row my-10').find('h4').find('a')['href'].split('/')[-2] + '/'
                result.append(data)

            save_project_first_data_to_db(result)

            await asyncio.sleep(90)


    async def scrap_project_page():
        while True:
            if task_urls:
                task = task_urls.pop(0)
                print('project page in progress', task['url'])

                # html = get_html(url=task['url'])
                # soup = BeautifulSoup(html, 'lxml')
                #
                # if str(soup) == '<html><head></head><body></body></html>':
                #     task_urls.append(task)
                #     continue
                #
                # try:
                #     if not check_html.check_h1(soup.find('h1').text.strip()):
                #         continue
                # except:
                #     continue

                result = {}

                # url
                result['url'] = task['url']

                result['uid'] = task['url'].split('~')[1][:-1]
                with db_connection().cursor() as cursor:
                    # project id
                    sql_query = f"SELECT id FROM job WHERE link=\'{result['url']}\'"
                    cursor.execute(sql_query)
                    result['id'] = cursor.fetchone()[0]

                    # title
                    sql_query = f"SELECT name FROM job WHERE id={result['id']}"
                    cursor.execute(sql_query)
                    result['title'] = cursor.fetchone()[0]

                    # sections = soup.find_all('section', class_='up-card-section')[:-1]
                    # # main tag
                    # result['specialty'] = {
                    #     'title': sections[0].find('div', class_='cfe-ui-job-breadcrumbs d-inline-block mr-10').find('a').text.strip(),
                    #     'occupation_uid': sections[0].find('div', class_='cfe-ui-job-breadcrumbs d-inline-block mr-10').find('a')['href'].split('=')[-1]
                    # }
                    # location
                    # result['location'] = sections[0].find('div', class_='mt-20 d-flex align-items-center location-restriction').find('span').text.strip()

                    # description
                    sql_query = f"SELECT description FROM job WHERE id={result['id']}"
                    cursor.execute(sql_query)
                    result['description'] = cursor.fetchone()[0]

                    # price
                    result['price'] = {}

                    sql_query = f"SELECT meta_value FROM meta_job WHERE id_job={result['id']} AND meta_key='price'"
                    cursor.execute(sql_query)
                    price = cursor.fetchone()[0]
                    if 'True' in price:
                        result['price'] = {
                            'isFixed': True,
                            'cost': float(price[1:-1].split(', ')[-1].split(': ')[-1])
                        }
                    else:
                        result['price'] = {
                            'isFixed': False,
                            'cost': {
                                'min': float(price[1:-1].split(', ')[1].split(': ')[-1][:-1]),
                                'max': float(price[1:-1].split(', ')[2].split(': ')[-1][:-1])
                            }
                        }

                    # tags
                    sql_query = f"SELECT meta_value FROM meta_job WHERE id_job={result['id']} AND meta_key='skill'"
                    result['tags'] = []
                    try:
                        cursor.execute(sql_query)
                        tags_id = [int(element) for element in cursor.fetchone()[0][1:-1].split(', ')]
                        for tag_id in tags_id:
                            sql_query = f"SELECT name, slug FROM skill WHERE id={tag_id}"
                            cursor.execute(sql_query)
                            r = cursor.fetchone()
                            result['tags'].append({
                                'name': r[0],
                                'slug': r[1],
                                'id': tag_id
                            })
                    except:
                        result['tags'].append({'name':'name', 'slug':'slug','id':100000})
                        # tags_span = soup.find_all('span', class_='cfe-ui-job-skill up-skill-badge disabled m-0-left m-0-top m-xs-bottom')
                        # for tag in tags_span:
                        #     slug = tag.text.lower().replace(' ', '_')
                        #     sql_query = f"SELECT EXISTS(SELECT id FROM skill WHERE slug='{slug}')"
                        #     cursor.execute(sql_query)
                        #     if cursor.fetchone()[0] == 0:
                        #         sql_query = f"INSERT INTO skill(name, slug) VALUES(\'{tag.text}\', \'{slug}\')"
                        #         cursor.execute(sql_query)
                        #     sql_query = f"SELECT id FROM skill WHERE slug=\'{slug}\'"
                        #     cursor.execute(sql_query)
                        #     tags_id.append(cursor.fetchone()[0])
                        #
                        # for tag_id in tags_id:
                        #     sql_query = f"SELECT name, slug FROM skill WHERE id={tag_id}"
                        #     cursor.execute(sql_query)
                        #     r = cursor.fetchone()
                        #     result['tags'].append({
                        #         'name': r[0],
                        #         'slug': r[1],
                        #         'id': tag_id
                        #     })

                        # add tags to meta_job
                        # sql_query = f"INSERT INTO meta_job(id_job, meta_key, meta_value) VALUES({result['id']}, 'skill', \'{str(tags_id)}\')"
                        # cursor.execute(sql_query)

                    # project_type
                    # try:
                    #     result['project_type'] = soup.find('ul', class_='cfe-ui-job-features p-0 fluid-layout-md').find_all('li')[-1].find('div', class_='header').find('strong').text.strip()
                    # except:
                    #     result['project_type'] = 'Without project type'

                    # activity_on_this_job
                    # result['activity_on_this_job'] = {}
                    # for li in soup.find('ul', class_='list-unstyled mb-0').find_all('li'):
                    #
                    #     # proposals
                    #     if li.find('span').text.strip() == 'Proposals':
                    #         try:
                    #             result['activity_on_this_job']['proposals'] = li.find('div', class_='d-none d-md-block').find('span').text.strip()
                    #         except:
                    #             result['activity_on_this_job']['proposals'] = 'Without proposals'
                    #
                    #     # interviewing
                    #     elif li.find('span').text.strip() == 'Interviewing':
                    #         try:
                    #             result['activity_on_this_job']['interviewing'] = int(li.find('div', class_='d-none d-md-block').find('span').text.strip())
                    #         except:
                    #             result['activity_on_this_job']['interviewing'] = 'Without interviewing'
                    #
                    #     # invites sent
                    #     elif li.find('span').text.strip() == 'Invites sent':
                    #         try:
                    #             result['activity_on_this_job']['invites_sent'] = int(li.find('div', class_='d-none d-md-block').find('span').text.strip())
                    #         except:
                    #             result['activity_on_this_job']['invites_sent'] = 'Without invites_sent'
                    #
                    #     # unanswered_invites
                    #     elif li.find('span').text.strip() == 'Unanswered invites':
                    #         try:
                    #             result['activity_on_this_job']['unanswered_invites'] = int(li.find('div', class_='d-none d-md-block').find('span').text.strip())
                    #         except:
                    #             result['activity_on_this_job']['unanswered_invites'] = 'Without unswered invites'
                    #
                    #     # last vieved by client
                    #     elif li.find('span').text.strip() == 'Last viewed by client':
                    #         try:
                    #             result['activity_on_this_job']['last_vieved_by_client'] = li.find('div', class_='d-none d-md-block').find('span').text.strip()
                    #         except:
                    #             result['activity_on_this_job']['last_vieved_by_client'] = 'Without last vieved'
                    #
                    #
                    # # client
                    # result['client'] = {}
                    #
                    #     # location
                    # try:
                    #     result['client']['location'] = soup.find('li', attrs={'data-qa': 'client-location'}).find('strong').text.strip()
                    # except:
                    #     result['client']['location'] = 'Without location'
                    #
                    #     # client job posting stats
                    # # try:
                    # result['client']['job_posting_stats'] = {}
                    #     # jobs posted
                    # result['client']['job_posting_stats']['jobs_posted'] = int(soup.find('li', attrs={'data-qa': 'client-job-posting-stats'}).find('strong').text.strip().split(' ')[0])
                    #
                    # hire_rate_open_jobs = soup.find('li', attrs={'data-qa': 'client-job-posting-stats'}).find('div').text.strip().split(',')
                    #
                    #     # hire rate
                    # result['client']['job_posting_stats']['hire_rate'] = int(hire_rate_open_jobs[0].strip().split('%')[0])
                    #
                    #     # open jobs
                    # result['client']['job_posting_stats']['open_jobs'] = int(hire_rate_open_jobs[1].strip().split(' ')[0])
                    # # except:
                    # #     result['client']['job_posting_stats'] = None
                    #
                    #     # client company profile
                    # try:
                    #     result['client']['company_profile'] = soup.find('li', attrs={'data-qa': 'client-company-profile'}).find('strong').text.strip()
                    # except:
                    #     result['client']['company_profile'] = 'Without company profile'
                    #
                    #     # client spend
                    # try:
                    #     result['client']['spend'] = soup.find('strong', attrs={'data-qa': 'client-spend'}).find('span').text.split(' ')[0]
                    # except:
                    #     result['client']['spend'] = 'Without spend'
                    #
                    #     #client hires
                    # try:
                    #     hires = soup.find('div', attrs={'data-qa': 'client-hires'}).text.strip()
                    #     result['client']['hires'] = int(hires.split(',')[0].split(' ')[0])
                    # except:
                    #     result['client']['hires'] = 'Without hires'
                    #
                    # try:
                    #     result['client']['active_hires'] = int(hires.split(',')[1].split(' ')[0])
                    # except:
                    #     result['client']['active_hires'] = 'Without active hires'


#                save_advanced_project_data_to_db(result)
                bots.bot_send(result)

            await asyncio.sleep(0.1)


    async def start_scrap():
        task1 = asyncio.create_task(scrap_search_page())
        task2 = asyncio.create_task(scrap_project_page())
        task3 = asyncio.create_task(bots.send_messages())
        await asyncio.gather(task1, task2, task3)


    asyncio.run(start_scrap())



def main():
    multiprocessing.Process(target=scrap).start()
    multiprocessing.Process(target=bots.bot_config).start()


if __name__ == '__main__':
    main()
