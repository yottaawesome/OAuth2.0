# OAuth2.0

## Introduction

Starter code for Auth &amp; Auth course, forked from [udacity/OAuth2.0](https://github.com/udacity/OAuth2.0). This fork cleans up the directories, adds a proper .gitignore, and proper support for environment isolation via `virtualenv` to bypass the need Vagrant if you already have a Linux environment set up. The Vagrant file has been removed.

## Running the Restaurant Menu App

* Create a Python 3 virtualenv.
* Activate the environment.
* Install the Python dependencies in `requirements.txt`.
* Run **python database_setup.py** to initialize the database.
* Run **python lotsofmenus.py** to populate the database with restaurants and menu items. (Optional)
* Run **python project.py** to run the Flask web server. In your browser visit [localhost:5000](http://localhost:5000) to view the restaurant menu app. You should be able to view, add, edit, and delete menu items and restaurants.
