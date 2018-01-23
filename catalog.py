# declare all imports
from flask import Flask, render_template, url_for, redirect, request, flash, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Category, Item

# imports for OAuth
from flask import session as login_session
import random
import string


from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

CLIENT_ID = json.loads(open('client_secret.json', 'r').read())['web']['client_id']

app = Flask(__name__)

engine = create_engine('postgresql://catalog:XXXXXX@55.555.555.555/inventory')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Fake category
category = {'name': 'Soccer', 'id': '1'}

categories = [{'name': 'Soccer', 'id': '1'}, {'name': 'Basketball', 'id': '2'}, {'name': 'Baseball', 'id': '3'}]


# Fake items
items = [{'name': 'Soccer cleats', 'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTFSpWARyxo8lHjzhAfnCtjNm25xN-iWm-qx2sar-SYbLdT2I9iZQ', 'description': 'Premium, super-strong cleats with integrated laces that provide stability.', 'price': '$65.99', 'id': '1'}, {'name': 'Jersey', 'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQhUOIHhr4DT4yvG-EgvHPQaU1I9IKnaPN9XfRUyIMs-UL-jbJ5', 'description': 'This quality jersery is constructed of light-weight durable mesh fabric that wicks moisture and provdes cooling through our patented technology', 'price': '$39.99', 'id': '2'}, {'name': 'Shinguards', 'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTwjtoSmx7cqfG2tzjQvhr3u6caJ8O03vnpoqZmSimaBEi0SnBy_A', 'description': 'Durable reinforced plastic shinguards with flexible construction for maximum protection', 'price': '$99.99', 'id': '3'}]
item = {'name': 'Soccer cleats', 'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTFSpWARyxo8lHjzhAfnCtjNm25xN-iWm-qx2sar-SYbLdT2I9iZQ', 'description': 'Premium, super-strong cleats with integrated laces that provide stability.', 'price': '$65.99'}


# Route user to login
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# server-side function to handle OAuth
# Handle user login through Google account
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # confirm that token that client sent to server matches token sent from server to client, ensures user is sending request
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # if statement not true then I can collect one-time code from server
    code = request.data
    # try to use code to exchange for a credentials object which will contain the access token for my server
    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secret.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        # initiate the exchange using code
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the there is a valid access token in it
    access_token = credentials.access_token
    # confirm access_token is valid against database
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access info, abort!
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's user ID doesn't match given User ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(json.dumps("Token's client ID does not match app's"), 401)
        print "Token's client ID does not match app's."
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # If the token passes the if statements above, we have a valid token and can store the access token in the session for later use.
    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id
    login_session['provider'] = 'google'

    # Get user info from google api
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    email = login_session['email']
    user_id = getUserID(email)

    if user_id is None:
        user_id = createUser(login_session)

    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# DISCONNECT - Revoke a current user's token and reset their login_session.
# tells server to reject its access token
@app.route('/gdisconnect')
def gdisconnect():
    # stored_gplus_id = login_session.get('gplus_id')
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # del login_session['credentials']
        # # del login_session['stored_gplus_id']
        # del login_session['username']
        # del login_session['email']
        # del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:

        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# Facebook Login
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.8/me"
    '''
        Due to the formatting for the result from the server token exchange we have to
        split the token first on commas and select the first index which gives us the key : value
        for the server access token then we split it on colons to pull out the actual token value
        and replace the remaining quotes with nothing so that it can be used directly in the graph
        api calls
    '''
    token = result.split(',')[0].split(':')[1].replace('"', '')

    url = 'https://graph.facebook.com/v2.8/me?access_token=%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = token

    # Get user picture
    url = 'https://graph.facebook.com/v2.8/me/picture?access_token=%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output


# facebook log out
@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


@app.route('/logout')
def disconnect():
    access_token = login_session.get('access_token')
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            # del stored_g_id
            # del credentials
            del login_session['gplus_id']
            del access_token
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']

        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out")
        return redirect(url_for('showCategories'))
    else:
        flash("You were not logged into begin with!")
        return redirect(url_for('showCategories'))


# API Endpoints
@app.route('/home/JSON')
def showCategoriesJSON():
    categories = session.query(Category).all()
    return jsonify(Category=[i.serialize for i in categories])


@app.route('/category/<int:category_id>/item/JSON')
def showItemsJSON(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    item = session.query(Item).filter_by(category_id=category_id).all()
    return jsonify(Item=[i.serialize for i in item])


@app.route('/category/<int:category_id>/item/<int:item_id>/JSON')
def showItemJSON(category_id, item_id):
    item = session.query(Item).filter_by(id=item_id).one()
    return jsonify(item=item.serialize)


# main page showcases categories
@app.route('/')
@app.route('/home')
def showCategories():
    categories = session.query(Category).order_by(Category.name)
    if 'username' not in login_session:
        return render_template('publiccategories.html', categories=categories)
    else:
        return render_template('categories.html', categories=categories)


# create new category
@app.route('/category/new', methods=['GET', 'POST'])
def newCategory():
    # test if user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    else:
        if request.method == 'POST':
            newC = Category(name=request.form['name'], user_id=login_session['user_id'])
            session.add(newC)
            session.commit()
            flash('New Category Created!')
            return redirect(url_for('showCategories'))
        else:
            return render_template('newcategory.html')


# edit category
@app.route('/category/<int:category_id>/edit', methods=['GET', 'POST'])
def editCategory(category_id):
    # test if user is logged in
    if 'username' not in login_session:
        return redirect('/login')
    editC = session.query(Category).filter_by(id=category_id).one()
    # check that person editting is the owner
    email = login_session['email']
    user_id = getUserID(email)
    if user_id == editC.user_id:
        if request.method == 'POST':
            if request.form['name']:
                editC.name = request.form['name']
            session.add(editC)
            session.commit()
            flash('Category Successfully Edited')
            return redirect(url_for('showCategories'))
        else:
            # if user has not made any changes
            return render_template('editcategory.html', c=editC)
    else:
        flash('You must be the owner of the item to make changes')
        return redirect(url_for('showCategories', category_id=category_id))


# delete category
@app.route('/category/<int:category_id>/delete', methods=['GET', 'POST'])
def deleteCategory(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    deleteC = session.query(Category).filter_by(id=category_id).one()
    email = login_session['email']
    user_id = getUserID(email)
    if user_id == deleteC.user_id:
        if request.method == 'POST':
            session.delete(deleteC)
            session.commit()
            return redirect(url_for('showCategories'))
        else:
            return render_template('deletecategory.html', category_id=category_id, c=deleteC)
    else:
        # if not owner of item, redirect to main page
        flash('You must be the owner of the item to make changes')
        return redirect(url_for('showCategories', category_id=category_id))


# show all items in category
@app.route('/category/<int:category_id>/', methods=['GET', 'POST'])
@app.route('/category/<int:category_id>/items/', methods=['GET', 'POST'])
def showItems(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    items = session.query(Item).filter_by(category_id=category_id).all()
    creator = getUserInfo(category.user_id)
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicitems.html', category=category, category_id=category_id, items=items, creator=creator)
    else:
        return render_template('items.html', category=category, category_id=category_id, items=items, creator=creator)


# add new item to a category
@app.route('/category/<int:category_id>/item/new', methods=['GET', 'POST'])
def newItem(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(id=category_id).one()
    email = login_session['email']
    user_id = getUserID(email)
    if user_id == category.user_id:
        if request.method == 'POST':
            newItem = Item(name=request.form['name'], image=request.form['image'], description=request.form['description'], price=request.form['price'], user_id=category.user_id, category=category)
            session.add(newItem)
            session.commit()
            flash('You have successfully added an item')
            return redirect(url_for('showItems', category_id=category_id))
        else:
            return render_template('newitem.html', category_id=category_id)
    else:
        flash('You must be the owner of the category to add items!')
        return redirect(url_for('showItems', category_id=category_id))


# edit an item
@app.route('/category/<int:category_id>/item/<int:item_id>/edit', methods=['GET', 'POST'])
def editItem(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    editItem = session.query(Item).filter_by(id=item_id).one()
    email = login_session['email']
    user_id = getUserID(email)
    if user_id == editItem.user_id:
        if request.method == 'POST':
            if request.form['name']:
                editItem.name = request.form['name']
            if request.form['image']:
                editItem.course = request.form['image']
            if request.form['description']:
                editItem.description = request.form['description']
            if request.form['price']:
                editItem.price = request.form['price']
            session.add(editItem)
            session.commit()
            flash('You have successfully edited an item')
            return redirect(url_for('showItems', category_id=category_id))
        else:
            return render_template('edititem.html', category_id=category_id, item_id=item_id, item=editItem)
    else:
        flash('You must be the owner of the item to make changes.')
        return redirect(url_for('showItems', category_id=category_id))


# delete an item
@app.route('/category/<int:category_id>/item/<int:item_id>/delete', methods=['GET', 'POST'])
def deleteItem(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    deleteItem = session.query(Item).filter_by(id=item_id).one()
    email = login_session['email']
    user_id = getUserID(email)
    if user_id == deleteItem.user_id:
        if request.method == 'POST':
            session.delete(deleteItem)
            session.commit()
            flash('You have successfully deleted an item')
            return redirect(url_for('showItems', category_id=category_id))
        else:
            return render_template('deleteitem.html', category_id=category_id, item_id=item_id, item=editItem)
    else:
        flash('You must be the owner of the item to make changes.')
        return redirect(url_for('showItems', category_id=category_id))


# Get the id # from the user's email address
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# returns user object using user id passed into function
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


# create a new user taking login session as argument
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


if __name__ == '__main__':
    app.secret_key = 'super secret key'
    # app.config['SESSION_TYPE'] = 'filesystem'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
