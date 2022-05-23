from config import Config
import pymysql

def db_connection():
    return pymysql.connect(host=Config.db_host, user=Config.db_user, database=Config.db_name, password=Config.db_password)
