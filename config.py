import os

class Config():
    db_password = os.environ['upwork_database_password']
    bot_sender_token = os.environ['upwork_bot1_token']
    bot_config_token = os.environ['upwork_bot2_token']
    db_user = 'root'
    db_host = 'localhost'
    db_name = 'Upwork'
