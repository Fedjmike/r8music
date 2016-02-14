import musicbrainzngs
import psycopg2
import sys
from config import database, user, password


conn = psycopg2.connect(user=user, database=database, password=password)
cur = conn.cursor()

def import_artist:
    pass

if __name__ == '__main__':
    import_artist(sys.argv[1])

