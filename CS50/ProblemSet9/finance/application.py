import os

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # list of all stocks that user currently possess
    current_stocks = []

    # get and store user cash to calculate overall total
    oa_total = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]['cash']

    # format user cash
    user_cash = usd(oa_total)

    # list of dictionaries is ordered by name
    user_stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM stocks WHERE user_id = ? GROUP BY symbol ORDER BY symbol", session['user_id'])

    # filter stocks whith quantity <= 0
    user_stocks = list(filter((lambda s: s['shares'] > 0), user_stocks))

    # get updated information of user's stocks and calculate total price for each of them
    if user_stocks:
        for stock in user_stocks:
            # update current stock's information
            upd_stock = lookup(stock['symbol'])

            # calculate total for current stock
            stock_total = stock['shares'] * upd_stock['price']

            # summarize total
            oa_total += stock_total

            # parse updated information
            parsed_dict = dict(
                    symbol = upd_stock['symbol'],
                    name   = upd_stock['name'],
                    shares = stock['shares'],
                    price  = usd(upd_stock['price']),
                    total  = usd(stock_total)
                )

            # add updated stock to list of current stocks
            current_stocks.append(parsed_dict)

    # format overall total
    oa_total = usd(oa_total)

    return render_template("index.html", stocks = current_stocks, cash = user_cash, total = oa_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # user reached route via 'post' (as by submitting a form)
    if request.method == "POST":

        ### idk if i am allowed to store such information in variables:

        # get user id
        user_id = session['user_id']

        # get user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]['cash']

        # from submitted form get symbol and shares
        form_symbol = request.form.get("symbol")
        form_shares = request.form.get("shares")

        # get information about symbol
        symbol_request = lookup(form_symbol)

        # ensure symbol form not empty
        if not form_symbol:
            return apology("missing symbol", 400)

        # ensure shares form not empty
        if not form_shares:
            return apology("missing shares", 400)
        else:
            # type check
            try:
                form_shares = int(form_shares)
            except:
                return apology("invalid shares", 403)

        # ensure symbol name exists in the market
        if not symbol_request:
            return apology("invalid symbol")
        else: # get current price of the symbol
            symbol_price = symbol_request['price']

        # ensure shares amount is greater or equal 1
        if form_shares < 1:
            return apology("invalid amount", 403)

        # ensure user posses required amount of cash before transaction
        stocks_price = symbol_price * form_shares
        if stocks_price >= user_cash:
            return apology("not enough money", 400)

        # store transaction in db
        db.execute("INSERT INTO stocks (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", user_id, form_symbol, form_shares, symbol_price)

        # update money in users's cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash - stocks_price, user_id)

        # on success redirect to index
        return redirect("/")

    # user reached route via 'get' (as by click or redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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

    # route via 'post' after clicking the button
    if request.method == "POST":

        # ensure field not empty
        if not request.form.get("symbol"):
            return apology("missing symbol")
        else:
            # request and parse infromation from iex
            result = lookup(request.form.get("symbol"))

            # if result has failed, return apology
            if not result:
                return apology("invalid symbol")
            # on success render webpage with information
            else:
                return render_template("quoted.html", name=result['name'], price=result['price'], symbol=result['symbol'])

    # route via 'get' method by clicking on link or redirect
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # route via 'post' user clicked on the registration button
    if request.method == "POST":

        # render apology if username input field is blank
        if not request.form.get("username"):
            return apology("username field can't be blank", 403)

        # render apology if either password or confirmation field is blank
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("password field can't be blank", 403)

        # query database for username
        username_db_query = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))

        # registrate user
        if len(username_db_query) == 0:
            # insert new user into db, storing username and hash of the user's password
            if request.form.get("password") == request.form.get("confirmation"):
                db.execute("INSERT INTO users (username, hash) VALUES (?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
            # render apology if password confirmation dosen't match
            else:
                return apology("passwords don't match", 400)
        # render apology if username is aready exists
        else:
            return apology("username is already exists", 400)

        # redirect users so they can login themselves
        return redirect("/")

    # route via 'get', by clicking on link or redirect
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # get user id
    user_id = session['user_id']
    # get user's stocks
    user_stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM stocks WHERE user_id = ? GROUP BY symbol ORDER BY symbol", user_id)
    # filter stocks whith quantity <= 0
    user_stocks = list(filter((lambda s: s['shares'] > 0), user_stocks))

    # route via 'post' user clicked on the sell button
    if request.method == "POST":

        form_symbol = request.form.get("symbol")
        form_shares = request.form.get("shares")

        # select requested stocks to sell
        user_sub_stocks = list(filter(lambda s: form_symbol in s.values(), user_stocks))

        # ensure user own shares of selected symbol
        if not user_sub_stocks:
            return apology("invalid symbol")

        # validate input field for shares
        # ensure shares field is not empty
        if not form_shares:
            return apology("missing shares")
        else:
            # ensure shares type is correct
            try:
                form_shares = int(form_shares)
            except:
                return apology("invalid shares", 403)

            # ensure shares amount is greater or equal 1
            if form_shares < 1:
                return apology("invalid shares", 403)

            # ensure user have enough shares to sell
            if form_shares > user_sub_stocks[0]['shares']:
                return apology("too many shares")

        # get selling price for shares
        symbol_price = lookup(form_symbol)['price']

        # calculate cash
        earnings = symbol_price * form_shares

        # update user's stocks
        db.execute("INSERT INTO stocks (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", user_id, form_symbol, - form_shares, symbol_price)

        # get user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]['cash']

        # update user's cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + earnings, user_id)

        # When a sale is complete, redirect the user back to the index page
        return redirect("/")

    else:
        #user_symbols = db.execute("SELECT DISTINCT symbol FROM stocks WHERE user_id = ? ORDER BY symbol", session['user_id'])
        return render_template("sell.html", stocks = user_stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
