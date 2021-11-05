"""
Additional Ideas:
 - Allow users to buy more shares or sell shares of stocks they already own via index itself, without having to type stocks’ symbols manually.
 - Require users’ passwords to have some number of letters, numbers, and/or symbols."""


import os

import time
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not request.form.get("current_password") or not request.form.get("password") or not request.form.get("password_confirmation"):
            return apology("Password fields can't be blank")

        # Check if the entered password matches the current password
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(rows[0]["hash"], request.form.get("current_password")):
            return apology("Password is wrong")

        if request.form.get("password") != request.form.get("password_confirmation"):
            return apology("Passwords do not match")

        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(
            request.form.get("password")), session["user_id"])
        return redirect("/")

    else:
        return render_template("change_password.html")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    all_stocks = db.execute("SELECT stock_name, stock_quantity FROM purchases WHERE user_id = ?", session["user_id"])

    sum = 0

    stock_list = []
    for stock in all_stocks:
        list_stock = {}

        symbol = stock["stock_name"]
        shares = stock["stock_quantity"]

        stock_detail = lookup(symbol)

        name = stock_detail["name"]
        price = stock_detail["price"]
        total = shares * price

        sum += total

        list_stock["symbol"] = symbol
        list_stock["name"] = name
        list_stock["shares"] = shares
        list_stock["price"] = price
        list_stock["total"] = usd(total)

        stock_list.append(list_stock)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    sum += cash[0]["cash"]

    return render_template("index.html", cash=usd(cash[0]["cash"]), stocks=stock_list, sum=usd(sum))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Symbol is the input of the user which represents a symbol of a certain stock
        symbol = request.form.get("symbol")
        stock = lookup(symbol)

        # Symbol should not be blank and it should be valid
        if not symbol:
            return apology("Symbol Cannot Be Blank")
        if not stock:
            return apology("Symbol Does Not Exist")

        # Shares input must be a positive integer, as shares are 'whole' and there is no such
        # thing as negative share
        shares = request.form.get("shares")
        if not shares.isdigit:
            return apology("Missing Shares")

        shares = int(shares)
        if shares < 1:
            return apology("Share Must Be A Positive Number")

        price = stock["price"]

        # Get the current cash of the current user
        result = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        current_cash = result[0]["cash"]

        total = price * shares
        # Check if the user have enough money to buy given amount of shares
        if current_cash < total:
            return apology("Can't Afford")

        # Get the time of transaction
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

        # Add the purchase to the database update the money user has
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash - total, session["user_id"])
        db.execute("INSERT INTO purchases (user_id, stock_name, stock_quantity, stock_price, date) VALUES(?, ?, ?, ?, ?)",
                    session["user_id"], symbol, shares, total, formatted_date )
        db.execute("INSERT INTO history (user_id, symbo0, shares, stock_price, date) VALUES(?, ?, ?, ?, ?)",
                    session["user_id"], symbol, shares, price, formatted_date)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        if not stock:
            return apology("Invalid Symbol")

        return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=stock["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        name = request.form.get("username")
        # Username is blank
        if not name:
            return apology("Username can't be blank")

        # Username already exists
        result = db.execute("SELECT username FROM users WHERE username = ?", name)
        if len(result) > 0:
            return apology("Username already exists")

        password = request.form.get("password")
        confirmation_password = request.form.get("confirmation")

        # Password is blank
        if not password or not confirmation_password:
            return apology("Password cannot be blank")

        # Passwords do not match
        if password != confirmation_password:
            return apology("Passwords must match")

        # Everything related to register is fine, insert the user into database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, generate_password_hash(password))

        # Automatically log in the user
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    SYMBOLS = db.execute("SELECT stock_name FROM purchases WHERE user_id = ?", session["user_id"])
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)

        # Error checking
        if not symbol:
            return apology("Missing Symbol")
        # TODO: Check if the symbol is indeed in users account

        shares_to_sell = request.form.get("shares")
        if not shares_to_sell.isdigit():
            return apology("Shares Must Be A Positive Number")

        shares_to_sell = int(shares_to_sell)
        if not shares_to_sell > 0:
            return apology("Shares Must Be A Positive Number")

        current_shares = db.execute("SELECT stock_quantity FROM purchases WHERE user_id = ? AND stock_name = ?",
                                    session["user_id"], stock["symbol"])[0]["stock_quantity"]

        if current_shares < shares_to_sell:
            return apology("Exceeded Current Shares")

        # Compute the total money gained
        gain = shares_to_sell * stock["price"]

        # Decrease the number of shares from the users account
        if shares_to_sell == current_shares:
            db.execute("DELETE FROM purchases WHERE stock_name = ? AND user_id = ?", symbol, session["user_id"])
        else:
            shares_left = current_shares - shares_to_sell
            db.execute("UPDATE purchases SET stock_quantity = ? WHERE user_id = ?", shares_left, session["user_id"])

        # Get current cash and compute the final cash
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        cash_after_transaction = gain + current_cash

        # Get the time of transaction
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

        # Add the money to the users account
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_after_transaction, session["user_id"])
        db.execute("INSERT INTO history (user_id, symbo0, shares, stock_price, date) VALUES(?, ?, ?, ?, ?)",
                    session["user_id"], symbol, -1 * shares_to_sell, stock["price"], formatted_date)

        return redirect("/")
    else:
        return render_template("sell.html", symbols=SYMBOLS)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
