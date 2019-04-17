#!/usr/bin/env python

from flask import (Flask, render_template, request, redirect,jsonify, url_for, 
  flash, session as login_session, make_response)

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import random, string, httplib2, json, requests

with open('cfg/clientid') as f:
  CLIENT_ID = f.read()
with open('cfg/clientsecret') as f:
  CLIENT_SECRET = f.read()

app = Flask(__name__)

#Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

# Create anti-forgery state token
@app.route('/login')
def showLogin():
  state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                  for x in range(32))
  login_session['state'] = state
  return render_template("login.html", client_id=CLIENT_ID, state=state)
  # return "The current session state is {}".format(login_session['state'])


@app.route('/gconnect', methods=['POST'])
def gconnect():
  # Validate state token
  if request.args.get('state') != login_session['state']:
      response = make_response(json.dumps('Invalid state parameter.'), 401)
      response.headers['Content-Type'] = 'application/json'
      return response
  # Obtain authorization code
  code = request.data

  try:
      # Upgrade the authorization code into a credentials object
      oauth_flow = flow_from_clientsecrets('cfg/client_secrets.json', scope='')
      oauth_flow.redirect_uri = 'postmessage'
      credentials = oauth_flow.step2_exchange(code)
  except FlowExchangeError:
      response = make_response(
          json.dumps('Failed to upgrade the authorization code.'), 401)
      response.headers['Content-Type'] = 'application/json'
      return response

  # Check that the access token is valid.
  access_token = credentials.access_token
  print('Got access token: {}'.format(access_token))
  url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
          % access_token)
  h = httplib2.Http()
  result = json.loads(h.request(url, 'GET')[1])
  # If there was an error in the access token info, abort.
  if result.get('error') is not None:
      response = make_response(json.dumps(result.get('error')), 500)
      response.headers['Content-Type'] = 'application/json'
      return response

  # Verify that the access token is used for the intended user.
  gplus_id = credentials.id_token['sub']
  if result['user_id'] != gplus_id:
      response = make_response(
          json.dumps("Token's user ID doesn't match given user ID."), 401)
      response.headers['Content-Type'] = 'application/json'
      return response

  # Verify that the access token is valid for this app.
  if result['issued_to'] != CLIENT_ID:
      response = make_response(
          json.dumps("Token's client ID does not match app's."), 401)
      print("Token's client ID does not match app's.")
      response.headers['Content-Type'] = 'application/json'
      return response

  stored_access_token = login_session.get('access_token')
  stored_gplus_id = login_session.get('gplus_id')
  if stored_access_token is not None and gplus_id == stored_gplus_id:
    print('Current token: {}'.format(stored_access_token))
    print('New token: {}'.format(credentials.access_token))
    revoke_token(login_session['access_token'])
    login_session['access_token'] = credentials.access_token
    response = make_response(json.dumps('Current user is already connected.'),
                              200)
    response.headers['Content-Type'] = 'application/json'
    return response

  # Store the access token in the session for later use.
  login_session['access_token'] = credentials.access_token
  login_session['gplus_id'] = gplus_id
  login_session['token_expiry'] = credentials.token_expiry

  # Get user info
  userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
  params = {'access_token': credentials.access_token, 'alt': 'json'}
  answer = requests.get(userinfo_url, params=params)

  data = answer.json()

  login_session['username'] = data['name']
  login_session['picture'] = data['picture']
  login_session['email'] = data['email']

  output = ''
  output += '<h1>Welcome, '
  output += login_session['username']
  output += '!</h1>'
  output += '<img src="'
  output += login_session['picture']
  output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
  flash("you are now logged in as %s" % login_session['username'])
  print("done!")
  return output

def revoke_token(access_token):
  response = requests.post('https://accounts.google.com/o/oauth2/revoke',
    params={'token': access_token},
    headers = {'content-type': 'application/x-www-form-urlencoded'})
  if response.status_code == 200:
    print('Token successfully revoked')
  else:
    print('Token revocation failed with status {}'.format(response.status_code))


@app.route('/gdisconnect')
def gdisconnect():
  access_token = login_session.get('access_token')
  if access_token is None:
    print('Access Token is None')
    response = make_response(json.dumps('Current user not connected.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  print('In gdisconnect access token is {}'.format(access_token))
  print('User name is {}'.format(login_session['username']))
  url = 'https://accounts.google.com/o/oauth2/revoke?token={}'.format(login_session['access_token'])
  print(url)
  h = httplib2.Http()
  result = h.request(url, 'POST', headers={'content-type': 'application/x-www-form-urlencoded'})[0]
  print('result is ')
  print(result)

  if result['status'] == '200':
    del login_session['access_token']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']
    response = make_response(json.dumps('Successfully disconnected.'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response
  else:
    response = make_response(json.dumps('Failed to revoke token for given user.'), 400)
    response.headers['Content-Type'] = 'application/json'
    return response


#JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
  try:
    session = DBSession()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])

  finally:
    if session:
      session.close()


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
  try:
    session = DBSession()
    Menu_Item = session.query(MenuItem).filter_by(id = menu_id).one()
    return jsonify(Menu_Item = Menu_Item.serialize)

  finally:
    if session:
      session.close()

@app.route('/restaurant/JSON')
def restaurantsJSON():
  try:
    session = DBSession()
    restaurants = session.query(Restaurant).all()
    return jsonify(restaurants= [r.serialize for r in restaurants])
  finally:
    if session:
      session.close()


#Show all restaurants
@app.route('/')
@app.route('/restaurant/')
def showRestaurants():
  try:
    session = DBSession()
    restaurants = session.query(Restaurant).order_by(asc(Restaurant.name))
    return render_template('restaurants.html', restaurants = restaurants)
  finally:
    if session:
        session.close()

#Create a new restaurant
@app.route('/restaurant/new/', methods=['GET','POST'])
def newRestaurant():
  try:
    session = DBSession()
    if request.method == 'POST':
        newRestaurant = Restaurant(name = request.form['name'])
        session.add(newRestaurant)
        flash('New Restaurant %s Successfully Created' % newRestaurant.name)
        session.commit()
        return redirect(url_for('showRestaurants'))
    else:
        return render_template('newRestaurant.html')
  finally:
      if session:
        session.close()

#Edit a restaurant
@app.route('/restaurant/<int:restaurant_id>/edit/', methods = ['GET', 'POST'])
def editRestaurant(restaurant_id):
  try:
    session = DBSession()
    editedRestaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        if request.form['name']:
          editedRestaurant.name = request.form['name']
          flash('Restaurant Successfully Edited %s' % editedRestaurant.name)
          return redirect(url_for('showRestaurants'))
    else:
      return render_template('editRestaurant.html', restaurant = editedRestaurant)
  finally:
    if session:
      session.close()

#Delete a restaurant
@app.route('/restaurant/<int:restaurant_id>/delete/', methods = ['GET','POST'])
def deleteRestaurant(restaurant_id):
  try:
    session = DBSession()
    restaurantToDelete = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
      session.delete(restaurantToDelete)
      flash('%s Successfully Deleted' % restaurantToDelete.name)
      session.commit()
      return redirect(url_for('showRestaurants', restaurant_id = restaurant_id))
    else:
      return render_template('deleteRestaurant.html',restaurant = restaurantToDelete)

  finally:
    if session:
      session.close()

#Show a restaurant menu
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
def showMenu(restaurant_id):
  try:
    session = DBSession()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    return render_template('menu.html', items = items, restaurant = restaurant)
  finally:
    if session:
      session.close()


#Create a new menu item
@app.route('/restaurant/<int:restaurant_id>/menu/new/',methods=['GET','POST'])
def newMenuItem(restaurant_id):
  try:
    session = DBSession()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        newItem = MenuItem(name = request.form['name'], description = request.form['description'], price = request.form['price'], course = request.form['course'], restaurant_id = restaurant_id)
        session.add(newItem)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newItem.name))
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('newmenuitem.html', restaurant_id = restaurant_id)
  finally:
    if session:
      session.close()


#Edit a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET','POST'])
def editMenuItem(restaurant_id, menu_id):
  try:
    session = DBSession()
    editedItem = session.query(MenuItem).filter_by(id = menu_id).one()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit() 
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('editmenuitem.html', restaurant_id = restaurant_id, menu_id = menu_id, item = editedItem)
  finally:
    if session:
      session.close()


#Delete a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods = ['GET','POST'])
def deleteMenuItem(restaurant_id,menu_id):
  try:
    session = DBSession()
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    itemToDelete = session.query(MenuItem).filter_by(id = menu_id).one() 
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('deleteMenuItem.html', item = itemToDelete)

  finally:
    if session:
      session.close()


if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)
