 .. image:: https://travis-ci.com/k-tamura/easybuggy4django.svg?branch=master&style=flat
    :target: https://travis-ci.com/k-tamura/easybuggy4django
    :alt: Build status
 
 .. image:: https://img.shields.io/badge/License-MIT-yellow.svg?style=flat
    :target: https://opensource.org/licenses/MIT
    :alt: License

 .. image:: https://img.shields.io/github/release/k-tamura/easybuggy4django.svg?style=flat
    :target: https://github.com/k-tamura/easybuggy4django/releases/latest
    :alt: Latest Version

EasyBuggy Django
================

EasyBuggy clone built on Django 2.0.
`EasyBuggy <https://github.com/k-tamura/easybuggy>`__ is a broken web
application in order to understand behavior of bugs and vulnerabilities,
for example, memory leak, deadlock, infinite loop, SQL injection and so
on.

.. image:: /static/easybuggy.png

Quick Start
--------------------

::

    $ git clone https://github.com/k-tamura/easybuggy4django.git
    $ cd easybuggy4django/
    $ pip install -r requirements.txt
    $ python manage.py runserver

However it is recommended to use venv (before running the above commands):

::

    $ python3 -m venv venv
    $ source venv/bin/activate

Access to

::

    http://localhost:8000

To stop:
^^^^^^^^

Use :kbd:`CTRL` + :kbd:`C`

