from flask import Flask, render_template

import sqlite3
from contextlib import closing
from flask import g

app = Flask(__name__)

# Database

def connect_db():
    rv = sqlite3.connect("sample.db")
    rv.row_factory = sqlite3.Row
    return rv
    
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        
        db.execute(
            "insert into artists (name, url) values (?, ?)",
            ("My Bloody Valentine", "my-bloody-valentine")
        )
        
        db.commit()

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.db = connect_db()
        
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

# 

@app.route("/")
@app.route("/<name>")
def render_release(name=None):
    print(query_db("select * from artists"))
    return render_template("release.html", name=name)

if __name__ == "__main__":
    app.run(debug=True)