import json
import requests
import asyncio

from db_connection import db_connection
from datetime import datetime
from time import sleep
from os import path

from config import Config

URL_sender = 'https://api.telegram.org/bot{}/'.format(Config.bot_sender_token)


def bot_send(data):
    with open('json.json', 'w') as file:
        json.dump(data, file, indent=2)

    with db_connection() as connection:
        with connection.cursor() as cursor:
            sql_query = "SELECT id, id_user, name FROM filters"
            cursor.execute(sql_query)
            filters = [{'id': filter[0], 'id_user': filter[1], 'name': filter[2]} for filter in cursor.fetchall()]

            for filter in filters:
                if check_unfilters(data, filter['id']):
                    continue

                sql_query = f"SELECT id_option, option_value FROM filter_elements WHERE id_filter={filter['id']}"
                cursor.execute(sql_query)
                filter_elements = [{'id_option': element[0], 'option_value': element[1]} for element in cursor.fetchall()]
                job_weight = 0
                flag = True

                for filter_element in filter_elements:
                    sql_query = f"SELECT func FROM option_for_filter WHERE id={filter_element['id_option']}"
                    cursor.execute(sql_query)
                    func = cursor.fetchone()[0]

                    if func == 'fixed_price':
                        if data['price']['isFixed']:
                            if not check_filter_fixed_price(data['price']['cost'], filter_element['option_value']):
                                flag = False
                        else:
                            flag = False

                    elif func == 'price':
                        if not check_filter_price(data['price'], filter_element['option_value']):
                            flag = False

                    elif func == 'hourly_price':
                        if not data['price']['isFixed']:
                            if not check_filter_hourly_price(data['price']['cost'], filter_element['option_value']):
                                flag = False
                        else:
                            flag = False

                    elif func == 'skill':
                        filter_skills_id = [int(element) for element in filter_element['option_value'][1:-1].split(', ')]
                        percent_skill = check_filter_skills(data['tags'], filter_skills_id)

                        if percent_skill >= 75:
                            job_weight += 1

                        sql_query = f"SELECT EXISTS(SELECT id FROM filter_elements WHERE id_filter={filter['id']} AND id_option=6)"
                        cursor.execute(sql_query)
                        if cursor.fetchone()[0] == 1:
                            sql_query = f"SELECT option_value FROM filter_elements WHERE id_filter={filter['id']} AND id_option=6"
                            cursor.execute(sql_query)
                            if percent_skill < float(cursor.fetchone()[0]):
                                flag = False

                if not flag:
                    continue

                print(f"{filter['id_user']}: {filter['name']}, {data_cost}")

                sql_query = f"SELECT id FROM job WHERE link=\'{data['link']}\'"
                cursor.execute(sql_query)
                id_job = cursor.fetchone()[0]

                sql_query = f"INSERT INTO messages(id_filter, id_job, job_weight, percent_skill, status) VALUES({filter['id']}, {id_job}, {job_weight}, 0)"
                cursor.execute(sql_query)

        connection.commit()




def check_filter_fixed_price(value, filter_text):
    filter = [float(filter_text[1:-1].split(', ')[0].split(': ')[-1]), float(filter_text[1:-1].split(', ')[1].split(': ')[-1])]
    if (min(filter) <= value <= max(filter)):
        return True
    return False

def check_filter_hourly_price(value, filter_text):
    filter = [float(filter_text[1:-1].split(', ')[0].split(': ')[-1]), float(filter_text[1:-1].split(', ')[1].split(': ')[-1])]
    if min(filter) <= (value['max']-value['min'])/2 + value['min'] <= max(filter):
        return True
    return False

def check_filter_price(value, filter_text):
    if value['isFixed']:
        return check_filter_fixed_price(value['cost'], filter_text)
    else:
        return check_filter_hourly_price(value['cost'], filter_text)

def check_filter_skills(value, filter):
    count = 0
    skills_id = [element['id'] for element in value]
    for skill_id in filter:
        if skill_id in skills_id:
            count += 1
    return (count/len(filter)) * (len(filter)/len(skills_id)) * 100

def check_filter_percent_skill(value, filter):
    if value >= filter:
        return True
    return False

def check_filter_country(value, filter):
    if value == filter:
        return True
    return False

def send(chat_id, text):
    url = URL_sender + 'sendMessage'
    data = {'chat_id': chat_id, 'text':text}
    response = requests.post(url, json=data)
    with open('response.json', 'w') as file:
        json.dump(response.json(), file, indent=2)


def check_unfilters(data, id_filter):
    sql_query = f"SELECT id_option, option_value FROM unfilter_elements WHERE id_filter={id_filter}"
    cursor.execute(sql_query)
    unfilter_elements = [{'id_option': int(element[0]), 'option_value': element[1]} for element in cursor.fetchall()]

    for unfilter_element in unfilter_elements:
        # skill
        if unfilter_element['id_option'] == 2:
            unskills_id = set([int(id) for id in unfilter_element['option_value'][1:-1].split(', ')])
            skills_id = set([tag['id'] for tag in data['tags']])
            if not skills_id.isdisjoint(unskills_id):
                return True

    return False


async def send_messages():
    while True:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                sql_query = "SELECT id, id_filter, id_job, job_weight, percent_skill, time FROM messages WHERE status=0"
                cursor.execute(sql_query)
                messages = [{'id': element[0], 'id_filter': element[1], 'id_job': element[2], 'job_weight': element[3], 'percent_skill': element[4], 'time': element[5].split(' ')[-1].split(':')[:2]} for element in cursor.fetchall()]
                for message in messages:


                    sql_query = f"SELECT code FROM user WHERE id = (SELECT id_user from filters WHERE id = {message['id_filter']})"
                    cursor.execute(sql_query)
                    chat_id = cursor.fetchone()[0]


                    sql_query = f"SELECT name FROM filters WHERE id={message['id']}"
                    cursor.execute(sql_query)
                    filter_name = cursor.fetchone()[0]

                    # filter name
                    message_text = f"{filter_name}\n\n"

                    # job weight
                    if message['job_weight'] == 1:
                        message_text += '🟩\n\n'
                    elif message['job_weight'] == 2:
                        message_text += '🟧 🟧\n\n'
                    elif message['job_weight'] == 3:
                        message_text += '🟥 🟥 🟥\n\n'

                    # link
                    sql_query = f"SELECT link FROM job WHERE id={message['id_job']}"
                    cursor.execute()
                    job_link = cursor.fetchone()[0]
                    message_text += f"Link:\n\t{job_link}\n\n"

                    # description
                    sql_query = f"SELECT description FROM job WHERE id={message['id_job']}"
                    cursor.execute()
                    job_description = cursor.fetchone()[0]
                    message_text += f"{job_description}\n\n"

                    # price
                    job_price = {}
                    sql_query = f"SELECT meta_value FROM meta_job WHERE meta_key='price' AND id_job={message['id_job']}"
                    cursor.execute(sql_query)
                    price = cursor.fetchone()[0]
                    if 'True' in price:
                        job_price['price'] = {
                            'isFixed': True,
                            'cost': float(price[1:-1].split(', ')[-1].split(': ')[-1])
                        }
                    else:
                        job_price['price'] = {
                            'isFixed': False,
                            'cost': {
                                'min': float(price[1:-1].split(', ')[1].split(': ')[-1][:-1]),
                                'max': float(price[1:-1].split(', ')[2].split(': ')[-1][:-1])
                            }
                        }

                    if data['price']['isFixed']:
                        message_text += 'Price:\n\t${}\n\n'.format(data['price']['cost'])
                    else:
                        message_text += 'Price:\n\t${}-${}\n\n'.format(data['price']['cost']['min'], data['price']['cost']['max'])

                    if 80 <= message['percent_skill'] <= 100:
                        message_text += 'Skill rate:\n\t5\n\n'
                    elif 65 <= message['percent_skill'] < 80:
                        message_text += 'Skill rate:\n\t4\n\n'
                    elif 50 <= message['percent_skill'] < 65:
                        message_text += 'Skill rate:\n\t3\n\n'
                    if 40 <= message['percent_skill'] < 50:
                        message_text += 'Skill rate:\n\t2\n\n'
                    if 0 <= message['percent_skill'] < 40:
                        message_text += 'Skill rate:\n\t1\n\n'

                    sql_query = f"SELECT meta_value FROM meta_job WHERE id_job={message['id_job']}"
                    cursor.execure(sql_query)
                    for id in cursor.fetchone()[1:-1].split(', '):
                        sql_query = "SELECT slug FROM skill WHERE id="+id
                        cursor.execute(sql_query)
                        message += '\t#{}\n'.format(cursor.fetchone()[0])

                    sql_query = f"SELECT EXISTS(SELECT id FROM filter_elements WHERE id_filter={message['id_filter']} AND id_option=7)"
                    cursor.execute(sql_query)
                    if cursor.fetchone()[0] == 0:
                        sql_query = f"UPDATE messages SET status=1 WHERE id={message['id']}"
                        cursor.execute(sql_query)
                        send(chat_id=chat_id, text=message_text)
                        continue

                    sql_query = f"SELECT option_value FROM filter_elements WHERE id_filter={message['id_filter']} AND id_option=7"
                    cursor.execute(sql_query)
                    work_time = [[e for e in element.split(':')] for element in cursor.fetchone()[0].split('-')]
                    minutes = []
                    minutes.append(int(work_time[0][0])*60 + int(work_time[0][1]))
                    job_time = int(message['time'][0])*60 + int(message['time'][1]) + 180
                    if minutes[1] < minutes[0]:
                        if job_time < minutes[0]:
                            if not (minutes[0] <= job_time+1440 <= minutes[1]+1440):
                                continue
                    else:
                        if not (minutes[0] <= job_time <= minutes[1]):
                            continue
                    sql_query = f"UPDATE messages SET status=1 WHERE id={message['id']}"
                    cursor.execute(sql_query)
                    send(chat_id=chat_id, text=message_text)

            connection.commit()
        await asyncio.sleep(90)


def bot_config():
    print('bot_config started')
    token = Config.bot_config_token
    URL_config = 'https://api.telegram.org/bot{}/'.format(token)
    message_id = 0
    while True:
        # getUpdates
        URL = URL_config + 'getUpdates'
        try:
            r = requests.get(URL).json()
        except:
            continue

        if not r['ok']:
            continue

        try:
            message = r['result'][-1]['message']
        except:
            continue

        with open('message.json', 'w') as file:
            json.dump(r, file, indent=2)


        new_message_id = r['result'][-1]['update_id']
        if new_message_id == message_id:
            continue

        message_id = new_message_id
        chat_id = message['chat']['id']
        with db_connection() as connection:
            with connection.cursor() as cursor:
                sql_query = f"SELECT EXISTS(SELECT id FROM user WHERE code={chat_id})"
                cursor.execute(sql_query)
                if cursor.fetchone()[0] == 0:
                    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    sql_query = f"INSERT INTO user(code, name, time_last_update) VALUES({chat_id}, '{message['from']['username']}', '{time}')"
                    cursor.execute(sql_query)
            connection.commit()
        sleep(3)
