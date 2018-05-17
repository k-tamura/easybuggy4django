.. image:: https://travis-ci.com/k-tamura/easybuggy4django.svg?branch=master
   :target: https://travis-ci.com/k-tamura/easybuggy4django
   
EasyBuggy Django
================

EasyBuggy clone built on Django 2.0.
`EasyBuggy <https://github.com/k-tamura/easybuggy>`__ is a broken web
application in order to understand behavior of bugs and vulnerabilities,
for example, `memory leak, deadlock, infinite loop, SQL injection and so
on <https://github.com/k-tamura/easybuggy/wiki>`__.

Quick Start
--------------------

::

    $ git clone https://github.com/k-tamura/easybuggy4django.git
    $ cd easybuggy4django/
    $ pip install -r requirements.txt
    $ python manage.py runserver

However it is recommended to use venv (before running the above commands):

::

    $ python -m venv venv
    $ source venv/bin/activate

Access to

::

    http://localhost:8000

To stop:
^^^^^^^^

Use :kbd:`CTRL` + :kbd:`C`

