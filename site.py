from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
@app.route("/<name>")
def render_release(name=None):
    return render_template("release.html", name=name)

if __name__ == "__main__":
    app.run(debug=True)